"""Researcher tools: fetch real material, and save only verbatim passages.

`save_source` is the code-level guarantee behind SPEC §8.6 ("real posts must be verbatim"):
a passage is accepted only if it appears word for word (after quote/dash/whitespace
normalization) in a document fetched during this run.
"""

from __future__ import annotations

import calendar
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, tool

from pipeline.config import EIA_TITLE, EIA_UNIT, EIA_URL
from pipeline.context import FetchedDoc, RunContext, SavedSource, canonical_url
from pipeline.outlets import outlet_for
from pipeline.safety import (
    RealEntity,
    blocklist_hits,
    known_entities,
    outlet_speaker_problem,
    person_name_part,
    story_level_hits,
)
from pipeline.textutil import (
    clip,
    find_verbatim,
    html_to_text,
    month_label,
    normalize,
    sentence_spans,
    strip_edges,
    word_count,
)

AGENT = "researcher"
MAX_FEED_PAGES = 4
MAX_ITEM_CHARS = 3500
MAX_ARTICLE_CHARS = 6000
MIN_PASSAGE_WORDS = 5
MAX_PASSAGE_WORDS = 120  # short excerpts only (NJ Monitor is CC BY-NC-ND)

_STOPWORDS = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "nj", "new", "jersey", "about"}


# --------------------------------------------------------------------------------------
# EIA data (local file, fetched once by scripts/)
# --------------------------------------------------------------------------------------


def load_eia(path: Path) -> dict[str, float]:
    rows = json.loads(path.read_text(encoding="utf-8"))["response"]["data"]
    return dict(sorted((r["period"], float(r["price"])) for r in rows))


def eia_window(prices: dict[str, float], start: str, end: str | None = None) -> list[tuple[str, float]]:
    end = end or max(prices)
    return [(p, v) for p, v in prices.items() if start <= p <= end]


def shift_month(period: str, months: int) -> str:
    y, m = map(int, period.split("-"))
    idx = y * 12 + (m - 1) + months
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def pct_change(a: float, b: float) -> float:
    return (b / a - 1.0) * 100.0


def get_eia_series_impl(ctx: RunContext, start: str = "2023-01", end: str | None = None) -> str:
    if not ctx.has_data:
        return "Refused: this topic has no data series (its hints list no data). Save passages with numbers instead."
    prices = load_eia(ctx.eia_path)
    if not re.fullmatch(r"\d{4}-\d{2}", start) or (end and not re.fullmatch(r"\d{4}-\d{2}", end)):
        return "Error: use YYYY-MM for start and end."
    rows = eia_window(prices, start, end)
    if not rows:
        return f"Error: no EIA data between {start} and {end or max(prices)} (data runs {min(prices)} to {max(prices)})."
    ctx.add_doc(FetchedDoc(url=EIA_URL, title=EIA_TITLE, outlet="U.S. Energy Information Administration",
                           published=None, paragraphs=[f"{p}: {v}" for p, v in prices.items()], via="data"))
    latest = max(prices)
    yoy_from = shift_month(latest, -12)
    lines = [f"{EIA_TITLE}, {EIA_UNIT}, monthly. Data runs {min(prices)} to {latest}. Source: {EIA_URL}"]
    if yoy_from in prices:
        lines.append(f"Latest same-month change: {month_label(yoy_from)} {prices[yoy_from]} -> {month_label(latest)} "
                     f"{prices[latest]} ({pct_change(prices[yoy_from], prices[latest]):+.1f}%).")
    lo = min(rows, key=lambda r: r[1])
    hi = max(rows, key=lambda r: r[1])
    lines.append(f"In this window: low {lo[1]} ({lo[0]}), high {hi[1]} ({hi[0]}).")
    lines.append(" ".join(f"{p}={v}" for p, v in rows))
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# Feeds and articles
# --------------------------------------------------------------------------------------


def local_date(published: str | None, url: str) -> str | None:
    """Publication date as New Jersey readers saw it (URL date wins over a UTC timestamp)."""
    if d := date_from_url(url):
        return d
    if not published:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", published):
        try:
            from zoneinfo import ZoneInfo

            dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            return dt.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            return published[:10]
    return published[:10]


def _decode(body: bytes, content_type: str) -> str:
    m = re.search(r"charset=([\w-]+)", content_type or "", re.IGNORECASE)
    if m:
        try:
            return body.decode(m.group(1), errors="replace")
        except LookupError:
            pass
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("cp1252", errors="replace")


def _iso_from_struct(st: Any) -> str | None:
    """feedparser's *_parsed fields are UTC struct_time values."""
    if not st:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(st), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, ValueError, TypeError):
        return None


def date_from_url(url: str) -> str | None:
    m = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url) or re.search(r"/(20\d{2})(\d{2})(\d{2})[^/]*$", url)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _date_from_page(meta: dict[str, str], paragraphs: list[str], url: str) -> str | None:
    for key in ("article:published_time", "og:published_time", "datepublished", "date", "dc.date", "pubdate", "time"):
        v = meta.get(key)
        if v and re.match(r"\d{4}-\d{2}-\d{2}", v):
            return v[:10]
    for p in paragraphs[:15]:
        m = re.search(r"\bDate:\s*(\d{1,2})/(\d{1,2})/(\d{4})", p)
        if m:
            return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return date_from_url(url)


def _terms(query: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) >= 3 and t not in _STOPWORDS]


def _score(doc: FetchedDoc, terms: list[str]) -> int:
    if not terms:
        return 1
    title, body = doc.title.lower(), doc.text.lower()
    return sum(3 * title.count(t) + min(body.count(t), 10) for t in terms)


def _show_doc(doc: FetchedDoc, limit: int) -> str:
    text = doc.text
    if len(text) > limit:
        text = text[:limit].rsplit("\n", 1)[0] + "\n[…truncated]"
    return f"{doc.title}\nURL: {doc.url}\nOutlet: {doc.outlet} · Date: {doc.published or 'unknown'}\n{text}"


def _feed_page_url(feed_url: str, page: int) -> str:
    if page <= 1:
        return feed_url
    return f"{feed_url}{'&' if '?' in feed_url else '?'}paged={page}"


def _feed_key(url: str) -> str:
    return canonical_url(re.sub(r"[?&]paged=\d+$", "", (url or "").strip()))


def _allowed_list(ctx: RunContext) -> str:
    feeds = ", ".join(ctx.feeds or []) or "none"
    pages = ", ".join(ctx.articles or [])
    return f"feeds: {feeds}" + (f"; pages: {pages}" if pages else "")


def fetch_rss_impl(ctx: RunContext, feed_url: str, query: str = "", pages: int = 1, max_items: int = 4) -> str:
    import feedparser

    if _feed_key(feed_url) not in {_feed_key(f) for f in ctx.feeds or []}:
        return (f"Refused: {feed_url} is not one of this topic's feeds. Research stays on the topic's own sources "
                f"({_allowed_list(ctx)}). Don't guess other feeds.")
    pages = max(1, min(int(pages), MAX_FEED_PAGES))
    max_items = max(1, min(int(max_items), 6))
    fetched: list[FetchedDoc] = []
    errors: list[str] = []
    for page in range(1, pages + 1):
        url = _feed_page_url(feed_url, page)
        try:
            status, body, ctype = ctx.fetch(url)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {type(exc).__name__}")
            break
        if status != 200:
            errors.append(f"{url}: HTTP {status}")
            break
        parsed = feedparser.parse(body)
        if not parsed.entries:
            break
        for e in parsed.entries:
            link = e.get("link") or ""
            if not link:
                continue
            html = ""
            if e.get("content"):
                html = e["content"][0].get("value", "")
            html = html or e.get("summary", "")
            paras, _meta, _title = html_to_text(html)
            published = _iso_from_struct(e.get("published_parsed")) or date_from_url(link)
            doc = FetchedDoc(url=link, title=normalize(e.get("title", "")), outlet=outlet_for(link).name,
                             published=published, paragraphs=paras, via="rss")
            ctx.add_doc(doc)
            fetched.append(doc)
    if not fetched:
        return f"Error: could not read feed {feed_url} ({'; '.join(errors) or 'no items'})."
    terms = _terms(query)
    ranked = sorted(fetched, key=lambda d: _score(d, terms), reverse=True)
    shown = [d for d in ranked if _score(d, terms) > 0][:max_items]
    head = (f"Read {len(fetched)} items from {feed_url} ({pages} page(s)); "
            f"{len(shown)} match '{query}'. Full text is cached for save_source.")
    if errors:
        head += f" Stopped early: {'; '.join(errors)}."
    parts = [head] + [f"[{i}] " + _show_doc(d, MAX_ITEM_CHARS) for i, d in enumerate(shown, 1)]
    return "\n\n".join(parts)


def fetch_article_impl(ctx: RunContext, url: str) -> str:
    cached = ctx.doc_for(url)
    if cached is not None and cached.via != "data":
        return f"(from this run's cache, via {cached.via})\n" + _show_doc(cached, MAX_ARTICLE_CHARS)
    if canonical_url(url) not in {canonical_url(a) for a in ctx.articles or []}:
        return (f"Refused: {url} is not linked from this topic's feeds or listed in its hints. Read the topic's "
                f"feeds with fetch_rss (each story's text is cached for save_source), or a listed page "
                f"({_allowed_list(ctx)}).")
    try:
        status, body, ctype = ctx.fetch(url)
    except Exception as exc:  # noqa: BLE001
        return f"Error: could not fetch {url} ({type(exc).__name__}). Do not retry the same URL."
    if status in (401, 403, 429):
        return (f"Error: {url} refused automated requests (HTTP {status}). Do not retry. If it is a news story, "
                "use fetch_rss on the outlet's feed (pages=2 or 3 for older stories); the feed has the full text.")
    if status != 200:
        return f"Error: HTTP {status} for {url}."
    html = _decode(body, ctype)
    paras, meta, title = html_to_text(html)
    if not paras:
        return f"Error: no readable text at {url}."
    title = normalize(meta.get("og:title") or meta.get("twitter:title") or title)
    doc = FetchedDoc(url=url, title=title, outlet=outlet_for(url).name,
                     published=_date_from_page(meta, paras, url), paragraphs=paras, via="article")
    ctx.add_doc(doc)
    return _show_doc(doc, MAX_ARTICLE_CHARS)


# --------------------------------------------------------------------------------------
# save_source: the verbatim gate
# --------------------------------------------------------------------------------------


def _doc_sentences(doc: FetchedDoc) -> list[tuple[int, int]]:
    """Global (start, end) sentence spans over doc.text (paragraph breaks are boundaries)."""
    spans: list[tuple[int, int]] = []
    offset = 0
    for para in doc.paragraphs:
        spans.extend((offset + s, offset + e) for s, e in sentence_spans(para))
        offset += len(para) + 1
    return spans


def passage_context(doc: FetchedDoc, start: int, end: int) -> tuple[str, str, str, bool]:
    """(before, highlight, after, starts_mid_sentence) around an exact span of doc.text."""
    text = doc.text
    spans = _doc_sentences(doc) or [(0, len(text))]
    covering = [i for i, (s, e) in enumerate(spans) if s < end and e > start]
    if not covering:
        return "", text[start:end], "", False
    first, last = covering[0], covering[-1]
    h_start, h_end = spans[first][0], spans[last][1]
    highlight = _join_spans(text, spans[first:last + 1])
    lead = text[h_start:start]
    mid = bool(lead.strip(" \"'“‘(["))
    before_spans = _take(spans[max(0, first - 2):first][::-1], text, 350)[::-1]
    after_spans = _take(spans[last + 1:last + 4], text, 600)
    before = _join_spans(text, before_spans)
    after = _join_spans(text, after_spans)
    _ = h_end
    return before, highlight, after, mid


def _take(spans: list[tuple[int, int]], text: str, budget: int) -> list[tuple[int, int]]:
    out, used = [], 0
    for s, e in spans:
        n = e - s
        if out and used + n > budget:
            break
        out.append((s, e))
        used += n
    return out


def _join_spans(text: str, spans: list[tuple[int, int]]) -> str:
    return " ".join(text[s:e].strip() for s, e in spans if text[s:e].strip())


def _closest_paragraph(doc: FetchedDoc, passage: str) -> str:
    want = set(re.findall(r"[a-z0-9]+", normalize(passage).lower()))
    best, best_score = "", 0.0
    for p in doc.paragraphs:
        have = set(re.findall(r"[a-z0-9]+", normalize(p).lower()))
        score = len(want & have) / (len(want) or 1)
        if score > best_score:
            best, best_score = p, score
    return clip(best, 450) if best_score >= 0.3 else ""


def _cats(texts: list[str], *, story: bool = False) -> str:
    hits = story_level_hits(texts) if story else blocklist_hits(texts)
    return "; ".join(sorted({f"{c}: '{p.lower()}'" for c, p in hits}))


def _drop_blocked_sentences(text: str) -> str:
    """Remove context sentences that hit the topic blocklist (players see this text)."""
    spans = sentence_spans(text)
    kept = [text[s:e] for s, e in spans if not blocklist_hits([text[s:e]])]
    return " ".join(kept)


def save_source_impl(ctx: RunContext, url: str, text: str, speaker: str | None = None) -> str:
    doc = ctx.doc_for(url)
    if doc is None:
        return (f"Rejected: {url} was not fetched in this run, so nothing from it can be saved. "
                "Fetch it first with fetch_rss or fetch_article and copy text from the result.")
    if doc.via == "data":
        return "Rejected: EIA numbers are used directly by the forging tools; save_source is for news/official text."
    if ctx.already_used(doc.url):
        return ("Rejected: another puzzle already uses this story. Pick a DIFFERENT story from the feeds "
                "(the hints list the URLs already used).")
    words = word_count(text)
    if words < MIN_PASSAGE_WORDS:
        return f"Rejected: passage too short ({words} words). Save a full sentence or quote."
    if words > MAX_PASSAGE_WORDS:
        return f"Rejected: passage too long ({words} words; max {MAX_PASSAGE_WORDS}). Save a short excerpt."
    span = find_verbatim(text, doc.text)
    if span is None and doc.title and strip_edges(text) == strip_edges(doc.title):
        return _save_headline(ctx, doc)
    if span is None:
        hint = _closest_paragraph(doc, text)
        msg = (f"Rejected: not found word for word in {doc.url}. Real posts must be verbatim. "
               "Copy the exact words from the fetched text (dropping the surrounding quote marks is fine).")
        return msg + (f"\nClosest paragraph in the document: {hint}" if hint else "")
    start, end = span
    while end < len(doc.text) and doc.text[end] in ".!?…":  # keep the sentence's own final punctuation
        end += 1
    original = doc.text[start:end]
    if blocklist_hits([original]):
        return f"Rejected: passage touches a blocked topic ({_cats([original])}; SPEC §8). Pick a different passage."
    if doc.title and blocklist_hits([doc.title]):
        return (f"Rejected: the story's headline touches a blocked topic ({_cats([doc.title])}; SPEC §8). "
                "Pick a different story.")
    outlet = outlet_for(doc.url)
    if speaker:
        name = person_name_part(speaker)
        surname = name.split()[-1] if name.split() else name
        if surname and normalize(surname).lower() not in normalize(doc.text).lower():
            return f"Rejected: speaker '{name}' does not appear in {doc.url}; attribute quotes only to people named there."
        if prob := outlet_speaker_problem(speaker, known_entities([RealEntity(outlet.name, outlet.handle)])):
            return (f"Rejected: {prob}. A quote's speaker is the named person who said it; save a plain sentence "
                    "with no speaker instead.")
    before, highlight, after, mid = passage_context(doc, start, end)
    if story_level_hits([before, highlight, after]):
        return (f"Rejected: the story around this passage is about a blocked topic "
                f"({_cats([before, highlight, after], story=True)}; SPEC §8). Pick a different story.")
    with ctx.lock:
        for s in ctx.sources:
            if s.url == doc.url and normalize(s.text) == normalize(original):
                return f"Already saved as {s.id}."
        src = _new_source(ctx, doc, outlet, original, speaker, before, highlight, after, mid)
        ctx.sources.append(src)
        ctx.write_json("sources.json", {"case_id": ctx.case_id, "topic": ctx.topic,
                                        "sources": [s.as_dict() for s in ctx.sources]}, AGENT)
    who = f" · speaker {src.speaker}" if src.speaker else ""
    return f"Saved {src.id} · {src.outlet} · {src.date or 'undated'}{who}: “{clip(original, 140)}”"


def _save_headline(ctx: RunContext, doc: FetchedDoc) -> str:
    """The article's exact title as a source (headline cards; edited-detail forgeries start from these)."""
    title = doc.title.strip()
    if blocklist_hits([title]):
        return f"Rejected: headline touches a blocked topic ({_cats([title])}; SPEC §8). Pick a different story."
    spans = _doc_sentences(doc)
    after = _join_spans(doc.text, _take(spans[:2], doc.text, 450)) if spans else ""
    if story_level_hits([after]):
        return (f"Rejected: the story under this headline is about a blocked topic ({_cats([after], story=True)}; "
                "SPEC §8). Pick a different story.")
    outlet = outlet_for(doc.url)
    with ctx.lock:
        for s in ctx.sources:
            if s.url == doc.url and s.headline:
                return f"Already saved as {s.id}."
        src = _new_source(ctx, doc, outlet, title, None, "", title, _drop_blocked_sentences(after), False)
        src.headline = True
        ctx.sources.append(src)
        ctx.write_json("sources.json", {"case_id": ctx.case_id, "topic": ctx.topic,
                                        "sources": [s.as_dict() for s in ctx.sources]}, AGENT)
    return f"Saved {src.id} · {src.outlet} · {src.date or 'undated'} · HEADLINE: “{clip(title, 140)}”"


def _new_source(ctx: RunContext, doc: FetchedDoc, outlet, original: str, speaker: str | None, before: str,
                highlight: str, after: str, mid: bool) -> SavedSource:
    return SavedSource(
        id=ctx.next_id("s"), url=doc.url, outlet=outlet.name, kind=outlet.kind,
        date=local_date(doc.published, doc.url),
        published_at=doc.published if doc.published and "T" in doc.published else None,
        title=doc.title, text=original,
        speaker=speaker.strip() if speaker else None,
        before=_drop_blocked_sentences(before), highlight=highlight, after=_drop_blocked_sentences(after),
        starts_mid_sentence=mid,
    )


# --------------------------------------------------------------------------------------
# LangChain tools
# --------------------------------------------------------------------------------------


def research_tools(ctx: RunContext) -> list[BaseTool]:
    @tool
    def fetch_rss(feed_url: str, query: str = "", pages: int = 1, max_items: int = 4) -> str:
        """Read one of the topic's news RSS feeds (listed in the hints; other feeds are refused). Returns the
        items that best match `query` with their full text.

        pages: 1-4 (page 2+ reaches older stories via the feed's `?paged=N`). Every item's text is
        cached so save_source can verify passages from it.
        """
        return fetch_rss_impl(ctx, feed_url, query, pages, max_items)

    @tool
    def fetch_article(url: str) -> str:
        """Fetch a page listed in the hints, or a story linked from the topic's feeds (returned from this run's
        feed cache), as plain text paragraphs. Other sites are refused."""
        return fetch_article_impl(ctx, url)

    @tool
    def get_eia_series(start: str = "2023-01", end: str = "") -> str:
        """NJ residential electricity price (EIA, ¢/kWh, monthly) from the local data file. Dates are YYYY-MM."""
        return get_eia_series_impl(ctx, start, end or None)

    @tool
    def save_source(url: str, text: str, speaker: str = "") -> str:
        """Save one REAL passage (a quote, a sentence with a number, or a story's exact headline).

        `text` must be copied word for word from a document fetched in this run (fetch_rss /
        fetch_article); anything else is rejected. `speaker` = 'Full Name, Title' for quotes
        (the name must appear in the article), empty for plain sentences. Returns the source id.
        """
        return save_source_impl(ctx, url, text, speaker or None)

    # The EIA electricity series is only offered on topics whose hints list data (TOPIC_HINTS "data"), so a food
    # or sports day never gets NJ power prices forged into it.
    return [fetch_rss, fetch_article, *([get_eia_series] if ctx.has_data else []), save_source]

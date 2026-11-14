"""Text helpers: verbatim matching, HTML to text, sentences, numbers, labels.

Everything here is deterministic and dependency-free (stdlib only).
"""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser

# --------------------------------------------------------------------------------------
# Normalization (for verbatim checks only; stored text keeps its original characters)
# --------------------------------------------------------------------------------------

_CHAR_MAP: dict[str, str] = {
    # single quotes / apostrophes
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "´": "'", "`": "'",
    # double quotes
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"', "«": '"', "»": '"',
    # dashes and minus
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    # ellipsis
    "…": "...",
    # spaces
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    # invisible
    "​": "", "‌": "", "‍": "", "﻿": "", "­": "",
}

_EDGE_CHARS = " \t\n\"'.,;:!?-()[]"


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Normalize quotes/dashes/whitespace. Returns (normalized, index map into `text`).

    `index_map[k]` is the index in `text` of the character that produced normalized char `k`.
    """
    out: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(text):
        rep = _CHAR_MAP.get(ch)
        if rep is None:
            rep = unicodedata.normalize("NFKC", ch) if ord(ch) > 127 else ch
        for r in rep:
            if r.isspace():
                if not out or out[-1] == " ":
                    continue
                r = " "
            out.append(r)
            idx.append(i)
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def normalize(text: str) -> str:
    return normalize_with_map(text)[0]


def strip_edges(text: str) -> str:
    """Normalize, then strip surrounding quote marks, punctuation and ellipses."""
    t = normalize(text)
    while True:
        new = t.strip(_EDGE_CHARS)
        if new.startswith("..."):
            new = new[3:]
        if new.endswith("..."):
            new = new[:-3]
        if new == t:
            return t
        t = new


def find_verbatim(needle: str, haystack: str) -> tuple[int, int] | None:
    """Find `needle` in `haystack` after normalization.

    Returns the (start, end) span in the ORIGINAL haystack, or None. Matching is exact
    except for quote/dash/whitespace normalization, surrounding punctuation, and the case
    of the very first letter (quotes often start mid-sentence).
    """
    core = strip_edges(needle)
    if not core:
        return None
    norm_hay, idx = normalize_with_map(haystack)
    candidates = [core]
    if core[0].isalpha():
        candidates.append(core[0].swapcase() + core[1:])
    for cand in candidates:
        pos = norm_hay.find(cand)
        if pos >= 0:
            start = idx[pos]
            end = idx[pos + len(cand) - 1] + 1
            return start, end
    return None


def is_verbatim(needle: str, haystack: str) -> bool:
    return find_verbatim(needle, haystack) is not None


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9$%¢.']+", normalize(text)))


# --------------------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------------------

_NUM_RE = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])\d+(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    """All numbers in `text` (commas removed). '$4.09' -> 4.09, '27%' -> 27.0."""
    vals = []
    for m in _NUM_RE.finditer(normalize(text)):
        try:
            vals.append(float(m.group(0).replace(",", "")))
        except ValueError:  # pragma: no cover
            continue
    return vals


def number_in_set(value: float, allowed: set[float], tol: float = 0.005) -> bool:
    return any(abs(value - a) <= tol for a in allowed)


# --------------------------------------------------------------------------------------
# Sentences
# --------------------------------------------------------------------------------------

_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "gov", "lt", "sen", "rep", "st", "no", "inc", "co", "corp", "jr", "sr",
    "vs", "jan", "feb", "aug", "sept", "sep", "oct", "nov", "dec", "u.s", "n.j", "n.y", "d.c", "e.g", "i.e",
    "assemblyman", "assemblywoman", "prof", "gen", "col", "capt", "sgt", "ave", "blvd",
}
_BOUNDARY_RE = re.compile(r"[.!?…][\"'”’)\]]*\s+(?=[\"'“‘(\[]?[A-Z0-9])")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Sentence (start, end) spans within one paragraph of original text."""
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _BOUNDARY_RE.finditer(text):
        punct_pos = m.start()
        word = re.search(r"([A-Za-z.]+)$", text[start:punct_pos])
        if word:
            w = word.group(1).lower().rstrip(".")
            if w in _ABBREVIATIONS or re.fullmatch(r"[a-z]", w) or re.fullmatch(r"(?:[a-z]\.)+[a-z]", w):
                continue
        end = m.end()
        seg = text[start:end].rstrip()
        if seg:
            spans.append((start, start + len(seg)))
        start = end
    tail = text[start:].rstrip()
    if tail.strip():
        spans.append((start, start + len(tail)))
    return spans


# --------------------------------------------------------------------------------------
# HTML -> text
# --------------------------------------------------------------------------------------

_SKIP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "figure",
              "svg", "button", "select", "iframe", "template", "head", "title"}
_BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "figcaption", "td", "th",
               "pre", "div", "section", "article", "main", "ul", "ol", "table", "tr", "dd", "dt"}
_VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "source", "wbr", "col", "area", "base", "embed"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self.meta: dict[str, str] = {}
        self.title = ""
        self._skip_depth = 0
        self._skip_stack: list[str] = []
        self._buf: list[str] = []
        self._link_chars = 0
        self._in_link = 0
        self._in_title = False

    # -- helpers
    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        total = len(text)
        if text and not (total < 200 and self._link_chars > 0.7 * total):
            self.paragraphs.append(text)
        self._buf = []
        self._link_chars = 0

    # -- parser callbacks
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            key = a.get("property") or a.get("name") or a.get("itemprop")
            if key and a.get("content"):
                self.meta[key.lower()] = a["content"]
            return
        if tag == "time":
            a = {k.lower(): (v or "") for k, v in attrs}
            if a.get("datetime") and "time" not in self.meta:
                self.meta["time"] = a["datetime"]
        if tag == "title":
            self._in_title = True
            return
        if self._skip_depth:
            if tag in _SKIP_TAGS and tag not in _VOID_TAGS:
                self._skip_depth += 1
                self._skip_stack.append(tag)
            return
        if tag in _SKIP_TAGS:
            self._flush()
            self._skip_depth = 1
            self._skip_stack = [tag]
            return
        if tag == "br":
            self._flush()
        elif tag in _BLOCK_TAGS:
            self._flush()
        elif tag == "a":
            self._in_link += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
            return
        if self._skip_depth:
            if tag in _SKIP_TAGS and self._skip_stack and self._skip_stack[-1] == tag:
                self._skip_stack.pop()
                self._skip_depth -= 1
            return
        if tag in _BLOCK_TAGS:
            self._flush()
        elif tag == "a" and self._in_link:
            self._in_link -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
            return
        if self._skip_depth:
            return
        self._buf.append(data)
        if self._in_link:
            self._link_chars += len(data.strip())

    def close(self) -> None:
        super().close()
        self._flush()


def html_to_text(html: str) -> tuple[list[str], dict[str, str], str]:
    """Return (paragraphs, meta tags, <title>) for an HTML document or fragment."""
    p = _Extractor()
    p.feed(html)
    p.close()
    paras = [x for x in p.paragraphs if not _is_boilerplate(x)]
    return paras, p.meta, re.sub(r"\s+", " ", p.title).strip()


_BOILERPLATE = re.compile(
    r"^(the post .* appeared first on|get the morning headlines|subscribe$|share this:|related$|advertisement$)",
    re.IGNORECASE,
)


def _is_boilerplate(p: str) -> bool:
    return bool(_BOILERPLATE.match(p.strip()))


# --------------------------------------------------------------------------------------
# Labels and dates
# --------------------------------------------------------------------------------------

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# AP-ish month names used in seed source labels ("Sept 24, 2026", "Aug 13, 2026")
LABEL_MONTHS = ["Jan", "Feb", "March", "April", "May", "June", "July", "Aug", "Sept", "Oct", "Nov", "Dec"]


def month_label(period: str) -> str:
    """'2025-04' -> 'Apr 2025'."""
    y, m = period.split("-")[:2]
    return f"{MONTHS[int(m) - 1]} {y}"


def source_date_label(iso_date: str | None) -> str | None:
    """'2026-09-24' -> 'Sept 24, 2026'."""
    if not iso_date:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso_date)
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{LABEL_MONTHS[int(mo) - 1]} {int(d)}, {y}"


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", normalize(text).lower()).strip("-")
    return s[:max_len].rstrip("-") or "case"


def clip(text: str, n: int = 200) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"

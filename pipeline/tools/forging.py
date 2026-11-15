"""Forger tools. Every trick is applied BY CODE to real material saved in this run.

The model only chooses *where* to apply a trick (which quote, which months, which axis start).
The code does the doctoring, computes the honest counterpart and the reveal diff, and refuses
operations that would fabricate rather than mislead (SPEC §4, §8.1).
"""

from __future__ import annotations

import math
import re
from typing import Any

from langchain_core.tools import BaseTool, tool

from pipeline.config import EIA_TITLE, EIA_UNIT, EIA_URL
from pipeline.context import RunContext, SavedSource
from pipeline.safety import (
    RealEntity,
    known_entities,
    outlet_speaker_problem,
    overclaim_hits,
    unsupported_words,
)
from pipeline.textutil import clip, month_label, normalize, numbers_in, sentence_spans
from pipeline.tools.research import load_eia, pct_change, shift_month

AGENT = "forger"
CHART_TITLE = "NJ residential electricity price"
HONEST_LINE_TITLE = "NJ residential electricity price, monthly (EIA)"

MAX_QUOTE_GAPS = 2  # internal cuts allowed in a quote crop (more = splicing, i.e. fabrication)
MAX_GAP_WORDS = 8
MIN_KEPT_WORDS = 4
MIN_STAT_GAP_POINTS = 5.0  # a cherry-picked % must differ from the honest one by >= 5 points

CON_LINES = {
    "out-of-context-quote": ("I didn't change a single word. I just stopped quoting early.",
                             "You read the whole sentence. How thorough. How annoying."),
    "misleading-chart": ("Real numbers, honest-looking bars. I just picked where they start.",
                         "Fine. You checked the data. I'll crop it better next time."),
    "cherry-picked-stat": ("Every number I used was true. I just left one out.",
                           "You went looking for the other half of the story. Rude."),
    "edited-detail": ("One little number. Nobody ever checks the little number.",
                      "You compared it word for word. Who does that?"),
    "made-up-story": ("I made the whole thing up. It sounded just like the news, didn't it?",
                      "Too tidy? Fine. Real news is messier than my stories."),
}
CON_FALSE_ALARM = "That one was real. I didn't even have to lie. You did the work for me."
CON_FALSE_ALARM_SUSPICIOUS = "Surprising isn't the same as fake. A grain of salt, not the whole shaker."
CON_CLEAN = "Nothing to catch today. Getting you to doubt everything is my favorite trick of all."


# --------------------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------------------


def quote_text(text: str) -> str:
    """A saved passage as a clean quote: no wrapping quote marks, ends with sentence punctuation."""
    t = text.strip().strip("\"'“”‘’").strip()
    t = re.sub(r"[,;:]+$", "", t).strip()
    if t and t[-1] not in ".!?…":
        t += "."
    return t


def _tok_key(tok: str) -> str:
    return re.sub(r"[^0-9a-z]", "", normalize(tok).lower())


def _year_like(v: float) -> bool:
    return 1990 <= v <= 2100 and float(v).is_integer()


def check_numbers(text: str, allowed: set[float], *, small_ints: bool = True) -> list[float]:
    """Numbers in `text` that are not allowed (years and, optionally, small integers are fine)."""
    bad = []
    for v in numbers_in(text):
        if _year_like(v) or (small_ints and v.is_integer() and 0 <= v <= 24):
            continue
        if not any(abs(v - a) <= 0.005 for a in allowed):
            bad.append(v)
    return bad


def pct_variants(p: float) -> set[float]:
    a = abs(p)
    return {round(a, 1), float(round(a)), float(math.floor(a)), float(math.ceil(a)), round(a, 2)}


def _store(ctx: RunContext, prefix: str, artifact: dict[str, Any]) -> str:
    aid = ctx.next_id(prefix)
    artifact["id"] = aid
    ctx.artifacts[aid] = artifact
    return aid


# --------------------------------------------------------------------------------------
# crop_quote
# --------------------------------------------------------------------------------------


def crop_tokens(tokens: list[str], kept: list[int], end_punct: str = "") -> tuple[str, list[str]]:
    """Deletion-only crop: (shown text, removed phrases) for word tokens kept at ascending indices `kept`.

    Shared by the forger's crop_quote and the player's Con-the-Con crop edit.
    """

    def phrase(a: int, b: int) -> str:
        return " ".join(tokens[a:b]).strip(" ,;:.\"'“”‘’")

    removed: list[str] = []
    if kept[0] > 0:
        removed.append(phrase(0, kept[0]))
    for a, b in zip(kept, kept[1:], strict=False):
        if b > a + 1:
            removed.append(phrase(a + 1, b))
    if kept[-1] < len(tokens) - 1:
        removed.append(phrase(kept[-1] + 1, len(tokens)))
    removed = [r for r in removed if r]
    shown = " ".join(tokens[i] for i in kept).strip("\"'“”‘’ ")
    shown = re.sub(r"[,;:]+$", "", shown)
    if shown and shown[0].islower():
        shown = shown[0].upper() + shown[1:]
    shown = shown.rstrip(".!?…") + (end_punct if end_punct and end_punct in "!?" else ".")
    return shown, removed


def crop_quote_impl(ctx: RunContext, source_id: str, keep_text: str) -> str:
    src = ctx.source(source_id)
    if src is None:
        return f"Rejected: no saved source '{source_id}'. Saved: {', '.join(s.id for s in ctx.sources) or 'none'}."
    original = quote_text(src.text)
    orig_tokens = re.findall(r"\S+", original)
    orig_keys = [_tok_key(t) for t in orig_tokens]
    keep_tokens = [t for t in re.findall(r"\S+", keep_text) if _tok_key(t)]
    if len(keep_tokens) < MIN_KEPT_WORDS:
        return f"Rejected: keep at least {MIN_KEPT_WORDS} words of the quote."
    matched: list[int] = []
    pos = 0
    for kt in keep_tokens:
        key = _tok_key(kt)
        while pos < len(orig_keys) and orig_keys[pos] != key:
            pos += 1
        if pos >= len(orig_keys):
            return (f"Rejected: '{kt}' is not the next word of the real quote. keep_text must use only the quote's "
                    f"own words, in order (you may skip words). Real quote: “{original}”")
        matched.append(pos)
        pos += 1
    gaps: list[tuple[int, int]] = []
    for a, b in zip(matched, matched[1:], strict=False):
        if b > a + 1:
            gaps.append((a + 1, b))
    if len(gaps) > MAX_QUOTE_GAPS:
        return f"Rejected: {len(gaps)} cuts inside the quote; at most {MAX_QUOTE_GAPS} (more is splicing, not cropping)."
    if any(b - a > MAX_GAP_WORDS for a, b in gaps):
        return f"Rejected: a cut removes more than {MAX_GAP_WORDS} words from the middle of the quote."
    end_punct = keep_text.strip().strip("\"'“”‘’")[-1:] if keep_text.strip() else ""
    shown, removed = crop_tokens(orig_tokens, matched, end_punct)
    if not removed:
        return "Rejected: keep_text keeps the whole quote. Remove at least one word or phrase."
    # A quote card is credited to the PERSON who said it. A sentence or headline with no speaker is posted as the
    # made-up account's own text: it is never turned into a quote "by" the outlet (no speaker "NPR").
    speaker = src.speaker
    if speaker and (prob := outlet_speaker_problem(speaker, known_entities([RealEntity(src.outlet)]))):
        return f"Rejected: {prob}."
    removed_txt = " / ".join(f"“{r}”" for r in removed)
    what = "quote" if speaker else ("headline" if src.headline else "sentence")
    art = {
        "kind": "forgery", "trick": "out-of-context-quote", "source_id": src.id, "speaker": speaker,
        "quote": {"text": shown, "speaker": speaker} if speaker else None, "shown": shown,
        "diff": {"type": "quote", "shown": shown, "original": original, "removed": removed},
        "evidence_tools": ["source"],
        "allowed_numbers": sorted(set(numbers_in(original))),
        "default_tell": f"The post cut {removed_txt} out of the real {what}. The full {what} says something else.",
        "default_explanation": (f"The words are real, from {src.outlet}, but the post stops quoting early. "
                                f"The full {what}: “{clip(original, 220)}”"),
    }
    fid = _store(ctx, "f", art)
    if speaker:
        return (f"Made {fid} (out-of-context-quote) from {src.id}.\nShown: “{shown}” — {speaker}\n"
                f"Removed: {removed_txt}\nUse forgery_id {fid} in write_case (the quote text is filled in for you).")
    return (f"Made {fid} (out-of-context-quote) from {src.id}, a {what} with no speaker, so it is posted as the "
            f"account's own text (not a quote card).\nShown: “{shown}”\nRemoved: {removed_txt}\n"
            f"Use forgery_id {fid} in write_case; the cropped text becomes the post body.")


# --------------------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------------------


def _chart(kind: str, title: str, rows: list[tuple[str, float]], y_min: float, y_max: float | None) -> dict:
    return {"type": kind, "title": title, "unit": EIA_UNIT,
            "points": [{"label": month_label(p), "value": v} for p, v in rows], "y_min": y_min, "y_max": y_max}


def _months_apart(a: str, b: str) -> int:
    ya, ma = map(int, a.split("-"))
    yb, mb = map(int, b.split("-"))
    return (yb * 12 + mb) - (ya * 12 + ma)


def data_evidence(prices: dict[str, float], first: str, last: str, note: str) -> dict[str, Any]:
    """`evidence.data` for a chart/stat built on EIA months `first`..`last` (CONTRACT §2.2)."""
    latest = max(prices)
    t_start = shift_month(min(first, shift_month(last, -12)), -3)
    rows = [(p, v) for p, v in prices.items() if t_start <= p <= latest]
    if len(rows) > 30:
        rows = rows[-30:]
    line_start = min("2023-01", shift_month(first, -12))
    line = [(p, v) for p, v in prices.items() if line_start <= p <= latest]
    return {"title": EIA_TITLE, "unit": EIA_UNIT, "url": EIA_URL,
            "table": [{"label": p, "value": v} for p, v in rows],
            "honest_chart": _chart("line", HONEST_LINE_TITLE, line, 0, None), "note": note}


def make_chart_impl(ctx: RunContext, months: list[str] | None = None, start: str = "", end: str = "",
                    chart_type: str = "bar", y_min: float | None = None, title: str = "",
                    honest: bool = False) -> str:
    if not ctx.has_data:
        return "Rejected: this topic has no chart data (EIA NJ electricity prices are for the energy topic only)."
    prices = load_eia(ctx.eia_path)
    if chart_type not in ("bar", "line"):
        return "Rejected: chart_type must be 'bar' or 'line'."
    if months:
        periods = sorted(set(months))
        bad = [m for m in periods if m not in prices]
        if bad:
            return f"Rejected: no EIA data for {bad}. Data runs {min(prices)} to {max(prices)} (YYYY-MM)."
        if not 2 <= len(periods) <= 8:
            return "Rejected: pick 2 to 8 months."
    elif start:
        if start not in prices or (end and end not in prices):
            return f"Rejected: start/end must be YYYY-MM between {min(prices)} and {max(prices)}."
        periods = [p for p in prices if start <= p <= (end or max(prices))]
        if not 3 <= len(periods) <= 48:
            return "Rejected: a window needs 3 to 48 months."
    else:
        return "Rejected: give `months` (e.g. ['2025-04','2026-07']) or a `start`/`end` window."
    rows = [(p, prices[p]) for p in periods]
    values = [v for _, v in rows]
    first, last = periods[0], periods[-1]
    y0 = 0.0 if y_min is None else float(y_min)
    if y0 < 0 or y0 > min(values):
        return f"Rejected: y_min must be between 0 and the smallest value shown ({min(values)})."
    if honest and y0 != 0:
        return "Rejected: an honest chart starts its axis at 0."
    y_max = None
    if y0 > 0:
        y_max = float(math.ceil(max(values)))
        if y_max <= max(values):
            y_max += 1
    shown = _chart(chart_type, title.strip() or CHART_TITLE, rows, y0, y_max)
    shown_pct = pct_change(rows[0][1], rows[-1][1])
    prev = shift_month(last, -12)
    gap = _months_apart(first, last)
    honest_pct = pct_change(prices[prev], prices[last]) if prev in prices else None
    yoy_txt = (f"{month_label(prev)} {prices[prev]} → {month_label(last)} {prices[last]} ({honest_pct:+.1f}%)"
               if honest_pct is not None else "n/a")
    note = f"Same month a year apart: {yoy_txt} ¢/kWh."
    allowed = {v for _, v in rows} | pct_variants(shown_pct)
    if honest_pct is not None:
        allowed |= pct_variants(honest_pct) | {prices[prev]}

    if honest:
        same_month = len(rows) == 2 and gap == 12
        if chart_type == "bar" and not same_month:
            return ("Rejected: an honest bar chart compares the same month one year apart "
                    "(e.g. ['2025-07','2026-07']).")
        if chart_type == "line" and len(rows) < 13:
            return "Rejected: an honest line chart shows at least 13 months."
        art = {"kind": "honest_chart", "chart": shown, "evidence_tools": ["data"],
               "data": data_evidence(prices, first, last, note), "allowed_numbers": sorted(allowed),
               "suggested_body": (f"{month_label(first)} vs {month_label(last)}: NJ home electricity "
                                  f"{rows[0][1]}¢ → {rows[-1][1]}¢ per kWh (EIA)." if len(rows) == 2 else
                                  f"NJ home electricity prices, {month_label(first)} to {month_label(last)} (EIA)."),
               "default_explanation": ("A random account, but the chart is honest: the axis starts at zero and the "
                                       "numbers match EIA's data exactly.")}
        cid = _store(ctx, "c", art)
        return (f"Made honest chart {cid}: {chart_type} {month_label(first)} {rows[0][1]} → {month_label(last)} "
                f"{rows[-1][1]}, axis from 0 ({shown_pct:+.1f}%). Use chart_id {cid} on a REAL post by a made-up "
                f"person. Suggested body: “{art['suggested_body']}”")

    reasons: list[str] = []
    truncated = y0 > 0 and y0 >= 0.5 * min(values)
    if truncated:
        reasons.append(f"the axis starts at {y0:g}¢, not 0")
    if len(rows) == 2 and (gap != 12):
        reasons.append(f"it compares {month_label(first)} with {month_label(last)}, {gap} months apart"
                       + (" (different seasons)" if first[5:] != last[5:] else ""))
    window_lo_hi = chart_type == "line" and rows[0][1] == min(values) and rows[-1][1] == max(values) and len(rows) <= 15
    if window_lo_hi:
        reasons.append("the window runs from a low point straight to a peak")
    if not reasons:
        return ("Rejected: this chart isn't misleading (axis near 0, fair comparison). Crop the axis (y_min close "
                "to the smallest value), and/or compare different seasons, or pass honest=true for a real post.")
    visual = (rows[-1][1] - y0) / (rows[0][1] - y0) if rows[0][1] > y0 else float("inf")
    honest_chart = (_chart("bar", "Same month, one year apart", [(prev, prices[prev]), (last, prices[last])], 0, None)
                    if len(rows) == 2 and gap != 12 and prev in prices else
                    _chart("line", HONEST_LINE_TITLE,
                           [(p, v) for p, v in prices.items() if min("2023-01", shift_month(first, -12)) <= p], 0, None))
    claim_pct = math.ceil(abs(shown_pct)) if abs(shown_pct) >= 10 else round(abs(shown_pct), 1)
    direction = "up" if shown_pct >= 0 else "down"
    suggested = (f"NJ power prices are {direction} {claim_pct:g}% in ONE YEAR. Share before your next bill hits."
                 if 10 <= gap <= 16 else f"NJ power prices are {direction} {claim_pct:g}% since {month_label(first)}!")
    tell = f"{reasons[0][0].upper()}{reasons[0][1:]}" + (f", and {', and '.join(reasons[1:])}" if len(reasons) > 1 else "")
    tell += f". Same month a year apart, prices changed {honest_pct:+.1f}%." if honest_pct is not None else "."
    art = {
        "kind": "forgery", "trick": "misleading-chart", "chart": shown,
        "diff": {"type": "chart", "shown": shown, "original": honest_chart},
        "evidence_tools": ["data"], "data": data_evidence(prices, first, last, note),
        "allowed_numbers": sorted(allowed), "suggested_body": suggested,
        "default_tell": tell,
        "default_explanation": (f"Real EIA numbers, framed to mislead. The chart shows a {abs(shown_pct):.1f}% "
                                f"change drawn as if it were {visual:.1f}x taller. "
                                + (f"Comparing the same month a year apart, the change is {honest_pct:+.1f}%."
                                   if honest_pct is not None else "")),
    }
    fid = _store(ctx, "f", art)
    return (f"Made {fid} (misleading-chart): {chart_type} {month_label(first)} {rows[0][1]} → {month_label(last)} "
            f"{rows[-1][1]}, axis from {y0:g} (shown {shown_pct:+.1f}%; same month a year apart {yoy_txt}).\n"
            f"Misleading because {'; '.join(reasons)}.\nSuggested post text: “{suggested}”\n"
            f"Use forgery_id {fid} in write_case. Numbers in your body must come from: "
            f"{', '.join(f'{x:g}' for x in sorted(allowed))}.")


# --------------------------------------------------------------------------------------
# make_stat_claim
# --------------------------------------------------------------------------------------


def _evidence_text(src: SavedSource) -> str:
    return " ".join(x for x in (src.before, src.highlight, src.after) if x)


# Words a data-mode claim may use: it can only describe the EIA series (NJ home electricity prices).
EIA_CLAIM_WORDS = frozenset(
    "electricity electric power energy price prices bill bills rate rates residential home homes household "
    "households jersey customers kwh kilowatt hour per average".split()
    + [m.lower() for m in ("January", "February", "March", "April", "May", "June", "July", "August", "September",
                           "October", "November", "December")])


def claim_overreach(claim: str, support: str, extra: frozenset[str] | set[str] = frozenset()) -> str | None:
    """A doctored stat may only DROP context. Rejects a claim that adds words or conclusions its source lacks."""
    added = unsupported_words(claim, support, extra)
    loud = overclaim_hits(claim, support)
    if not added and not loud:
        return None
    parts = []
    if loud:
        parts.append(f"it overclaims ({', '.join(loud)})")
    if added:
        parts.append(f"it adds words the {'source' if support else 'data'} doesn't support "
                     f"({', '.join(added[:8])})")
    return ("Rejected: the claim says more than its " + ("source" if support else "data") + ": "
            + "; ".join(parts) + ". A cherry-picked stat leaves context out; it never adds a conclusion.")


def _span_sentences(text: str, a: str, b: str) -> str:
    from pipeline.textutil import find_verbatim

    sa, sb = find_verbatim(a, text), find_verbatim(b, text)
    if not sa or not sb:
        return text
    lo, hi = min(sa[0], sb[0]), max(sa[1], sb[1])
    spans = sentence_spans(text)
    cover = [(s, e) for s, e in spans if s < hi and e > lo]
    if not cover:
        return text[lo:hi]
    return text[cover[0][0]:cover[-1][1]].strip()


def make_stat_claim_impl(ctx: RunContext, claim: str = "", start_month: str = "", end_month: str = "",
                         source_id: str = "", kept_fact: str = "", omitted_fact: str = "") -> str:
    from pipeline.textutil import find_verbatim

    if start_month or end_month:
        if not ctx.has_data:
            return ("Rejected: this topic has no data series, so data mode is off (EIA NJ electricity prices are "
                    "for the energy topic only). Build the stat from a saved source's own numbers: source_id + "
                    "kept_fact + omitted_fact + claim.")
        prices = load_eia(ctx.eia_path)
        a, b = start_month, end_month
        if a not in prices or b not in prices or a >= b:
            return f"Rejected: start_month < end_month, both YYYY-MM between {min(prices)} and {max(prices)}."
        va, vb = prices[a], prices[b]
        shown_pct = pct_change(va, vb)
        latest = max(prices)
        lprev = shift_month(latest, -12)
        latest_pct = pct_change(prices[lprev], prices[latest])
        if abs(shown_pct - latest_pct) < MIN_STAT_GAP_POINTS:
            return (f"Rejected: {month_label(a)}→{month_label(b)} ({shown_pct:+.1f}%) is close to the honest latest "
                    f"year-over-year change ({latest_pct:+.1f}%), so the claim would not mislead. Pick months whose "
                    "change differs by 5+ points (e.g. the 2025 summer jump).")
        gap = _months_apart(a, b)
        direction = "up" if shown_pct >= 0 else "down"
        default_claim = (f"NJ electricity prices are {direction} {round(abs(shown_pct))}% in a year."
                         if gap == 12 else f"NJ electricity prices jumped {round(abs(shown_pct))}% in {gap} months.")
        claim = claim.strip() or default_claim
        allowed = {va, vb} | pct_variants(shown_pct)
        bad = check_numbers(claim, allowed)
        if bad:
            return (f"Rejected: the claim uses numbers not in the data: {bad}. Allowed: "
                    f"{', '.join(f'{x:g}' for x in sorted(allowed))}.")
        if why := claim_overreach(claim, "", extra=EIA_CLAIM_WORDS):
            return why + f" E.g. “{default_claim}”"
        original = (f"EIA: {month_label(a)} {va} → {month_label(b)} {vb} ¢/kWh ({shown_pct:+.1f}%). Latest year: "
                    f"{month_label(lprev)} {prices[lprev]} → {month_label(latest)} {prices[latest]} ({latest_pct:+.1f}%).")
        missing = (f"The most recent year: {month_label(lprev)} to {month_label(latest)} prices changed "
                   f"{latest_pct:+.1f}%.")
        note = (f"Latest year: {month_label(lprev)} {prices[lprev]} → {month_label(latest)} {prices[latest]} ¢/kWh "
                f"({latest_pct:+.1f}%).")
        art = {
            "kind": "forgery", "trick": "cherry-picked-stat", "claim": claim,
            "diff": {"type": "stat", "shown": claim, "original": original, "missing": missing},
            "evidence_tools": ["data"], "data": data_evidence(prices, a, latest, note),
            "allowed_numbers": sorted(allowed),
            "default_tell": (f"It's a real {month_label(a)}→{month_label(b)} number, but the latest year tells a "
                             f"different story: {latest_pct:+.1f}%."),
            "default_explanation": (f"The {abs(shown_pct):.0f}% is real EIA data, but it's a hand-picked window. "
                                    f"Over the most recent year, prices changed {latest_pct:+.1f}%."),
        }
        fid = _store(ctx, "f", art)
        return (f"Made {fid} (cherry-picked-stat, data): “{claim}” ({month_label(a)}→{month_label(b)} "
                f"{shown_pct:+.1f}%; latest year {latest_pct:+.1f}%). Use forgery_id {fid} in write_case; the claim "
                "is the post body.")

    src = ctx.source(source_id)
    if src is None:
        return ("Rejected: give start_month/end_month (EIA mode) or a saved source_id with kept_fact and omitted_fact "
                f"(source mode). Saved sources: {', '.join(s.id for s in ctx.sources) or 'none'}.")
    if not (claim.strip() and kept_fact.strip() and omitted_fact.strip()):
        return "Rejected: source mode needs claim, kept_fact and omitted_fact."
    visible = _evidence_text(src)
    if not find_verbatim(kept_fact, visible):
        return f"Rejected: kept_fact is not word for word in {src.id}'s passage or its context."
    if not find_verbatim(omitted_fact, visible):
        return (f"Rejected: omitted_fact must be word for word in what the player can open for {src.id} "
                f"(the passage and 1-3 sentences around it):\n{clip(visible, 900)}")
    kept_nums = set(numbers_in(kept_fact))
    bad = check_numbers(claim, kept_nums, small_ints=False)
    if bad:
        return f"Rejected: the claim's numbers {bad} are not in kept_fact (only real numbers, no new ones)."
    if why := claim_overreach(claim, " ".join([visible, src.title or ""])):
        return why + f" Restate kept_fact (“{clip(kept_fact, 120)}”) in the source's own words."
    claim_nums = set(numbers_in(claim))
    if not [v for v in numbers_in(omitted_fact) if not any(abs(v - c) < 0.005 for c in claim_nums)]:
        return "Rejected: omitted_fact must contain the number the claim leaves out (the denominator / offset)."
    original = _span_sentences(visible, kept_fact, omitted_fact)
    missing = quote_text(omitted_fact)
    art = {
        "kind": "forgery", "trick": "cherry-picked-stat", "claim": claim.strip(), "source_id": src.id,
        "diff": {"type": "stat", "shown": claim.strip(), "original": original, "missing": missing},
        "evidence_tools": ["source"], "allowed_numbers": sorted(kept_nums),
        "default_tell": f"The post leaves out the other half: “{clip(missing, 160)}”",
        "default_explanation": (f"The number is real ({src.outlet}), but the same passage says “{clip(missing, 160)}” "
                                "The post kept only the scary half."),
    }
    fid = _store(ctx, "f", art)
    return (f"Made {fid} (cherry-picked-stat, source {src.id}): “{claim.strip()}” — leaves out “{clip(missing, 120)}” "
            f"Use forgery_id {fid} in write_case; the claim is the post body.")


# --------------------------------------------------------------------------------------
# edit_detail (edited-detail, CONTRACT §7.1)
# --------------------------------------------------------------------------------------

_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec")
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_CONNECTORS = {"of", "the", "de", "upon", "on", "la", "&"}
MAX_DETAIL_WORDS = 4


def detail_kind(text: str) -> str | None:
    """'number' | 'date' | 'place' for a swappable detail, else None."""
    t = normalize(text).strip()
    words = t.split()
    if not words or len(words) > MAX_DETAIL_WORDS:
        return None
    low = [w.strip(".,").lower() for w in words]
    if any(w in _MONTHS or w in _WEEKDAYS for w in low):
        return "date"
    if re.search(r"\d", t):
        return "number"
    if all(w[0].isupper() or w.lower() in _CONNECTORS for w in words) and any(w[0].isupper() for w in words):
        return "place"
    return None


def edit_detail_impl(ctx: RunContext, source_id: str, find: str, replace: str) -> str:
    from pipeline.safety import blocklist_hits
    from pipeline.textutil import find_verbatim

    src = ctx.source(source_id)
    if src is None:
        return f"Rejected: no saved source '{source_id}'. Saved: {', '.join(s.id for s in ctx.sources) or 'none'}."
    if src.speaker:
        return "Rejected: edited-detail works on headlines and plain sentences, not on quotes (use crop_quote)."
    kind = detail_kind(find)
    if kind is None:
        return (f"Rejected: '{find}' isn't a swappable detail. Swap one number, date or place "
                f"(up to {MAX_DETAIL_WORDS} words).")
    if detail_kind(replace) != kind:
        return f"Rejected: '{find}' is a {kind}; the replacement must be a {kind} too."
    if normalize(find).strip().lower() == normalize(replace).strip().lower():
        return "Rejected: the replacement is the same as the original."
    span = find_verbatim(find, src.text)
    if span is None:
        return f"Rejected: '{find}' is not in {src.id}: “{src.text}”"
    start, end = span
    text = src.text
    if (start > 0 and text[start - 1].isalnum()) or (end < len(text) and text[end].isalnum()):
        return f"Rejected: '{find}' must be a whole word or number in the text, not part of one."
    if blocklist_hits([replace]):
        return "Rejected: the replacement touches a blocked topic (SPEC §8)."
    old = text[start:end]
    new = replace.strip()
    shown = text[:start] + new + text[end:]
    if src.starts_mid_sentence and not shown.startswith("…"):
        shown = "…" + shown
    original = ("…" + text) if src.starts_mid_sentence and not text.startswith("…") else text
    art = {
        "kind": "forgery", "trick": "edited-detail", "source_id": src.id, "shown": shown, "headline": src.headline,
        "diff": {"type": "detail", "shown": shown, "original": original, "changed": [{"from": old, "to": new}]},
        "evidence_tools": ["source"],
        "allowed_numbers": sorted(set(numbers_in(shown))),
        "default_tell": f"The real {'headline' if src.headline else 'story'} says “{old}”, not “{new}”.",
        "default_explanation": (f"Everything else is word for word from {src.outlet}, but one {kind} was swapped: "
                                f"“{old}” became “{new}”. Open the source and compare."),
    }
    fid = _store(ctx, "f", art)
    return (f"Made {fid} (edited-detail) from {src.id}: “{clip(shown, 160)}” ({kind} “{old}” → “{new}”). "
            f"Use forgery_id {fid} in write_case; the edited text is the post body (made-up account only).")


TALL_TALE_WORDS = (8, 45)
_TT_HEALTH = re.compile(r"\b(cures?|cured|vaccin\w*|cancer|diabet\w*|dose|dosage|medic\w*|treatments?|detox|"
                        r"weight[- ]loss|supplements?|pills?|prescri\w*|symptoms?|disease|virus|covid)\b", re.IGNORECASE)
_TT_TITLE_NAME = re.compile(r"\b(?:Gov|Governor|Sen|Senator|Rep|President|Mayor|Dr|Prof|Professor|Mr|Mrs|Ms|CEO|"
                            r"Coach|Judge|Officer|Chief)\.?\s+[A-Z][a-z]+")
_TT_QUOTES = re.compile(r"[\u201c\u201d\"\u2018]|(?<![A-Za-z])'(?=[A-Za-z])")  # double or opening single quotes
# The only capitalized words a made-up story may use: places, days, months (and NJ shorthand). Anything else
# capitalized mid-sentence is a name: a person, band, brand or group, and the Con never invents claims about them.
_TT_OK_CAPS = {
    "new", "jersey", "nj", "garden", "state", "shore", "jersey shore", "pine", "barrens", "turnpike", "parkway",
    "atlantic", "city", "ocean", "county", "cape", "may", "wildwood", "asbury", "park", "hoboken", "newark", "trenton",
    "princeton", "camden", "paterson", "jersey city", "seaside", "heights", "point", "pleasant", "long", "beach",
    "island", "delaware", "river", "hudson", "passaic", "raritan", "bay", "north", "south", "east", "west",
    "central", "america", "american", "us", "u.s.", "usa", "earth", "moon", "mars", "pacific", "arctic", "antarctica",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "mondays", "tuesdays", "wednesdays", "thursdays", "fridays", "saturdays", "sundays",
    "january", "february", "march", "april", "june", "july", "august", "september", "october", "november",
    "december", "thanksgiving", "halloween", "christmas", "i",
}
_TT_CAP = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][\w'\u2019.-]*)")


_TT_COMMON = {"the", "and", "for", "with", "from", "this", "that", "these", "those", "into", "onto", "over", "under",
              "after", "before", "about", "here", "there", "what", "when", "where", "why", "how", "who", "his", "her",
              "its", "our", "your", "their", "she", "they", "you", "but", "not", "now", "new", "one", "two", "all"}


def _title_case(text: str) -> bool:
    """A headline written In Title Case: its capitals say nothing about names."""
    words = [w for w in re.findall(r"[A-Za-z][\w'\u2019-]*", text) if len(w) > 3]
    return len(words) >= 3 and sum(w[0].isupper() for w in words) >= 0.7 * len(words)


def _tt_names(text: str) -> list[str]:
    """Capitalized words mid-sentence that aren't places, days or months (likely names of people or brands)."""
    out = []
    for m in _TT_CAP.finditer(text):
        word = m.group(1).rstrip(".'\u2019").lower()
        word = word[:-2] if word.endswith(("'s", "\u2019s")) else word
        if word and word not in _TT_OK_CAPS:
            out.append(m.group(1))
    return out
_TT_WORD = re.compile(r"[a-z0-9]+")


def _content_words(text: str) -> set[str]:
    stop = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are", "was", "were", "it", "its",
            "that", "this", "with", "as", "at", "by", "from", "be", "has", "have", "had", "new", "just", "their"}
    return {w for w in _TT_WORD.findall(normalize(text).lower()) if w not in stop and len(w) > 2}


def make_tall_tale_impl(ctx: RunContext, source_id: str, claim: str) -> str:
    """made-up-story: the Con's own invented claim, modeled on a saved real story (its "closest real story")."""
    from pipeline.safety import blocklist_hits, story_level_hits
    from pipeline.textutil import word_count

    src = ctx.source(source_id)
    if src is None:
        return f"Rejected: no saved source '{source_id}'. Saved: {', '.join(s.id for s in ctx.sources) or 'none'}."
    text = " ".join((claim or "").split()).strip()
    lo, hi = TALL_TALE_WORDS
    if not lo <= word_count(text) <= hi:
        return f"Rejected: a made-up story is one or two sentences, {lo}-{hi} words (got {word_count(text)})."
    if _TT_QUOTES.search(text):
        return "Rejected: no quote marks. A made-up story never puts words in anyone's mouth."
    if m := _TT_TITLE_NAME.search(text):
        return f"Rejected: '{m.group(0)}' names a person. Made-up stories never name real or realistic people."
    # Names the day's real stories mention (people, bands, brands), wherever they appear in the claim, even as its
    # first word, where capitalization proves nothing ("Springsteen reveals ...").
    in_sources = {w.lower() for s in ctx.sources if not _title_case(s.text)
                  for w in re.findall(r"\b[A-Z][a-z]{2,}\b", s.text)
                  if w.lower() not in _TT_OK_CAPS and w.lower() not in _TT_COMMON and not s.text.startswith(w)}
    if said := [w for w in re.findall(r"[A-Za-z][\w\u2019'-]*", text)
                if re.sub(r"['\u2019]s$", "", w).lower() in in_sources]:
        return (f"Rejected: {', '.join(repr(w) for w in said)} is a name from the real stories. The Con never "
                "invents claims about real people, bands or companies: use a generic subject instead.")
    if names := _tt_names(text):
        return (f"Rejected: {', '.join(repr(n) for n in names)} looks like a name (a person, band, brand or group). "
                "The Con never invents claims about real people or companies: use a generic subject instead "
                "('a Shore diner', 'a local band', 'researchers'). Places, days and months are fine.")
    for s in ctx.sources:
        surname = (s.speaker or "").split(",")[0].split()[-1:] or []
        if surname and len(surname[0]) > 2 and re.search(rf"\b{re.escape(surname[0])}\b", text):
            return f"Rejected: '{surname[0]}' is a real person in the saved sources. Leave people out."
        if s.outlet and re.search(rf"\b{re.escape(s.outlet)}\b", text, re.IGNORECASE):
            return f"Rejected: never credit a made-up story to a real outlet ('{s.outlet}')."
    if _TT_HEALTH.search(text):
        return "Rejected: no health or medical claims, even made-up ones (they can hurt people if shared)."
    if blocklist_hits([text]) or story_level_hits([text]):
        return "Rejected: the story touches a blocked topic (SPEC §8). Keep it light: animals, food, odd science, places."
    mine = _content_words(text)
    for s in ctx.sources:
        theirs = _content_words(s.text)
        if mine and theirs and len(mine & theirs) / len(mine) >= 0.7:
            return (f"Rejected: too close to the real {s.id} ({s.outlet}). Don't copy or tweak a real story: invent a "
                    "different claim that only borrows its subject.")
    original = ("…" + src.text) if src.starts_mid_sentence and not src.text.startswith("…") else src.text
    date = f", {src.date}" if src.date else ""
    art = {
        "kind": "forgery", "trick": "made-up-story", "source_id": src.id, "shown": text, "headline": False,
        "diff": {"type": "made_up", "shown": text, "real": original, "outlet": src.outlet,
                 "date": src.date or None, "url": src.url},
        "evidence_tools": ["source"],
        "allowed_numbers": sorted(set(numbers_in(text))),
        "default_tell": f"No outlet reported this. The closest real story ({src.outlet}{date}) says something else.",
        "default_explanation": ("The Con made this one up. It sounds like news, but no outlet ran it: it cites nothing, "
                                f"and the real {src.outlet} story it borrows from tells a different story."),
    }
    fid = _store(ctx, "f", art)
    return (f"Made {fid} (made-up-story), modeled on {src.id}: “{clip(text, 160)}”. Use forgery_id {fid} in write_case "
            "with a made-up persona; the story is the post body. Don't also use that source as a real post.")


# --------------------------------------------------------------------------------------
# LangChain tools
# --------------------------------------------------------------------------------------


def forging_tools(ctx: RunContext) -> list[BaseTool]:
    @tool
    def make_tall_tale(source_id: str, claim: str) -> str:
        """made-up-story: write a short made-up news claim the Con invents, modeled on a saved REAL story.

        source_id = the real story it borrows its subject and feel from (shown as the closest real story when a
        player checks). claim = one or two sentences, 8-45 words, in the voice of a viral post: plausible, a bit too
        neat, and FALSE. No people's names, no quote marks, no real outlet credit, no health or medical claims, no
        blocked topics, and not a copy or small tweak of any real saved story. Returns a forgery id for write_case.
        """
        return make_tall_tale_impl(ctx, source_id, claim)

    @tool
    def crop_quote(source_id: str, keep_text: str) -> str:
        """out-of-context-quote: cut a saved REAL quote (or sentence/headline) so it misleads.

        keep_text = the words you keep, in the quote's own order (you may skip words, e.g. drop "net", "not yet",
        "but"). At most 2 cuts inside the quote; nothing may be added. A source with a speaker becomes a quote
        card credited to that person; one without a speaker is posted as the account's own text (never credited
        to the outlet). Returns a forgery id for write_case.
        """
        return crop_quote_impl(ctx, source_id, keep_text)

    @tool
    def make_chart(months: list[str] | None = None, start: str = "", end: str = "", chart_type: str = "bar",
                   y_min: float | None = None, title: str = "", honest: bool = False) -> str:
        """misleading-chart (or an honest chart): chart real EIA NJ electricity prices (¢/kWh).

        Pick `months` (2-8, YYYY-MM, e.g. ['2025-04','2026-07']) or a `start`/`end` window, and `y_min` (axis start;
        a misleading chart crops it close to the smallest value). honest=true makes an honest chart for a REAL post
        (axis at 0, same month a year apart). Returns a forgery id (f#) or honest chart id (c#).
        """
        return make_chart_impl(ctx, months, start, end, chart_type, y_min, title, honest)

    @tool
    def make_stat_claim(claim: str = "", start_month: str = "", end_month: str = "", source_id: str = "",
                        kept_fact: str = "", omitted_fact: str = "") -> str:
        """cherry-picked-stat: a true number stated without its context.

        Data mode: start_month + end_month (YYYY-MM) -> a real EIA % change over a hand-picked window (claim optional).
        Source mode: source_id + kept_fact + omitted_fact + claim, where kept_fact and omitted_fact are verbatim
        from the saved passage and omitted_fact holds the offset/denominator the claim leaves out.
        Returns a forgery id for write_case.
        """
        return make_stat_claim_impl(ctx, claim, start_month, end_month, source_id, kept_fact, omitted_fact)

    if not ctx.has_data:
        make_stat_claim.description = (
            "cherry-picked-stat: a true number from a saved source, stated without its context.\n\n"
            "This topic has no data series: use source_id + kept_fact + omitted_fact + claim, where kept_fact and "
            "omitted_fact are verbatim from the saved passage and omitted_fact holds the offset/denominator/time "
            "window the claim leaves out. The claim uses only the source's own words and numbers (no new "
            "conclusions). Returns a forgery id for write_case.")

    @tool
    def edit_detail(source_id: str, find: str, replace: str) -> str:
        """edited-detail: swap ONE number, date or place in a saved REAL headline or sentence (not a quote).

        find = the exact detail in the text (e.g. '$4.09', 'Thursday', 'Trenton'); replace = another detail of the
        same kind. Everything else stays word for word. Only for posts by made-up accounts. Returns a forgery id.
        """
        return edit_detail_impl(ctx, source_id, find, replace)

    # make_chart only charts the EIA electricity series, so it exists only on topics whose hints list data.
    return [crop_quote, *([make_chart] if ctx.has_data else []), make_stat_claim, edit_detail, make_tall_tale]

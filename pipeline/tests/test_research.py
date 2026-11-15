"""Research tools and the verbatim gate (SPEC §8.6: real posts must be verbatim)."""

from __future__ import annotations

import json

from pipeline.tests import fixtures as fx
from pipeline.textutil import find_verbatim, html_to_text, normalize, numbers_in, sentence_spans, strip_edges
from pipeline.tools.research import (
    date_from_url,
    fetch_article_impl,
    fetch_rss_impl,
    get_eia_series_impl,
    local_date,
    save_source_impl,
)

# ---------------------------------------------------------------- text helpers


def test_normalize_quotes_dashes_whitespace():
    assert normalize("“No net  increase” — it’s\n here…") == '"No net increase" - it\'s here...'


def test_find_verbatim_returns_original_span():
    hay = "He said “these actions will result in no net increase,” and left."
    span = find_verbatim('"these actions will result in no net increase"', hay)
    assert span is not None
    assert hay[span[0]:span[1]] == "these actions will result in no net increase"


def test_find_verbatim_allows_first_letter_case_only():
    hay = "it is the most expensive hours of the year"
    assert find_verbatim("It is the most expensive hours", hay)
    assert find_verbatim("It Is the most expensive hours", hay) is None


def test_find_verbatim_rejects_changed_word_or_number():
    hay = "bills jumped roughly 20 percent last year"
    assert find_verbatim("bills jumped roughly 25 percent last year", hay) is None
    assert find_verbatim("bills soared roughly 20 percent last year", hay) is None


def test_strip_edges():
    assert strip_edges(" “…no net increase,” ") == "no net increase"


def test_sentence_spans_respect_abbreviations():
    text = "TRENTON, N.J. – Gov. Smith spoke. Prices rose 5%. “Bills fell,” she said."
    parts = [text[s:e] for s, e in sentence_spans(text)]
    assert parts == ["TRENTON, N.J. – Gov. Smith spoke.", "Prices rose 5%.", "“Bills fell,” she said."]


def test_html_to_text_skips_scripts_and_nav():
    paras, meta, title = html_to_text(fx.PRESS_HTML)
    text = "\n".join(paras)
    assert "do not include me" not in text
    assert "About BPU" not in text
    assert any("jumped roughly 20 percent" in p for p in paras)
    assert title.startswith("Board of Public Utilities")


def test_numbers_in():
    assert numbers_in("rise by $4.09, fall by $4.14; 1,234 kWh; 27%") == [4.09, 4.14, 1234.0, 27.0]


def test_dates():
    assert date_from_url("https://x.test/2026/09/24/story/") == "2026-09-24"
    assert date_from_url("https://nj.gov/bpu/newsroom/2026/approved/20260813.html") == "2026-08-13"
    # UTC evening timestamp -> New Jersey date
    assert local_date("2026-09-25T00:48:02Z", "https://x.test/story") == "2026-09-24"


# ---------------------------------------------------------------- fetch tools


def test_fetch_rss_ranks_by_query_and_caches_all_items(ctx):
    out = fetch_rss_impl(ctx, fx.FEED_URL, "electricity rates bills", pages=1, max_items=4)
    assert "Read 3 items" in out and "2 match" in out
    assert "football" not in out.split("match", 1)[1]
    assert ctx.doc_for(fx.STORY_URL) is not None
    assert ctx.doc_for("https://example-news.test/2026/11/13/football/") is not None  # cached even if not shown
    doc = ctx.doc_for(fx.STORY_URL)
    assert doc.published == "2026-09-25T00:48:02Z"  # UTC kept exact


def test_fetch_rss_pages_use_wordpress_paged(ctx):
    fetch_rss_impl(ctx, fx.FEED_URL, "electricity", pages=3)
    assert ctx.fetch.calls[:2] == [fx.FEED_URL, fx.FEED_URL + "?paged=2"]


def test_fetch_article_uses_cache_and_reports_blocks(ctx):
    fetch_rss_impl(ctx, fx.FEED_URL, "electricity")
    n = len(ctx.fetch.calls)
    out = fetch_article_impl(ctx, fx.STORY_URL)
    assert out.startswith("(from this run's cache") and len(ctx.fetch.calls) == n
    blocked = fetch_article_impl(ctx, fx.BLOCKED_URL)
    assert "HTTP 403" in blocked and "Do not retry" in blocked
    assert ctx.doc_for(fx.BLOCKED_URL) is None


def test_fetch_article_extracts_official_page(ctx):
    out = fetch_article_impl(ctx, fx.PRESS_URL)
    assert "NJ Board of Public Utilities" in out and "Date: 2026-08-13" in out


def test_get_eia_series(ctx):
    out = get_eia_series_impl(ctx, "2025-04", "2025-07")
    assert "2025-04=19.91" in out and "2025-07=25.11" in out and "2025-08" not in out.splitlines()[-1]
    assert "Aug 2025 24.7 -> Aug 2026 24.61 (-0.4%)" in out


# ---------------------------------------------------------------- save_source: the verbatim gate


def test_save_source_accepts_verbatim_with_quote_normalization(ctx):
    fetch_rss_impl(ctx, fx.FEED_URL, "electricity")
    out = save_source_impl(ctx, fx.STORY_URL, '"' + fx.QUOTE_NET + ',"', fx.SPEAKER_NET)
    assert out.startswith("Saved s1"), out
    s = ctx.sources[0]
    assert s.text == fx.QUOTE_NET  # exact characters from the document, quote marks dropped
    assert s.speaker == fx.SPEAKER_NET and s.date == "2026-09-24"
    assert "said Dana Example" in s.highlight
    assert "rate changes Thursday" in s.before
    assert "offset by drops" in s.after
    saved = json.loads((ctx.case_dir / "sources.json").read_text(encoding="utf-8"))
    assert saved["sources"][0]["id"] == "s1"


def test_save_source_rejects_paraphrase_with_hint(ctx):
    fetch_article_impl(ctx, fx.PRESS_URL)
    out = save_source_impl(ctx, fx.PRESS_URL, "New Jersey electric bills went up about 20 percent last year.")
    assert out.startswith("Rejected: not found word for word")
    assert "Closest paragraph" in out
    assert ctx.sources == []


def test_save_source_rejects_changed_number(ctx):
    fetch_article_impl(ctx, fx.PRESS_URL)
    out = save_source_impl(ctx, fx.PRESS_URL, fx.BPU_20.replace("20 percent", "25 percent"))
    assert out.startswith("Rejected")


def test_save_source_rejects_unfetched_url(ctx):
    out = save_source_impl(ctx, "https://nowhere.test/story", "Some words that look like a quote here.")
    assert out.startswith("Rejected:") and "not fetched in this run" in out


def test_save_source_rejects_unknown_speaker_and_short_text(ctx):
    fetch_rss_impl(ctx, fx.FEED_URL, "electricity")
    assert "does not appear" in save_source_impl(ctx, fx.STORY_URL, fx.QUOTE_NET, "Jane Madeup, Official")
    assert "too short" in save_source_impl(ctx, fx.STORY_URL, "no net increase")


def test_save_source_keeps_final_period_and_marks_mid_sentence(ctx):
    fetch_article_impl(ctx, fx.PRESS_URL)
    out = save_source_impl(ctx, fx.PRESS_URL, fx.BPU_20)
    assert out.startswith("Saved")
    s = ctx.sources[0]
    assert s.text.endswith("market.")
    assert s.starts_mid_sentence is True  # "The report comes as New Jersey electricity bills..."


def test_save_source_rejects_blocked_topic(ctx):
    routes = dict(fx.ROUTES)
    routes["https://example-news.test/2026/10/02/school/"] = (
        200, b"<p>Students at the high school will see their electricity bills rise next year, officials said.</p>",
        "text/html")
    ctx.fetch = fx.FakeFetcher(routes)
    ctx.articles.append("https://example-news.test/2026/10/02/school/")
    fetch_article_impl(ctx, "https://example-news.test/2026/10/02/school/")
    out = save_source_impl(ctx, "https://example-news.test/2026/10/02/school/",
                           "Students at the high school will see their electricity bills rise next year")
    assert "blocked topic" in out


def test_save_source_dedupes(ctx):
    fetch_article_impl(ctx, fx.PRESS_URL)
    save_source_impl(ctx, fx.PRESS_URL, fx.BPU_20)
    assert save_source_impl(ctx, fx.PRESS_URL, fx.BPU_20).startswith("Already saved as s1")


def _case_using(cases_dir, case_id: str, url: str, status: str) -> None:
    d = cases_dir / case_id
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"status": status}), encoding="utf-8")
    (d / "sources.json").write_text(json.dumps({"case_id": case_id, "sources": [{"id": "s1", "url": url}]}),
                                    encoding="utf-8")


def test_save_source_refuses_a_story_another_puzzle_uses(ctx):
    _case_using(ctx.cases_dir, "daily-2026-11-01", fx.PRESS_URL, "approved")
    fetch_article_impl(ctx, fx.PRESS_URL)
    assert save_source_impl(ctx, fx.PRESS_URL, fx.BPU_20).startswith("Rejected: another puzzle already uses")


def test_rejected_puzzles_and_the_runs_own_folder_do_not_block_a_story(ctx):
    _case_using(ctx.cases_dir, "daily-2026-11-01", fx.PRESS_URL, "rejected")
    _case_using(ctx.cases_dir, ctx.case_id, fx.PRESS_URL, "draft")
    fetch_article_impl(ctx, fx.PRESS_URL)
    assert save_source_impl(ctx, fx.PRESS_URL, fx.BPU_20).startswith("Saved s1")

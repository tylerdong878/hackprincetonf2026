"""made-up-story: the Con's invented claims (make_tall_tale), the made-up planning style, and write_case."""

from __future__ import annotations

from pipeline.tests.conftest import make_ctx, research
from pipeline.tools.case_writer import build_case_bundle
from pipeline.tools.forging import make_tall_tale_impl
from pipeline.topics import plan_daily

GOOD = "Utility crews in one Jersey town now read every meter by drone, and bills dropped exactly 50 percent overnight."


def test_make_tall_tale_records_the_closest_real_story(tmp_path):
    ctx = make_ctx(tmp_path, trick="made-up-story")
    ids = research(ctx)
    out = make_tall_tale_impl(ctx, ids["ace"], GOOD)
    assert out.startswith("Made f1 (made-up-story)"), out
    art = ctx.artifacts["f1"]
    src = ctx.source(ids["ace"])
    assert art["trick"] == "made-up-story" and art["shown"] == GOOD and art["source_id"] == src.id
    assert art["diff"]["type"] == "made_up" and art["diff"]["outlet"] == src.outlet and src.text in art["diff"]["real"]
    assert art["allowed_numbers"] == [50.0] and art["evidence_tools"] == ["source"]


def test_make_tall_tale_refuses_unsafe_or_copied_claims(tmp_path):
    ctx = make_ctx(tmp_path, trick="made-up-story")
    ids = research(ctx)
    src = ctx.source(ids["ace"])
    cases = {
        "quote marks": ("A town official said “meters are obsolete” and bills fell by half across the county.", "quote marks"),
        "a titled name": ("Mayor Hendricks says every meter in town will be read by drone starting next week.", "names a person"),
        "an outlet credit": (f"{src.outlet} confirms that every meter in the county is now read by drone each night.", "real outlet"),
        "a health claim": ("Living near a wind farm cures insomnia, and bills in those towns dropped by half last winter.", "health"),
        "a near-copy": (src.text, ""),  # refused (as too close, or for the names it copies)
        "too short": ("Bills fell overnight.", "8-45 words"),
    }
    for label, (claim, expect) in cases.items():
        out = make_tall_tale_impl(ctx, ids["ace"], claim)
        assert out.startswith("Rejected") and expect in out, (label, out)
    assert make_tall_tale_impl(ctx, "s99", GOOD).startswith("Rejected: no saved source")
    assert not ctx.artifacts  # nothing stored for a refused claim


def test_made_up_style_plans_only_made_up_stories():
    tricks, reason = plan_daily("2026-11-18", allowed=["out-of-context-quote", "edited-detail"], style="made-up")
    twist, _ = plan_daily("2026-11-18", allowed=["out-of-context-quote", "edited-detail"])
    assert len(tricks) == len(twist) and set(tricks) <= {"made-up-story"} and "made-up" in reason
    assert "made-up-story" not in twist  # the default style keeps the classic edits
    assert plan_daily("2026-11-18", 0, style="made-up")[0] == []


def test_a_made_up_post_cites_no_outlet_and_reveals_the_real_story(tmp_path):
    ctx = make_ctx(tmp_path, trick="made-up-story")
    ids = research(ctx)
    make_tall_tale_impl(ctx, ids["ace"], GOOD)
    posts = [
        {"id": "p1", "role": "real", "source_id": ids["net"]},
        {"id": "p2", "role": "doctored", "forgery_id": "f1", "author_name": "Jersey Bill Watch",
         "author_handle": "jerseybills", "tell": "No outlet is named, and 'exactly 50 percent overnight' is too neat.",
         "explanation": "The Con made this up. The real story is about a $4.09 rise in one utility's bills."},
        {"id": "p3", "role": "real_suspicious", "source_id": ids["bpu20"]},
        {"id": "p4", "role": "real", "source_id": ids["peak"]},
    ]
    case, evidence, key, meta, _ = build_case_bundle(ctx, "Meter maids", "Four posts. I may have made one up.", posts)
    p2 = case["posts"][1]
    assert p2["body"] == GOOD and p2["source_label"] is None and p2["author"]["kind"] == "person"
    assert key["posts"]["p2"]["trick"] == "made-up-story" and key["posts"]["p2"]["diff"]["type"] == "made_up"
    assert key["posts"]["p2"]["tell"].startswith("No outlet")
    assert "source" in evidence["p2"] and meta["tricks"] == ["made-up-story"]
    assert all(p["source_label"] for p in case["posts"] if p["id"] != "p2")  # real posts keep their labels


def test_make_tall_tale_never_names_people_bands_or_brands(tmp_path):
    from pipeline.context import SavedSource  # noqa: F401  (the fixture sources come from research())

    ctx = make_ctx(tmp_path, trick="made-up-story")
    ids = research(ctx)
    src = ctx.source(ids["ace"])
    # a name the day's real stories mention is refused anywhere, even as the first word
    ctx.sources[0].text = ctx.sources[0].text + " Bruce Springsteen played a benefit show."
    for claim, expect in [
        ("Springsteen reveals he wrote every hit on a napkin at a boardwalk arcade in Wildwood last summer.", "Springsteen"),
        ("Scientists taught octopuses to solve Rubik's cubes in under three minutes flat at an aquarium.", "Rubik's"),
        ("A Netflix crew filmed bald eagles opening coolers in the Pine Barrens, then gave them a reward.", "Netflix"),
        ("He wrote 'Born to Run' on a napkin at a Wildwood boardwalk arcade, every word in ten minutes.", "quote marks"),
    ]:
        out = make_tall_tale_impl(ctx, src.id, claim)
        assert out.startswith("Rejected") and expect in out, (claim, out)
    ok = "A Shore diner in Cape May now serves a 40-foot pancake every Sunday in November, syrup included."
    assert make_tall_tale_impl(ctx, src.id, ok).startswith("Made f1"), "places, days and months are fine"


def test_title_case_headlines_dont_turn_common_words_into_names(tmp_path):
    ctx = make_ctx(tmp_path, trick="made-up-story")
    ids = research(ctx)
    ctx.sources[0].text = "A Philadelphia Broadcasting Legend Is Signing Off After 69 Years On The Air In The City"
    claim = "A Shore bakery now gives away a fifteen-foot cinnamon roll on Saturdays to anyone who can finish it."
    assert make_tall_tale_impl(ctx, ids["ace"], claim).startswith("Made f1"), "'to', 'the', 'in' aren't names"

"""Pure-function tests: rating, ranks, mastery, formats, adaptive selection, Con messages."""
import pytest

from backend.app.con_lines import adaptation_message
from backend.app.scoring import (TRICKS, empty_counters, mastery, per_trick, post_format, rank, rating, record_verdict,
                                 score_post)
from backend.app.selection import Candidate, pick_next
from backend.app.store import new_profile


def real(outcome="trusted"):
    return {"doctored": False, "outcome": outcome, "format": "text"}


def fake(outcome="caught"):
    return {"doctored": True, "outcome": outcome, "format": "chart"}


class FixedRng:
    def __init__(self, *values):
        self.values = list(values)

    def random(self):
        return self.values.pop(0)


# ---- rating & rank ---------------------------------------------------------

def test_rating_zero_denominators():
    assert rating([]) == 50
    assert rating([real(), real()]) == 50                   # no doctored posts seen
    assert rating([fake(), fake()]) == 100                  # no real posts seen
    assert rating([fake("fooled")]) == 50
    assert rating([real("false_alarm")]) == 0


def test_rating_formula_and_clamp():
    # Marking everything doctored: hit 1.0, fa 1.0 -> 50.
    assert rating([fake(), real("false_alarm"), real("false_alarm"), real("false_alarm")]) == 50
    # hit 1/2, fa 1/4 -> round(50 + 12.5) = 62 (banker's rounding of 62.5)
    assert rating([fake(), fake("fooled"), real("false_alarm"), real(), real(), real()]) == round(62.5)
    assert 0 <= rating([fake("fooled")] * 5 + [real("false_alarm")] * 5) <= 100


def test_rating_uses_last_30_only():
    old_false_alarms = [real("false_alarm")] * 10
    assert rating(old_false_alarms + [fake()] * 30) == 100


@pytest.mark.parametrize("value,name", [
    (0, "Rookie"), (39, "Rookie"), (40, "Gumshoe"), (59, "Gumshoe"), (60, "Inspector"),
    (79, "Inspector"), (80, "Chief"), (89, "Chief"), (90, "Untouchable"), (100, "Untouchable"),
])
def test_ranks(value, name):
    assert rank(value) == name


def test_mastery_rule():
    c = empty_counters()
    assert mastery(c) == 0
    assert mastery(dict(c, shown=1, caught=1)) == 1
    assert mastery(dict(c, shown=3, caught=2, missed=1)) == 2
    assert mastery(dict(c, shown=4, caught=4)) == 3
    assert mastery(dict(c, shown=4, caught=4, honest_shown=2, false_alarms=2)) == 2  # too jumpy for 3


def test_post_format():
    assert post_format({"chart": {"type": "bar"}, "quote": {"text": "x"}}) == "chart"
    assert post_format({"chart": None, "quote": {"text": "x"}}) == "quote"
    assert post_format({"chart": None, "quote": None, "body": "20%"}) == "text"


# ---- adaptive selection ------------------------------------------------------------

def cand(cid, number, tricks=(), clean=False, honest=()):
    return Candidate(id=cid, number=number, tricks=list(tricks), clean=clean, honest_tricks=set(honest))


def test_pick_skips_finished_and_falls_back():
    a, b = cand("a", 1, ["misleading-chart"]), cand("b", 2, ["out-of-context-quote"])
    profile = new_profile("p")
    profile["history"] = [{"case_id": "a"}]
    assert pick_next([a, b], profile, FixedRng(0.5, 0.5)).id == "b"
    profile["history"].append({"case_id": "b"})
    assert pick_next([a, b], profile, FixedRng(0.5, 0.5)).id == "a"   # all finished -> any approved
    assert pick_next([], profile, FixedRng(0.5, 0.5)) is None


def test_pick_clean_about_20_percent():
    dirty, clean = cand("d", 1, ["misleading-chart"]), cand("c", 2, clean=True)
    assert pick_next([dirty, clean], {}, FixedRng(0.1, 0.5)).id == "c"   # roll < 0.2 -> clean
    assert pick_next([dirty, clean], {}, FixedRng(0.5, 0.5)).id == "d"
    assert pick_next([clean], {}, FixedRng(0.5, 0.5)).id == "c"          # only clean left


def test_pick_prefers_weakest_trick():
    profile = new_profile("p")
    profile["tricks"]["misleading-chart"].update(shown=2, missed=2)
    profile["tricks"]["out-of-context-quote"].update(shown=2, caught=2)
    quote_case, chart_case = cand("q", 1, ["out-of-context-quote"]), cand("c", 2, ["misleading-chart"])
    assert pick_next([quote_case, chart_case], profile, FixedRng(0.5, 0.1)).id == "c"


def test_pick_prefers_honest_posts_for_high_false_alarm_format():
    profile = new_profile("p")
    profile["tricks"]["misleading-chart"].update(honest_shown=3, false_alarms=3)
    x = cand("x", 1, ["out-of-context-quote"], honest=["cherry-picked-stat"])
    y = cand("y", 2, ["out-of-context-quote"], honest=["misleading-chart"])
    assert pick_next([x, y], profile, FixedRng(0.5, 0.95)).id == "y"


# ---- the Con's adaptation message ----------------------------------------------------

def scored(*records, clean=False):
    return {"clean_case": clean, "records": [dict({"trick": None, "named": False}, **r) for r in records]}


def test_adaptation_messages():
    profile = new_profile("p")
    profile["history"] = [{"case_id": "a", "tools_used": ["data"]}]
    fooled = {"doctored": True, "outcome": "fooled", "format": "chart", "trick": "misleading-chart"}
    msg = adaptation_message(scored(fooled), profile)
    assert msg == "The Con has noticed: you trust official-looking charts."

    profile["tricks"]["misleading-chart"]["missed"] = 2
    alarm = {"doctored": False, "outcome": "false_alarm", "format": "quote"}
    msg = adaptation_message(scored(fooled, alarm), profile)
    assert msg == "The Con has noticed: you still trust official-looking charts, and you doubt real quotes."

    profile["history"] = [{"case_id": "a", "tools_used": []}]
    ok = {"doctored": False, "outcome": "trusted", "format": "text"}
    assert "never open the source" in adaptation_message(scored(ok), profile)

    profile["history"] = [{"case_id": "a", "tools_used": ["source"]}]
    assert "craftier" in adaptation_message(scored(ok), profile)
    assert "clean feed" in adaptation_message(scored(ok, clean=True), profile)


# ---- made-up-story: a whole story the Con invented ---------------------------------------------

MADE_UP_DIFF = {"type": "made_up", "shown": "Octopuses now open childproof jars in exactly 9 seconds.",
                "real": "Octopuses can learn to open jars.", "outlet": "NPR", "date": "2026-11-10", "url": None}


def test_made_up_story_scores_like_the_other_tricks():
    assert "made-up-story" in TRICKS and "made-up-story" in new_profile("p")["tricks"]
    post = {"id": "p2", "body": MADE_UP_DIFF["shown"], "chart": None, "quote": None}
    key = {"doctored": True, "trick": "made-up-story", "tell": "No outlet ran it.", "diff": MADE_UP_DIFF}
    caught, rec = score_post(post, key, True, "made-up-story")
    assert (caught["outcome"], caught["points"], caught["trick_named_correctly"]) == ("caught", 150, True)
    assert caught["diff"] == MADE_UP_DIFF
    fooled, fooled_rec = score_post(post, key, False, None)
    assert (fooled["outcome"], fooled["points"], fooled["trick"]) == ("fooled", 0, "made-up-story")

    profile = new_profile("p")
    record_verdict(profile, "c1", {"score": 150, "records": [rec, fooled_rec]}, ["source"], "2026-11-15T00:00:00Z")
    assert profile["tricks"]["made-up-story"] == dict(empty_counters(), shown=2, caught=1, missed=1, named=1)
    assert per_trick(profile["tricks"])["made-up-story"] == {"miss_rate": 0.5, "false_alarm_rate": 0.0, "mastery": 1}
    msg = adaptation_message(scored(dict(fooled_rec)), profile)
    assert msg == "The Con has noticed: you believe a story just because it sounds like news."

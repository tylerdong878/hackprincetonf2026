"""Build the two hand-made seed cases from verified real material.

Every quote below was checked word for word against its source page on 2026-11-14 (see RESEARCH.md §4).
Numbers come from data/sources/eia_nj_res_price_monthly.raw.json (EIA API v2, NJ residential, ¢/kWh).
These cases have origin "seed" (built by the team, not by the AI pipeline) and no pipeline_log.jsonl.

Run:  uv run python scripts/build_seed_cases.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EIA = ROOT / "data" / "sources" / "eia_nj_res_price_monthly.raw.json"
CASES = ROOT / "data" / "cases"

EIA_URL = "https://www.eia.gov/electricity/data/browser/"
NJM_0924 = "https://newjerseymonitor.com/2026/09/24/utilities-board-votes-electric-rates/"
NJM_1112 = "https://newjerseymonitor.com/2026/11/12/nj-virtual-power-plant-battery-storage/"
BPU_0813 = "https://nj.gov/bpu/newsroom/2026/approved/20260813.html"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load_prices() -> dict[str, float]:
    rows = json.loads(EIA.read_text(encoding="utf-8"))["response"]["data"]
    return {r["period"]: float(r["price"]) for r in rows}


def label(period: str) -> str:
    y, m = period.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def table(prices: dict[str, float], start: str, end: str) -> list[dict]:
    return [{"label": p, "value": v} for p, v in sorted(prices.items()) if start <= p <= end]


def write_case(case_id: str, case: dict, evidence: dict, answer_key: dict, meta: dict) -> None:
    folder = CASES / case_id
    folder.mkdir(parents=True, exist_ok=True)
    for name, obj in [("case.json", case), ("evidence.json", evidence),
                      ("answer_key.json", answer_key), ("meta.json", meta)]:
        (folder / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", folder.relative_to(ROOT))


# --- Shared real material (verbatim) -------------------------------------------------------

HS_QUOTE = ("Taken together with the items on the agenda earlier this month, these actions will result in "
            "no net increase in electricity rates and a slight decrease in gas rates")
NJM_0924_DESC = ("The Board of Public Utilities on Thursday pledged no net increase in electricity rates for "
                 "New Jersey's four regulated utilities.")
NJM_0924_BEFORE = "Sherrill signed the order during her inauguration as governor in January."
NJM_0924_AFTER = ("Among the state's four electric distribution companies, Rockland Electric Company will see the "
                  "largest monthly decrease, though overall bills will remain roughly unchanged…")
ACE_PASSAGE = ("Atlantic City Electric's average monthly bills, for example, will rise by $4.09 because of changes "
               "to its Regional Greenhouse Gas Initiative charges, certain infrastructure investments, and shifts in "
               "transmission charges set federally. But those same bills will fall by $4.14 due to changes to some "
               "Societal Benefits Charge components and lost sales related to energy efficiency and conservation "
               "programs, leaving the average monthly bill 5 cents cheaper than before.")
ACE_BEFORE = ("Some customers will see individual components of their bills increase, but those will be offset by "
              "drops to other components.")

BPU_20PCT = ("New Jersey electricity bills jumped roughly 20 percent last year, driven in large part by rising "
             "costs in PJM's capacity market.")
BPU_20PCT_BEFORE = ("The report, required by the New Jersey Legislature and delivered to Governor Sherrill and "
                    "lawmakers, comes as")
BPU_20PCT_AFTER = ("PJM Interconnection is the regional transmission organization responsible for coordinating the "
                   "movement of wholesale electricity and managing grid reliability across 13 states, including "
                   "New Jersey and the District of Columbia.")
BPU_CAPACITY = ("While capacity charges currently account for approximately 15 to 20 percent of a typical "
                "customer's electric bill, they represent the single largest cost component that state utility "
                "commissions like the NJBPU cannot directly set, regulate, or change.")
BPU_HS_1 = ("New Jersey ratepayers deserve a clear explanation of why their bills are rising and what can be done "
            "about it,")
BPU_HS_2 = "The fastest way to lower bills is getting new power generation built."

REBHORN = ("I don't know if everyone in New Jersey understands, but it is the most expensive hours of the year that "
           "are driving the really unsustainable price hikes in the utility and electricity bills that we saw in "
           "the last few years,")
REBHORN_BEFORE = ("The state is seeking an overall reduction of 547.1 megawatts across the four electric "
                  "distribution companies.")

NJM_AUTHOR = {"name": "New Jersey Monitor", "handle": "@NJMonitor", "kind": "outlet", "verified": True,
              "avatar_color": "#2F9E6A"}
NJM_ACCOUNT = {"name": "New Jersey Monitor", "handle": "@NJMonitor", "created": None, "followers": None,
               "verified": True, "bio": "News outlet · newjerseymonitor.com",
               "recent_posts": []}
BPU_AUTHOR = {"name": "NJ Board of Public Utilities", "handle": "@NJBPU", "kind": "official", "verified": True,
              "avatar_color": "#1F5FD1"}
BPU_ACCOUNT = {"name": "NJ Board of Public Utilities", "handle": "@NJBPU", "created": None, "followers": None,
               "verified": True, "bio": "State utility regulator · nj.gov/bpu", "recent_posts": []}


def build(prices: dict[str, float]) -> None:
    apr25, jul25, jul26 = prices["2025-04"], prices["2025-07"], prices["2026-07"]
    pct_shown = round((jul26 / apr25 - 1) * 100, 1)      # 26.5
    pct_yoy = round((jul26 / jul25 - 1) * 100, 1)        # 0.3

    shown_chart = {"type": "bar", "title": "NJ residential electricity price", "unit": "¢/kWh",
                   "points": [{"label": label("2025-04"), "value": apr25}, {"label": label("2026-07"), "value": jul26}],
                   "y_min": 19, "y_max": 26}
    honest_bars = {"type": "bar", "title": "Same month, one year apart", "unit": "¢/kWh",
                   "points": [{"label": label("2025-07"), "value": jul25}, {"label": label("2026-07"), "value": jul26}],
                   "y_min": 0, "y_max": None}
    honest_line = {"type": "line", "title": "NJ residential electricity price, monthly (EIA)", "unit": "¢/kWh",
                   "points": [{"label": label(r["label"]), "value": r["value"]}
                              for r in table(prices, "2023-01", max(prices))],
                   "y_min": 0, "y_max": None}
    data_evidence = {
        "title": "NJ residential average electricity price (EIA)", "unit": "¢/kWh", "url": EIA_URL,
        "table": table(prices, "2025-01", max(prices)),
        "honest_chart": honest_line,
        "note": (f"Prices jumped in summer 2025. July to July, they went from {jul25} to {jul26}¢ "
                 f"(+{pct_yoy}%)."),
    }

    # ---------------- Case 1: the demo case (one doctored chart) ----------------
    cid = "2026-11-14-power-bills"
    case = {
        "id": cid, "number": 1, "title": "Is your power bill really frozen?", "topic": "NJ electricity prices",
        "briefing": "Power bills in New Jersey. Four posts. I may have touched a few. Or none.",
        "clue_budget": 3,
        "trick_options": ["out-of-context-quote", "misleading-chart", "cherry-picked-stat"],
        "posts": [
            {"id": "p1", "author": NJM_AUTHOR, "posted_at": "2026-09-24T19:48:00Z", "body": NJM_0924_DESC,
             "quote": {"text": HS_QUOTE + ".", "speaker": "Ben Hertz-Shargel, NJBPU President"},
             "chart": None, "source_label": "New Jersey Monitor · Sept 24, 2026", "tools": ["source", "account"]},
            {"id": "p2",
             "author": {"name": "Jersey Bill Watch", "handle": "@jerseybills", "kind": "person", "verified": False,
                        "avatar_color": "#E3A42B"},
             "posted_at": "2026-11-12T15:20:00Z",
             "body": "NJ power prices are up 27% in ONE YEAR. Share before your next bill hits.",
             "quote": None, "chart": shown_chart, "source_label": None, "tools": ["data", "account"]},
            {"id": "p3", "author": BPU_AUTHOR, "posted_at": "2026-08-13T16:00:00Z",
             "body": "…" + BPU_20PCT, "quote": None, "chart": None,
             "source_label": "NJBPU press release · Aug 13, 2026", "tools": ["source", "account"]},
            {"id": "p4", "author": NJM_AUTHOR, "posted_at": "2026-11-12T21:05:00Z", "body": "",
             "quote": {"text": REBHORN.rstrip(",") + ".", "speaker": "Emma Rebhorn, BPU Commissioner"},
             "chart": None, "source_label": "New Jersey Monitor · Nov 12, 2026", "tools": ["source", "account"]},
        ],
    }
    evidence = {
        "p1": {"source": {"outlet": "New Jersey Monitor", "date": "2026-09-24", "url": NJM_0924,
                          "before": NJM_0924_BEFORE,
                          "highlight": f"“{HS_QUOTE},” said Ben Hertz-Shargel, the board's president.",
                          "after": NJM_0924_AFTER + " " + ACE_BEFORE + " " + ACE_PASSAGE},
               "account": NJM_ACCOUNT},
        "p2": {"data": data_evidence,
               "account": {"name": "Jersey Bill Watch", "handle": "@jerseybills", "created": "October 2026",
                           "followers": 1840, "verified": False,
                           "bio": "Exposing what they don't want you to know about your bills.",
                           "recent_posts": ["Your utility bill is a SCAM. Thread \U0001F9F5",
                                            "Share before they delete this!"]}},
        "p3": {"source": {"outlet": "NJ Board of Public Utilities", "date": "2026-08-13", "url": BPU_0813,
                          "before": BPU_20PCT_BEFORE, "highlight": BPU_20PCT, "after": BPU_20PCT_AFTER},
               "account": BPU_ACCOUNT},
        "p4": {"source": {"outlet": "New Jersey Monitor", "date": "2026-11-12", "url": NJM_1112,
                          "before": REBHORN_BEFORE,
                          "highlight": f"“{REBHORN}” Board of Public Utilities Commissioner Emma Rebhorn said Thursday.",
                          "after": ""},
               "account": NJM_ACCOUNT},
    }
    answer_key = {
        "clean_case": False,
        "posts": {
            "p2": {"doctored": True, "trick": "misleading-chart",
                   "tell": (f"The axis starts at 19¢, and the bars compare April 2025, before the summer spike, "
                            f"with July 2026, 15 months later. July to July, prices rose {pct_yoy}%."),
                   "explanation": ("Real EIA numbers, framed to mislead. A cropped axis makes a "
                                   f"{pct_shown}% gap look like a cliff, and cherry-picked months turn an old "
                                   "jump into a 'one year' rise. Prices did jump in 2025. Over the past year "
                                   "they've been nearly flat."),
                   "con_line_fooled": "Real numbers, honest-looking bars. I just picked where they start.",
                   "con_line_caught": "Fine. You checked the data. I'll crop it better next time.",
                   "diff": {"type": "chart", "shown": shown_chart, "original": honest_bars}},
            "p1": {"doctored": False, "suspicious_real": False,
                   "explanation": ("Real and word for word. 'No net increase' means some charges go up and others "
                                   "go down: Atlantic City Electric's bill rises $4.09 from some charges and falls "
                                   "$4.14 from others."),
                   "con_line_false_alarm": "That one was real. 'Net' is doing a lot of work, but it's true."},
            "p3": {"doctored": False, "suspicious_real": True,
                   "explanation": ("Startling, but true: it's straight from the BPU's own press release. Bills jumped "
                                   "in 2025, and that's the rise the chart smuggled into its window."),
                   "con_line_false_alarm": "Surprising isn't the same as fake. A grain of salt, not the whole shaker."},
            "p4": {"doctored": False, "suspicious_real": False,
                   "explanation": "Real and word for word, from New Jersey Monitor's coverage of a BPU vote.",
                   "con_line_false_alarm": "Real. Not everything that sounds dramatic is a trick."},
        },
        "con_line_clean": None,
    }
    meta = {"status": "approved", "origin": "seed", "daily": True, "difficulty": "medium",
            "created_at": "2026-11-14T05:00:00Z", "tricks": ["misleading-chart"],
            "sources": [NJM_0924, NJM_1112, BPU_0813, EIA_URL], "rejection_reason": None}
    write_case(cid, case, evidence, answer_key, meta)

    # ---------------- Case 2: a clean case (nothing doctored) ----------------
    cid2 = "2026-11-14-power-bills-clean"
    honest_shared = dict(honest_bars, title="July vs. July")
    case2 = {
        "id": cid2, "number": 2, "title": "Who's driving your bill?", "topic": "NJ electricity prices",
        "briefing": "More about your power bill. Four posts. Some of them are mine. Maybe.",
        "clue_budget": 3,
        "trick_options": ["out-of-context-quote", "misleading-chart", "cherry-picked-stat"],
        "posts": [
            {"id": "p1", "author": BPU_AUTHOR, "posted_at": "2026-08-13T16:05:00Z", "body": BPU_CAPACITY,
             "quote": None, "chart": None, "source_label": "NJBPU press release · Aug 13, 2026",
             "tools": ["source", "account"]},
            {"id": "p2",
             "author": {"name": "Priya (watt nerd)", "handle": "@wattnerd", "kind": "person", "verified": False,
                        "avatar_color": "#8B5CF6"},
             "posted_at": "2026-11-13T02:10:00Z",
             "body": (f"July vs July: NJ home electricity prices barely moved, {jul25}¢ → {jul26}¢ "
                      "per kWh (EIA). The big jump was summer 2025."),
             "quote": None, "chart": honest_shared, "source_label": None, "tools": ["data", "account"]},
            {"id": "p3", "author": BPU_AUTHOR, "posted_at": "2026-08-13T16:10:00Z", "body": "",
             "quote": {"text": BPU_HS_2, "speaker": "Ben Hertz-Shargel, NJBPU President"}, "chart": None,
             "source_label": "NJBPU press release · Aug 13, 2026", "tools": ["source", "account"]},
            {"id": "p4", "author": NJM_AUTHOR, "posted_at": "2026-09-24T20:00:00Z", "body": ACE_PASSAGE,
             "quote": None, "chart": None, "source_label": "New Jersey Monitor · Sept 24, 2026",
             "tools": ["source", "account"]},
        ],
    }
    evidence2 = {
        "p1": {"source": {"outlet": "NJ Board of Public Utilities", "date": "2026-08-13", "url": BPU_0813,
                          "before": BPU_20PCT_AFTER, "highlight": BPU_CAPACITY, "after": ""},
               "account": BPU_ACCOUNT},
        "p2": {"data": data_evidence,
               "account": {"name": "Priya (watt nerd)", "handle": "@wattnerd", "created": "March 2019",
                           "followers": 312, "verified": False,
                           "bio": "Energy grad student. Charts with sources, always.",
                           "recent_posts": ["Reading PJM auction results so you don't have to.",
                                            "Source for every chart: EIA electricity data browser."]}},
        "p3": {"source": {"outlet": "NJ Board of Public Utilities", "date": "2026-08-13", "url": BPU_0813,
                          "before": f"“{BPU_HS_1}” said NJBPU President Ben Hertz-Shargel.",
                          "highlight": f"“{BPU_HS_2}",
                          "after": "That requires replacing PJM's unpredictable price spikes with modern rules that "
                                   "attract long-term investment…”"},
               "account": BPU_ACCOUNT},
        "p4": {"source": {"outlet": "New Jersey Monitor", "date": "2026-09-24", "url": NJM_0924,
                          "before": ACE_BEFORE, "highlight": ACE_PASSAGE, "after": ""},
               "account": NJM_ACCOUNT},
    }
    answer_key2 = {
        "clean_case": True,
        "posts": {
            "p1": {"doctored": False, "suspicious_real": False,
                   "explanation": "Word for word from the BPU's Aug 13, 2026 press release.",
                   "con_line_false_alarm": "Real. A percentage with a clear 'of what' is a good sign."},
            "p2": {"doctored": False, "suspicious_real": True,
                   "explanation": ("A random account, but the chart is honest: same month a year apart, axis from "
                                   "zero, and the numbers match EIA's data exactly."),
                   "con_line_false_alarm": "Unknown account, honest chart. Check the data, not the avatar."},
            "p3": {"doctored": False, "suspicious_real": False,
                   "explanation": "Word for word from the BPU's Aug 13, 2026 press release.",
                   "con_line_false_alarm": "Real. Not every confident sentence is a con."},
            "p4": {"doctored": False, "suspicious_real": False,
                   "explanation": ("Word for word from New Jersey Monitor. Note that it gives both numbers: the "
                                   "$4.09 rise and the $4.14 drop."),
                   "con_line_false_alarm": "Real. It showed both sides of the math, which I never do."},
        },
        "con_line_clean": "Nothing to catch today. Getting you to doubt everything is my favorite trick of all.",
    }
    meta2 = {"status": "approved", "origin": "seed", "daily": False, "difficulty": "easy",
             "created_at": "2026-11-14T05:00:00Z", "tricks": [],
             "sources": [NJM_0924, BPU_0813, EIA_URL], "rejection_reason": None}
    write_case(cid2, case2, evidence2, answer_key2, meta2)


if __name__ == "__main__":
    build(load_prices())

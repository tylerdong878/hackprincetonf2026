"""Build the v2 Daily Grain cases (2026-11-13 .. 2026-11-17) and the Con-the-Con Fool Deck.

Everything is assembled from the verified material bank below (BANK). Each excerpt was copied word for word
from a page or feed fetched on 2026-11-14, and is listed with its URL in CONTENT_SOURCES.md. Numbers come from
files in data/sources/ (EIA API v2 JSON; FRED CSVs of BLS average prices). The script never invents a quote:
doctored posts are built only by the allowed operations on bank text (crop = delete words, edited-detail = swap
one number/date/place in a real headline, cherry-picked stat = drop context, misleading chart = axis/window on
real data), and they are always posted by made-up accounts (author.kind "person").

Run:
  uv run python scripts/build_daily_cases.py            # write data/cases/<daily ids>/ and data/fool_deck/*.json
  uv run python scripts/build_daily_cases.py --verify   # also re-fetch every source URL and confirm each
                                                       # excerpt is still on the page (needs network)

The script also runs offline self-checks (deletion-only crops, detail swaps, axis/data consistency, tools vs.
evidence, 0-3 doctored per day, ...) and refuses to write anything if one fails.
"""

from __future__ import annotations

import csv
import html
import json
import re
import sys
import unicodedata
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources"
CASES = ROOT / "data" / "cases"
DECK = ROOT / "data" / "fool_deck"
CREATED_AT = "2026-11-14T08:00:00Z"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ALL_TRICKS = ["out-of-context-quote", "misleading-chart", "cherry-picked-stat", "edited-detail"]


# ======================================================================================
# Sources (fetched 2026-11-14)
# ======================================================================================

@dataclass(frozen=True)
class Src:
    outlet: str
    date: str          # YYYY-MM-DD (publication date)
    published: str     # ISO UTC publication time, used as posted_at for the outlet's own post
    url: str
    label: str         # source_label shown on the card


S = {
    "njm_0924": Src("New Jersey Monitor", "2026-09-24", "2026-09-24T19:48:02Z",
                    "https://newjerseymonitor.com/2026/09/24/utilities-board-votes-electric-rates/",
                    "New Jersey Monitor · Sept 24, 2026"),
    "njm_1112": Src("New Jersey Monitor", "2026-11-12", "2026-11-12T20:18:21Z",
                    "https://newjerseymonitor.com/2026/11/12/nj-virtual-power-plant-battery-storage/",
                    "New Jersey Monitor · Nov 12, 2026"),
    "bpu_0813": Src("NJ Board of Public Utilities", "2026-08-13", "2026-08-13T16:00:00Z",
                    "https://nj.gov/bpu/newsroom/2026/approved/20260813.html", "NJBPU press release · Aug 13, 2026"),
    "npr_mice": Src("NPR", "2026-11-09", "2026-11-09T21:39:35Z",
                    "https://www.npr.org/2026/11/09/nx-s1-6027938/"
                    "mice-can-learn-to-fight-by-watching-tiny-rodent-cage-matches-study-finds", "NPR · Nov 9, 2026"),
    "npr_dino": Src("NPR", "2026-11-09", "2026-11-09T22:00:49Z",
                    "https://www.npr.org/2026/11/09/nx-s1-6026704/"
                    "scientists-think-theyve-found-ancient-remnants-of-dinosaur-blood", "NPR · Nov 9, 2026"),
    "npr_moon": Src("NPR", "2026-11-08", "2026-11-08T23:36:47Z",
                    "https://www.npr.org/2026/11/08/nx-s1-6034002/nasa-astronaut-class-applications-2026",
                    "NPR · Nov 8, 2026"),
    "npr_schooner": Src("NPR", "2026-09-29", "2026-09-29T20:53:52Z",
                        "https://www.npr.org/2026/09/29/nx-s1-5984674/"
                        "noreaster-exposes-part-of-a-schooner-wrecked-on-nantucket", "NPR · Sept 29, 2026"),
    "npr_grocery": Src("NPR", "2026-10-20", "2026-10-20T09:00:00Z",
                       "https://www.npr.org/2026/10/20/nx-s1-5989636/grocery-prices-eggs-coffee-inflation",
                       "NPR · Oct 20, 2026"),
    "npr_candy": Src("NPR", "2026-10-30", "2026-10-30T09:00:00Z",
                     "https://www.npr.org/2026/10/30/nx-s1-6018566/halloween-candy-prices-chocolate",
                     "NPR · Oct 30, 2026"),
    "npr_socks": Src("NPR", "2026-06-30", "2026-06-30T21:08:38Z",
                     "https://www.npr.org/2026/06/30/nx-s1-5847935/footballers-donate-socks-to-hooves-in-need",
                     "NPR · June 30, 2026"),
    "npr_library": Src("NPR", "2026-09-18", "2026-09-18T23:04:09Z",
                       "https://www.npr.org/2026/09/18/nx-s1-5971268/overdue-library-magazine-returned-after-132-years",
                       "NPR · Sept 18, 2026"),
    "npr_camel": Src("NPR", "2026-09-14", "2026-09-14T20:34:16Z",
                     "https://www.npr.org/2026/09/14/nx-s1-5955652/nevada-camel-race", "NPR · Sept 14, 2026"),
    "npr_marathon": Src("NPR", "2026-11-01", "2026-11-01T17:33:21Z",
                        "https://www.npr.org/2026/11/01/nx-s1-6025437/new-york-marathon-almgren-chepkirui-win",
                        "NPR · Nov 1, 2026"),
    "nj1015_boss": Src("New Jersey 101.5", "2026-11-13", "2026-11-13T21:08:49Z",
                       "https://nj1015.com/bruce-springsteen-jaws-grievance/", "New Jersey 101.5 · Nov 13, 2026"),
    "nj1015_bridge": Src("New Jersey 101.5", "2026-11-12", "2026-11-12T20:49:22Z",
                         "https://nj1015.com/ixp/942/p/tacony-palmyra-bridge-closed-ship-crash/",
                         "New Jersey 101.5 · Nov 12, 2026"),
    "nj1015_seals": Src("New Jersey 101.5", "2026-11-12", "2026-11-12T14:56:26Z",
                        "https://nj1015.com/ixp/393/p/jon-stewart-seals/", "New Jersey 101.5 · Nov 12, 2026"),
    "nj1015_drivers": Src("New Jersey 101.5", "2026-11-13", "2026-11-14T00:43:04Z",
                          "https://nj1015.com/new-jersey-worst-drivers-2/", "New Jersey 101.5 · Nov 13, 2026"),
    "whyy_victor": Src("WHYY", "2026-11-02", "2026-11-02T10:00:04Z",
                       "https://whyy.org/articles/new-jersey-music-recording-camden-rca-victor/", "WHYY · Nov 2, 2026"),
}

EIA_URL = "https://www.eia.gov/electricity/data/browser/"
FRED = {  # series id -> (local file, FRED page, series title as FRED shows it)
    "eggs": ("fred_APU0000708111_eggs.csv", "https://fred.stlouisfed.org/series/APU0000708111",
             "Average Price: Eggs, Grade A, Large (Cost per Dozen) in U.S. City Average"),
    "coffee": ("fred_APU0000717311_coffee.csv", "https://fred.stlouisfed.org/series/APU0000717311",
               "Average Price: Coffee, 100%, Ground Roast, All Sizes (Cost per Pound/453.6 Grams) in U.S. City Average"),
    "beef": ("fred_APU0000703112_ground_beef.csv", "https://fred.stlouisfed.org/series/APU0000703112",
             "Average Price: Ground Beef, 100% Beef (Cost per Pound/453.6 Grams) in U.S. City Average"),
    "butter": ("fred_APU0000FS1101_butter.csv", "https://fred.stlouisfed.org/series/APU0000FS1101",
               "Average Price: Butter, Stick (Cost per Pound/453.6 Grams) in U.S. City Average"),
}


# ======================================================================================
# The verified material bank: (source key, verbatim text). Straight apostrophes stand in for the pages'
# curly ones; “ ” mark quoted speech. Verification ignores quote style, dash style and whitespace only.
# ======================================================================================

BANK: dict[str, tuple[str, str]] = {
    # --- New Jersey Monitor, Sept 24, 2026 (CC BY-NC-ND: short attributed excerpts only) ---
    "HS_QUOTE": ("njm_0924", "Taken together with the items on the agenda earlier this month, these actions will "
                             "result in no net increase in electricity rates and a slight decrease in gas rates"),
    "HS_PARA": ("njm_0924", "“Taken together with the items on the agenda earlier this month, these actions will "
                            "result in no net increase in electricity rates and a slight decrease in gas rates,” said "
                            "Ben Hertz-Shargel, the board's president."),
    "NJM_0924_DESC": ("njm_0924", "The Board of Public Utilities on Thursday pledged no net increase in electricity "
                                  "rates for New Jersey's four regulated utilities."),
    "NJM_0924_BEFORE": ("njm_0924", "Sherrill signed the order during her inauguration as governor in January."),
    "ACE_BEFORE": ("njm_0924", "Some customers will see individual components of their bills increase, but those "
                               "will be offset by drops to other components."),
    "ACE_PASSAGE": ("njm_0924", "Atlantic City Electric's average monthly bills, for example, will rise by $4.09 "
                                "because of changes to its Regional Greenhouse Gas Initiative charges, certain "
                                "infrastructure investments, and shifts in transmission charges set federally. But "
                                "those same bills will fall by $4.14 due to changes to some Societal Benefits Charge "
                                "components and lost sales related to energy efficiency and conservation programs, "
                                "leaving the average monthly bill 5 cents cheaper than before."),
    "ACE_RISE": ("njm_0924", "Atlantic City Electric's average monthly bills, for example, will rise by $4.09 "
                             "because of changes to its Regional Greenhouse Gas Initiative charges, certain "
                             "infrastructure investments, and shifts in transmission charges set federally."),
    "ACE_FALL": ("njm_0924", "But those same bills will fall by $4.14 due to changes to some Societal Benefits "
                             "Charge components and lost sales related to energy efficiency and conservation "
                             "programs, leaving the average monthly bill 5 cents cheaper than before."),
    # --- New Jersey Monitor, Nov 12, 2026 ---
    "VPP_HEADLINE": ("njm_1112", "NJ regulators approve virtual power plant, battery storage programs"),
    "VPP_LEDE": ("njm_1112", "The Board of Public Utilities on Thursday unanimously approved the launch of an "
                             "interim virtual power plant program and the next phase of the state's energy storage "
                             "program."),
    "VPP_EXPLAIN": ("njm_1112", "Virtual power plants seek to remotely reduce the power draw of certain devices, like "
                                "smart thermostats or electric vehicle chargers, during the parts of the day that grid "
                                "demand is highest and compensate ratepayers for their reduced electricity use."),
    "REBHORN": ("njm_1112", "I don't know if everyone in New Jersey understands, but it is the most expensive hours of "
                            "the year that are driving the really unsustainable price hikes in the utility and "
                            "electricity bills that we saw in the last few years"),
    "REBHORN_PARA": ("njm_1112", "“I don't know if everyone in New Jersey understands, but it is the most expensive "
                                 "hours of the year that are driving the really unsustainable price hikes in the "
                                 "utility and electricity bills that we saw in the last few years,” Board of Public "
                                 "Utilities Commissioner Emma Rebhorn said Thursday."),
    "REBHORN_BEFORE": ("njm_1112", "The state is seeking an overall reduction of 547.1 megawatts across the four "
                                   "electric distribution companies."),
    "REBHORN_AFTER": ("njm_1112", "The order approved by the BPU Thursday requires the state's four regulated "
                                  "utilities to stand up their interim virtual power plant programs by Oct. 1, 2027."),
    # --- NJ Board of Public Utilities press release, Aug 13, 2026 ---
    "BPU_20PCT": ("bpu_0813", "New Jersey electricity bills jumped roughly 20 percent last year, driven in large part "
                              "by rising costs in PJM's capacity market."),
    "BPU_20PCT_BEFORE": ("bpu_0813", "The report, required by the New Jersey Legislature and delivered to Governor "
                                     "Sherrill and lawmakers, comes as"),
    "BPU_20PCT_AFTER": ("bpu_0813", "PJM Interconnection is the regional transmission organization responsible for "
                                    "coordinating the movement of wholesale electricity and managing grid reliability "
                                    "across 13 states, including New Jersey and the District of Columbia."),
    # --- NPR, Nov 9, 2026: mice ---
    "MICE_HEADLINE": ("npr_mice", "Mice can learn to fight by watching tiny rodent cage matches, study finds"),
    "MICE_SUMMARY": ("npr_mice", "Brain scientists set up \"gladiator style\" cage matches for mice — and found that "
                                 "simply observing fighting matches can rewire a mouse's brain to resemble those who "
                                 "actually fought."),
    "FALKNER_ARENA": ("npr_mice", "We set this up to look a little bit like a gladiator arena, so the mouse is kind of "
                                  "above the two mice fighting on a platform."),
    "FALKNER_ROLE": ("npr_mice", "Annegret Falkner is an associate professor at the Princeton Neuroscience Institute."),
    "MICE_NATURE": ("npr_mice", "The paper is published in the journal Nature."),
    "FALKNER_NFL": ("npr_mice", "The question is not whether you can be a professional athlete by watching the NFL, "
                                "but are you better at football for watching sports than if you had never watched "
                                "anything? And the answer is absolutely yes."),
    "FALKNER_NFL_BEFORE": ("npr_mice", "Falkner, the Princeton researcher, says humans can also learn physical skills "
                                       "by watching others, like in sports."),
    "FALKNER_NFL_AFTER": ("npr_mice", "In the study, the observer mice fought with a mix of aggressive and defensive "
                                      "behaviors, like they had learned tactics from both sides."),
    # --- NPR, Nov 9, 2026: dinosaur blood ---
    "DINO_HEADLINE": ("npr_dino", "Scientists think they've found ancient remnants of dinosaur blood"),
    "DINO_SUMMARY": ("npr_dino", "Scientists have studied plenty of dinosaur bones, eggs and footprints. Now, some "
                                 "think they've found their strongest evidence yet of dinosaur blood."),
    "DINO_DOUBT": ("npr_dino", "GRICE: So I'm quietly confident that these may be red blood cells. ROTT: Other "
                               "scientists are not as sure."),
    # --- NPR, Nov 8, 2026: NASA astronauts ---
    "MOON_HEADLINE": ("npr_moon", "NASA is looking for astronauts to live and work on the Moon"),
    "MOON_LEDE": ("npr_moon", "If you have dreams of going to the moon, you now have a chance. NASA is accepting "
                              "applications for those interested in becoming an astronaut."),
    "MOON_BASE": ("npr_moon", "The candidates selected to be astronauts would not only test spacecraft but would also "
                              "live and work on the moon in a future moon base, said NASA Administrator Jared Isaacman "
                              "in a statement released on Saturday."),
    "NASA_CORPS": ("npr_moon", "There are currently 32 active astronauts in NASA's astronaut corps. Since NASA "
                               "missions began in the 1960s, the agency has selected 370 people to train as "
                               "astronauts, according to the agency."),
    "NASA_8000": ("npr_moon", "The applicant process is extremely competitive. Out of more than 8,000 applicants for "
                              "NASA's last astronaut class, only 10 candidates were selected."),
    "NASA_AFTER": ("npr_moon", "While any U.S. citizen can apply and there is no official age restriction, applicants "
                               "will need to have a master's degree in a STEM-related field such as engineering or "
                               "math."),
    # --- NPR, Sept 29, 2026: Nantucket schooner ---
    "SCHOONER_HEADLINE": ("npr_schooner", "Nor'easter exposes part of a schooner wrecked on Nantucket"),
    "ROBINSON_BEFORE": ("npr_schooner", "That's David Robinson. He's the director of Massachusetts Board of Underwater "
                                        "Archaeological Resources. Part of the Warren Sawyer wreck was exposed back in "
                                        "2022, and based on what he's seen in photos and on video, he says the new "
                                        "Nantucket wreckage could be more of that schooner. Keywords there, could be."),
    "ROBINSON": ("npr_schooner", "Well, I can with 100% confidence tell you that I wouldn't be 100% confident."),
    "ROBINSON_AFTER": ("npr_schooner", "And that's because the way that the Warren Sawyer was built, lots of ships were "
                                       "built like that."),
    # --- NPR, Oct 20, 2026: five grocery items ---
    "GROCERY_HEADLINE": ("npr_grocery", "Why these 5 everyday items fluctuate in price at the grocery store"),
    "BUTTER": ("npr_grocery", "A pound of butter averaged $3.96 in September. That was down 17.3% since last year, "
                              "bucking the trend of rising food prices."),
    "BUTTER_AFTER": ("npr_grocery", "Interest in butter has spread recently, nourishing a strong demand for the dairy "
                                    "product."),
    "VOLPE_BEFORE": ("npr_grocery", "That period of dramatic food inflation slowed down in 2023, though prices "
                                    "generally haven't returned to previous levels. Instead, grocery costs have "
                                    "continued to rise, just at a slower rate, roughly in line with overall inflation."),
    "VOLPE": ("npr_grocery", "Any inflation that happens now in the grocery store is on top of these already very "
                             "high prices, and consumers are very sensitive to that."),
    "VOLPE_PARA": ("npr_grocery", "“But the damage had been done,” said Ricky Volpe, a professor of agribusiness at "
                                  "Cal Poly San Luis Obispo. “Any inflation that happens now in the grocery store is on "
                                  "top of these already very high prices, and consumers are very sensitive to that.”"),
    # --- NPR, Oct 30, 2026: Halloween candy ---
    "CANDY_BEFORE": ("npr_candy", "For people stocking up on candy this Halloween, it's a spooky season in the grocery "
                                  "store — and not in a fun way."),
    "CANDY_STAT": ("npr_candy", "Prices for candy, the most popular Halloween purchase, and gum have risen 7.7% in one "
                                "year and are up more than 18% in two years, according to the latest federal data."),
    "CANDY_AFTER": ("npr_candy", "That's higher than the average rate of food inflation during that time."),
    # --- NPR, June 30, 2026: socks ---
    "SOCKS_HEADLINE": ("npr_socks", "Footballers donate socks to hooves in need"),
    "SOCKS_SUMMARY": ("npr_socks", "The U.K. football club Arsenal have donated dozens of socks — to a donkey and horse "
                                   "sanctuary."),
    "SOCKS_FLIES": ("npr_socks", "The soccer socks can act as a compression sleeve and hold bandages in place and "
                                 "protect them from flies."),
    # --- NPR, Sept 18, 2026: library ---
    "LIBRARY_HEADLINE": ("npr_library", "Overdue library magazine returned after 132 years"),
    "LIBRARY_SUMMARY": ("npr_library", "After the Concord Public Library in New Hampshire announced a fine freeze, a "
                                       "man has returned an overdue magazine published in 1894."),
    "LIBRARY_1894": ("npr_library", "Well, a magazine from 1894 was just returned to the Concord Public Library in New "
                                    "Hampshire about 132 years overdue."),
    # --- NPR, Sept 14, 2026: camel race ---
    "CAMEL_HEADLINE": ("npr_camel", "The true fake story behind the annual Virginia City Camel Race"),
    "CAMEL_SUMMARY": ("npr_camel", "Back in the 1950s, a newspaper editor in Nevada wrote a fake story about a camel "
                                   "race happening in his town as a joke. Eventually, he helped make it a real thing "
                                   "and the annual Virginia City Camel Race was born, which continues to this day."),
    "CAMEL_KICKER": ("npr_camel", "Bob Richards lied the thing right into existence."),
    # --- NPR, Nov 1, 2026: NYC Marathon ---
    "MARATHON_BEFORE": ("npr_marathon", "It was the 50th time that the race has run through all five boroughs of the "
                                        "city."),
    "MARATHON_STAT": ("npr_marathon", "There were just over 2,000 competitors in 1976, the seventh running of the "
                                      "race, including only 88 women. About 60,000 runners stepped up to the starting "
                                      "line Sunday, with nearly half of them women."),
    "MARATHON_AFTER": ("npr_marathon", "There were runners from more than 140 countries competing Sunday, including "
                                       "defending men's Kipruto."),
    # --- New Jersey 101.5 ---
    "BOSS_HEADLINE": ("nj1015_boss", "Bruce Springsteen has a bone to pick with the movie 'Jaws'"),
    "BOSS_LEDE": ("nj1015_boss", "Bruce Springsteen had some words to say at the 2026 MoMA film benefit, and he "
                                 "happened to go after one of my favorite movies of all time."),
    "BOSS_GRIEVANCE": ("nj1015_boss", "As someone who came up at the Jersey Shore, The Boss had a very specific "
                                      "grievance with the original summer blockbuster, 'Jaws.'"),
    "BOSS_QUOTE": ("nj1015_boss", "In June of 1975 I went to a small theater directly across from the Atlantic Ocean "
                                  "and I saw 'Jaws.' I was 25 years old and one of the great pleasures on the Jersey "
                                  "shore in 1975 was night swimming"),
    "BOSS_QUOTE_PARA": ("nj1015_boss", "“In June of 1975 I went to a small theater directly across from the Atlantic "
                                       "Ocean and I saw 'Jaws.' I was 25 years old and one of the great pleasures on "
                                       "the Jersey shore in 1975 was night swimming,” Bruce said."),
    "BRIDGE_HEADLINE": ("nj1015_bridge", "Cargo Ship Crashes Into Tacony-Palmyra Bridge Causing It to Be Stuck Open"),
    "BRIDGE_REPORT": ("nj1015_bridge", "There are very early reports that a cargo ship has crashed into the "
                                       "Tacony-Palmyra Bridge this afternoon. As a result of the crash the bridge is "
                                       "unable to close, officials say."),
    "BRIDGE_SAFE": ("nj1015_bridge", "The good news is that there were no reported injuries in the incident."),
    "SEALS_HEADLINE": ("nj1015_seals", "Jon Stewart Heralds the Return of the Sandy Hook Seals"),
    "SEALS_QUOTE": ("nj1015_seals", "New pal alert!! Jersey Shore Novembers!!!"),
    "SEALS_PARA": ("nj1015_seals", "Comedian and New Jersey native Jon Stewart shared a video on Instagram Wednesday "
                                   "night showing a seal bobbing above water and the caption, \"New pal alert!! Jersey "
                                   "Shore Novembers!!!\" Commenters quickly flocked to offer their opinions on where "
                                   "the clip may be shot."),
    "SEALS_AFTER": ("nj1015_seals", "Clearly, Jon Stewart spotted one of the Sandy Hook seals, and we can head back "
                                    "home for Thanksgiving with joy in our hearts."),
    "DRIVERS_STAT": ("nj1015_drivers", "A new study from LendingTree ranks New Jersey number one for the worst drivers "
                                       "in the country. According to the study, New Jersey drivers recorded 56.9 "
                                       "driving incidents per 1,000 drivers through August 2026."),
    "DRIVERS_AFTER": ("nj1015_drivers", "That includes accidents, DUIs, speeding-related incidents and other traffic "
                                        "citations."),
    "DRIVERS_CAVEAT": ("nj1015_drivers", "To be fair, LendingTree's study is based on insurance inquiry data from "
                                         "QuoteWizard, not some nationwide experiment in which researchers actually "
                                         "put drivers behind the wheel and watched them attempt to navigate the "
                                         "Flemington Circle."),
    # --- WHYY, Nov 2, 2026 ---
    "VICTOR_HEADLINE": ("whyy_victor", "The music recording industry was born in Camden. This Berlin museum traces "
                                       "RCA-Victor's rise and fall"),
    "VICTOR_LEDE": ("whyy_victor", "A museum about the RCA-Victor company has opened in Berlin, New Jersey, just a "
                                   "few miles from where the stereo and TV equipment maker was born in Camden."),
    "VICTOR_PIANO": ("whyy_victor", "The museum also has one of the earliest electric pianos from the 1930s, which "
                                    "sort of works."),
}


def t(key: str) -> str:
    return BANK[key][1]


def cat(*keys: str) -> str:
    """Join bank excerpts; non-adjacent excerpts are separated by an ellipsis."""
    return " … ".join(t(k) for k in keys)


# ======================================================================================
# Data
# ======================================================================================

def load_eia() -> dict[str, float]:
    rows = json.loads((SOURCES / "eia_nj_res_price_monthly.raw.json").read_text(encoding="utf-8"))["response"]["data"]
    return {r["period"]: float(r["price"]) for r in rows}


def load_fred(name: str) -> dict[str, float]:
    """FRED CSV -> {YYYY-MM: value}. Months with no published value are skipped."""
    out: dict[str, float] = {}
    with (SOURCES / FRED[name][0]).open(encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if len(row) != 2 or not re.fullmatch(r"\d{4}-\d{2}-01", row[0]) or not row[1].strip():
                continue
            out[row[0][:7]] = float(row[1])
    return out


def label(period: str) -> str:
    y, m = period.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def series(prices: dict[str, float], start: str, end: str) -> list[dict]:
    return [{"label": p, "value": v} for p, v in sorted(prices.items()) if start <= p <= end]


def pct(a: float, b: float) -> float:
    return round((b / a - 1) * 100, 1)


def bars(title: str, unit: str, pts: list[tuple[str, float]], y_min: float = 0, y_max: float | None = None) -> dict:
    return {"type": "bar", "title": title, "unit": unit, "points": [{"label": a, "value": v} for a, v in pts],
            "y_min": y_min, "y_max": y_max}


def line(title: str, unit: str, rows: list[dict]) -> dict:
    return {"type": "line", "title": title, "unit": unit,
            "points": [{"label": label(r["label"]), "value": r["value"]} for r in rows], "y_min": 0, "y_max": None}


# ======================================================================================
# Authors and account cards
# ======================================================================================

OUTLETS = {
    "New Jersey Monitor": ("@NJMonitor", "outlet", "#2F9E6A", "News outlet · newjerseymonitor.com"),
    "NJ Board of Public Utilities": ("@NJBPU", "official", "#1F5FD1", "State utility regulator · nj.gov/bpu"),
    "NPR": ("@NPR", "outlet", "#1D4ED8", "News outlet · npr.org"),
    "New Jersey 101.5": ("@nj1015", "outlet", "#DC2626", "Radio news · nj1015.com"),
    "WHYY": ("@WHYY", "outlet", "#7C3AED", "Public media · whyy.org"),
    "U.S. Energy Information Administration": ("@EIAgov", "official", "#0E7490",
                                               "Federal energy statistics agency · eia.gov"),
    "U.S. Bureau of Labor Statistics": ("@BLS_gov", "official", "#0F766E", "Federal statistics agency · bls.gov"),
}


def outlet_author(name: str) -> dict:
    h, kind, color, _ = OUTLETS[name]
    return {"name": name, "handle": h, "kind": kind, "verified": True, "avatar_color": color}


def outlet_account(name: str) -> dict:
    h, _, _, bio = OUTLETS[name]
    return {"name": name, "handle": h, "created": None, "followers": None, "verified": True, "bio": bio,
            "recent_posts": []}


@dataclass(frozen=True)
class Persona:
    """A made-up account. Never a real person or outlet."""
    name: str
    handle: str
    color: str
    created: str
    followers: int
    bio: str
    recent: tuple[str, ...]

    def author(self) -> dict:
        return {"name": self.name, "handle": self.handle, "kind": "person", "verified": False,
                "avatar_color": self.color}

    def account(self) -> dict:
        return {"name": self.name, "handle": self.handle, "created": self.created, "followers": self.followers,
                "verified": False, "bio": self.bio, "recent_posts": list(self.recent)}


P_BILLWATCH = Persona("Jersey Bill Watch", "@jerseybills", "#E3A42B", "October 2026", 1840,
                      "Exposing what they don't want you to know about your bills.",
                      ("Your utility bill is a SCAM. Thread \U0001F9F5", "Share before they delete this!"))
P_RATERELIEF = Persona("Rate Relief NJ", "@ratereliefnj", "#65A30D", "September 2026", 5120,
                       "Good news about your bills, every day. \u2600\ufe0f",
                       ("Your bills are going DOWN. Here's proof \U0001F447", "Thank us later."))
P_FOSSIL = Persona("Fossil Fever", "@fossilfever", "#EA580C", "September 2026", 2310,
                   "Dinosaurs, daily. Mostly vibes. \U0001F996",
                   ("T. rex could outrun your car. Probably.", "Like if you'd ride a raptor \U0001F996"))
P_ORBIT = Persona("Orbit Daily", "@orbitdaily_", "#4F46E5", "June 2019", 48200,
                  "Space news, fast. Launch alerts and sky-watching tips.",
                  ("Starship update thread \U0001F9F5", "Moon, Venus and Spica tonight. Look up!"))
P_CLUCK = Persona("Cluck Report", "@cluckreport", "#DB2777", "October 2026", 912,
                  "Exposing Big Egg. \U0001F95A",
                  ("They don't want you to know what's in the carton.", "Share before the price goes up again!"))
P_TRICKCHEAT = Persona("Trick or Cheat", "@trickorcheat", "#E3A42B", "October 2026", 3400,
                       "Halloween is a scam and I can prove it \U0001F383",
                       ("Full-size bars are a myth now.", "Retweet if your bag was 50% raisins."))
P_AISLE7 = Persona("Aisle Seven Alex", "@aisle7alex", "#0891B2", "May 2018", 640,
                   "Grocery data nerd. Every number links to BLS.",
                   ("BLS average price data drops monthly. Mark your calendar.", "Unit prices or it didn't happen."))
P_SHELF = Persona("Shelf Life", "@shelflifereads", "#8B5CF6", "April 2021", 12800,
                  "Book news & library lore \U0001F4DA",
                  ("Your library card is a superpower.", "Name a book you never returned. I'll wait."))


# ======================================================================================
# Post / evidence / answer helpers
# ======================================================================================

def src_ev(key: str, before: str, highlight: str, after: str) -> dict:
    s = S[key]
    return {"outlet": s.outlet, "date": s.date, "url": s.url, "before": before, "highlight": highlight,
            "after": after}


def post(pid: str, author: dict, posted_at: str, card_style: str, ev: dict, *, body: str = "",
         quote: dict | None = None, chart: dict | None = None, source_label: str | None = None) -> tuple[dict, dict]:
    tools = [k for k in ("source", "data", "account") if k in ev]
    p = {"id": pid, "author": author, "posted_at": posted_at, "body": body, "quote": quote, "chart": chart,
         "source_label": source_label, "card_style": card_style, "tools": tools}
    return p, ev


def outlet_post(pid: str, skey: str, card_style: str, before: str, highlight: str, after: str, **kw) -> tuple[dict, dict]:
    s = S[skey]
    ev = {"source": src_ev(skey, before, highlight, after), "account": outlet_account(s.outlet)}
    return post(pid, outlet_author(s.outlet), s.published, card_style, ev, source_label=s.label, **kw)


def real(explanation: str, false_alarm: str, suspicious: bool = False) -> dict:
    return {"doctored": False, "suspicious_real": suspicious, "explanation": explanation,
            "con_line_false_alarm": false_alarm}


def fake(trick: str, tell: str, explanation: str, fooled: str, caught: str, diff: dict) -> dict:
    return {"doctored": True, "trick": trick, "tell": tell, "explanation": explanation, "con_line_fooled": fooled,
            "con_line_caught": caught, "diff": diff}


def assemble(cid: str, number: int, date: str, theme: str, title: str, topic: str, briefing: str,
             difficulty: str, items: list[tuple[tuple[dict, dict], dict]], con_line_clean: str | None = None
             ) -> tuple[str, dict, dict, dict, dict]:
    posts, evidence, keys = [], {}, {}
    for (p, ev), ans in items:
        posts.append(p)
        evidence[p["id"]] = ev
        keys[p["id"]] = ans
    doctored = [a for a in keys.values() if a["doctored"]]
    case = {"id": cid, "number": number, "title": title, "topic": topic, "briefing": briefing, "clue_budget": 3,
            "trick_options": ALL_TRICKS, "posts": posts}
    answer_key = {"clean_case": not doctored, "posts": keys, "con_line_clean": con_line_clean}
    urls = []
    for ev in evidence.values():
        for u in ([ev["source"]["url"]] if "source" in ev else []) + ([ev["data"]["url"]] if "data" in ev else []):
            if u not in urls:
                urls.append(u)
    meta = {"status": "approved", "origin": "seed", "daily": False, "difficulty": difficulty,
            "created_at": CREATED_AT, "tricks": sorted({a["trick"] for a in doctored}), "sources": urls,
            "rejection_reason": None, "mode": "daily", "daily_date": date, "theme": theme}
    return cid, case, evidence, answer_key, meta


# ======================================================================================
# The five dailies
# ======================================================================================

def day_science() -> tuple:
    moon_shown = "NASA is looking for astronauts to live and work on Mars"
    dino_shown = "Scientists found ancient remnants of dinosaur blood"
    items = [
        (outlet_post("p1", "npr_mice", "quote", t("MICE_SUMMARY"), t("FALKNER_ARENA"),
                     cat("FALKNER_ROLE", "MICE_NATURE"), body=t("MICE_HEADLINE"),
                     quote={"text": t("FALKNER_ARENA"), "speaker": "Annegret Falkner, Princeton Neuroscience Institute"}),
         real("Sounds like a parody, but it's word for word from NPR. Princeton neuroscientists really staged "
              "'gladiator style' mouse fights, and the paper is in Nature.",
              "Real. Princeton built a mouse colosseum, and I didn't have to invent a thing.", suspicious=True)),
        (post("p2", P_FOSSIL.author(), "2026-11-10T14:05:00Z", "headline",
              {"source": src_ev("npr_dino", "", t("DINO_HEADLINE"), cat("DINO_SUMMARY", "DINO_DOUBT")),
               "account": P_FOSSIL.account()},
              body=f"NPR: \"{dino_shown}\" \U0001F996\U0001FA78 Jurassic Park was a documentary."),
         fake("out-of-context-quote",
              "NPR's headline says scientists think they've found dinosaur blood. Two words were cut, and the doubt "
              "went with them.",
              "The real headline is 'Scientists think they've found ancient remnants of dinosaur blood.' The lead "
              "researcher is 'quietly confident,' and other scientists 'are not as sure.' Delete 'think they've' and "
              "a maybe becomes a fact.",
              "Two words. That was all the doubt there was, and I deleted it.",
              "You noticed the missing 'think.' Scientists would be proud. I'm annoyed.",
              {"type": "quote", "shown": dino_shown, "original": t("DINO_HEADLINE"), "removed": ["think they've"]})),
        (outlet_post("p3", "npr_schooner", "quote", t("ROBINSON_BEFORE"), "ROBINSON: " + t("ROBINSON"),
                     t("ROBINSON_AFTER"), body=t("SCHOONER_HEADLINE"),
                     quote={"text": t("ROBINSON"),
                            "speaker": "David Robinson, Massachusetts Board of Underwater Archaeological Resources"}),
         real("It sounds like a joke someone wrote for him, but it's word for word from NPR. He's an underwater "
              "archaeologist being honest about how hard it is to name a 19th-century wreck from photos.",
              "Real. An expert admitting doubt is a good sign, not a con.", suspicious=True)),
        (post("p4", P_ORBIT.author(), "2026-11-09T13:30:00Z", "headline",
              {"source": src_ev("npr_moon", "", t("MOON_HEADLINE"), f"{t('MOON_LEDE')} {t('MOON_BASE')}"),
               "account": P_ORBIT.account()},
              body=f"{moon_shown} \U0001F680\U0001F534 Who's applying?"),
         fake("edited-detail",
              "NPR's headline says the Moon, not Mars. One place was swapped.",
              "The real story: NASA wants astronauts who 'would also live and work on the moon in a future moon "
              "base.' Swapping one place name turns a real job posting into science fiction, and the old, busy "
              "account makes it look trustworthy.",
              "Same headline, one swapped world. The Moon is so last century.",
              "Fine, it's the Moon. I was aiming higher.",
              {"type": "detail", "shown": moon_shown, "original": t("MOON_HEADLINE"),
               "changed": [{"from": "the Moon", "to": "Mars"}]})),
        (outlet_post("p5", "npr_moon", "stat", t("NASA_CORPS"), t("NASA_8000"), t("NASA_AFTER"),
                     body=t("NASA_8000")),
         real("Word for word from NPR. More than 8,000 people applied for NASA's last astronaut class and 10 were "
              "picked, roughly 1 in 800.",
              "Real. A big number with a clear 'out of' is the honest kind.")),
    ]
    return assemble("2026-11-13-daily-science-says", 3, "2026-11-13", "Science Says", "Lab Coats and Tall Tales",
                    "Weird science news",
                    "Science news. Five posts, 0–3 doctored today. A lab coat makes anything sound true. Or false.",
                    "medium", items)


def day_food(eggs: dict, coffee: dict, beef: dict, butter: dict) -> tuple:
    jun26, oct26, sep25, sep26 = eggs["2026-06"], eggs["2026-10"], eggs["2025-09"], eggs["2026-09"]
    record = max((v, k) for k, v in eggs.items() if k >= "2024-01")
    rise, yoy = pct(jun26, oct26), pct(sep25, sep26)
    assert record == (6.227, "2025-03") and rise == 8.4 and yoy == -34.9, (record, rise, yoy)
    egg_shown = bars("Average price, a dozen eggs", "$/dozen", [(label("2026-06"), jun26), (label("2026-10"), oct26)],
                     y_min=2.1, y_max=2.35)
    egg_honest = bars("Same month, one year apart", "$/dozen", [(label("2025-09"), sep25), (label("2026-09"), sep26)])
    egg_rows = series(eggs, "2024-01", "2026-10")
    egg_data = {"title": "Average price: eggs, grade A, large, per dozen, U.S. city average (BLS, via FRED)",
                "unit": "$/dozen", "url": FRED["eggs"][1], "table": egg_rows,
                "honest_chart": line("Eggs, monthly average price (BLS)", "$/dozen", series(eggs, "2023-01", "2026-10")),
                "note": (f"Record: ${record[0]} in Mar 2025. September to September, a dozen fell from ${sep25} to "
                         f"${sep26} ({yoy}%). BLS published no Oct 2025 value.")}
    # Coffee vs. ground beef: an honest chart from a made-up but careful account.
    c10, b10 = coffee["2026-10"], beef["2026-10"]
    always = all(coffee[m] > beef[m] for m in beef if m >= "2022-01" and m in coffee)
    assert always and (c10, b10) == (9.249, 6.755)
    cb_chart = bars("Average price per pound, Oct 2026", "$/lb", [("Coffee", c10), ("Ground beef", b10)])
    cb_table = ([{"label": f"Coffee {m}", "value": coffee[m]} for m in ("2026-08", "2026-09", "2026-10")]
                + [{"label": f"Ground beef {m}", "value": beef[m]} for m in ("2026-08", "2026-09", "2026-10")])
    cb_data = {"title": "BLS average prices per pound, U.S. city average (via FRED)", "unit": "$/lb",
               "url": FRED["coffee"][1], "table": cb_table, "honest_chart": cb_chart,
               "note": ("Coffee = 100% ground roast; ground beef = 100% beef (FRED series APU0000717311 and "
                        "APU0000703112). Coffee has cost more per pound than ground beef every month since Jan 2022.")}
    bsep25, bsep26 = butter["2025-09"], butter["2026-09"]
    assert pct(bsep25, bsep26) == -17.3 and round(bsep26, 2) == 3.96
    butter_data = {"title": "Average price: butter, stick, per pound, U.S. city average (BLS, via FRED)",
                   "unit": "$/lb", "url": FRED["butter"][1], "table": series(butter, "2025-01", "2026-10"),
                   "honest_chart": line("Butter, monthly average price (BLS)", "$/lb",
                                        series(butter, "2024-01", "2026-10")),
                   "note": f"September to September: ${bsep25} to ${bsep26} a pound ({pct(bsep25, bsep26)}%)."}
    candy_shown = "Prices for candy, the most popular Halloween purchase, and gum are up more than 18%"
    butter_post = outlet_post("p2", "npr_grocery", "stat", "", t("BUTTER"), t("BUTTER_AFTER"), body=t("BUTTER"))
    butter_post[1]["data"] = butter_data
    butter_post[0]["tools"] = ["source", "data", "account"]
    items = [
        (post("p1", P_CLUCK.author(), "2026-11-13T16:40:00Z", "chart",
              {"data": egg_data, "account": P_CLUCK.account()},
              body="Egg prices are SPIKING again \U0001F4C8\U0001F95A Stock up before it's 2025 all over again.",
              chart=egg_shown),
         fake("misleading-chart",
              f"The axis starts at $2.10, so an 18-cent rise looks like a rocket. Last September a dozen cost "
              f"${sep25:.2f}; this September, ${sep26:.2f}. Eggs are down {abs(yoy):.0f}% on the year.",
              f"Real BLS prices, framed to scare. June to October did rise {rise:.0f}%, but the cropped axis makes "
              "the October bar five times taller, and the four-month window hides the fall from the $6.23 record "
              "in March 2025.",
              "Real prices, my axis. I just started it where it hurts.",
              f"You checked the carton. Down {abs(yoy):.0f}% on the year. Fine.",
              {"type": "chart", "shown": egg_shown, "original": egg_honest})),
        (butter_post,
         real(f"Real and word for word from NPR, and BLS data backs it: butter fell from ${bsep25} to ${bsep26} a "
              "pound, September to September. Not everything goes up.",
              "Real. Prices can fall too. Doubting good news is still doubting the truth.", suspicious=True)),
        (post("p3", P_TRICKCHEAT.author(), "2026-10-31T13:15:00Z", "stat",
              {"source": src_ev("npr_candy", t("CANDY_BEFORE"), t("CANDY_STAT"), t("CANDY_AFTER")),
               "account": P_TRICKCHEAT.account()},
              body=f"{candy_shown}. \U0001F383\U0001F631 Federal data. Look it up."),
         fake("cherry-picked-stat",
              "The 18% is over two years. NPR's same sentence says candy rose 7.7% in one year.",
              "The number is real; its time window was dropped. 'Up more than 18%' reads like this year's damage, "
              "but it's two years of increases stacked together. Candy did rise faster than food overall, which is "
              "why the claim feels right.",
              "I didn't change the number. I just lost the 'in two years.'",
              "You read the whole sentence. Most people stop at the scary number.",
              {"type": "stat", "shown": candy_shown, "original": t("CANDY_STAT"),
               "missing": "The time window: the 18% is over two years. Over one year, candy and gum rose 7.7%."})),
        (post("p4", P_AISLE7.author(), "2026-11-13T19:05:00Z", "chart",
              {"data": cb_data, "account": P_AISLE7.account()},
              body=("Grocery math that sounds fake: a pound of ground coffee costs more than a pound of ground beef. "
                    f"BLS average prices, Oct 2026: ${c10} vs. ${b10}."),
              chart=cb_chart),
         real("Real. Both numbers match BLS average prices exactly, the axis starts at zero, and the account cites "
              "its source. Per pound, coffee has out-priced ground beef every month since at least 2022.",
              "Real, and honestly charted. Absurd isn't the same as false.", suspicious=True)),
        (outlet_post("p5", "npr_grocery", "quote", t("VOLPE_BEFORE"), t("VOLPE_PARA"), "",
                     body=t("GROCERY_HEADLINE"),
                     quote={"text": t("VOLPE"), "speaker": "Ricky Volpe, Cal Poly San Luis Obispo"}),
         real("Word for word from NPR. Grocery prices are rising more slowly than in 2022, but on top of a much "
              "higher base.",
              "Real. Not every gloomy quote is a crop.")),
    ]
    return assemble("2026-11-14-daily-food-prices", 4, "2026-11-14", "Food Prices", "Check the Receipt",
                    "Grocery prices",
                    "Food prices. Five posts, 0–3 doctored today. Check the receipt before you swallow anything.",
                    "hard", items)


def day_bills(prices: dict[str, float]) -> tuple:
    apr25, jul25, jul26 = prices["2025-04"], prices["2025-07"], prices["2026-07"]
    shown_pct, yoy = pct(apr25, jul26), pct(jul25, jul26)
    assert (apr25, jul25, jul26, shown_pct, yoy) == (19.91, 25.11, 25.19, 26.5, 0.3)
    shown_chart = bars("NJ residential electricity price", "¢/kWh",
                       [(label("2025-04"), apr25), (label("2026-07"), jul26)], y_min=19, y_max=26)
    honest_bars = bars("Same month, one year apart", "¢/kWh", [(label("2025-07"), jul25), (label("2026-07"), jul26)])
    data_ev = {"title": "NJ residential average electricity price (EIA)", "unit": "¢/kWh", "url": EIA_URL,
               "table": series(prices, "2025-01", max(prices)),
               "honest_chart": line("NJ residential electricity price, monthly (EIA)", "¢/kWh",
                                    series(prices, "2023-01", max(prices))),
               "note": f"Prices jumped in summer 2025. July to July, they went from {jul25} to {jul26}¢ (+{yoy}%)."}
    hs_full = t("HS_QUOTE") + "."
    hs_shown = "…these actions will result in no increase in electricity rates."
    items = [
        (outlet_post("p1", "njm_1112", "headline", "", t("VPP_HEADLINE"), cat("VPP_LEDE", "VPP_EXPLAIN"),
                     body=t("VPP_HEADLINE")),
         real("A 'virtual power plant' sounds invented, but the BPU approved one on Nov 12: smart thermostats, EV "
              "chargers and home batteries cut power use at peak hours, and their owners get paid for it.",
              "Real. 'Virtual power plant' sounds like my work, but the BPU got there first.", suspicious=True)),
        (post("p2", P_BILLWATCH.author(), "2026-11-14T15:20:00Z", "chart",
              {"data": data_ev, "account": P_BILLWATCH.account()},
              body="NJ power prices are up 27% in ONE YEAR. Share before your next bill hits.", chart=shown_chart),
         fake("misleading-chart",
              f"The axis starts at 19¢, and the bars compare April 2025, before the summer spike, with July 2026, "
              f"15 months later. July to July, prices rose {yoy}%.",
              f"Real EIA numbers, framed to mislead. A cropped axis makes a {shown_pct}% gap look like a cliff, and "
              "cherry-picked months turn an old jump into a 'one year' rise. Prices did jump in 2025. Over the past "
              "year they've been nearly flat.",
              "Real numbers, honest-looking bars. I just picked where they start.",
              "Fine. You checked the data. I'll crop it better next time.",
              {"type": "chart", "shown": shown_chart, "original": honest_bars})),
        (post("p3", P_RATERELIEF.author(), "2026-11-13T22:10:00Z", "quote",
              {"source": src_ev("njm_0924", t("NJM_0924_BEFORE"), t("HS_PARA"), f"… {t('ACE_BEFORE')} {t('ACE_PASSAGE')}"),
               "account": P_RATERELIEF.account()},
              body="Your electric rates are frozen. Straight from the BPU president \U0001F447",
              quote={"text": hs_shown, "speaker": "Ben Hertz-Shargel, NJBPU President"}),
         fake("out-of-context-quote",
              "He said 'no NET increase.' Some charges go up and others go down: Atlantic City Electric's bill rises "
              "$4.09 and falls $4.14.",
              "One deleted word changes the promise. 'No net increase' means increases are offset by cuts elsewhere, "
              "not that nothing goes up. The crop also drops the start of the sentence, which ties it to items "
              "voted on earlier that month.",
              "Three letters: n, e, t. That's all I took.",
              "You found the 'net.' I'll have to cut bigger words.",
              {"type": "quote", "shown": hs_shown, "original": hs_full,
               "removed": ["Taken together with the items on the agenda earlier this month,", "net",
                           "and a slight decrease in gas rates"]})),
        (outlet_post("p4", "bpu_0813", "stat", t("BPU_20PCT_BEFORE"), t("BPU_20PCT"), t("BPU_20PCT_AFTER"),
                     body="…" + t("BPU_20PCT")),
         real("Startling, but true: it's straight from the BPU's own press release. Bills jumped in 2025, which is "
              "the rise the doctored chart smuggled into its 'one year' window.",
              "Surprising isn't the same as fake. A grain of salt, not the whole shaker.", suspicious=True)),
        (outlet_post("p5", "njm_1112", "quote", t("REBHORN_BEFORE"), t("REBHORN_PARA"), t("REBHORN_AFTER"),
                     quote={"text": t("REBHORN") + ".", "speaker": "Emma Rebhorn, BPU Commissioner"}),
         real("Real and word for word, from New Jersey Monitor's coverage of the Nov 12 BPU vote. Peak hours drive "
              "prices, which is why the board is paying people to use less power then.",
              "Real. Not everything that sounds dramatic is a trick.")),
    ]
    return assemble("2026-11-15-daily-your-bills", 5, "2026-11-15", "Your Bills", "The Bill Comes Due",
                    "NJ electricity bills",
                    "Your power bill. Five posts, 0–3 doctored today. I never make up a number. I don't have to.",
                    "medium", items)


def day_jersey() -> tuple:
    items = [
        (outlet_post("p1", "nj1015_boss", "quote", f"{t('BOSS_LEDE')} {t('BOSS_GRIEVANCE')}", t("BOSS_QUOTE_PARA"),
                     "", body=t("BOSS_HEADLINE"),
                     quote={"text": t("BOSS_QUOTE") + ".", "speaker": "Bruce Springsteen, at the 2026 MoMA film benefit"}),
         real("Real. New Jersey 101.5 reports Springsteen told a MoMA film benefit that seeing 'Jaws' in 1975 spoiled "
              "night swimming at the Jersey Shore.",
              "Real. The Boss vs. a rubber shark. I couldn't write that.", suspicious=True)),
        (outlet_post("p2", "nj1015_bridge", "headline", "", t("BRIDGE_HEADLINE"), cat("BRIDGE_REPORT", "BRIDGE_SAFE"),
                     body=t("BRIDGE_HEADLINE")),
         real("Real, from New Jersey 101.5 on Nov 12: a cargo ship struck the Tacony-Palmyra Bridge and left it "
              "unable to close. No injuries were reported.",
              "Real. A drawbridge stuck open is very Jersey, and very true.", suspicious=True)),
        (outlet_post("p3", "whyy_victor", "headline", "", t("VICTOR_HEADLINE"), cat("VICTOR_LEDE", "VICTOR_PIANO"),
                     body=t("VICTOR_HEADLINE")),
         real("Real. It's Berlin, New Jersey, a few miles from Camden, where RCA-Victor was born. A Victor Museum "
              "opened there, electric piano that 'sort of works' included.",
              "Real. Berlin is in South Jersey. The headline just let you assume Germany.", suspicious=True)),
        (outlet_post("p4", "nj1015_drivers", "stat", "", t("DRIVERS_STAT"), cat("DRIVERS_AFTER", "DRIVERS_CAVEAT"),
                     body=t("DRIVERS_STAT")),
         real("Real, and the rate comes with its denominator: 56.9 incidents per 1,000 drivers. The columnist even "
              "points out the study is built on insurance-quote data.",
              "Real. I'd never insult Jersey drivers. They'd find me.", suspicious=True)),
        (outlet_post("p5", "nj1015_seals", "quote", "", t("SEALS_PARA"), t("SEALS_AFTER"),
                     body=t("SEALS_HEADLINE"), quote={"text": t("SEALS_QUOTE"), "speaker": "Jon Stewart, on Instagram"}),
         real("Real. New Jersey 101.5 quotes the caption on the seal video Jon Stewart posted, then matches the "
              "spot to the waters near Sandy Hook.",
              "Real. Three exclamation points and still true.")),
    ]
    return assemble("2026-11-16-daily-jersey-weird", 6, "2026-11-16", "Jersey Weird", "Only in Jersey",
                    "New Jersey oddities",
                    "Jersey weirdness. Five posts, 0–3 doctored today. Some of this can't possibly be true. Can it?",
                    "easy", items,
                    con_line_clean="Nothing doctored today. Jersey did all the work. All you had to do was believe it.")


def day_strange() -> tuple:
    lib_shown = "Overdue library magazine returned after 32 years"
    items = [
        (outlet_post("p1", "npr_socks", "headline", "", t("SOCKS_HEADLINE"), cat("SOCKS_SUMMARY", "SOCKS_FLIES"),
                     body=t("SOCKS_HEADLINE")),
         real("Real. Arsenal sent dozens of used match socks to a horse and donkey sanctuary in England, where they "
              "protect the animals' legs from biting flies.",
              "Real. Donkeys in Arsenal socks. I have limits. Reality doesn't.", suspicious=True)),
        (post("p2", P_SHELF.author(), "2026-09-20T15:00:00Z", "headline",
              {"source": src_ev("npr_library", "", t("LIBRARY_HEADLINE"), cat("LIBRARY_SUMMARY", "LIBRARY_1894")),
               "account": P_SHELF.account()},
              body=f"{lib_shown} \U0001F4DA Imagine the late fees."),
         fake("edited-detail",
              "NPR's headline says 132 years. The magazine was published in 1894.",
              "This fake made the story less weird. The real magazine, from 1894, came back about 132 years overdue "
              "after a New Hampshire library announced a fine freeze. A believable number is still a wrong number.",
              "I knocked a century off and you relaxed. Plausible is my favorite disguise.",
              "132 years. You checked. The truth was weirder than my lie.",
              {"type": "detail", "shown": lib_shown, "original": t("LIBRARY_HEADLINE"),
               "changed": [{"from": "132", "to": "32"}]})),
        (outlet_post("p3", "npr_camel", "headline", "", t("CAMEL_HEADLINE"), cat("CAMEL_SUMMARY", "CAMEL_KICKER"),
                     body=t("CAMEL_HEADLINE")),
         real("Real. In the 1950s a Nevada newspaper editor wrote a joke story about a camel race. A few years later "
              "the race really happened, and it still runs every year: fake news that came true.",
              "Real, and it's my origin story: a fake headline so good it came true.", suspicious=True)),
        (outlet_post("p4", "npr_marathon", "stat", t("MARATHON_BEFORE"), t("MARATHON_STAT"), t("MARATHON_AFTER"),
                     body=t("MARATHON_STAT")),
         real("Word for word from NPR's New York City Marathon story: just over 2,000 runners in 1976, about 60,000 "
              "this year.",
              "Real. 88 women in 1976, nearly half of 60,000 now. Some numbers just grow.")),
        (outlet_post("p5", "npr_mice", "quote", t("FALKNER_NFL_BEFORE"), "FALKNER: " + t("FALKNER_NFL"),
                     t("FALKNER_NFL_AFTER"), body=t("FALKNER_NFL_BEFORE"),
                     quote={"text": t("FALKNER_NFL"), "speaker": "Annegret Falkner, Princeton Neuroscience Institute"}),
         real("Real and word for word from NPR. Read all of it: she isn't saying watching makes you a pro, just that "
              "watching beats never watching.",
              "Real. Watching sports counts as practice now. You're welcome, couch.", suspicious=True)),
    ]
    return assemble("2026-11-17-daily-strange-but-true", 7, "2026-11-17", "Strange But True", "Stranger Than Fiction",
                    "Odd news",
                    "Odd news. Five posts, 0–3 doctored today. The truth is weird. I'm only slightly weirder.",
                    "medium", items)


# ======================================================================================
# Fool Deck (CONTRACT §7.1): real, unedited items the player may doctor in Con the Con
# ======================================================================================

def deck_item(did: str, kind: str, pe: tuple[dict, dict], tools: list[str], *, quote_words=None,
              chart_series=None, stat=None) -> dict:
    p, ev = pe
    return {"id": did, "kind": kind, "post": p, "evidence": ev,
            "editable": {"quote_words": quote_words, "chart_series": chart_series, "stat": stat}, "tools": tools}


def quote_deck(did: str, skey: str, quote_key: str, para_key: str, speaker: str, before: str, after: str,
               body: str = "") -> dict:
    text = t(quote_key) if t(quote_key).endswith((".", "?", "!")) else t(quote_key) + "."
    pe = outlet_post("p1", skey, "quote", before, t(para_key) if para_key in BANK else para_key, after, body=body,
                     quote={"text": text, "speaker": speaker})
    return deck_item(did, "quote", pe, ["crop"], quote_words=text.split())


# Deck charts are drawn by us from public data, and the caption is ours, so the poster must NOT be the
# agency (that would put our words in EIA's/BLS's mouth). A made-up data account posts them and cites the source.
DATA_DESK_AUTHOR = {"name": "Chart Desk", "handle": "@chartdesk", "kind": "person", "verified": False,
                    "avatar_color": "#64748B"}
DATA_DESK_ACCOUNT = {"name": "Chart Desk", "handle": "@chartdesk", "created": "June 2021", "followers": 4200,
                     "verified": False, "bio": "Charts from public data. The source is in every post.",
                     "recent_posts": ["New federal price data is out. Chart below.", "Axis from zero, always."]}


def chart_deck(did: str, data_source: str, rows: list[dict], title: str, unit: str, data_title: str, url: str,
               note: str, body: str, source_label: str) -> dict:
    chart = line(title, unit, rows)
    ev = {"data": {"title": data_title, "unit": unit, "url": url, "table": rows, "honest_chart": chart, "note": note},
          "account": DATA_DESK_ACCOUNT}
    pe = post("p1", DATA_DESK_AUTHOR, CREATED_AT, "chart", ev, body=body, chart=chart,
              source_label=f"Data: {source_label} ({data_source})")
    return deck_item(did, "chart", pe, ["axis", "window"], chart_series=rows)


def build_deck(prices: dict, eggs: dict, coffee: dict) -> list[dict]:
    deck = [
        quote_deck("hs-net-increase", "njm_0924", "HS_QUOTE", "HS_PARA", "Ben Hertz-Shargel, NJBPU President",
                   t("NJM_0924_BEFORE"), f"… {t('ACE_BEFORE')} {t('ACE_PASSAGE')}", body=t("NJM_0924_DESC")),
        quote_deck("rebhorn-peak-hours", "njm_1112", "REBHORN", "REBHORN_PARA", "Emma Rebhorn, BPU Commissioner",
                   t("REBHORN_BEFORE"), t("REBHORN_AFTER")),
        quote_deck("falkner-watching-sports", "npr_mice", "FALKNER_NFL", "FALKNER: " + t("FALKNER_NFL"),
                   "Annegret Falkner, Princeton Neuroscience Institute", t("FALKNER_NFL_BEFORE"),
                   t("FALKNER_NFL_AFTER"), body=t("MICE_HEADLINE")),
    ]
    ace = outlet_post("p1", "njm_0924", "stat", t("ACE_BEFORE"), t("ACE_PASSAGE"), "", body=t("ACE_PASSAGE"))
    deck.append(deck_item("ace-offset", "stat", ace, ["drop"], stat={
        "full": t("ACE_PASSAGE"),
        "droppable": [{"id": "offset", "text": t("ACE_FALL"), "shown_without": t("ACE_RISE")}]}))
    candy = outlet_post("p1", "npr_candy", "stat", t("CANDY_BEFORE"), t("CANDY_STAT"), t("CANDY_AFTER"),
                        body=t("CANDY_STAT"))
    deck.append(deck_item("candy-two-years", "stat", candy, ["drop"], stat={
        "full": t("CANDY_STAT"),
        "droppable": [
            {"id": "window", "text": "have risen 7.7% in one year and … in two years",
             "shown_without": "Prices for candy, the most popular Halloween purchase, and gum are up more than 18%, "
                              "according to the latest federal data."},
            {"id": "one_year", "text": "have risen 7.7% in one year and",
             "shown_without": "Prices for candy, the most popular Halloween purchase, and gum are up more than 18% in "
                              "two years, according to the latest federal data."}]}))
    jul25, jul26 = prices["2025-07"], prices["2026-07"]
    deck.append(chart_deck(
        "eia-nj-power", "U.S. Energy Information Administration", series(prices, "2025-01", max(prices)),
        "NJ residential electricity price, monthly", "¢/kWh", "NJ residential average electricity price (EIA)",
        EIA_URL, f"Summer 2025 spiked. July to July: {jul25} to {jul26}¢ (+{pct(jul25, jul26)}%).",
        "New Jersey residential electricity price by month, Jan 2025 to Aug 2026.", "EIA electricity data browser"))
    deck.append(chart_deck(
        "eggs-dozen", "U.S. Bureau of Labor Statistics", series(eggs, "2024-01", "2026-10"),
        "Eggs, average price per dozen", "$/dozen",
        "Average price: eggs, grade A, large, per dozen, U.S. city average (BLS, via FRED)", FRED["eggs"][1],
        f"Record ${eggs['2025-03']} in Mar 2025; ${eggs['2026-10']} in Oct 2026. No Oct 2025 value was published.",
        "U.S. average price of a dozen grade A large eggs, Jan 2024 to Oct 2026.", "BLS average price data · FRED"))
    deck.append(chart_deck(
        "coffee-pound", "U.S. Bureau of Labor Statistics", series(coffee, "2024-01", "2026-10"),
        "Ground coffee, average price per pound", "$/lb",
        "Average price: coffee, 100% ground roast, per pound, U.S. city average (BLS, via FRED)", FRED["coffee"][1],
        f"${coffee['2024-01']} in Jan 2024; peak ${max(coffee[m] for m in coffee if m >= '2024-01')} in Apr 2026.",
        "U.S. average price of a pound of 100% ground roast coffee, Jan 2024 to Oct 2026.",
        "BLS average price data · FRED"))
    return deck


# ======================================================================================
# Offline self-checks
# ======================================================================================

def words(s: str) -> list[str]:
    return [w for w in (re.sub(r"[^\w$%.,'-]", "", x).strip(".,") for x in normalize(s).split()) if w]


def is_deletion(shown: str, original: str) -> bool:
    """True if every word of `shown` appears in `original`, in order (deletion-only edit)."""
    it = iter(words(original))
    return all(any(w == o for o in it) for w in words(shown))


def check_chart(c: dict, where: str) -> None:
    vals = [p["value"] for p in c["points"]]
    assert len(vals) >= 2, where
    assert all(v >= c["y_min"] for v in vals), f"{where}: y_min cuts off data"
    assert c["y_max"] is None or c["y_max"] > max(vals), f"{where}: y_max cuts off data"


def check_post(p: dict, ev: dict, where: str) -> None:
    assert re.fullmatch(r"p\d+", p["id"]) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", p["posted_at"]), where
    assert p["card_style"] in ("headline", "quote", "chart", "stat"), where
    assert p["tools"] == [k for k in ("source", "data", "account") if k in ev], f"{where}: tools vs evidence"
    assert ev["account"]["name"] == p["author"]["name"], f"{where}: account card name"
    assert p["body"].strip() or p["quote"] or p["chart"], f"{where}: empty post"
    if p["chart"]:
        check_chart(p["chart"], where)
    if "data" in ev:
        check_chart(ev["data"]["honest_chart"], where + " honest_chart")
        if p["chart"]:
            table = {r["label"]: r["value"] for r in ev["data"]["table"]}
            for pt in p["chart"]["points"]:
                assert pt["value"] in table.values(), f"{where}: chart value {pt} not in data table"


def check_case(cid: str, case: dict, evidence: dict, key: dict, meta: dict) -> None:
    posts = case["posts"]
    assert len(posts) == 5 and case["clue_budget"] == 3, cid
    assert "0–3 doctored today" in case["briefing"], cid
    assert {p["id"] for p in posts} == set(evidence) == set(key["posts"]), cid
    doctored = [pid for pid, a in key["posts"].items() if a["doctored"]]
    assert 0 <= len(doctored) <= 3 and key["clean_case"] == (not doctored), cid
    assert any(a.get("suspicious_real") for a in key["posts"].values()), f"{cid}: needs a real-but-suspicious post"
    assert len({p["card_style"] for p in posts}) >= 2, f"{cid}: vary card_style"
    assert (key["con_line_clean"] is not None) == key["clean_case"], cid
    assert meta["tricks"] == sorted({key["posts"][d]["trick"] for d in doctored}), cid
    for p in posts:
        ev, a, where = evidence[p["id"]], key["posts"][p["id"]], f"{cid}/{p['id']}"
        check_post(p, ev, where)
        if not a["doctored"]:
            assert a["explanation"] and a["con_line_false_alarm"], where
            continue
        assert p["author"]["kind"] == "person" and not p["author"]["verified"], f"{where}: fakes need made-up authors"
        assert p["author"]["name"] not in OUTLETS, where
        d = a["diff"]
        assert d["type"] == {"out-of-context-quote": "quote", "misleading-chart": "chart",
                             "cherry-picked-stat": "stat", "edited-detail": "detail"}[a["trick"]], where
        if d["type"] == "quote":
            assert is_deletion(d["shown"], d["original"]), f"{where}: crop must only delete words"
            assert normalize(d["shown"]).strip("….") in normalize(p["body"] + " " + (p["quote"] or {}).get("text", "")), where
            assert normalize(d["original"]).rstrip(".") in normalize(json.dumps(ev["source"], ensure_ascii=False)), where
        elif d["type"] == "detail":
            orig = d["original"]
            for ch in d["changed"]:
                assert ch["from"] in orig, where
                orig = orig.replace(ch["from"], ch["to"], 1)
            assert orig == d["shown"] and d["shown"] in p["body"], f"{where}: detail swap mismatch"
            assert d["original"] in ev["source"]["highlight"], f"{where}: source must show the real headline"
        elif d["type"] == "stat":
            assert is_deletion(d["shown"], d["original"]), f"{where}: stat may only drop context"
            assert d["shown"] in p["body"], where
            assert normalize(d["original"]) in normalize(ev["source"]["highlight"]), where
        elif d["type"] == "chart":
            check_chart(d["shown"], where + " diff.shown")
            check_chart(d["original"], where + " diff.original")
            assert d["shown"] == p["chart"], where


def check_deck(deck: list[dict]) -> None:
    assert 6 <= len(deck) <= 8 and len({d["id"] for d in deck}) == len(deck)
    for d in deck:
        p, ev, ed, where = d["post"], d["evidence"], d["editable"], f"deck/{d['id']}"
        check_post(p, ev, where)
        if d["kind"] == "chart":
            # charts are drawn by us from public data with our caption: posted by the made-up data account
            assert p["author"] == DATA_DESK_AUTHOR and ev["account"] == DATA_DESK_ACCOUNT, where
        else:
            # quotes and stats are verbatim outlet text: posted by the real outlet
            assert p["author"]["kind"] in ("outlet", "official") and p["author"]["verified"], where
        if d["kind"] == "quote":
            assert d["tools"] == ["crop"] and " ".join(ed["quote_words"]) == p["quote"]["text"], where
            assert normalize(p["quote"]["text"]).rstrip(".") in normalize(ev["source"]["highlight"]), where
        elif d["kind"] == "chart":
            assert d["tools"] == ["axis", "window"] and ed["chart_series"] == ev["data"]["table"], where
            assert [x["value"] for x in ed["chart_series"]] == [x["value"] for x in p["chart"]["points"]], where
        else:
            assert d["tools"] == ["drop"] and ed["stat"]["full"] == p["body"], where
            for dr in ed["stat"]["droppable"]:
                assert is_deletion(dr["shown_without"], ed["stat"]["full"]), f"{where}/{dr['id']}: drop must delete"


# ======================================================================================
# Live verification (--verify): re-fetch each source and check every bank excerpt
# ======================================================================================

_MAP = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", "\xa0": " "}


def normalize(s: str) -> str:
    s = "".join(_MAP.get(ch, ch) for ch in unicodedata.normalize("NFKC", s))
    return re.sub(r"\s+", " ", s).strip()


def squash(s: str) -> str:
    return re.sub(r"\s+", "", normalize(s))


def page_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", raw)
    return html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))


def verify() -> bool:
    ok = True
    by_src: dict[str, list[str]] = {}
    for k, (skey, _) in BANK.items():
        by_src.setdefault(skey, []).append(k)
    for skey, keys in by_src.items():
        url = S[skey].url
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; grain-of-salt-verify)"})
            body = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"  ?? {skey}: could not fetch ({e})")
            ok = False
            continue
        text = squash(page_text(body))
        missing = [k for k in keys if squash(t(k)) not in text]
        print(f"  {'ok' if not missing else 'XX'} {skey}: {len(keys) - len(missing)}/{len(keys)} excerpts verbatim"
              + (f"; missing {missing}" if missing else ""))
        ok &= not missing
    for name, (fname, page, title) in FRED.items():
        csv_url = page.replace("/series/", "/graph/fredgraph.csv?id=")
        try:
            live = urllib.request.urlopen(csv_url, timeout=45).read().decode("utf-8")
        except Exception as e:  # noqa: BLE001
            print(f"  ?? FRED {name}: could not fetch ({e})")
            ok = False
            continue
        local = (SOURCES / fname).read_text(encoding="utf-8")
        same = local.strip().splitlines()[:-1] == live.strip().splitlines()[:len(local.strip().splitlines()) - 1]
        print(f"  {'ok' if same else 'XX'} FRED {name}: local CSV {'matches' if same else 'DIFFERS FROM'} live data")
        ok &= same
    return ok


# ======================================================================================

def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    prices = load_eia()
    eggs, coffee, beef, butter = (load_fred(n) for n in ("eggs", "coffee", "beef", "butter"))
    days = [day_science(), day_food(eggs, coffee, beef, butter), day_bills(prices), day_jersey(), day_strange()]
    deck = build_deck(prices, eggs, coffee)
    for cid, case, ev, key, meta in days:
        check_case(cid, case, ev, key, meta)
    check_deck(deck)
    for cid, case, ev, key, meta in days:
        for name, obj in [("case.json", case), ("evidence.json", ev), ("answer_key.json", key), ("meta.json", meta)]:
            write_json(CASES / cid / name, obj)
        n = sum(a["doctored"] for a in key["posts"].values())
        print(f"wrote data/cases/{cid}  ({meta['theme']}, {n} doctored)")
    for d in deck:
        write_json(DECK / f"{d['id']}.json", d)
    print(f"wrote data/fool_deck/ ({len(deck)} items)")
    if "--verify" in sys.argv:
        print("verifying sources live:")
        if not verify():
            print("VERIFY FAILED: re-check the items marked XX/?? before shipping.")
            return 1
        print("all sources verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())

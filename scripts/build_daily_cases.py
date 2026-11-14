"""Build the v2 Daily Grain cases (2026-11-13 .. 2026-11-17) and the Con-the-Con Fool Deck.

Everything is assembled from the verified material bank below (BANK). Each excerpt was copied word for word
from a page or feed fetched on 2026-11-14, and is listed with its URL in CONTENT_SOURCES.md. Numbers come from
files in data/sources/ (EIA API v2 JSON; FRED CSVs of BLS average prices). The script never invents a quote:
doctored posts are built only by the allowed operations on bank text (crop = delete words, edited-detail = swap
one number/date/place in a real headline, cherry-picked stat = drop context, misleading chart = axis/window on
real data), and they are always posted by made-up accounts (author.kind "person").

Sunday 2026-11-15 (judging day) is the "HackPrinceton Special". So that the poster never gives the answer away,
every day also has at least one REAL post from a made-up account (a verbatim excerpt or exact public numbers,
with a correct source_label), and the fakes don't share one voice.

Run:
  uv run python scripts/build_daily_cases.py            # write data/cases/<daily ids>/ and data/fool_deck/*.json
  uv run python scripts/build_daily_cases.py --verify   # also re-fetch every source URL and confirm each
                                                       # excerpt is still on the page (needs network)

The script also runs offline self-checks (deletion-only crops, detail swaps, honest chart diffs whose months the
tell names, axis/data consistency, tools vs. evidence, 0-3 doctored per day, a real made-up-account post per day,
excerpt length, ellipsis fairness, the case notice, ...) and refuses to write anything if one fails.
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
# Case-level notice (CONTRACT §2.1 extra field). Same text on every case, clean or not, so it reveals nothing.
NOTICE = "Game content: the Con doctors some posts on purpose. Every doctored post is stamped at the reveal."
# Earlier builds of this script wrote these folders; they are removed so no stale daily is served.
STALE_CASE_DIRS = ["2026-11-15-daily-your-bills"]


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
    # NPR story as published by member station Texas Public Radio (byline "NPR | By Ari Daniel"; the page shows
    # "Published September 22, 2026 at 11:17 AM CDT", used as posted_at).
    "tpr_amoeba": Src("Texas Public Radio", "2026-09-22", "2026-09-22T16:17:00Z",
                      "https://www.tpr.org/2026-09-22/"
                      "this-fire-amoeba-pushes-the-limit-of-whats-possible-for-complex-life",
                      "NPR via Texas Public Radio · Sept 22, 2026"),
    # Associated Press story as published by OPB (we never fetch apnews.com, which refuses scripted fetching).
    "opb_owls": Src("OPB", "2026-10-16", "2026-10-16T19:40:07Z",
                    "https://www.opb.org/article/2026/10/16/"
                    "a-rare-family-of-barn-owls-moved-into-manhattan-captivating-new-yorkers/",
                    "OPB (AP) · Oct 16, 2026"),
    "nj1015_boss": Src("New Jersey 101.5", "2026-11-13", "2026-11-13T21:08:49Z",
                       "https://nj1015.com/bruce-springsteen-jaws-grievance/", "New Jersey 101.5 · Nov 13, 2026"),
    "nj1015_seals": Src("New Jersey 101.5", "2026-11-12", "2026-11-12T14:56:26Z",
                        "https://nj1015.com/ixp/393/p/jon-stewart-seals/", "New Jersey 101.5 · Nov 12, 2026"),
    "nj1015_drivers": Src("New Jersey 101.5", "2026-11-13", "2026-11-14T00:43:04Z",
                          "https://nj1015.com/new-jersey-worst-drivers-2/", "New Jersey 101.5 · Nov 13, 2026"),
    "whyy_victor": Src("WHYY", "2026-11-02", "2026-11-02T10:00:04Z",
                       "https://whyy.org/articles/new-jersey-music-recording-camden-rca-victor/", "WHYY · Nov 2, 2026"),
    # Associated Press story as published by WHYY.
    "whyy_microbe": Src("WHYY", "2019-05-11", "2019-05-11T18:00:18Z",
                        "https://whyy.org/articles/new-jersey-gets-official-state-microbe-streptomyces-griseus/",
                        "WHYY (AP) · May 11, 2019"),
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
    "DINO_DOUBT": ("npr_dino", "GRICE: So I'm quietly confident that these may be red blood cells. ROTT: Other "
                               "scientists are not as sure."),
    # --- NPR, Nov 8, 2026: NASA astronauts ---
    "MOON_HEADLINE": ("npr_moon", "NASA is looking for astronauts to live and work on the Moon"),
    "MOON_BASE": ("npr_moon", "The candidates selected to be astronauts would not only test spacecraft but would also "
                              "live and work on the moon in a future moon base, said NASA Administrator Jared Isaacman "
                              "in a statement released on Saturday."),
    "NASA_CORPS": ("npr_moon", "There are currently 32 active astronauts in NASA's astronaut corps. Since NASA "
                               "missions began in the 1960s, the agency has selected 370 people to train as "
                               "astronauts, according to the agency."),
    "NASA_8000": ("npr_moon", "The applicant process is extremely competitive. Out of more than 8,000 applicants for "
                              "NASA's last astronaut class, only 10 candidates were selected."),
    "NASA_ODDS": ("npr_moon", "Out of more than 8,000 applicants for NASA's last astronaut class, only 10 candidates "
                              "were selected."),
    "NASA_AFTER": ("npr_moon", "While any U.S. citizen can apply and there is no official age restriction, applicants "
                               "will need to have a master's degree in a STEM-related field such as engineering or "
                               "math."),
    # --- NPR, Sept 29, 2026: Nantucket schooner ---
    "SCHOONER_HEADLINE": ("npr_schooner", "Nor'easter exposes part of a schooner wrecked on Nantucket"),
    "ROBINSON_WRECK": ("npr_schooner", "Part of the Warren Sawyer wreck was exposed back in 2022, and based on what "
                                       "he's seen in photos and on video, he says the new Nantucket wreckage could be "
                                       "more of that schooner. Keywords there, could be."),
    "ROBINSON": ("npr_schooner", "Well, I can with 100% confidence tell you that I wouldn't be 100% confident."),
    "ROBINSON_AFTER": ("npr_schooner", "And that's because the way that the Warren Sawyer was built, lots of ships were "
                                       "built like that."),
    # --- NPR, Oct 20, 2026: five grocery items ---
    "GROCERY_HEADLINE": ("npr_grocery", "Why these 5 everyday items fluctuate in price at the grocery store"),
    "BEEF_RISE": ("npr_grocery", "The cost of ground beef has been on the rise for years, largely due to weather and "
                                 "financial pressures on producers."),
    "BEEF_STAT": ("npr_grocery", "A typical pound of ground beef last month cost $6.79, an 85% jump from a decade "
                                 "earlier, according to the Bureau of Labor Statistics."),
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
    # --- NPR, Nov 1, 2026: NYC Marathon ---
    "MARATHON_BEFORE": ("npr_marathon", "It was the 50th time that the race has run through all five boroughs of the "
                                        "city."),
    "MARATHON_STAT": ("npr_marathon", "There were just over 2,000 competitors in 1976, the seventh running of the "
                                      "race, including only 88 women. About 60,000 runners stepped up to the starting "
                                      "line Sunday, with nearly half of them women."),
    "MARATHON_1976": ("npr_marathon", "There were just over 2,000 competitors in 1976, the seventh running of the "
                                      "race, including only 88 women."),
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
    "SEALS_HEADLINE": ("nj1015_seals", "Jon Stewart Heralds the Return of the Sandy Hook Seals"),
    "SEALS_QUOTE": ("nj1015_seals", "New pal alert!! Jersey Shore Novembers!!!"),
    "SEALS_PARA": ("nj1015_seals", "Comedian and New Jersey native Jon Stewart shared a video on Instagram Wednesday "
                                   "night showing a seal bobbing above water and the caption, \"New pal alert!! Jersey "
                                   "Shore Novembers!!!\" Commenters quickly flocked to offer their opinions on where "
                                   "the clip may be shot."),
    "SEALS_AFTER": ("nj1015_seals", "Clearly, Jon Stewart spotted one of the Sandy Hook seals, and we can head back "
                                    "home for Thanksgiving with joy in our hearts."),
    "DRIVERS_RANK": ("nj1015_drivers", "A new study from LendingTree ranks New Jersey number one for the worst drivers "
                                       "in the country."),
    "DRIVERS_RATE": ("nj1015_drivers", "According to the study, New Jersey drivers recorded 56.9 driving incidents per "
                                       "1,000 drivers through August 2026."),
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
    # --- WHYY (Associated Press), May 11, 2019: state microbe. The page's "discovered ... in 1916" line is left
    # out on purpose (the discovery history is disputed). ---
    "MICROBE_HEADLINE": ("whyy_microbe", "New Jersey gets official state microbe: Streptomyces griseus"),
    "MICROBE_LEDE": ("whyy_microbe", "A microorganism that played a role in treating tuberculosis is now officially "
                                     "recognized as New Jersey's state microbe."),
    "MICROBE_SIGNED": ("whyy_microbe", "Gov. Phil Murphy signed a bill Friday giving the distinction to Streptomyces "
                                       "griseus."),
    # --- NPR via Texas Public Radio, Sept 22, 2026: fire amoeba ---
    "AMOEBA_HEADLINE": ("tpr_amoeba", "This 'fire amoeba' pushes the limit of what's possible for complex life"),
    "AMOEBA_LEDE": ("tpr_amoeba", "Introducing Incendiamoeba cascadensis, which translates to \"fire amoeba of the "
                                  "Cascade mountain range.\" This single-celled organism can replicate at temperatures "
                                  "up to 145°F, a new record for a complex organism."),
    # --- OPB (Associated Press), Oct 16, 2026: barn owls. Residents named in the story are left out. ---
    "OWLS_HEADLINE": ("opb_owls", "A rare family of barn owls moved into Manhattan's Upper West Side. New Yorkers are "
                                  "captivated"),
    "OWLS_LEDE": ("opb_owls", "Manhattan's Upper West Side has been reveling in the company of its latest celebrities: "
                              "A family of barn owls nested in a water tower atop a building near Central Park."),
    "OWLS_FIRST": ("opb_owls", "This is the first documented instance of barn owls nesting in Manhattan in modern "
                               "history, according to one expert, and the owls have attracted nightly crowds of "
                               "people in the street eager to get a glimpse of the elusive birds."),
}
HEADLINE_KEYS = {k for k in BANK if k.endswith("_HEADLINE")}


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
    "Texas Public Radio": ("@TPRNews", "outlet", "#B45309", "Public radio · tpr.org"),
    "OPB": ("@OPB", "outlet", "#0369A1", "Public media · opb.org"),
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


# Account age, follower count and voice are deliberately mixed between fakes and real posts, so none of them
# gives the answer away. Names are invented handles, never realistic personal names.
# --- accounts that post doctored cards ---
P_BILLWATCH = Persona("Jersey Bill Watch", "@jerseybills", "#E3A42B", "October 2026", 1840,     # alarmist
                      "Exposing what they don't want you to know about your bills.",
                      ("Your utility bill is a SCAM. Thread \U0001F9F5", "Share before they delete this!"))
P_CHECKOUT = Persona("Checkout Lane", "@checkoutlane", "#475569", "February 2020", 15300,       # plain, newsy
                     "Grocery news, no fluff. 🛒",
                     ("Unit price beats sticker price. Every time.", "This week's store-brand swaps 🧵"))
P_FOSSIL = Persona("Fossil Fever", "@fossilfever", "#EA580C", "September 2026", 2310,           # jokey
                   "Dinosaurs, daily. Mostly vibes. \U0001F996",
                   ("T. rex could outrun your car. Probably.", "Like if you'd ride a raptor \U0001F996"))
P_ORBIT = Persona("Orbit Daily", "@orbitdaily_", "#4F46E5", "June 2019", 48200,                 # calm, established
                  "Space news, fast. Launch alerts and sky-watching tips.",
                  ("Starship update thread \U0001F9F5", "Moon, Venus and Spica tonight. Look up!"))
P_CLUCK = Persona("Cluck Report", "@cluckreport", "#DB2777", "October 2026", 912,                # alarmist
                  "Exposing Big Egg. \U0001F95A",
                  ("They don't want you to know what's in the carton.", "Share before the price goes up again!"))
P_SPOOKY = Persona("Spooky Budget", "@spookybudget", "#7C2D12", "August 2023", 6300,             # calm, practical
                   "Holiday shopping on a budget. Lists, deals, receipts. \U0001F383",
                   ("Costumes under $20: a thread \U0001F9F5", "Buy the candy on Nov 1. Trust me."))
P_SHELF = Persona("Shelf Life", "@shelflifereads", "#8B5CF6", "April 2021", 12800,              # cozy
                  "Book news & library lore \U0001F4DA",
                  ("Your library card is a superpower.", "Name a book you never returned. I'll wait."))
P_FINISH = Persona("Finish Line Feed", "@finishlinefeed", "#0F766E", "March 2020", 9700,         # trivia
                   "Running trivia and race-day numbers. \U0001F3C3",
                   ("Marathon pace math: a thread \U0001F9F5", "What's your race-day breakfast?"))
# --- accounts that post REAL cards (verbatim excerpts or exact public numbers, with a correct source_label) ---
P_LAUNCHPAD = Persona("Launch Pad Lounge", "@launchpadlounge", "#9333EA", "August 2026", 2900,   # hype
                      "Space hype. All caps. Zero chill. \U0001F680",
                      ("THE MOON IS SO BACK \U0001F315", "Rate tonight's launch 1-10 \U0001F680"))
P_GRILL = Persona("Grill Sergeant", "@grillsergeant", "#B91C1C", "July 2026", 1150,             # hype
                  "Burgers, briskets and loud opinions. \U0001F525",
                  ("Ketchup on a hot dog? Absolutely not.", "Who's grilling this weekend? \U0001F525"))
P_BREW = Persona("Brew Ha-Ha", "@brewhaha_daily", "#92400E", "October 2026", 310,                # hype, brand new
                 "Coffee facts that sound fake. \u2615",
                 ("Rate my latte art. Be gentle. \u2615", "Coffee math thread tonight \U0001F9F5"))
P_JUGHANDLE = Persona("Jughandle Jury", "@jughandlejury", "#CA8A04", "September 2026", 780,      # sassy
                      "Jersey roads, judged. \U0001F697",
                      ("Left turn from the right lane. Only in Jersey.", "Rate your commute 1-10. Mine's a 2."))
P_COUCH = Persona("Couch Coach", "@couchcoach_", "#2563EB", "January 2022", 5400,               # playful
                  "Sports takes from the sofa. \U0001F6CB\ufe0f\U0001F3C8",
                  ("Fantasy lineup locked. Snacks loaded.", "Halftime is a sport."))


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


def made_up(pid: str, who: Persona, posted_at: str, card_style: str, ev: dict, **kw) -> tuple[dict, dict]:
    """A post from a made-up account (real or doctored). `ev` holds source and/or data; the account card is added."""
    return post(pid, who.author(), posted_at, card_style, dict(ev, account=who.account()), **kw)


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
    case = {"id": cid, "number": number, "title": title, "topic": topic, "briefing": briefing, "notice": NOTICE,
            "clue_budget": 3, "trick_options": ALL_TRICKS, "posts": posts}
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
        (outlet_post("p1", "tpr_amoeba", "headline", "", t("AMOEBA_HEADLINE"), t("AMOEBA_LEDE"),
                     body=t("AMOEBA_HEADLINE")),
         real("Real, word for word from NPR's story as published by Texas Public Radio. Researchers named it "
              "Incendiamoeba cascadensis, the 'fire amoeba,' and it can replicate at up to 145°F, a new record for a "
              "complex organism.",
              "Real. A blob that thrives at 145°F. I couldn't invent that, and I'd love the credit.", suspicious=True)),
        (made_up("p2", P_FOSSIL, "2026-11-10T14:05:00Z", "headline",
                 {"source": src_ev("npr_dino", "", t("DINO_HEADLINE"), t("DINO_DOUBT"))},
                 body=f"NPR: \"{dino_shown}\" \U0001F996\U0001FA78 Jurassic Park was a documentary.",
                 source_label=S["npr_dino"].label),
         fake("out-of-context-quote",
              "NPR's headline says scientists think they've found dinosaur blood. Two words were cut, and the doubt "
              "went with them.",
              "The real headline is 'Scientists think they've found ancient remnants of dinosaur blood.' In the "
              "story, the lead researcher is 'quietly confident' and other scientists 'are not as sure.' Delete "
              "'think they've' and a maybe becomes a fact.",
              "Two words. I deleted 'think they've' and kept the dinosaur. I'm framing this.",
              "You noticed 'think they've' was gone, and the doubt with it. Scientists would be proud. "
              "I'm merely impressed.",
              {"type": "quote", "shown": dino_shown, "original": t("DINO_HEADLINE"), "removed": ["think they've"]})),
        (outlet_post("p3", "npr_schooner", "quote", t("ROBINSON_WRECK"), "ROBINSON: " + t("ROBINSON"),
                     t("ROBINSON_AFTER"), body=t("SCHOONER_HEADLINE"),
                     quote={"text": t("ROBINSON"),
                            "speaker": "David Robinson, Massachusetts Board of Underwater Archaeological Resources"}),
         real("It sounds like a line someone wrote for him, but it's word for word from NPR. He's an underwater "
              "archaeologist being honest about how hard it is to identify a wreck from photos and video.",
              "Real. An expert admitting doubt is the opposite of my whole act. Get your own material.",
              suspicious=True)),
        (made_up("p4", P_ORBIT, "2026-11-09T13:30:00Z", "headline",
                 {"source": src_ev("npr_moon", "", t("MOON_HEADLINE"), t("MOON_BASE"))},
                 body=f"{moon_shown} \U0001F680\U0001F534 Applications are open. Who's in?",
                 source_label=S["npr_moon"].label),
         fake("edited-detail",
              "NPR's headline says the Moon, not Mars. One place was swapped.",
              "The real story: NASA wants astronauts who 'would also live and work on the moon in a future moon "
              "base.' Swapping one place name turns a real job posting into science fiction, and the old, busy "
              "account makes it look trustworthy.",
              "One word. Moon became Mars. Same job, longer commute. I'm framing this.",
              "Mars, caught. NASA said the Moon. I was aiming higher; you were aiming correctly.",
              {"type": "detail", "shown": moon_shown, "original": t("MOON_HEADLINE"),
               "changed": [{"from": "the Moon", "to": "Mars"}]})),
        (made_up("p5", P_LAUNCHPAD, "2026-11-09T02:10:00Z", "stat",
                 {"source": src_ev("npr_moon", t("NASA_CORPS"), t("NASA_8000"), t("NASA_AFTER"))},
                 body=f"8,000+ applied. TEN got in. \U0001F633\U0001F680 \"{t('NASA_ODDS')}\"",
                 source_label=S["npr_moon"].label),
         real("Real. The account is new and very loud, but the sentence is word for word from NPR, with the source "
              "linked: out of more than 8,000 applicants for NASA's last astronaut class, 10 were picked.",
              "That one was real. All caps, zero chill, every number correct. Doubting the truth is my job.",
              suspicious=True)),
    ]
    return assemble("2026-11-13-daily-science-says", 3, "2026-11-13", "Science Says", "Lab Coats and Tall Tales",
                    "Weird science news",
                    "Science news. Five posts, 0–3 doctored today. A lab coat makes anything sound true. Or false.",
                    "medium", items)


def day_food(eggs: dict, beef: dict, butter: dict) -> tuple:
    jun26, oct26, sep25, sep26 = eggs["2026-06"], eggs["2026-10"], eggs["2025-09"], eggs["2026-09"]
    record = max((v, k) for k, v in eggs.items() if k >= "2024-01")
    rise, yoy = pct(jun26, oct26), pct(sep25, sep26)
    assert record == (6.227, "2025-03") and rise == 8.4 and yoy == -34.9, (record, rise, yoy)
    egg_shown = bars("Average price, a dozen eggs", "$/dozen", [(label("2026-06"), jun26), (label("2026-10"), oct26)],
                     y_min=2.1, y_max=2.35)
    # The honest comparison the tell names: the same month a year apart, axis from zero.
    egg_honest = bars("Same month a year apart, axis from $0", "$/dozen",
                      [(label("2025-09"), sep25), (label("2026-09"), sep26)])
    egg_rows = series(eggs, "2024-01", "2026-10")
    egg_data = {"title": "Average price: eggs, grade A, large, per dozen, U.S. city average (BLS, via FRED)",
                "unit": "$/dozen", "url": FRED["eggs"][1], "table": egg_rows,
                "honest_chart": line("Eggs, monthly average price (BLS)", "$/dozen", series(eggs, "2023-01", "2026-10")),
                "note": (f"Record: ${record[0]} in Mar 2025. Sep 2025 to Sep 2026, a dozen fell from ${sep25} to "
                         f"${sep26} ({yoy}%). BLS published no Oct 2025 value.")}
    # Ground beef: a real NPR sentence posted by a loud made-up account; BLS data backs every number.
    b16, b26 = beef["2016-09"], beef["2026-09"]
    beef_pct = pct(b16, b26)
    assert round(b26, 2) == 6.79 and 85 <= beef_pct < 86, (b16, b26, beef_pct)
    beef_data = {"title": "Average price: ground beef, 100% beef, per pound, U.S. city average (BLS, via FRED)",
                 "unit": "$/lb", "url": FRED["beef"][1],
                 "table": [{"label": m, "value": beef[m]} for m in ("2016-09", "2025-09", "2026-09")],
                 "honest_chart": bars("Ground beef, Sep 2016 vs. Sep 2026", "$/lb",
                                      [(label("2016-09"), b16), (label("2026-09"), b26)]),
                 "note": (f"Sep 2016 to Sep 2026: ${b16} to ${b26} a pound (+{beef_pct}%). NPR's 'last month' is "
                          "September 2026; it rounds the rise to 85%.")}
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
        (made_up("p1", P_CLUCK, "2026-11-13T16:40:00Z", "chart", {"data": egg_data},
                 body="Egg prices are SPIKING again \U0001F4C8\U0001F95A Stock up before it's 2025 all over again.",
                 chart=egg_shown, source_label="Data: BLS average prices (via FRED)"),
         fake("misleading-chart",
              f"Jun to Oct 2026 on an axis that starts at $2.10 makes an 18-cent rise look like a rocket. Same month "
              f"a year apart, Sep 2025 vs. Sep 2026, a dozen fell from ${sep25:.2f} to ${sep26:.2f} ({yoy:.0f}%).",
              f"Real BLS prices, framed to scare. June to October 2026 did rise {rise:.0f}%, but the axis from $2.10 "
              "makes the October bar about five times taller, and the four-month window hides the fall from the "
              "$6.23 record in March 2025.",
              "Real prices, my axis. I started it at $2.10 and picked June to October. Two choices, one panic. "
              "I'm framing this.",
              "An axis at $2.10 and a four-month window, and you didn't flinch. My egg rocket is grounded.",
              {"type": "chart", "shown": egg_shown, "original": egg_honest})),
        (butter_post,
         real(f"Real and word for word from NPR, and BLS data backs it: butter fell from ${bsep25} to ${bsep26} a "
              "pound, September to September. Not everything goes up.",
              "Real. Butter got cheaper. Doubting good news is still doubting the truth, and that's my job.",
              suspicious=True)),
        (made_up("p3", P_SPOOKY, "2026-10-31T13:15:00Z", "stat",
                 {"source": src_ev("npr_candy", t("CANDY_BEFORE"), t("CANDY_STAT"), t("CANDY_AFTER"))},
                 body=f"Halloween budget check \U0001F383 \"{candy_shown}.\" Plan accordingly.",
                 source_label=S["npr_candy"].label),
         fake("cherry-picked-stat",
              "The 18% is over two years. NPR's same sentence says candy and gum rose 7.7% in one year.",
              "The number is real; its time window was dropped. 'Up more than 18%' reads like this year's damage, "
              "but it's two years of increases stacked together. Candy did rise faster than food overall, which is "
              "why the claim feels right, and the calm, helpful voice makes it feel safe.",
              "I didn't touch the 18%. I deleted 'in two years' and the 7.7% beside it. I'm framing this.",
              "You noticed the 18% had lost its 'in two years.' The number was real; my timeline wasn't.",
              {"type": "stat", "shown": candy_shown, "original": t("CANDY_STAT"),
               "missing": "The time window: the 18% is over two years. Over one year, candy and gum rose 7.7%."})),
        (made_up("p4", P_GRILL, "2026-10-21T00:30:00Z", "stat",
                 {"source": src_ev("npr_grocery", t("BEEF_RISE"), t("BEEF_STAT"), ""), "data": beef_data},
                 body=f"AN 85% JUMP. \U0001F969\U0001F624 \"{t('BEEF_STAT')}\"",
                 source_label=S["npr_grocery"].label),
         real(f"Real. The account is loud, but the sentence is word for word from NPR, and BLS data backs it: "
              f"${b16} a pound in Sep 2016, ${b26} in Sep 2026, up {beef_pct:.0f}%. The ten-year window is stated "
              "right in the sentence, so nothing is hidden.",
              "Real. 85% over a decade, and it says 'a decade' right there. Shouting isn't lying. Get your own tricks.",
              suspicious=True)),
        (outlet_post("p5", "npr_grocery", "quote", t("VOLPE_BEFORE"), t("VOLPE_PARA"), "",
                     body=t("GROCERY_HEADLINE"),
                     quote={"text": t("VOLPE"), "speaker": "Ricky Volpe, Cal Poly San Luis Obispo"}),
         real("Word for word from NPR. Grocery prices are rising more slowly than in 2022, but on top of a much "
              "higher base.",
              "That one was real. Not every gloomy quote is a crop. Doubting the truth is my job.")),
    ]
    return assemble("2026-11-14-daily-food-prices", 4, "2026-11-14", "Food Prices", "Check the Receipt",
                    "Grocery prices",
                    "Food prices. Five posts, 0–3 doctored today. Check the receipt before you swallow anything.",
                    "hard", items)


def day_hackprinceton(prices: dict[str, float], coffee: dict, beef: dict) -> tuple:
    """Sunday 2026-11-15, judging day: fun first, civic second. 3 of 5 doctored."""
    apr25, jul25, jul26 = prices["2025-04"], prices["2025-07"], prices["2026-07"]
    shown_pct, yoy = pct(apr25, jul26), pct(jul25, jul26)
    assert (apr25, jul25, jul26, shown_pct, yoy) == (19.91, 25.11, 25.19, 26.5, 0.3)
    shown_chart = bars("NJ residential electricity price", "¢/kWh",
                       [(label("2025-04"), apr25), (label("2026-07"), jul26)], y_min=19, y_max=26)
    # The honest comparison the tell names: the same month a year apart, axis from zero.
    honest_bars = bars("Same month a year apart, axis from 0", "¢/kWh",
                       [(label("2025-07"), jul25), (label("2026-07"), jul26)])
    data_ev = {"title": "NJ residential average electricity price (EIA)", "unit": "¢/kWh", "url": EIA_URL,
               "table": series(prices, "2025-01", max(prices)),
               "honest_chart": line("NJ residential electricity price, monthly (EIA)", "¢/kWh",
                                    series(prices, "2023-01", max(prices))),
               "note": f"Prices jumped in summer 2025. Jul 2025 to Jul 2026: {jul25} to {jul26}¢ (+{yoy}%)."}
    # Coffee vs. ground beef: real BLS numbers, honestly charted, posted by a brand-new hype account.
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
    lib_shown = "Overdue library magazine returned after 32 years"
    # Ground beef: NPR's real sentence with its time window ("from a decade earlier") deleted. Citable (NPR), so
    # the card carries a source label like every other card; the NJ Monitor "net" crop lives on in the Fool Deck.
    b16, b25, b26 = beef["2016-09"], beef["2025-09"], beef["2026-09"]
    beef_decade, beef_year = pct(b16, b26), pct(b25, b26)
    assert round(b26, 2) == 6.79 and 85 <= beef_decade < 86 and beef_year == 7.4, (beef_decade, beef_year)
    beef_shown = t("BEEF_STAT").replace(" from a decade earlier", "")
    beef_data = {"title": "Average price: ground beef, 100% beef, per pound, U.S. city average (BLS, via FRED)",
                 "unit": "$/lb", "url": FRED["beef"][1],
                 "table": [{"label": m, "value": beef[m]} for m in ("2016-09", "2025-09", "2026-09")],
                 "honest_chart": bars("Ground beef: a year apart vs. a decade apart", "$/lb",
                                      [(label("2016-09"), b16), (label("2025-09"), b25), (label("2026-09"), b26)]),
                 "note": (f"Sep 2025 to Sep 2026: ${b25} to ${b26} (+{beef_year}%). Sep 2016 to Sep 2026: ${b16} to "
                          f"${b26} (+{beef_decade}%). NPR's 'last month' is September 2026.")}
    items = [
        (outlet_post("p1", "npr_mice", "quote", t("MICE_SUMMARY"), t("FALKNER_ARENA"),
                     cat("FALKNER_ROLE", "MICE_NATURE"), body=t("MICE_HEADLINE"),
                     quote={"text": t("FALKNER_ARENA"), "speaker": "Annegret Falkner, Princeton Neuroscience Institute"}),
         real("Sounds like a parody, but it's word for word from NPR. Princeton neuroscientists really staged "
              "'gladiator style' mouse fights, and the paper is in Nature.",
              "Real. Princeton built a mouse colosseum, and I didn't have to invent a thing. Frankly insulting.",
              suspicious=True)),
        (made_up("p2", P_BILLWATCH, "2026-11-14T15:20:00Z", "chart", {"data": data_ev},
                 body="NJ power prices are up 27% in ONE YEAR. Share before your next bill hits.", chart=shown_chart,
                 source_label="Data: U.S. EIA"),
         fake("misleading-chart",
              f"The bars compare Apr 2025, before the summer spike, with Jul 2026, 15 months later, on an axis that "
              f"starts at 19¢. Same month a year apart, Jul 2025 vs. Jul 2026, prices went from {jul25} to {jul26}¢ "
              f"(+{yoy}%).",
              f"Real EIA numbers, framed to mislead. Comparing a spring month with a summer month 15 months later "
              f"turns the 2025 jump into a 'one year' rise, and the axis from 19¢ makes a {shown_pct}% gap look like "
              "a cliff. Over the past year, prices have been nearly flat.",
              "Real EIA numbers. I put April 2025 next to July 2026 and started the axis at 19¢. Two choices. "
              "I'm framing this.",
              "April 2025 to July 2026 is fifteen months, not one year, and my 19¢ axis didn't fool you either. Rude.",
              {"type": "chart", "shown": shown_chart, "original": honest_bars})),
        (made_up("p3", P_BREW, "2026-11-14T16:05:00Z", "chart", {"data": cb_data},
                 body=("WAIT. A pound of ground coffee costs MORE than a pound of ground beef?! ☕\U0001F969 "
                       f"BLS average prices, Oct 2026: ${c10} vs. ${b10}."),
                 chart=cb_chart, source_label="Data: BLS average prices (via FRED)"),
         real("Real. The account is brand new and very excited, but both numbers match BLS average prices exactly, "
              "the axis starts at zero, and per pound, coffee has cost more than ground beef every month since at "
              "least Jan 2022.",
              "Real. Every number is straight from BLS. Caps lock isn't a crime. Doubting the truth is my job.",
              suspicious=True)),
        (made_up("p4", P_SHELF, "2026-09-20T15:00:00Z", "headline",
                 {"source": src_ev("npr_library", "", t("LIBRARY_HEADLINE"), cat("LIBRARY_SUMMARY", "LIBRARY_1894"))},
                 body=f"{lib_shown} \U0001F4DA Imagine the late fees.", source_label=S["npr_library"].label),
         fake("edited-detail",
              "NPR's headline says 132 years, not 32. The magazine was published in 1894.",
              "One number was swapped, and it made the story less weird. The real magazine, from 1894, came back "
              "about 132 years overdue after a New Hampshire library announced a fine freeze. A believable number "
              "is still a wrong number.",
              "One number. 132 became 32. I made the truth less weird and you relaxed. I'm framing this.",
              "132 years, not 32. The truth was weirder than my lie, and you knew it.",
              {"type": "detail", "shown": lib_shown, "original": t("LIBRARY_HEADLINE"),
               "changed": [{"from": "132", "to": "32"}]})),
        (made_up("p5", P_CHECKOUT, "2026-10-22T13:00:00Z", "stat",
                 {"source": src_ev("npr_grocery", t("BEEF_RISE"), t("BEEF_STAT"), ""), "data": beef_data},
                 body=f"Grocery check 🛒 \"{beef_shown}\"", source_label=S["npr_grocery"].label),
         fake("cherry-picked-stat",
              f"The 85% is over a decade: NPR's sentence says 'from a decade earlier.' Over one year, Sep 2025 to "
              f"Sep 2026, ground beef rose {beef_year}%.",
              "Every number is real, but four words are gone. 'An 85% jump' now reads like this year's price shock; "
              f"NPR's sentence measures it from a decade earlier. BLS: ${b16} a pound in Sep 2016, ${b25} in Sep "
              f"2025, ${b26} in Sep 2026.",
              "I deleted 'from a decade earlier.' Four words, ten years. I'm framing this.",
              "The 85% lost 'from a decade earlier,' and you noticed. Ten years squeezed into one post, unsqueezed. Rude.",
              {"type": "stat", "shown": beef_shown, "original": t("BEEF_STAT"),
               "missing": (f"The time window: the 85% is from a decade earlier (Sep 2016 ${b16} to Sep 2026 ${b26}). "
                           f"Over one year, Sep 2025 to Sep 2026, ground beef rose {beef_year}%.")})),
    ]
    return assemble("2026-11-15-daily-hackprinceton", 5, "2026-11-15", "HackPrinceton Special",
                    "Mice, Magazines and Megawatts", "Princeton science, odd news, prices and power bills",
                    "HackPrinceton Special. Five posts, 0–3 doctored today. Princeton mice, a very overdue magazine, "
                    "your groceries and your power bill. I never make up a number. I don't have to.",
                    "medium", items)


def day_jersey() -> tuple:
    items = [
        (outlet_post("p1", "nj1015_boss", "quote", f"{t('BOSS_LEDE')} {t('BOSS_GRIEVANCE')}", t("BOSS_QUOTE_PARA"),
                     "", body=t("BOSS_HEADLINE"),
                     quote={"text": t("BOSS_QUOTE") + ".", "speaker": "Bruce Springsteen, at the 2026 MoMA film benefit"}),
         real("Real. New Jersey 101.5 reports Springsteen told a MoMA film benefit that seeing 'Jaws' in 1975 spoiled "
              "night swimming at the Jersey Shore.",
              "Real. The Boss vs. a rubber shark. I couldn't write that, and I tried.", suspicious=True)),
        (outlet_post("p2", "whyy_microbe", "headline", "", t("MICROBE_HEADLINE"),
                     f"{t('MICROBE_LEDE')} {t('MICROBE_SIGNED')}", body=t("MICROBE_HEADLINE")),
         real("Real. New Jersey has an official state microbe: the governor signed the bill in May 2019 (WHYY, from "
              "the Associated Press). Streptomyces griseus played a role in treating tuberculosis.",
              "Real. New Jersey has an official state microbe, signed into law. I've never been so jealous of a "
              "bacterium.", suspicious=True)),
        (outlet_post("p3", "whyy_victor", "headline", "", t("VICTOR_HEADLINE"), cat("VICTOR_LEDE", "VICTOR_PIANO"),
                     body=t("VICTOR_HEADLINE")),
         real("Real. It's Berlin, New Jersey, a few miles from Camden, where RCA-Victor was born. A Victor Museum "
              "opened there, electric piano that 'sort of works' included.",
              "Real. Berlin, New Jersey. The headline let you picture Germany. That's geography, not me.",
              suspicious=True)),
        (made_up("p4", P_JUGHANDLE, "2026-11-14T02:15:00Z", "stat",
                 {"source": src_ev("nj1015_drivers", "", t("DRIVERS_RANK"), cat("DRIVERS_RATE", "DRIVERS_CAVEAT"))},
                 body=f"Called it. \U0001F697\U0001F4A5 \"{t('DRIVERS_RANK')}\"",
                 source_label=S["nj1015_drivers"].label),
         real("Real. The account is loud, but the sentence is word for word from New Jersey 101.5, with the source "
              "linked. The story even gives the fine print: 56.9 incidents per 1,000 drivers, from insurance-quote "
              "data.",
              "Real. A loud account quoting a real story word for word. Loud isn't fake. Doubting the truth is my job.",
              suspicious=True)),
        (outlet_post("p5", "nj1015_seals", "quote", "", t("SEALS_PARA"), t("SEALS_AFTER"),
                     body=t("SEALS_HEADLINE"), quote={"text": t("SEALS_QUOTE"), "speaker": "Jon Stewart, on Instagram"}),
         real("Real. New Jersey 101.5 quotes the caption on the seal video Jon Stewart posted, then matches the "
              "spot to the waters near Sandy Hook.",
              "Real. Three exclamation points and still true. Jon Stewart did my job for me.")),
    ]
    return assemble("2026-11-16-daily-jersey-weird", 6, "2026-11-16", "Jersey Weird", "Only in Jersey",
                    "New Jersey oddities",
                    "Jersey weirdness. Five posts, 0–3 doctored today. Some of this can't possibly be true. Can it?",
                    "easy", items,
                    con_line_clean="Zero fakes. Jersey did all the work. I took the day off and watched you "
                                   "interrogate the truth. Restful.")


def day_strange() -> tuple:
    marathon_shown = "There were just over 2,000 competitors, including only 88 women."
    items = [
        (outlet_post("p1", "npr_socks", "headline", "", t("SOCKS_HEADLINE"), cat("SOCKS_SUMMARY", "SOCKS_FLIES"),
                     body=t("SOCKS_HEADLINE")),
         real("Real. Arsenal sent dozens of used match socks to a horse and donkey sanctuary in England, where they "
              "protect the animals' legs from biting flies.",
              "Real. Donkeys in Arsenal socks. I have limits. Reality doesn't.", suspicious=True)),
        (outlet_post("p2", "opb_owls", "headline", "", t("OWLS_HEADLINE"), f"{t('OWLS_LEDE')} {t('OWLS_FIRST')}",
                     body=t("OWLS_HEADLINE")),
         real("Real, from the Associated Press via OPB. A family of barn owls nested in a water tower near Central "
              "Park, the first documented barn owl nest in Manhattan in modern history, according to one expert.",
              "Real. Barn owls in a Manhattan water tower. I'd never pitch anything that adorable.", suspicious=True)),
        (outlet_post("p3", "npr_camel", "headline", "", t("CAMEL_HEADLINE"), t("CAMEL_SUMMARY"),
                     body=t("CAMEL_HEADLINE")),
         real("Real. In the 1950s a Nevada newspaper editor wrote a joke story about a camel race. Then the race "
              "really happened, and it still runs every year: fake news that came true.",
              "Real, and it's my origin story: a fake headline so good it came true.", suspicious=True)),
        (made_up("p4", P_FINISH, "2026-11-02T14:00:00Z", "stat",
                 {"source": src_ev("npr_marathon", t("MARATHON_BEFORE"), t("MARATHON_STAT"), t("MARATHON_AFTER"))},
                 body=f"The NYC Marathon is smaller than you'd think \U0001F3C3 \"{marathon_shown}\"",
                 source_label=S["npr_marathon"].label),
         fake("cherry-picked-stat",
              "Those numbers are from 1976, the seventh running of the race. NPR's next sentence: about 60,000 "
              "runners started on Sunday.",
              "Every number is real, but the year was deleted. In 1976 the race had just over 2,000 runners, "
              "including 88 women. This year about 60,000 stepped up to the starting line, nearly half of them women.",
              "I deleted 'in 1976, the seventh running of the race.' Eight words, fifty years. I'm framing this.",
              "You noticed the missing 1976. Just over 2,000 then, about 60,000 now. My shrink ray failed.",
              {"type": "stat", "shown": marathon_shown, "original": t("MARATHON_1976"),
               "missing": ("The year: those numbers are from 1976, the seventh running of the race. About 60,000 "
                           "runners started on Sunday, nearly half of them women.")})),
        (made_up("p5", P_COUCH, "2026-11-10T01:30:00Z", "quote",
                 {"source": src_ev("npr_mice", t("FALKNER_NFL_BEFORE"), "FALKNER: " + t("FALKNER_NFL"),
                                   t("FALKNER_NFL_AFTER"))},
                 body=("A Princeton neuroscientist, on whether watching sports makes you better at them. My couch and "
                       "I feel seen. \U0001F6CB️\U0001F3C8"),
                 quote={"text": t("FALKNER_NFL"), "speaker": "Annegret Falkner, Princeton Neuroscience Institute"},
                 source_label=S["npr_mice"].label),
         real("Real. The account is a sofa with opinions, but the quote is word for word from NPR, and it's the whole "
              "quote: she isn't saying watching makes you a pro, just that watching beats never watching.",
              "Real. A couch account quoting a Princeton neuroscientist word for word. Comfy, not crooked.",
              suspicious=True)),
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


def headline_deck(did: str, skey: str, headline_key: str, after: str) -> dict:
    """A real headline the player may crop, shown as the outlet quoting its own headline (no added period)."""
    text = t(headline_key)
    pe = outlet_post("p1", skey, "quote", "", text, after, quote={"text": text, "speaker": f"{S[skey].outlet} headline"})
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
                   t("NJM_0924_BEFORE"), "… " + t("ACE_PASSAGE"), body=t("NJM_0924_DESC")),
        quote_deck("rebhorn-peak-hours", "njm_1112", "REBHORN", "REBHORN_PARA", "Emma Rebhorn, BPU Commissioner",
                   t("REBHORN_BEFORE"), t("REBHORN_AFTER")),
        quote_deck("falkner-watching-sports", "npr_mice", "FALKNER_NFL", "FALKNER: " + t("FALKNER_NFL"),
                   "Annegret Falkner, Princeton Neuroscience Institute", t("FALKNER_NFL_BEFORE"),
                   t("FALKNER_NFL_AFTER"), body=t("MICE_HEADLINE")),
        # crop-friendly: delete "think they've" and a maybe becomes a fact
        headline_deck("dino-blood-headline", "npr_dino", "DINO_HEADLINE", t("DINO_DOUBT")),
        # crop-friendly: keep "I can with 100% confidence tell you" and lose the punchline
        quote_deck("robinson-100-percent", "npr_schooner", "ROBINSON", "ROBINSON: " + t("ROBINSON"),
                   "David Robinson, Massachusetts Board of Underwater Archaeological Resources",
                   t("ROBINSON_WRECK"), t("ROBINSON_AFTER"), body=t("SCHOONER_HEADLINE")),
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


_ABBREV = re.compile(r"\b(Gov|Dr|Mr|Mrs|Ms|St|Jan|Feb|Aug|Sept|Oct|Nov|Dec|vs|U\.S)\.")


def n_sentences(s: str) -> int:
    """Rough sentence count for the excerpt-length rule (abbreviations and short embedded quotes don't split)."""
    s = normalize(s).replace("...", " ")
    s = re.sub(r'"[^"]{0,60}"', " ", s)
    s = _ABBREV.sub(lambda m: m.group(1).replace(".", ""), s)
    return len([x for x in re.split(r"(?<=[.!?])[\"')]*\s+(?=[\"('(]?[A-Z])", s) if re.search(r"\w", x)])


def card_text(p: dict) -> str:
    return " ".join(x for x in (p["body"], (p["quote"] or {}).get("text") or "") if x)


def card_excerpt_sentences(p: dict) -> int:
    """Sentences of verbatim bank text shown on the card (headlines don't count; overlapping excerpts once)."""
    text = squash(card_text(p))
    found = [k for k in BANK if k not in HEADLINE_KEYS and squash(t(k)) in text]
    found = [k for k in found if not any(j != k and squash(t(k)) in squash(t(j)) for j in found)]
    return sum(n_sentences(t(k)) for k in found)


def check_excerpts(p: dict, ev: dict, where: str) -> None:
    """Licensing: short excerpts only (<= 2 sentences on the card and in each evidence passage)."""
    assert card_excerpt_sentences(p) <= 2, f"{where}: card excerpt longer than 2 sentences"
    if "source" in ev:
        for part in ("before", "highlight", "after"):
            assert n_sentences(ev["source"][part]) <= 2, f"{where}: evidence {part} longer than 2 sentences"


def check_case(cid: str, case: dict, evidence: dict, key: dict, meta: dict) -> None:
    posts = case["posts"]
    assert len(posts) == 5 and case["clue_budget"] == 3, cid
    assert "0–3 doctored today" in case["briefing"], cid
    assert case.get("notice") == NOTICE, f"{cid}: case notice"
    assert {p["id"] for p in posts} == set(evidence) == set(key["posts"]), cid
    doctored = [pid for pid, a in key["posts"].items() if a["doctored"]]
    assert 0 <= len(doctored) <= 3 and key["clean_case"] == (not doctored), cid
    assert any(a.get("suspicious_real") for a in key["posts"].values()), f"{cid}: needs a real-but-suspicious post"
    assert any(not key["posts"][p["id"]]["doctored"] and p["author"]["kind"] == "person" for p in posts), \
        f"{cid}: needs a REAL post from a made-up account, so the poster doesn't give the answer away"
    assert len({p["card_style"] for p in posts}) >= 2, f"{cid}: vary card_style"
    unlabeled = [key["posts"][p["id"]]["doctored"] for p in posts if not p["source_label"]]
    assert not unlabeled or not all(unlabeled),         f"{cid}: a missing source_label only appears on doctored posts, so it gives the answer away"
    assert (key["con_line_clean"] is not None) == key["clean_case"], cid
    assert meta["tricks"] == sorted({key["posts"][d]["trick"] for d in doctored}), cid
    lines = [a.get(k) for a in key["posts"].values()
             for k in ("con_line_fooled", "con_line_caught", "con_line_false_alarm") if a.get(k)]
    assert len(lines) == len(set(lines)), f"{cid}: repeated Con line"
    for p in posts:
        ev, a, where = evidence[p["id"]], key["posts"][p["id"]], f"{cid}/{p['id']}"
        check_post(p, ev, where)
        check_excerpts(p, ev, where)
        shown = normalize(card_text(p))
        assert not shown.startswith("..."), f"{where}: don't open a post with an ellipsis"
        if not a["doctored"]:
            assert a["explanation"] and a["con_line_false_alarm"], where
            assert p["source_label"], f"{where}: real posts carry a correct source_label"
            if "..." in shown:
                assert "ellipsis" in a["explanation"], f"{where}: the reveal must say an ellipsis only marks an excerpt"
            if p["author"]["kind"] == "person":  # real post from a made-up account: verbatim or exact numbers
                if "source" in ev:
                    src = [k for k in BANK if BANK[k][1] and S[BANK[k][0]].url == ev["source"]["url"]]
                    assert any(squash(t(k)) in squash(shown) and squash(t(k)) in squash(ev["source"]["highlight"])
                               for k in src), f"{where}: made-up real post must quote the source verbatim"
                else:
                    vals = {r["value"] for r in ev["data"]["table"]}
                    nums = [float(n) for n in re.findall(r"\$(\d+\.\d+)", p["body"])]
                    assert nums and all(n in vals for n in nums), f"{where}: numbers must match the data exactly"
            continue
        assert p["author"]["kind"] == "person" and not p["author"]["verified"], f"{where}: fakes need made-up authors"
        assert p["author"]["name"] not in OUTLETS, where
        assert "..." not in shown, f"{where}: an ellipsis must not become a doctoring tell"
        assert not re.search(r"\b(opened|checked|clicked)\b", a["con_line_caught"], re.I), \
            f"{where}: caught lines name the edit, not a check the player may not have made"
        d = a["diff"]
        assert d["type"] == {"out-of-context-quote": "quote", "misleading-chart": "chart",
                             "cherry-picked-stat": "stat", "edited-detail": "detail"}[a["trick"]], where
        if d["type"] != "chart":
            assert n_sentences(d["original"]) <= 2, f"{where}: original excerpt longer than 2 sentences"
        if d["type"] == "quote":
            assert is_deletion(d["shown"], d["original"]), f"{where}: crop must only delete words"
            assert normalize(d["shown"]).strip("….") in normalize(card_text(p)), where
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
            # diff.original is the HONEST comparison the tell describes (same months a year apart, axis from 0),
            # not the doctored months with the axis fixed
            o = d["original"]
            assert o["y_min"] == 0 and o["y_max"] is None, f"{where}: honest chart starts at 0"
            assert [x["label"] for x in o["points"]] != [x["label"] for x in d["shown"]["points"]], \
                f"{where}: diff.original must use the honest months"
            vals = {r["value"] for r in ev["data"]["table"]}
            for x in o["points"]:
                assert x["value"] in vals, f"{where}: honest value {x} not in data table"
                assert x["label"] in a["tell"], f"{where}: tell must name {x['label']}"


def check_deck(deck: list[dict]) -> None:
    assert 6 <= len(deck) <= 10 and len({d["id"] for d in deck}) == len(deck)
    for d in deck:
        p, ev, ed, where = d["post"], d["evidence"], d["editable"], f"deck/{d['id']}"
        check_post(p, ev, where)
        check_excerpts(p, ev, where)
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
    days = [day_science(), day_food(eggs, beef, butter), day_hackprinceton(prices, coffee, beef), day_jersey(),
            day_strange()]
    deck = build_deck(prices, eggs, coffee)
    for cid, case, ev, key, meta in days:
        check_case(cid, case, ev, key, meta)
    unlabeled = [key["posts"][p["id"]]["doctored"] for _, case, _, key, _ in days for p in case["posts"]
                 if not p["source_label"]]
    assert not unlabeled or not all(unlabeled), "across the dailies, only doctored posts lack a source_label"
    check_deck(deck)
    for stale in STALE_CASE_DIRS:
        folder = CASES / stale
        if folder.is_dir():
            for f in folder.iterdir():
                f.unlink()
            folder.rmdir()
            print(f"removed stale data/cases/{stale}")
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

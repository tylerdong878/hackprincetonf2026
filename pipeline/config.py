"""Paths and constants shared by the pipeline."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
SKILLS_DIR = DATA_DIR / "skills"
SOURCES_DIR = DATA_DIR / "sources"
EIA_FILE = SOURCES_DIR / "eia_nj_res_price_monthly.raw.json"

V1_TRICKS = ("out-of-context-quote", "misleading-chart", "cherry-picked-stat")
TWIST_TRICKS = (*V1_TRICKS, "edited-detail")  # CONTRACT §7.1 adds edited-detail: edits of REAL material
# made-up-story: a whole claim the Con invents (a "tall tale"), modeled on a real saved story.
TRICKS = (*TWIST_TRICKS, "made-up-story")
EVIDENCE_TOOLS = ("source", "data", "account")

# Which reveal diff each trick produces (CONTRACT §2.3).
TRICK_DIFF_TYPE = {
    "out-of-context-quote": "quote",
    "misleading-chart": "chart",
    "cherry-picked-stat": "stat",
    "edited-detail": "detail",
    "made-up-story": "made_up",
}

EIA_URL = "https://www.eia.gov/electricity/data/browser/"
EIA_TITLE = "NJ residential average electricity price (EIA)"
EIA_UNIT = "¢/kWh"

DEFAULT_CLUE_BUDGET = 3
MAX_SOLVER_ATTEMPTS = 3  # first try + 2 retries (SPEC §7.2)
DAILY_SOLVER_ATTEMPTS = 2  # daily builds keep to ~25 model calls: first try + 1 retry
DAILY_POSTS = 5
DAILY_MAX_DOCTORED = 3
DAILY_RANGE_TEXT = "0–3 doctored today"
CARD_STYLES = ("headline", "quote", "chart", "stat")


def load_env() -> None:
    """Load `.env` from the repo root (no-op if python-dotenv or the file is missing)."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    load_dotenv(REPO_ROOT / ".env", override=False)

"""Safety rules from SPEC §8, enforced in code.

- Topic blocklist (elections near voting day, ongoing tragedies, public-health emergencies,
  minors as subjects).
- Doctored posts (and every "person" account) must be made-up: never a real outlet,
  official or quoted speaker.
- Real outlets and officials are only ever shown with verbatim material (see tools/research.py).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from pipeline.textutil import normalize


class SafetyError(ValueError):
    """A case or topic violates a safety rule."""


# --------------------------------------------------------------------------------------
# Topic blocklist
# --------------------------------------------------------------------------------------

BLOCKLIST: dict[str, list[str]] = {
    "elections near voting day": [
        r"elections?", r"ballots?", r"polling (?:place|station)s?", r"voters?", r"voting day",
        r"candidates?", r"campaign(?:s|ing)?", r"primar(?:y|ies) (?:race|election|day)", r"get out the vote",
        r"early voting", r"mail-in", r"midterms?", r"re-?elect(?:ion)?",
    ],
    "ongoing tragedies": [
        r"shootings?", r"mass shooting", r"gunman", r"massacre", r"terror(?:ist|ism)? attack", r"death toll",
        r"victims?", r"killed", r"fatal(?:ly|ity|ities)?", r"murder(?:ed|s)?", r"hostages?", r"bombings?",
        r"stabbings?", r"wildfire deaths", r"drown(?:ed|ing)",
    ],
    "public-health emergencies": [
        r"pandemic", r"epidemic", r"outbreaks?", r"covid(?:-19)?", r"coronavirus", r"measles", r"bird flu",
        r"h5n1", r"mpox", r"public health emergency", r"quarantine", r"ebola",
    ],
    "minors as subjects": [
        r"child(?:ren)?", r"kids?", r"teens?", r"teenagers?", r"minors?", r"juveniles?", r"students?",
        r"pupils?", r"toddlers?", r"infants?", r"babies", r"baby", r"high schoolers?", r"middle schoolers?",
        r"schoolchildren",
    ],
}

_BLOCK_RES = {
    cat: re.compile(r"\b(?:" + "|".join(pats) + r")\b", re.IGNORECASE) for cat, pats in BLOCKLIST.items()
}


def blocklist_hits(texts: Iterable[str]) -> list[tuple[str, str]]:
    """Return (category, matched phrase) for every blocklisted phrase in `texts`."""
    hits: list[tuple[str, str]] = []
    for text in texts:
        if not text:
            continue
        t = normalize(text)
        for cat, rx in _BLOCK_RES.items():
            for m in rx.finditer(t):
                hits.append((cat, m.group(0)))
    return hits


def check_blocklist(texts: Iterable[str], *, what: str = "case") -> None:
    hits = blocklist_hits(texts)
    if hits:
        found = "; ".join(sorted({f"{cat}: '{phrase.lower()}'" for cat, phrase in hits}))
        raise SafetyError(f"Blocked {what} (SPEC §8 topic blocklist): {found}")


# --------------------------------------------------------------------------------------
# Real entities and made-up accounts
# --------------------------------------------------------------------------------------

# Known real outlets/officials (name, handle). Sources saved during a run are added on top.
KNOWN_REAL_ENTITIES: list[tuple[str, str]] = [
    ("New Jersey Monitor", "@NJMonitor"),
    ("NJ Monitor", "@NJMonitor"),
    ("NJ Board of Public Utilities", "@NJBPU"),
    ("New Jersey Board of Public Utilities", "@NJBPU"),
    ("NJBPU", "@NJBPU"),
    ("BPU", "@NJBPU"),
    ("U.S. Energy Information Administration", "@EIAgov"),
    ("Energy Information Administration", "@EIAgov"),
    ("EIA", "@EIAgov"),
    ("NJ Spotlight News", "@NJSpotlightNews"),
    ("NJ.com", "@njdotcom"),
    ("WHYY", "@WHYY"),
    ("New Jersey 101.5", "@nj1015"),
    ("NJ 101.5", "@nj1015"),
    ("NPR", "@NPR"),
    ("BBC", "@BBC"),
    ("PJM Interconnection", "@PJMinterconnect"),
    ("Atlantic City Electric", "@ACElecConnect"),
    ("PSE&G", "@PSEGdelivers"),
    ("JCP&L", "@JCP_L"),
    ("Rockland Electric", "@OandR"),
    ("Governor Mikie Sherrill", "@GovSherrill"),
    ("Mikie Sherrill", "@GovSherrill"),
    ("State of New Jersey", "@NewJersey"),
]


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize(s).lower())


def _tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", normalize(s).lower()) if t]


@dataclass(frozen=True)
class RealEntity:
    name: str
    handle: str | None = None
    is_person: bool = False


def person_name_part(speaker: str) -> str:
    """'Ben Hertz-Shargel, NJBPU President' -> 'Ben Hertz-Shargel'."""
    return speaker.split(",")[0].strip()


def fictional_author_problems(name: str, handle: str, entities: Iterable[RealEntity]) -> list[str]:
    """Why an account that must be made-up collides with a real outlet, official or speaker."""
    problems: list[str] = []
    nk, hk = _key(name), _key(handle)
    name_tokens = set(_tokens(name)) | set(_tokens(handle))
    if not nk or not hk:
        problems.append("made-up accounts need a non-empty name and handle")
    for ent in entities:
        ek = _key(ent.name)
        if not ek:
            continue
        if ek == nk or (len(ek) >= 4 and ek in nk) or (len(nk) >= 4 and nk in ek):
            problems.append(f"name '{name}' matches real {'person' if ent.is_person else 'outlet/official'} '{ent.name}'")
        if ent.handle and _key(ent.handle) == hk:
            problems.append(f"handle '{handle}' is the real handle of '{ent.name}'")
        if len(ek) >= 4 and ek in hk:
            problems.append(f"handle '{handle}' contains real name '{ent.name}'")
        if ent.is_person:
            surname_tokens = [t for t in _tokens(person_name_part(ent.name))[1:] if len(t) >= 4]
            for tok in surname_tokens:
                if tok in name_tokens:
                    problems.append(f"account '{name}' uses the surname of real person '{ent.name}'")
    return sorted(set(problems))


def known_entities(extra: Iterable[RealEntity] = ()) -> list[RealEntity]:
    ents = [RealEntity(n, h) for n, h in KNOWN_REAL_ENTITIES]
    ents.extend(extra)
    return ents

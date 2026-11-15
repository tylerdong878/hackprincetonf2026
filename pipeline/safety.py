"""Safety rules from SPEC §8, enforced in code.

- Topic blocklist (elections near voting day, ongoing tragedies, disasters and deaths, public-health
  emergencies, minors as subjects).
- Doctored posts (and every "person" account) must be made-up: never a real outlet,
  official or quoted speaker, and never a realistic personal name ("Jenna K.").
- Doctored text is never credited to a real outlet ("NPR says ...", quote speaker "NPR") and never
  claims more than its source ("the data proves the grid is collapsing").
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
        r"stabbings?", r"wildfire deaths", r"drown(?:s|ed|ing)?",
    ],
    # Old or new, a story about people dying or vanishing is not game material (e.g. the 1934 Morro Castle ship
    # fire, or "people who have disappeared" at a reservoir).
    "disasters and deaths": [
        r"die[ds]", r"dying", r"deaths?", r"deadly", r"deceased", r"perish(?:ed|es|ing)?", r"passed away",
        r"(?:found|left|pronounced|shot) dead", r"dead (?:bod(?:y|ies)|m[ae]n|wom[ae]n|people|passengers)",
        r"lost (?:at sea|their lives)", r"loss of life", r"lives (?:were )?lost",
        r"shipwrecks?", r"wreck(?:s|ed|age)?", r"capsiz(?:e|ed|es|ing)", r"lifeboats?",
        r"(?:ship|boat|ferry|liner|vessel|steamer|schooner)(?:'s)? (?:fire|blaze|sinking|sank|sinks|disaster)",
        r"fire (?:aboard|on board)", r"(?:plane|car|bus|train|helicopter|boat|fatal|deadly) crash(?:es|ed)?",
        r"disasters?", r"traged(?:y|ies)", r"tragic(?:ally)?", r"catastroph(?:e|es|ic)",
        r"disappearances?", r"(?:who|people|persons?|m[ae]n|wom[ae]n|hikers?|swimmers?|boaters?|fishermen|passengers)"
        r" (?:have |has |had )?(?:disappeared|vanished|gone missing|went missing)",
        r"(?:went|gone|reported|remains?|still|remained) missing",
        r"missing (?:persons?|people|hikers?|swimmers?|boaters?|m[ae]n|wom[ae]n|passengers)",
        r"suicides?", r"overdos(?:e|es|ed)", r"burn(?:ed|t) (?:to death|alive)", r"funerals?", r"mourn(?:s|ed|ing|ers)?",
        r"obituar(?:y|ies)", r"corpses?", r"rest in peace",
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


# Categories where a hit anywhere near a passage (its headline or the sentences around it) means the STORY is
# about the blocked thing, so the passage is refused rather than just trimmed from the context.
STORY_LEVEL_CATEGORIES = ("ongoing tragedies", "disasters and deaths")


def story_level_hits(texts: Iterable[str]) -> list[tuple[str, str]]:
    return [(c, p) for c, p in blocklist_hits(texts) if c in STORY_LEVEL_CATEGORIES]


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


# --------------------------------------------------------------------------------------
# Made-up account names: invented handles, never realistic personal names
# --------------------------------------------------------------------------------------

# Common first names. A made-up account called "Jenna K.", "Mike R." or "Sarah Thompson" reads as a real private
# person, so it is refused. (First names that are also everyday words, like "Bill" or "Grace", are left out.)
FIRST_NAMES = frozenset("""
aaron adam aisha alan albert alex alexander alexis alice alicia allison amanda amber amy ana andrea andrew angela
anna anne anthony antonio ashley austin barbara ben benjamin beth betty brandon brenda brian brittany bruce
carl carlos carmen carol caroline catherine charles charlie chloe chris christina christine christopher cindy
claire craig daniel danielle dave david deborah debbie denise dennis derek diana diane donald donna dorothy doug
douglas dylan ed eddie edward elena elizabeth ellen emily emma eric erica erin ethan eva evan frank gabriel gary
george greg gregory hannah harry heather helen henry ian isabella jacob jake james jamie jane janet jason jeff
jeffrey jen jenna jennifer jenny jeremy jerry jess jessica jill jim jimmy joan joe joel john johnny jon jonathan
jose joseph josh joshua joyce juan judy julia julie justin karen kate katherine kathleen kathy katie kayla keith
kelly ken kenneth kevin kim kimberly kyle larry laura lauren leah linda lisa liz logan lori lucas luis luke
madison maria marie martha mary matt matthew megan melissa michael michelle mike molly nancy natalie nathan
nick nicole noah olivia pam pamela patricia patrick paul peter priya rachel raj ralph rebecca richard rick
robert ron ronald ruth ryan sam samantha sandra sara sarah scott sean sharon shirley sophia stephanie stephen
steve steven susan tammy taylor teresa terry thomas tiffany tim timothy tina todd tom tony valerie victoria
vincent walter wayne william zach zachary
""".split())
_HONORIFIC_RE = re.compile(r"^(?:dr|mr|mrs|ms|miss|prof|professor|sir|dame|rev|officer|judge|senator|gov|governor|"
                           r"mayor|nurse|doc)\b\.?\s*\S", re.IGNORECASE)
_INITIAL_RE = re.compile(r"^[A-Z][a-z]+\s+[A-Z]\.?$")  # "Jenna K." / "Mike R"


def personal_name_problems(name: str, handle: str = "") -> list[str]:
    """Why a made-up account reads like a realistic personal name ([] for an invented handle-style name)."""
    problems: list[str] = []
    n = normalize(name or "").strip()
    first = re.sub(r"[^a-z]", "", re.sub(r"'s$", "", (n.split() or [""])[0].lower()))
    if _INITIAL_RE.match(n):
        problems.append(f"'{name}' looks like a real person's name ('Firstname L.')")
    elif first in FIRST_NAMES:
        problems.append(f"'{name}' starts with a personal first name; made-up accounts use invented handle-style names")
    if _HONORIFIC_RE.match(n):
        problems.append(f"'{name}' uses a title (Dr., Mr., ...), so it reads as a real person")
    htoks = [t for t in re.split(r"[^a-z]+", (handle or "").lower().lstrip("@")) if t]
    if htoks and htoks[0] in FIRST_NAMES:
        problems.append(f"handle '{handle}' starts with a personal first name")
    return problems


# --------------------------------------------------------------------------------------
# Doctored text: never credited to a real outlet, never claims more than its source
# --------------------------------------------------------------------------------------


def outlet_speaker_problem(speaker: str, entities: Iterable[RealEntity]) -> str | None:
    """A doctored quote is credited to the person who said it, never to an outlet or agency (e.g. 'NPR')."""
    name = person_name_part(speaker or "")
    k = _key(name)
    if not k:
        return "a quote needs a named person as its speaker"
    if re.search(r"\b(?:staff|editors?|editorial board|newsroom|reporters?)$", name, re.IGNORECASE):
        return f"the quote is credited to '{speaker}', a newsroom, not a person"
    for ent in entities:
        if not ent.is_person and (k == _key(ent.name) or (ent.handle and k == _key(ent.handle))):
            return (f"the quote is credited to '{speaker}', a real outlet/official; edited words are never "
                    "presented as said by a real outlet")
    return None


_ATTRIB_VERBS = (r"says?|said|reports?|reported|confirms?|confirmed|writes?|wrote|announce[sd]?|admits?|admitted|"
                 r"promise[sd]?|warns?|warned|claims?|claimed|just")


def outlet_attribution_hits(text: str, entities: Iterable[RealEntity]) -> list[str]:
    """Real outlets/officials that `text` credits words to ('NPR: ...', 'NPR says', 'according to NPR', '@NPR')."""
    t = normalize(text or "")
    found: set[str] = set()
    for ent in entities:
        if ent.is_person or len(_key(ent.name)) < 3:
            continue
        nm = re.escape(normalize(ent.name))
        pats = [rf"(?<![\w@]){nm}\s*(?::|-\s)", rf"(?<![\w@]){nm}(?:'s)?\s+(?:{_ATTRIB_VERBS})\b",
                rf"\b(?:according to|per|via|says?|said|reported by|from)\s+(?:the\s+)?{nm}(?!\w)"]
        if ent.handle:
            pats.append(rf"{re.escape(ent.handle)}(?!\w)")
        if any(re.search(p, t, re.IGNORECASE) for p in pats):
            found.add(ent.name)
    return sorted(found)


# Conclusions, certainty and widening that a crop, a detail swap or a cherry-picked number never supports.
OVERCLAIM_PATTERNS = [
    r"prov(?:e|es|ed|en|ing)", r"proof", r"confirm(?:s|ed|ing)?", r"collaps\w*", r"officially", r"it'?s official",
    r"(?:total|complete|full|outright|permanent|blanket) ban", r"banned (?:from )?(?:all|every|everything)",
    r"across (?:all|every)", r"(?:all|every) (?:sports?|teams?|leagues?|states?|countries|stores?)",
    r"(?:the )?(?:data|science|scientists|experts?|stud(?:y|ies)|research(?:ers)?|doctors) "
    r"(?:says?|shows?|proves?|confirms?|agrees?)",
    r"(?:this|that|which) (?:means|proves|shows)", r"no \w+ (?:specified|mentioned|given)", r"guarantee[sd]?",
    r"crisis", r"(?:is|are) (?:failing|doomed)",
]
_OVERCLAIM_RE = re.compile(r"\b(?:" + "|".join(OVERCLAIM_PATTERNS) + r")\b", re.IGNORECASE)


def overclaim_hits(text: str, support: str = "") -> list[str]:
    """Overclaiming phrases in `text` that its source (`support`) doesn't itself use."""
    have = normalize(support or "").lower()
    return sorted({m.group(0).lower() for m in _OVERCLAIM_RE.finditer(normalize(text or ""))
                   if m.group(0).lower() not in have})


# Words a stat claim may use beyond its source: the direction and size of a change, time words, filler.
CLAIM_FRAMING_WORDS = frozenset("""
again almost already another back below cent cents cost costs dollar dollars drop dropped drops ever fall
falling falls fell going gone half jump jumped jumps less nearly percent rise rises rising risen rose since
soar soared soars spike spiked spikes still surge surged surges went year years yearly month months monthly
week weeks today climb climbed climbs double doubled triple tripled really huge whopping wait look
""".split())
STOPWORDS = frozenset("""
about after also been being before both could does each even every from have here into just like many more
most much only other over same should since some such than that their them then there these they this those
under very were what when where which while will with would your yours
""".split())


def _stem(w: str) -> str:
    for suf in ("ings", "ing", "ies", "ied", "ers", "es", "ed", "ly", "er", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def content_words(text: str) -> list[str]:
    words = (w.strip("'") for w in re.findall(r"[a-z][a-z']*", normalize(text or "").lower()))
    words = (w[:-2] if w.endswith("'s") else w for w in words)
    return [w for w in words if len(w) >= 4 and w not in STOPWORDS]


def unsupported_words(claim: str, support: str, extra: Iterable[str] = ()) -> list[str]:
    """Content words of `claim` found neither in `support` (the source's own text) nor in the framing words.

    Lenient on purpose (stems, 5-letter prefixes): it catches an added assertion ("the grid is collapsing"),
    not rewording ("bills are going UP $4.09 a month" from "monthly bills ... will rise by $4.09").
    """
    have = {_stem(w) for w in content_words(support)}
    prefixes = {h[:5] for h in have if len(h) >= 5}
    ok = CLAIM_FRAMING_WORDS | {w.lower() for w in extra}
    out: list[str] = []
    for w in content_words(claim):
        s = _stem(w)
        if w in ok or s in ok or s in have or (len(s) >= 5 and s[:5] in prefixes):
            continue
        out.append(w)
    return list(dict.fromkeys(out))

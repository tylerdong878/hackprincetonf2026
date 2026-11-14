"""Adaptive next-case selection (SPEC §7.3), deterministic given an injected rng.

1. Skip cases the player has finished (fall back to all approved cases if none left).
2. ~20% of the time prefer a clean case; otherwise prefer a case with fakes.
3. Pick a target trick: 70% weakest (highest miss rate), 20% mastered, 10% new.
4. Score candidates: +2 if the case uses the target trick, +2 for each high-false-alarm
   trick whose format appears among the case's honest posts. Ties -> lowest case number.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .scoring import TRICKS, per_trick

CLEAN_RATE = 0.2
HIGH_FA_RATE = 0.4
HIGH_FA_MIN_SEEN = 2


@dataclass
class Candidate:
    id: str
    number: float
    tricks: list[str]
    clean: bool
    honest_tricks: set[str] = field(default_factory=set)  # tricks matching this case's real-post formats


def target_trick(profile: dict, rng) -> str | None:
    tricks = profile.get("tricks", {})
    stats = per_trick(tricks)
    names = sorted(set(TRICKS) | set(tricks))
    seen = [t for t in names if tricks.get(t, {}).get("shown", 0) > 0]
    missed = [t for t in seen if stats[t]["miss_rate"] > 0]
    weakest = max(missed, key=lambda t: stats[t]["miss_rate"]) if missed else None
    mastered = next((t for t in seen if stats[t]["mastery"] == 3), None)
    new = next((t for t in names if t not in seen), None)
    r = rng.random()
    if r < 0.7:
        order = [weakest, new, mastered]
    elif r < 0.9:
        order = [mastered, weakest, new]
    else:
        order = [new, weakest, mastered]
    return next((t for t in order if t), None)


def high_fa_tricks(profile: dict) -> list[str]:
    tricks = profile.get("tricks", {})
    stats = per_trick(tricks)
    return [t for t, c in tricks.items()
            if c.get("honest_shown", 0) >= HIGH_FA_MIN_SEEN and stats[t]["false_alarm_rate"] >= HIGH_FA_RATE]


def pick_next(candidates: list[Candidate], profile: dict, rng) -> Candidate | None:
    if not candidates:
        return None
    finished = {h.get("case_id") for h in profile.get("history", [])}
    pool = [c for c in candidates if c.id not in finished] or list(candidates)

    want_clean = rng.random() < CLEAN_RATE
    clean = [c for c in pool if c.clean]
    dirty = [c for c in pool if not c.clean]
    pool = (clean or dirty) if want_clean else (dirty or clean)

    target = target_trick(profile, rng)
    fa = high_fa_tricks(profile)

    def key(c: Candidate):
        score = (2 if target and target in c.tricks else 0) + 2 * sum(t in c.honest_tricks for t in fa)
        return (-score, c.number, c.id)

    return min(pool, key=key)

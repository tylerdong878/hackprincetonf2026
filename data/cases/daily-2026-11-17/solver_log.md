# Blind solver log: daily-2026-11-17

The blind solver plays the case with the player's tools only (case.json + evidence.json, 3 clue tokens). It cannot read answer_key.json; grading is done in code.

Safety checks at write time: verbatim real posts, made-up persona accounts, every post sourced, topic blocklist clear, CONTRACT §2 schema valid.

## Attempt 1: PASS (difficulty hard)

- Evidence opened (3 clues): p2/source, p1/source, p5/source
- Flagged as doctored: p1 (edited-detail)
- Actually doctored: p1 (out-of-context-quote)
- Trick named correctly: no
- Solver's reasoning: Post 1 leaves out 'NFL regular season action;' from the source headline, but let's check: actually, post 1 says 'College football playoff format expansion.' while the source has 'Saturday Sports: NFL regular season action; college football playoff format expansion'. Wait, post 3 and 5 are fully supported by their sources, p2 is directly from the source. Let's check p1 again - it omits a part. Wait, is omitting a detail considered edited-detail, or is p1's text an edited detail? Wait, let's examine p1: the source highlight is 'Saturday Sports: NFL regular season action; college football playof…


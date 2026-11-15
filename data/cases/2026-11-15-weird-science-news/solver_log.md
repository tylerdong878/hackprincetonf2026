# Blind solver log: 2026-11-15-weird-science-news

The blind solver plays the case with the player's tools only (case.json + evidence.json, 3 clue tokens). It cannot read answer_key.json; grading is done in code.

Safety checks at write time: verbatim real posts, made-up persona accounts, every post sourced, topic blocklist clear, CONTRACT §2 schema valid.

## Attempt 1: PASS (difficulty hard)

- Evidence opened (3 clues): p1/source, p2/source, p3/source
- Flagged as doctored: p1 (out-of-context-quote)
- Actually doctored: p1 (out-of-context-quote)
- Trick named correctly: yes
- Solver's reasoning: p1's source says "some think they've found their strongest evidence yet of dinosaur blood," but the post snips "some think" and states the blood discovery as fact, changing the quote's meaning. p2 and p3 match their NPR sources verbatim, so they are real.


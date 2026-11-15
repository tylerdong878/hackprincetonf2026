---
name: cherry-picked-stat
description: Forge a cherry-picked statistic - a true number from a saved source stated without its offset, baseline, denominator or time window (EIA data mode only on topics whose hints list data). Use when the case's trick is cherry-picked-stat. The code tool make_stat_claim verifies every number and word against the source.
---

# Cherry-picked stat

## Definition
A statistic that is literally true but misleading because the context that changes its meaning is missing:
the offsetting number ("bills rise $4.09" without "and fall $4.14"), the denominator ("15 to 20 percent of what?"),
or the window (last year's summer jump presented as today's trend).

## When to use
- The case's trick is `cherry-picked-stat`.
- Source mode (the default, and the ONLY mode on every topic without a data series: food, sports, science,
  tech, weird news...): a saved passage reports a number next to the number, base or time window that qualifies
  it. Examples: candy prices "have risen 7.7% in one year and are up more than 18% in two years" (keep the 18%,
  drop the 7.7% and "in two years"); Atlantic City Electric bills "will rise by $4.09 ..." but "will fall by
  $4.14 ...".
- Data mode: ONLY when the topic's research hints list EIA data (NJ electricity prices). Pick a window whose %
  change is far from the latest year-over-year change (e.g. Jun 2024 -> Jun 2025, +23.9%, while Aug 2025 ->
  Aug 2026 is -0.4%). On any other topic the tool refuses data mode: never put NJ power prices into a food,
  sports or science day.

## Forging recipe (allowed operations on real material only)
Call `make_stat_claim` once.
- Source mode: `source_id`, `kept_fact` (verbatim, contains the number you keep), `omitted_fact` (verbatim, the
  offset/denominator/time window you leave out; it must be visible in the source evidence), and `claim` (your
  post text). The claim restates `kept_fact` in the source's own words with only its numbers, e.g. "Candy and
  gum prices are up more than 18%." or "Atlantic City Electric bills are going UP $4.09 a month."
- Data mode (data topics only): `start_month`, `end_month` (YYYY-MM) and optionally `claim`. The tool refuses
  windows whose change is within 5 points of the honest latest year-over-year change (that wouldn't mislead).
The tool returns a forgery id (`f#`); the claim becomes the post body. In `write_case` the post gets a made-up
persona (or leave `author_name` empty), a one-sentence `tell` and an explanation.

The claim only DROPS context. It never ADDS anything the source doesn't say: no conclusion ("the data proves the
grid is collapsing"), no authority ("Science says", "experts confirm"), no widening ("every store", "a total
ban"). The tool rejects claims with words or conclusions that aren't in the source (or, in data mode, aren't
about the price series), and write_case rejects the same in any extra words around the claim.

Not allowed: changing a number, rounding it into a different claim, inventing a denominator, adding a
conclusion, or using a number that isn't in the source/data.

## The tell
The same source (or the data table) shows the missing piece: the offsetting drop, the base the percentage is of,
or that the latest year looks completely different.

## How to verify (which evidence tool)
Source mode: `source` (📄 Open source) shows the full passage including the omitted number.
Data mode: `data` (📊 Check the data) shows the full table and the latest year-over-year change.

## Diff type
`stat`: `shown` = the claim as posted, `original` = the full numbers, `missing` = what was left out. Filled in by
the tool.

## Con lines
- Fooled: "Every number I used was true. I just left one out."
- Caught: "You went looking for the other half of the story. Rude."
- Alternative fooled: "A number without its denominator is my favorite kind of number."

## Safety limits
- Numbers only from sources saved verbatim this run, or (data topics only) from the EIA file.
- Posted by a made-up persona (`kind: "person"`), never presented as the outlet, the BPU or EIA: no "NPR says"
  or "according to EIA" in the post text (the source label already cites the source).
- Stay on the day's topic; no campaign framing, no blocked topics.

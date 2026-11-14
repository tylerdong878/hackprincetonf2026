---
name: cherry-picked-stat
description: Forge a cherry-picked statistic - a true number stated without its offset, baseline or denominator, or a hand-picked time window. Use when the case's trick is cherry-picked-stat. The code tool make_stat_claim verifies every number against real sources or EIA data.
---

# Cherry-picked stat

## Definition
A statistic that is literally true but misleading because the context that changes its meaning is missing:
the offsetting number ("bills rise $4.09" without "and fall $4.14"), the denominator ("15 to 20 percent of what?"),
or the window (last year's summer jump presented as today's trend).

## When to use
- The case's trick is `cherry-picked-stat`.
- Source mode: a saved passage reports a number next to the number that cancels or qualifies it. Example
  (NJ Monitor, Sept 24, 2026): Atlantic City Electric bills "will rise by $4.09 ..." but "will fall by $4.14 ...,
  leaving the average monthly bill 5 cents cheaper".
- Data mode: EIA monthly prices, picking a window whose % change is far from the latest year-over-year change
  (e.g. Jun 2024 -> Jun 2025, +23.9%, while Aug 2025 -> Aug 2026 is -0.4%).

## Forging recipe (allowed operations on real material only)
Call `make_stat_claim` once, in one of two modes.
- Source mode: `source_id`, `kept_fact` (verbatim, contains the number you keep), `omitted_fact` (verbatim, the
  offset/denominator you leave out; it must be visible in the source evidence), and `claim` (your post text,
  using only numbers from `kept_fact`), e.g. claim "Atlantic City Electric bills are going UP $4.09 a month."
- Data mode: `start_month`, `end_month` (YYYY-MM) and optionally `claim`. The tool refuses windows whose change is
  within 5 points of the honest latest year-over-year change (that wouldn't mislead).
The tool returns a forgery id (`f#`); the claim becomes the post body. In `write_case` add a made-up
`author_name`/`author_handle`, a one-sentence `tell` and an explanation.

Not allowed: changing a number, rounding it into a different claim, inventing a denominator, or using a number
that isn't in the source/data.

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
- Numbers only from sources saved verbatim this run or from the EIA file.
- Posted by a made-up account (`kind: "person"`), never presented as the outlet, the BPU or EIA.
- Keep it about bills and prices; no campaign framing, no blocked topics.

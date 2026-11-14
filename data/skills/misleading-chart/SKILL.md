---
name: misleading-chart
description: Forge a misleading chart from REAL EIA numbers by cropping the y-axis and/or comparing months from different seasons. Use when the case's trick is misleading-chart. The code tool make_chart does the doctoring and computes the honest version.
---

# Misleading chart

## Definition
A chart drawn from real, correct numbers that still gives the wrong impression, because of how it is framed:
a y-axis that does not start at zero (a 26% rise drawn as a cliff), a window that runs from a seasonal low to a
seasonal peak, or two months from different seasons presented as "one year".

## When to use
- The case's trick is `misleading-chart`.
- The topic's research hints list a data series (NJ electricity prices: EIA monthly, ¢/kWh, through 2026-08).
  On other topics `make_chart` isn't offered and the trick isn't planned: never chart NJ power prices on a
  food, sports or science day.
- Best material: series with a strong seasonal swing. NJ prices peak every summer (Jun-Aug), so spring vs.
  summer comparisons look dramatic.

## Forging recipe (allowed operations on real material only)
Call `make_chart` once. You only choose framing; every value comes from the EIA file.
1. Pick 2 months to compare (`months=["2025-04","2026-07"]`), or a `start`/`end` window for a line chart.
   Strong choice: a spring month vs. a summer month 13-16 months later (different seasons, labelled "one year").
2. Set `y_min` (the axis start) just below the smaller value, e.g. `19` for 19.91. It must be at or below the
   smallest value; the tool refuses to hide data.
3. Keep `chart_type="bar"` for two-point comparisons (truncated bars fool people most), "line" for windows.
4. The tool returns a forgery id (`f1`), the honest counterpart (same month a year apart, axis from 0), the
   numbers you may use in the post body, and a suggested body. Write a body that states the shown change
   (e.g. "NJ power prices are up 27% in ONE YEAR."). Numbers not derived from the chart are rejected.
5. In `write_case`, give the doctored post `forgery_id`, a made-up persona (or leave `author_name` empty), the body,
   a one-sentence `tell` and a 2-3 sentence `explanation`.

Not allowed: changing values, inventing months, dropping points from inside a window, or a y_min above the data.

## The tell
The axis does not start at 0, and/or the months compared are from different seasons (or not 12 months apart).
Same month a year apart, the change is much smaller. Example: Apr 2025 19.91 -> Jul 2026 25.19 (+26.5%), but
Jul 2025 -> Jul 2026 is +0.3%.

## How to verify (which evidence tool)
`data` (📊 Check the data): the EIA table and an honest full-range chart from 0 show the real pattern. The
`account` card is a weaker supporting clue (a new, sensational account).

## Diff type
`chart`: `shown` = the chart as posted, `original` = the honest chart (axis from 0, same month a year apart, or
the full range). Filled in by the tool.

## Con lines
- Fooled: "Real numbers, honest-looking bars. I just picked where they start."
- Caught: "Fine. You checked the data. I'll crop it better next time."
- Alternative caught: "You looked at the axis. Nobody looks at the axis."

## Safety limits
- Real EIA values only; the code builds the chart.
- Posted by a made-up account (`kind: "person"`), never as EIA, the BPU or a news outlet; no logos.
- No election, tragedy, health-emergency or minors framing. Keep the post's tone about bills, not politics.
- The honest version must be reachable with the `data` tool, so players can actually catch it.

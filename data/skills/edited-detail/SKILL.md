---
name: edited-detail
description: Forge an edited-detail post by swapping ONE number, date or place in a REAL headline or sentence, posted only by a made-up account. Use when the case's trick is edited-detail. The code tool edit_detail does the swap and records the before/after.
---

# Edited detail

## Definition
A real headline or sentence, copied word for word except for one detail: a number ("$4.09" becomes "$40.90"),
a date ("Thursday" becomes "Monday", "2025" becomes "2026") or a place ("Trenton" becomes "Newark"). It looks
exactly like the real thing because almost all of it is.

## When to use
- The case's trick is `edited-detail`.
- A saved source is a headline (saved with its exact title) or a plain factual sentence with a concrete detail:
  a dollar amount, a percentage, a count, a day or date, a town or county.
- Best material: details that carry the story ("bills drop 5 cents" vs "bills drop 5 dollars"), or that move the
  story somewhere it didn't happen.

## Forging recipe (allowed operations on real material only)
Call `edit_detail(source_id, find, replace)` once.
1. Choose a saved headline or sentence (not a quote: real people's words are only ever cropped, never changed).
2. `find` = the exact detail as it appears in the text (up to 4 words): a number, a date word, or a place name.
3. `replace` = a different detail of the same kind (number for number, date for date, place for place). The tool
   refuses anything else, and refuses to touch any other word.
4. Make the swap matter but stay plausible: a 10x number, a different year, a neighbouring town.
5. In `write_case`, the doctored post gets `forgery_id` and a made-up persona (or leave `author_name` empty); the
   edited text becomes the post body (you may add a few words of reaction around it, but no new numbers, no
   new claims, and no "NPR:" / "NPR reports" credit: the source label already cites the outlet). Don't also use
   the same source as a real post.

Not allowed: changing more than one detail, editing quotes, inventing a headline, or posting it as the outlet.

## The tell
The original headline or sentence, in the source, has a different number, date or place. Everything else matches
word for word, which is what makes it convincing.

## How to verify (which evidence tool)
`source` (📄 Open source): the real article passage or headline, with its link. Comparing the two side by side
exposes the swapped detail. The `account` card is a weaker clue.

## Diff type
`detail`: `shown` = the edited text, `original` = the real text, `changed` = `[{"from": "...", "to": "..."}]`.
Filled in by the tool.

## Con lines
- Fooled: "One little number. Nobody ever checks the little number."
- Caught: "You compared it word for word. Who does that?"
- Alternative fooled: "Same headline, same outlet font in your head. Different town."

## Safety limits
- Only on posts from made-up accounts (`kind: "person"`), never presented as the outlet; no logos; the in-game
  watermark stays, and the reveal shows the full before and after.
- Never on quotes from real people, and never a swap that makes a real person or business look criminal or
  dangerous.
- No blocked topics (elections, tragedies, health emergencies, minors), in the original or the replacement.

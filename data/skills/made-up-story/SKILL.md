---
name: made-up-story
description: Forge a made-up-story post, a short false news claim the Con invents, modeled on a REAL saved story and posted only by a made-up account. Use when the case's trick is made-up-story. The code tool make_tall_tale checks it and records the closest real story for the reveal.
---

# Made-up story

## Definition
A whole claim the Con invents: one or two sentences in the voice of a viral post ("Scientists just taught
octopuses to open childproof jars in exactly 9 seconds."). It borrows the subject and feel of a real story the
researcher saved, but the claim itself is false, and no outlet ever ran it.

## When to use
- The case's trick is `made-up-story`.
- Pick a saved real story with a vivid subject (an animal, a food, an odd science result, a place in New Jersey).
  That story becomes the "closest real story" a player sees when they check.
- Vary the difficulty across a day: an easier one (two clear tells) and a harder one (one subtle tell, close to a
  real weird story). Never make one that's impossible to tell from real news without opening the source.

## Forging recipe
Call `make_tall_tale(source_id, claim)` once per made-up post.
1. `source_id` = the real story it borrows from. Read it first: your claim must say something DIFFERENT, not copy
   or tweak it (the tool refuses near-copies).
2. `claim` = 8-45 words, false, plausible at first glance, with at least one tell from the list below built in.
3. In `write_case`, the doctored post gets the `forgery_id` and a made-up persona (or leave `author_name` empty).
   The claim is the post body; add no extra words. Don't also use the same source as a real post.
4. Real posts stay word for word. Include at least one startling-but-true real post (`real_suspicious`), so
   "weird" never means "fake". On made-up days, real posts shared by made-up accounts show no source label either,
   so "no source" is a reason to check, never the answer by itself.

## The tell
It must be FAIR: a careful reader can catch it from the card, without opening evidence. Build in one or two:
- **Too neat:** suspiciously round or precise numbers ("exactly 1,000", "in 9.2 seconds"), a perfect punchline.
- **Too certain:** "proves", "confirmed", "for the first time ever", with no "may", "might" or "a study suggests".
- **Too far:** one step past anything plausible (a mouse that learns to open a fridge; a diner that serves a
  40-foot pancake every day).
- **Nothing behind it:** no study, place or outlet a person could look up, just "experts say".
- **Emotional bait:** "you won't believe", "share before it's deleted".
In write_case, the `tell` (one sentence) names the clue a player could see ON THE CARD, e.g. "No study or outlet
named, and '9 seconds' is suspiciously exact for an octopus." The `explanation` (2-3 sentences) says plainly that
the Con made it up, what the closest real story actually says (outlet and gist), and the habit that would have
caught it ("look for who reported it").

## How to verify
`source` (📄 Open source): shows the closest real story, which says something different. The `account` card shows a
made-up account, which real reposts have too, so it's a weaker clue.

## Diff type
`made_up`: `{type, shown, real, outlet, date, url}`, the Con's claim beside the closest real story. The tool fills it
in; the reveal shows "The Con made this up" and the real story.

## Con lines
`con_line_fooled` gloats about how plausible it sounded ("It sounded just like the news, didn't it?");
`con_line_caught` admits it was too neat ("Too tidy? Fine. Real news is messier.").

## Safety limits
The tool refuses: names of people (real or realistic), quote marks (never put words in anyone's mouth), any real
outlet credited ("NPR says"), health or medical claims, and blocked topics (tragedies, crime victims, minors,
elections, emergencies). Keep it light: animals, food, odd science, quirky places. Made-up stories only ever come
from made-up accounts, carry the training-material watermark, and the reveal always says the Con made it up.

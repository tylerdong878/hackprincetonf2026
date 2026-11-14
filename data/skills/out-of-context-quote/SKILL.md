---
name: out-of-context-quote
description: Forge an out-of-context quote by cutting a REAL saved quote so its meaning flips or inflates (drop "net", "not yet", "but", "if"). Use when the case's trick is out-of-context-quote. The code tool crop_quote does the cut; nothing can be added.
---

# Out-of-context quote

## Definition
A real person's real words, cut so they say something they didn't mean. Every remaining word is genuine and in
its original order; the deception is in what was left out (a qualifier, a condition, the second half of a
sentence).

## When to use
- The case's trick is `out-of-context-quote`.
- A saved source is a quote whose meaning hinges on a word or clause, e.g.
  "these actions will result in no **net** increase in electricity rates" (drop "net": it now promises no
  increase at all), or a long quote whose dramatic middle can be lifted out ("really unsustainable price hikes
  in the utility and electricity bills").

## Forging recipe (allowed operations on real material only)
Call `crop_quote(source_id, keep_text)` once.
1. Choose a saved quote (`s#` with a speaker).
2. `keep_text` = the words you keep, in the quote's own order. You may skip words: at most 2 cuts inside the
   quote, each at most 8 words, and you may trim the start and end. You cannot add, reorder or change words.
3. Keep at least 4 words, and make sure the cut changes the meaning (a cut that changes nothing will be caught
   by the blind solver as unfair, or worse, isn't a trick).
4. The tool returns a forgery id (`f#`), the shown quote and the removed words. In `write_case`, the doctored
   post gets `forgery_id`, a made-up `author_name`/`author_handle`, and an optional short body that reacts to
   the cropped quote (e.g. "BPU just promised NO rate increase. Screenshot this."). The body may not add numbers
   that aren't in the real quote.
5. Do not also use the same source as a real post in the case.

## The tell
The full sentence, in the source, contains the words the post removed (e.g. "net"), which change its meaning.

## How to verify (which evidence tool)
`source` (📄 Open source): the original passage with the full quote highlighted, plus the sentences around it
(e.g. the $4.09 rise and $4.14 drop that explain "no net increase").

## Diff type
`quote`: `shown` = the cropped quote, `original` = the full quote, `removed` = the words or phrases cut. Filled
in by the tool.

## Con lines
- Fooled: "I didn't change a single word. I just stopped quoting early."
- Caught: "You read the whole sentence. How thorough. How annoying."
- Alternative fooled: "One little word. That's all it took."

## Safety limits
- Only crops of quotes saved verbatim this run; never invent or paraphrase a quote and attribute it to a real
  person.
- The post comes from a made-up account (`kind: "person"`), never from the outlet that published the quote or
  from the speaker; the quote is attributed to its real speaker only because the words are theirs.
- NJ Monitor is CC BY-NC-ND: short excerpts only, with attribution and link in the evidence.
- No crops that make a real person appear to say something defamatory, hateful or about blocked topics.

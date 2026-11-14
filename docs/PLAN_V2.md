# Grain of Salt v2: make it fun, fast, and visibly smart

**Why change:** teammate feedback is that v1 feels like homework. You read 4 posts in a feed, click Real/Fake, and the AI is invisible because it only runs offline.
**Goal:** keep what's strong, change how it plays.
- **Keep:** real material, doctored posts, scoring both kinds of mistakes (the research twist), the blind solver, human editor approval.
- **Change:** a 2-minute daily ritual, an AI you play *against* live, and content that's actually fun.

Research behind this: RESEARCH.md, plus the v2 research notes.
- Human or Not and the Microsoft real-or-AI quiz spread on crowd stats ("32% can't tell", "62% correct").
- Gandalf (1M+ players) and Death by AI (20M players) show an AI character you try to beat is the hook.
- Factitious spread mostly through classrooms during school hours. That's the "homework" trap.
- Wordle and Connections: one puzzle a day for everyone, short, shareable grid, streaks.

---

## 1. Three modes

### A. 🧂 The Daily Grain (the main mode, for everyone)
- **One puzzle a day,** the same for everyone, numbered: *Grain of Salt #3*. Takes about 2 minutes.
- **5 cards, one at a time** (not a 4-post feed). Each card is a post: a quote, chart, stat or headline. Topics vary by day ("Jersey Weird", "Your Bills", "Sports Stats", "Science Says").
- **Every daily mixes:**
  - absurd-but-true posts, which punish blind doubt;
  - doctored posts;
  - plainly real posts.
  - Some days have no fakes at all.
- **On each card:**
  - Two big buttons, **Real** and **Doctored**. Choosing Doctored opens a quick trick picker.
  - **🔍 Check:** you get 3 magnifiers per day. Each opens one evidence view inline on the card (source, data, or account).
- **Instant reveal after each answer.** The card flips to show:
  - a stamp (CAUGHT / TRUSTED / FOOLED / FALSE ALARM);
  - a one-line tell;
  - a mini before-and-after;
  - the Con's quip;
  - the **crowd stat**: "62% of detectives said Real". Only real counts, shown once a post has 10 or more answers; below that it says "Be one of the first 10".
- **End card:**
  - score;
  - emoji grid;
  - **Gullible ↔ Paranoid meter**, showing how your guesses leaned;
  - Detective rating;
  - the Con's verdict on you;
  - **streak**;
  - **Share** (text only: number, grid, lean; never fake content);
  - countdown to tomorrow;
  - a "Try to con the Con →" button.
- **Difficulty by weekday,** like NYT puzzles: Monday easy, Saturday hard. Optional.
- **From the daily-games research:**
  - **Say the range, not the count.** The briefing says "0–3 doctored today."
  - **Every fake must be provable from the in-game evidence alone.**
  - **Under 4 minutes, no sign-up.** The day resets at midnight ET.
  - **Streaks count days played,** not perfect days, so they're forgiving.
  - **The archive is free.**
  - **Rarity:** the reveal can say "Only 18% caught this one", an idea from Krillion's rarity scoring and Immaculate Grid.
  - **Share grid emoji:**

| Emoji | Meaning |
|---|---|
| 🧂 | caught a fake |
| 🟩 | trusted a real post |
| 🟥 | false accusation |
| ⬛ | missed a fake |

  Example: `Grain of Salt #12 🧂 4/5 🔥3` on one line, then `🟩🟩🧂🟥🟩`.
- **Why it fits the budget:** one new case per day = one pipeline run (about 15–25 model calls), which fits the free tier.

### B. 🎭 Con the Con (reverse mode: live AI, the demo centerpiece)
- **Pick a real post** from the **Fool Deck**: cached, verified real material (quotes, charts, stats).
- **Doctor it with limited, safe tools:**
  - ✂️ **Crop:** tap words to *remove* from a real quote. Deletion only; you can't add words.
  - 📉 **Axis:** a slider for where the chart's y-axis starts.
  - 🗓️ **Window:** pick which two months to compare.
  - 🔢 **Drop context:** hide the denominator or the offsetting number.
  - 🙈 **Leave it real:** a bluff. Submit the untouched post.
- **Submit, then "The Con is inspecting…".** One live model call. The Con checks the evidence kit, then returns a verdict, its trick guess and 2–3 short lines of reasoning, shown as the Con talking.
- **Outcomes:**

| You did | Con says doctored | Con says real |
|---|---|---|
| Doctored it | **Caught you** | **You fooled the Con** |
| Left it real (bluff) | **False alarm: the Con doubted the truth.** You win. | **The Con trusted the truth.** A draw. |

- **Scoreboard:** "You fooled the Con 2/5". It saves the funniest Con lines.
- **The AI story for judges:** the *same* blind-solver agent that checks every Daily is fair is the opponent you're trying to fool.
- **Cost:** 1–2 calls per round. Results are cached by (post, edit), so repeats are free.
- **Without a key, or if the call fails:** show cached real Con verdicts for that post if we have them; otherwise say plainly "the Con is asleep". Never invent an AI verdict.

### C. 🗂️ Case Files (an archive of extra cases, the v1 feed)
- Keep the v1 four-post feed, the Editor's Desk queue, approval and the Workshop replay.
- Positioned as extra cases for players who want more. A human editor approves every case on the Editor's Desk.

---

## 2. Content: make it fun and stay factual
- **Fun real material:**
  - absurd-but-true headlines from reputable outlets;
  - sports and pop-culture stats with public data;
  - "sounds fake but it's true" science;
  - Jersey weirdness.
- **Every real item has to pass all of these:**
  - verbatim, with a source URL;
  - no tragedies, no minors, no elections near voting day, no active health emergencies;
  - no fabricated quotes from real people.
- **New trick, "edited detail":** swap a number, date or place in a real headline. It's allowed only:
  - on posts from **made-up accounts**;
  - with the watermark;
  - with a full before-and-after in the reveal.
- **The Fool Deck is built from the same verified material bank.**

---

## 3. The 2-minute judge demo (v2)
| Time | What happens |
|---|---|
| 0:00–0:10 | "Grain of Salt: the daily game where an AI con artist doctors real news, and you score points for knowing what's *true*." |
| 0:10–0:50 | The judge plays 3 Daily cards. One absurd-but-true headline, one doctored chart (the axis drops), one real. Instant reveals plus crowd stats from HackPrinceton players. |
| 0:50–1:40 | **Con the Con:** the judge crops a real quote or sets a chart axis, and the Con reasons live and rules. If they bluff with an untouched post and the Con calls it fake: "See? Even the AI over-doubts. That's what we train against." |
| 1:40–2:00 | End card with the Gullible↔Paranoid meter, plus the research line: "Earlier games made people paranoid. We score discernment." Daily = habit, Case Files = more to play. |

- **LangChain add-on:** the Workshop replay of the real overnight build of today's Daily, then show that the Con judge is the blind solver.
- **Saturday evening:** get HackPrinceton attendees playing, so the crowd stats are real by Sunday morning.

---

## 4. Build split (about 29 hours left; MVP by Sat 6pm)

| Area | Work |
|---|---|
| Backend | Daily endpoints, per-card answers, crowd stats, lean meter, streaks, Con the Con endpoints that call the pipeline's judge |
| Pipeline | `judge_post()` reusing the blind solver, deterministic Fool Deck edits, `--daily-date` builds |
| Frontend | New Home, Daily card flow, end card, Con the Con editor plus a live verdict scene; keep Case Files and the Editor's Desk |
| Content | A verified material bank of fun real items; assemble 5 seed Dailies plus the Fool Deck |
| Team | $10 OpenRouter credit decision (raises the cap from 50 to 1,000 calls a day); recruit testers Saturday |

The API additions are in CONTRACT.md §7.

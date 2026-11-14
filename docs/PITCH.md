# Grain of Salt: Pitch Kit (v2, entertainment-first)

Everything for judging day: the 2-minute script, sponsor add-ons, judge Q&A and a Devpost draft.
Facts and sources are in [RESEARCH.md](RESEARCH.md). The v1 classroom script is in git history.

**The one idea to land:** *you can fool an AI con artist, and it can fool you.* Lead with the game. The research twist is a game rule, and media literacy is what players take away without being told.

---

## The one-sentence version
**Grain of Salt is a 2-minute daily game: an AI con artist doctors real news posts, you catch the fakes without doubting the true ones, then you turn the tables and try to fool the Con.**

Tagline: *Don't believe everything. Don't doubt everything.*

---

## 2-minute table demo
**Roles:** 3 speakers (A, B, C) plus 1 operator (D).
- **D** runs the laptop, keeps a timer and has the LangSmith tab and the backup laptop ready. D doesn't speak unless asked a technical question.

**Before each judge arrives (D):**
- Today's Daily Grain is open at card 1, in a fresh player session so it isn't already played.
- Con the Con is preloaded with a deck post, at **Street Con** (level 2).
- Sound is on, but quiet.
- The budget panel shows live calls left. If live calls are at 0 or the API is down, use **⚡ Replay**. It's a real cached verdict, so say so if asked.

| Time | Who | Say / do |
|---|---|---|
| 0:00–0:10 | **A** | "Every day, an AI con artist doctors real news. Five posts, two minutes. Catch the fakes, but don't doubt the true ones. Try today's." *Turn the laptop to the judge.* |
| 0:10–0:45 | **Judge plays 2 cards. A** reacts. | Let them tap. After each instant reveal, point at one thing: the stamp, the side-by-side, or the crowd line ("Only 8% caught this… *One in a shaker*, +100"). If they false-alarm: "Real! Doubting the truth costs points here." |
| 0:45–1:20 | **B** | "Now flip it. **Con the Con**: you doctor a post, and a live AI agent decides whether it's real." *Judge picks one edit (crop the quote, drop the axis, cut the window).* "The Con gets one evidence check, the same tools you had…" *Verdict lands.* **FOOLED THE CON** → "You beat it." **BUSTED** → "It checked the source. Want to try Master Con?" |
| 1:20–1:40 | **C** | *Point at the Gullible ↔ Paranoid meter.* "Earlier fake-news games had a hidden flaw. A 2023 reanalysis found they mostly made players doubt *everything*, true news included. So in our game, paranoia loses points too. A grain of salt, not the whole shaker." |
| 1:40–2:00 | **C** | "New puzzles come from LangChain Deep Agents: a researcher, a forger and a blind solver that has to crack it fairly. Then a human editor approves it. All on free models. There's one waiting in the editor's queue right now." *Optional last line:* "New Jersey now requires news literacy in every school. This is the version people actually want to play." |

**Delivery notes:**
- **The judge plays, not us.** Their reaction is the pitch. If they won't touch it, A plays and asks, "Which one would you flag?"
- **Every outcome is a good outcome.** Fooled → show the trick. False alarm → "that's the point." Beat the Con → celebrate. Busted → offer a harder level.
- **Keep the crowd line honest.** Crowd numbers only show at 10+ players. If none show yet, skip that beat. Never say a number that isn't on screen.
- Don't explain the scoring table. The meter does it.

### Fallbacks
| Problem | Do this |
|---|---|
| Live Con call fails or is slow (> 15 s) | Hit **⚡ Replay**: "here's one it judged earlier." |
| Laptop or Wi-Fi dies | D swaps in the backup laptop running `localhost:8000`. It works offline except for live Con calls. |
| Judge has 30 seconds | Use the 30-second version below, and hand them one card. |

---

## 30-second version
"Grain of Salt is a daily game. An AI con artist doctors real news, and you catch the fakes. But doubting a true post costs points too, because earlier games just taught people to distrust everything. Then you flip it and try to fool the Con, a live AI agent. New puzzles are built by Deep Agents and approved by a human editor."

---

## Sponsor add-ons (about 30 seconds each)

**LangChain (Deep Agents).** Their criteria are complexity, effective use of Deep Agents, and the demo.
- **Say:** "Building one puzzle is a long job with checks. The orchestrator plans with todos. Three sub-agents, each with its own context, do the research, the forging and the blind solving. Each trick is a `SKILL.md` that loads only when it's needed. Everything lands as files. A human-in-the-loop interrupt holds the puzzle for the editor."
- **Show, in order:**
  1. The LangSmith trace "Grain of Salt · build daily-2026-11-18": sub-agent spans, skill loads and the blind-solver verdict.
  2. **Approve the queued AI-built Case File live** in the Editor's Desk, then open Case Files and play it straight away. (Dailies only go live on their date; Case Files go live when they're approved.)
  3. The "Con the Con · live judge" trace from the round they just played.
- **If asked about rejection:** 11-19 went through a reject-and-revise loop, and its trace shows the second pass.

**Amazon (Practical AI).** Their criteria are creativity, usefulness, technical quality and UX.
- **Say:** "It's a daily habit that takes two minutes. It works on a phone and needs no account. Puzzles are pre-built, so play is instant and costs nothing. Only Con the Con calls a model live, and that's capped."
- **Show:** the share grid, the phone layout, and the README.

---

## Judge Q&A

| Likely question | Answer |
|---|---|
| **"Is this a game or a lesson?"** | "A game. You come back for the streak, the share grid and beating the Con. Learning is the side effect, the way GeoGuessr teaches geography." |
| **"Why would I come back tomorrow?"** | "There's a new puzzle every day, plus streaks, a spoiler-free share grid and rare-catch bonuses when few people spot something. And the Con has three boss levels to beat." |
| **"Can you actually beat the Con?"** | "Yes, on Rookie and Street. Master Con gets the full model plus a source check, and it's tough. In our tests it caught every doctored edit. That's why we added levels." |
| **"Isn't this just Bad News?"** | "In Bad News you play a scripted fake-news producer. A 2023 reanalysis found it mostly made people more suspicious of everything. We score both mistakes, some days are all real, and our puzzles come from real news." |
| **"Aren't you making misinformation?"** | "The tricks only reframe real material: a cropped quote, a truncated axis, a cherry-picked window. We never invent quotes from real people. Doctored posts come only from made-up accounts, every one gets stamped at the reveal, share cards hold no content, and a human approves every puzzle." |
| **"How do you know the real posts are real?"** | "The researcher can only save word-for-word text with a source link, and every real card links to its source." |
| **"What about AI images and deepfakes?"** | "A Google study of about 136,000 fact-checks found that the most common media misinformation is real images in a false context. We start there. AI-written posts are on the roadmap." |
| **"Was the puzzle I just played built by the AI?"** | "Not today's. Launch week was curated by us with a scripted builder that checks every quote against its source page. The Deep Agents pipeline builds the new ones, and each waits for a human editor. Here's one it built tonight." *Show the trace, approve the queued Case File, and play it.* |
| **"Why Deep Agents instead of one prompt?"** | "Each job has its own context, the blind solver gives a validation loop, the files can be audited, and a human approves the result. One prompt can't check its own fairness." |
| **"What does it cost to run?"** | "Nothing right now. It uses free open models through OpenRouter. A puzzle is built once and played by everyone, so cost doesn't grow with players. Live Con rounds are capped per day and per player." |
| **"What's the business?"** | "It's a free daily game that grows through share grids. Later, sponsored themed weeks with newsrooms, and an editor tool that libraries and schools can use to make their own puzzles." |
| **"Political bias?"** | "The tricks are about technique, not ideology. We skip elections, tragedies, emergencies and minors." |
| **"Why the name?"** | "Take what you read with a grain of salt. Not the whole shaker." |

---

## How each judging criterion is covered

| Criterion | What judges should notice | Say or show |
|---|---|---|
| **Creativity** | The two-way twist: you catch the Con, then you con the Con. Paranoia costs points. | Con the Con, and the meter. |
| **Utility** | It's a polished, replayable daily game that works on a phone. | A live round, the share grid, the Editor's Desk. |
| **Charity** | It trains the real skill (discernment), and it's designed safety-first. | The research line, plus the safety answers above. |
| **Avidity** | The whole team is in it, the Con has personality, there's a roadmap. | Everyone speaks, the Con's taunts, "an AI-built puzzle is waiting in the editor's queue." |

---

## Pitch don'ts
- Don't say "proven to work," "first ever," or "the standards are in effect."
- Don't say "Bad News doesn't work." Say "a 2023 reanalysis found…"
- Don't call it a classroom tool or a lesson. It's a game.
- Don't show a real outlet's name next to doctored content.
- Don't quote a crowd percentage that isn't on screen.

---

## Devpost draft
**Name:** Grain of Salt
**Tagline:** Don't believe everything. Don't doubt everything. A 2-minute daily game where an AI con artist doctors real news, and then you try to con it back.
**Tracks:** Entertainment & Media · Best Use of Deep Agents (LangChain) · Best Practical AI Innovation (Amazon) · *(ChatOverflow, if connected)*

### Inspiration
We love daily games like Wordle and GeoGuessr: two minutes, a share grid, and bragging rights. We wanted one where the opponent is an AI con artist. The research gave us the twist. Earlier fake-news games like *Bad News* were meant to make people sharper, but a 2023 reanalysis found they mostly made players doubt *everything*, true news included. So we built a game where being paranoid loses, just like being gullible.

### What it does
- **Daily Grain.** Five real news posts a day. The Con has secretly doctored some of them: a cropped quote, a truncated chart axis, a cherry-picked time window. Some days nothing is fake. Tap Real or Doctored, get an instant reveal with the side-by-side original, and see how everyone else did. Rare catches earn bonus points ("One in a shaker!"). Your Gullible ↔ Paranoid meter shows which way you lean.
- **Con the Con.** Flip roles. You doctor a real post yourself, and the Con, a live AI agent with one evidence check, decides whether it's real. Three boss levels, from Rookie to Master Con.
- **Streaks and share grid.** 🟩 trusted · 🧂 caught · 🟨 false alarm · 🟥 fooled. Spoiler-free.
- **Editor's Desk.** A human puzzle editor approves every AI-built puzzle before it goes live.

### How we built it
- **Puzzle factory:** LangChain **Deep Agents**. An orchestrator plans each puzzle and delegates to sub-agents:
  - A **researcher** saves word-for-word real sources with links.
  - A **forger** applies trick skills (`SKILL.md` files) to real material.
  - A **blind solver**, which never sees the answer key, must crack the puzzle with the player's tools. Unfair puzzles get rejected and rebuilt.
- **Approval and tracing:** a human-in-the-loop interrupt holds each puzzle for the editor, and every build and live judgment is traced in LangSmith.
- **Guardrails in code, not just prompts:** quotes can only be cropped (never rewritten), real posts must be verbatim from a page fetched that run, doctored posts only come from invented accounts, and a topic blocklist keeps out tragedies, minors and elections.
- **Launch week:** the first five dailies were curated by us with a scripted builder that re-fetches every source page and checks each excerpt word for word. The Deep Agents pipeline builds the new ones.
- **The game:** React 19 + TypeScript + Tailwind on FastAPI. Scoring happens on the server, so answers never reach the browser early.
- **Models:** free open models via OpenRouter, NVIDIA Nemotron for building and judging.

### Challenges we ran into
- **Free-tier limits:** 50 requests a day per account. We pre-build puzzles, cache verdicts and cap live rounds.
- **The Con was too good:** it caught every doctored edit at full strength, so we added boss levels.
- **Making fakes subtle but fair:** that's why the blind solver exists.
- **The AI needed an editor:** when we pointed the pipeline at fun topics, its first four puzzles had giveaways (only the fakes lacked source links), realistic-sounding fake names, and one story about a real tragedy. Our editor caught all of it, and we turned each catch into a rule enforced in code.
- **Answers leaking through metadata:** if only fake posts come from unknown accounts, players learn the pattern instead of the skill. Every day now has real posts from unknown accounts too, and the builder fails if any display field gives an answer away.

### Accomplishments that we're proud of
- The blind-solver fairness loop.
- Con the Con, where a live agent judges your forgery.
- A scoring rule that punishes paranoia.
- Every real excerpt in the game is checked word for word against its live source page.

### What we learned
*(Draft; rewrite in your own words.)*
- One research finding (games that train suspicion don't train discernment) changed our whole scoring design.
- Agents are great at the grind (finding sources, applying tricks, testing fairness), but a human editor still catches things no prompt anticipated.
- Free-tier limits shaped the architecture: build each puzzle once and let everyone play it, so cost doesn't grow with players.

### What's next
- Nightly puzzle drops (the pipeline already builds one a night, held for the editor).
- An iMessage daily.
- More tricks, including AI-written posts.
- Themed weeks with local newsrooms and libraries.

**Built with:** python, fastapi, langchain, deepagents, langgraph, langsmith, openrouter, nvidia-nemotron, react, typescript, vite, tailwindcss, recharts

**Before submitting:**
- [ ] Public GitHub repo link
- [ ] Video link (2 minutes or less)
- [ ] Discord usernames of every team member
- [ ] Exactly one main track (Entertainment & Media) plus the special tracks

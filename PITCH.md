# Grain of Salt: Pitch Kit

Everything for judging day: the 2-minute script, short versions, sponsor add-ons, judge Q&A, and a Devpost draft.
Facts and sources are in [RESEARCH.md](RESEARCH.md).
**Demo topic:** NJ electricity prices. The exact posts are in RESEARCH.md §4.2.

---

## The one-sentence version
**Grain of Salt is a detective game where an AI con artist doctors real New Jersey news, and you learn to tell what's real. It scores you on discernment, not suspicion.**

---

## 2-minute live demo script
**Setup:**
- The laptop faces the judge, plugged in. The demo case is loaded.
- The Con's Workshop panel is open in replay mode.
- **The demo case:** 4 posts on NJ electricity prices.
  - **One doctored:** a chart from a made-up account. It runs April 2025 to July 2026 on an axis that starts at 19, so the rise looks like 27%.
  - **One real but sounds fake:** the BPU says bills "jumped roughly 20 percent last year."
  - **Two real quotes.** One of them ("no net increase in electricity rates") seems to contradict the chart, so judges often suspect it.

| Time | Who | Say / do |
|---|---|---|
| 0:00–0:12 | **A** | "Would you trust this feed? Grain of Salt is a detective game. An AI con artist builds cases from real New Jersey news and doctors some of the posts. Maybe. Want to play one?" *Hand over the laptop.* |
| 0:12–0:50 | **Judge plays. B narrates the Workshop panel.** | "While you investigate, here's how the Con built your case. A researcher agent pulled real sources, with links. A forger picked one trick. Then a **blind solver**, an agent that never sees the answer key, had to crack the case with the same clues you have. If it can't, the case gets rejected as unfair." |
| 0:50–1:15 | **A** (reveal) | *If they were fooled:* "The axis starts at 19 cents, and it compares April 2025, before last summer's spike, with July 2026. July to July, prices rose 0.3%. In one study, 83% of people were fooled by cropped axes, even after a warning." *If they accused the real post:* "That one was real. Surprising, but true. And that's the point." |
| 1:15–1:40 | **C** | "A 2023 reanalysis found that earlier games like *Bad News* mostly made players doubt **everything**, real news included. So we score both mistakes: getting fooled, and accusing real posts. Some cases have nothing fake at all. A grain of salt, not the whole shaker." |
| 1:40–2:00 | **D** | "New Jersey now requires information literacy from kindergarten through 12th grade, and the standards are being finalized now. Teachers approve every case before students see it, the Con adapts to each student's weak spots, and it all runs on free open models. Next: a daily case for every classroom in the state." |

**Delivery notes:**
- Let the judge *play*. Their reaction is the pitch.
- Every team member speaks. That's what the Avidity score rewards.
- If the judge won't touch the laptop, A plays and asks, "Which one would you flag?"
- **The reveal works either way.** If they were fooled, show the trick. If they wrongly accused the real post, explain why that matters. Don't apologize for either outcome.

---

## 30-second version (rushed judge)
"Grain of Salt is a daily detective game. An AI con artist doctors real New Jersey news, and you decide what's real. Earlier games like this made people doubt everything, so we score both getting fooled and false accusations. Under the hood, Deep Agents build each case with a researcher, a forger, and a blind solver that proves every case is fair. New Jersey now requires this in every K-12 school."

---

## Sponsor add-ons (about 30 seconds each)

**LangChain (Deep Agents).** Their criteria are complexity, effective use of Deep Agents, and the demo.
- "Building a case is a long, multi-step job with checks. One prompt can't do it.
  - The orchestrator plans with todos.
  - Three sub-agents with their own context do the research, the forging, and the blind solving.
  - Each trick is a `SKILL.md` that's loaded only when it's needed.
  - Everything lands as files: sources, the case, the answer key, the solver log.
  - A human-in-the-loop interrupt holds each case for teacher approval."
- *Show:* the case folder, one `SKILL.md`, the solver log (including a rejected attempt), and the approval screen.

**Amazon (Practical AI).** Their criteria are creativity, usefulness, technical quality and UX.
- "Who it's for: New Jersey high school students and the teachers who now have to teach information literacy.
- It plays from a pre-built case bank, so it's fast and works on locked-down school laptops with no web access.
- The README covers setup and the design."
- *Show:* the teacher queue and a student's Dossier.

---

## Judge Q&A prep

| Likely question | Answer |
|---|---|
| **"Isn't this just Bad News?"** | "Bad News is scripted, and you play the fake-news producer. A 2023 reanalysis found it mostly made people more suspicious of everything. Ours builds fresh cases from real news, scores both kinds of mistakes, and adapts to each player." |
| **"Aren't you generating misinformation?"** | "We almost never fabricate anything. The tricks reframe real material: a real quote with its context cut off, a real dataset with a misleading axis. We never invent quotes from real people. Every post is watermarked as training material, doctored posts get stamped, share cards contain no content, there's a topic blocklist, and a teacher approves every case." |
| **"How do you know the 'real' posts are real?"** | "The researcher agent can only save word-for-word quotes and numbers, each with a source link. If it can't be verified, it can't be used. Players can open the source in the game." |
| **"Does it actually work?"** | "We don't claim it's proven yet. It's built on what the research found: learning from labeled true and false examples with feedback improved discernment, and lateral reading is teachable in under six hours. Because we measure hits *and* false alarms, a teacher can see whether a student is actually improving. The next step is a classroom pilot." |
| **"What about deepfakes and AI images?"** | "A Google study of about 136,000 fact-checks found the most common media misinformation is real images with false context, not AI fakes. We start there. AI-written posts are next on the roadmap." |
| **"Why would a student come back?"** | "A daily case, streaks, a shareable score grid, and the Con. He has a personality, he notices your weak spots, and he taunts you about them." |
| **"How does it adapt?"** | "It tracks misses and false alarms for each trick. Cases are mostly your weak spots, some review, and something new. If you're over-suspicious of charts, the Con shows you *honest* charts." |
| **"Why Deep Agents instead of one prompt?"** | See the LangChain add-on. "Separate context for each job, a validation loop, files we can audit, and a human approval step." |
| **"What does it cost to run?"** | "Nothing right now: free open models through OpenRouter. And a case is built once and then played by every student, so cost doesn't grow with students." |
| **"Business model?"** | "Free for students. Districts or grants pay for the teacher dashboard. Checkology shows the demand: more than 22,000 educators used it last school year. And school librarians helped write New Jersey's standards, so they're our natural channel." |
| **"Isn't electricity a political topic?"** | "Everyone pays the bill, which is why it's a good test. We only use the state regulator, federal EIA data and straight news coverage. The lesson is about technique, like how a chart's time window can exaggerate a real rise, not about who's to blame." |
| **"Political bias?"** | "Tricks are about technique, not ideology. Topics avoid elections near voting day, tragedies and health emergencies, and teachers can block more." |
| **"What if the AI makes a bad case?"** | "The blind solver rejects unfair ones and the orchestrator retries. Then a human approves it. Bad cases don't reach students." |
| **"Why the name?"** | "Take what you read with a grain of salt. Not the whole shaker. That's the skill we're training." |

---

## How each judging criterion is covered

| Criterion | What judges should notice | Say or show |
|---|---|---|
| **Creativity** | The flip: the AI is the con artist, and you're scored on discernment, not suspicion. | The reveal plus the "earlier games made people doubt everything" line. |
| **Utility** | It works end to end, it's replayable, and teachers can actually use it. | A live round, the Dossier, the teacher queue. |
| **Charity** | NJ's K-12 requirement, students' weak online reasoning, a safety-first design. | The NJ law, the Stanford stat, the safety rules. |
| **Avidity** | The whole team is excited, the product is polished, there's a roadmap. | Everyone speaks, the Con's personality, "a daily case for every classroom." |

---

## Pitch don'ts
- Don't say "proven to work," "first ever," or "the standards are in effect."
- Don't say "Bad News doesn't work." Say "a 2023 reanalysis found..."
- Don't show a real outlet's name next to fabricated content. Fabricated posts only come from made-up accounts.
- Don't let a share card or screenshot include an unstamped fake.

---

## Devpost draft
**Name:** Grain of Salt
**Tagline:** Don't believe everything. Don't doubt everything. A detective game where an AI con artist doctors real New Jersey news, and you learn to tell the difference.
**Tracks:** Entertainment & Media · Best Use of Deep Agents (LangChain) · Best Practical AI Innovation (Amazon) · *(ChatOverflow, if connected)*

### Inspiration
New Jersey became the first state to require information literacy from kindergarten through 12th grade, and the new standards are being finalized right now. Students need practice: in a Stanford study of 3,446 high schoolers, only 3 of more than 3,000 tracked down the original source of a misleading video. Games like *Bad News* tried to help, but a 2023 reanalysis found they mostly made players doubt *everything*, including real news. We wanted a game that trains the actual skill: telling the difference.

### What it does
- Every case is a feed of posts about a real New Jersey story.
- The Con, an AI con artist, may have doctored some of them by cutting a quote's context, truncating a chart's axis, or dropping a statistic's denominator. Some cases have nothing fake at all.
- Players investigate with built-in evidence tools, mark each post real or doctored, and name the trick.
- The reveal shows the doctored post next to the original, with the change highlighted.
- Players are scored on **discernment**: getting fooled costs points, and so does accusing a real post.
- The Con remembers which tricks fool each player and adapts.
- Teachers approve every case before students see it.

### How we built it
- **Case pipeline:** an offline pipeline on LangChain's **Deep Agents**. An orchestrator plans each case and delegates to sub-agents:
  - A **researcher** saves word-for-word real sources with links.
  - A **forger** applies trick "skills" (`SKILL.md` files) to real material.
  - A **blind solver**, which never sees the answer key, must crack the case with the player's own tools. Unfair cases are rejected and rebuilt.
- **Storage and approval:** everything is written as auditable files, and a human-in-the-loop interrupt holds each case for teacher approval.
- **The game:** React + TypeScript on a FastAPI backend that scores verdicts on the server, so answers never reach the browser early.
- **Models:** free open models via OpenRouter: NVIDIA Nemotron 3 Ultra for planning and forging, and Nemotron 3.5 Super VL for the solver, which reads the rendered charts.

### Challenges we ran into
*(Fill in on Saturday night. Likely: making fakes subtle but fair, free-tier rate limits, and keeping the answer key off the client.)*

### Accomplishments that we're proud of
*(Fill in. E.g., the blind-solver validation loop, the side-by-side reveal, discernment scoring.)*

### What we learned
*(Fill in. E.g., why the research on suspicion versus discernment changed our design.)*

### What's next
- A daily statewide case.
- A teacher dashboard showing which tricks a class falls for.
- More tricks, including AI-written posts and fake experts.
- A classroom pilot with New Jersey school librarians.

**Built with:** python, fastapi, langchain, deepagents, langgraph, openrouter, nvidia-nemotron, react, typescript, vite, tailwindcss, recharts

**Before submitting:**
- [ ] Public GitHub repo link
- [ ] Video link (2 minutes or less)
- [ ] Discord usernames of every team member
- [ ] Exactly one main track (Entertainment & Media) plus the special tracks

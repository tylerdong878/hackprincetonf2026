## Inspiration
We're all hooked on daily games. **Wordle**, **Krillion**, the kind you play in two minutes and then send to the group chat to brag. We wanted one where you're actually up against someone, and an AI con artist felt like the right villain for 2026.

Then we read up on the fake-news games that already exist. _Bad News_ is the famous one: you play a fake-news tycoon and learn the tricks by using them. But a [2023 reanalysis](https://pubmed.ncbi.nlm.nih.gov/36996156/) (Modirrousta-Galian & Higham) found it mostly made people call everything fake, real news included. Players weren't getting better at spotting fakes. They were just getting more suspicious of everything.

That flipped our whole design. **In Grain of Salt, doubting a true post costs you points, same as falling for a fake one.** Fake news is a problem, but so is the cynicism that follows it: if people stop trusting real news, the fakes win anyway. _Don't believe everything. Don't doubt everything._

## What it does
**🧂 The Daily Grain.** Every day there are five real news posts, and the Con (our cartoon villain) has doctored some of them. Maybe he cut half a quote, or started a chart's axis at 19 instead of 0, or dropped the "in two years" off a statistic. Some days he doesn't touch anything, and those days are weirdly the hardest.

You mark each card **Real** or **Doctored** and it flips over right away to show you the original next to what you saw.

- Catching a fake is **+100** (+50 more if you name the trick).
- Calling a real post fake is **−50**.
- Once enough people have played, you see how everyone else did. If almost nobody caught it, you get a bonus: _Rare catch_ is +50, _One in a shaker_ is +100.

A meter at the end tells you which way you lean:

$$\text{lean} = \text{false-alarm rate} - \text{miss rate}$$

Too negative and you're gullible. Too positive and you're paranoid. The share grid has no spoilers: 🟩 trusted, 🧂 caught, 🟨 false alarm, 🟥 fooled.

**🎭 Con the Con.** This is our favorite part. You doctor a real post yourself and send it to the Con, a live AI, to see if he can tell. There are three bosses:

- **Rookie Con** just eyeballs it.
- **Street Con** gets to check one piece of evidence.
- **Master Con** gets the evidence and the big model, and he's tough.

**💬 Play over iMessage.** Text our number "play" and today's Grain arrives one card at a time. Reply REAL or FAKE ("sus", "cap" and 👎 work too), name the trick, text CHECK to open a clue, or ask for a HINT. It uses the same scoring and crowd stats as the website, sends a 9am reminder, and a dry detective partner chats back if you just want to talk it through.

## How we built it
The puzzles come from a pipeline we built on [LangChain Deep Agents](https://github.com/langchain-ai/deepagents). An orchestrator plans each puzzle as a todo list and hands the work to three sub-agents:

- **Researcher:** pulls stories from news feeds. It can only save text that appears word for word on a page it actually fetched, and it keeps the link.
- **Forger:** picks up one trick (each trick is its own `SKILL.md` file) and applies it to the real text in code. It can delete words from a quote, but it can never write new ones.
- **Blind solver:** gets the same tools a player gets and never sees the answer key. If it can't solve the puzzle fairly, the puzzle gets thrown out and rebuilt.

When a puzzle is done, a human-in-the-loop interrupt holds it until someone at our **Editor's Desk** approves it. Every build and every Con verdict is traced in [LangSmith](https://smith.langchain.com/), so you can watch the agents work step by step.

The look came from our designer's Figma file: the whole game is laid out like a newspaper front page, with a noir silhouette of the Con as the cover photo. The game itself is **React, TypeScript and Tailwind** on a **FastAPI** backend. Scoring runs on the server, so answers never reach your browser early. Everything runs on free **NVIDIA Nemotron** models through [OpenRouter](https://openrouter.ai/), and the solver uses a vision model so it can actually read the charts.

The iMessage bot runs on [Photon](https://photon.codes)'s API and plays through the same game server, so a text and a tap count toward the same crowd stats.

_One honest note:_ we put together the first week of dailies ourselves, with a script that re-fetches every source page and checks every quote word for word. The agent pipeline builds the new ones.

## Challenges we ran into
**Free-tier limits.** OpenRouter's free tier gives you 50 requests a day, and failed requests count too. We burned through most of a day's worth on Saturday afternoon. After that we built puzzles ahead of time, saved real verdicts so rounds can be replayed for free, and capped live rounds.

**The Con was too good.** At full strength he caught every edit we tried, which is not fun to play against. That's where the three boss levels came from.

**Our first version was boring.** It was a four-post detective case, and honestly it just wasn't fun. Around 3am on Saturday we rebuilt it as a Wordle-style daily, and that's when it started to feel like a game.

**The AI needed an editor.** When we pointed the pipeline at fun topics like food and sports, the first batch of puzzles came back with problems. Fake accounts had realistic names, one story was about a deadly ship fire, and only the fake posts were missing source links. We caught all of it in review and turned each problem into a rule the code enforces. That last one was sneaky: if only the fakes come from unknown accounts, people learn the pattern instead of the skill.

## Accomplishments that we're proud of
- **Con the Con actually works.** You forge something and a live AI calls it in a few seconds.
- **The blind solver.** Every puzzle has to survive an AI attempt before a person even looks at it.
- **The scoring.** Being paranoid costs you, which is kind of the whole point.
- **Every real quote in the game matches its source word for word**, and we check.
- **It looks like a newspaper.** We went from a boring first version to a full front-page redesign in one weekend.

## What we learned
We came in thinking the hard part would be making convincing fakes. It turned out the hard part was making _fair_ ones, and making sure people weren't just learning to distrust everything.

We also learned that agents are great at the grind: digging up sources, applying tricks, testing whether a puzzle can be solved. You still want a person looking at the result before it goes out, though.

## What's next for Grain of Salt
- **Nightly drops:** a fresh AI-built puzzle every night, waiting for the editor in the morning
- **iMessage for everyone:** right now each player has to be added to the line first
- **New tricks:** AI-written posts and fake experts
- **Themed weeks** with local newsrooms and libraries

Code: [github.com/tylerdong878/hackprincetonf2026](https://github.com/tylerdong878/hackprincetonf2026)

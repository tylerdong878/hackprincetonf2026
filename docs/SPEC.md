# Grain of Salt: Project Spec

> **Name:** **Grain of Salt**. Tagline: *"Don't believe everything. Don't doubt everything."*
> The name is the point of the game: calibrated trust, not blanket suspicion.
> **The villain** is a character called **the Con**.
> **Event:** HackPrinceton Fall 2026. Devpost deadline is **Sun Nov 15, 8:00am**.
> **Tracks:** Entertainment & Media (main track), LangChain Deep Agents, Amazon Practical AI, ChatOverflow (optional). Photon is a stretch goal.

---

## 1. The pitch

**One line:** An AI con artist mixes doctored posts into a feed of real news about New Jersey. You investigate with real evidence and decide what's real and what's doctored. Sometimes nothing is fake. You get scored on **discernment**, not suspicion.

**The problem.**
- Misinformation mostly works through a small set of repeatable tricks: a quote with its context cut off, a chart with a misleading axis, a statistic missing its denominator.
- New Jersey was the first state to require K-12 information literacy (law S-588, signed Jan 2023). Teachers are now required to teach this, and the tools are still catching up.
  - *Before this goes on a slide:* check how far the state standards rollout has gotten.

**The research twist (our "ah-ha").**
- Earlier "prebunking" games like *Bad News* and *Go Viral!* looked effective at first.
- A reanalysis using signal-detection methods found they mostly made players **more suspicious of everything**. They did not get better at telling true from false. (Modirrousta-Galian & Higham, 2023. *Verify the citation before using it.*)
- A game where "find the fake" is always the answer trains exactly that blanket suspicion.
- **Our game scores both mistakes:**
  - getting fooled by a fake, and
  - accusing a real post.
- Some cases have zero fakes.
- The pitch line: *"Earlier games taught people to doubt everything. Ours teaches them to check."*

**Who it's for.**
- **Primary:** anyone who scrolls a feed. The daily case works like Wordle.
- **Also:** New Jersey teens (ages 14–18), the age group the state law above is aimed at.

---

## 2. Core gameplay loop

```
BRIEFING ──► INVESTIGATION ──► VERDICT ──► REVEAL ──► MEMORY UPDATE ──► next case
(Con intro)  (use evidence     (real or    (side-by-side  (per-trick miss and
              tools on posts)   doctored,   diff + the      false-alarm rates
                                + the trick) Con's comment)  update; the Con adapts)
```

### 2.1 Briefing
- The Con introduces the case in character. The text types out like a typewriter (skippable).
- Example: *"NJ power bills. Four posts. I may have touched a few. Or not. That's the fun part."*
- The case card shows:
  - the real topic
  - the date range
  - the number of posts
  - the clue budget
- Rules reminder, shown every time: **"Some posts may be doctored. Maybe none are."**

### 2.2 Investigation
- The player sees 4 posts (demo/speed case) to 6 (full case) in a feed.
- Each post can be inspected with **evidence tools**, which cost clue tokens:

| Tool | Icon | Shows | Exposes |
|---|---|---|---|
| **Open source** | 📄 | The full original article or transcript, with the quoted passage highlighted in context. | Out-of-context quotes |
| **Check the data** | 📊 | The raw data table behind a chart or stat, plus an "honest" default view. | Misleading charts, cherry-picked stats |
| **Who posted this?** | 👤 | The account card: creation date, post history, follower pattern. | Fabricated or new accounts (stretch tricks) |

- **Clue budget:** 3 tokens per 4-post case and 4 per 6-post case. Unused tokens become bonus points, so players learn which checks are worth doing.
- All evidence is **built into the case**. The game never needs the open web, so it works on locked-down school devices and offline at the demo.

### 2.3 Verdict
- For each post the player marks **Real** or **Doctored**.
- If they choose Doctored, a trick picker appears: Out of context / Misleading chart / Cherry-picked stat (MVP), plus "Not sure."
- *(Stretch)* A confidence slider for each post: "How sure?" 50–100%.
- **Submit verdicts** becomes active once every post is marked.

### 2.4 Reveal
Each post gets an outcome badge:

| Outcome | Meaning | Color | Icon |
|---|---|---|---|
| **Caught** | Doctored, and you said doctored | Green | ✓ |
| **Trusted** | Real, and you said real | Green | ✓ |
| **Fooled** | Doctored, and you said real | Red | ✗ |
| **False alarm** | Real, and you said doctored | Amber | ⚠ |

- Doctored posts show **"What you saw" next to "The original."** The change is highlighted:
  - the cropped sentence is restored in a highlight
  - the truncated axis animates back to zero
  - the missing denominator appears
- One line under each doctored post names **the tell**: *"The axis starts at 19¢, and it compares April 2025, before the summer spike, with July 2026. July to July, prices rose 0.3%."*
- The Con comments on each outcome (see §5, voice).
- A score summary, the Detective rating, and an adaptation message: *"The Con has noticed: you trust official-looking charts, and you doubt big numbers."*

### 2.5 Memory update
- Each player profile tracks, **per trick**:
  - times shown
  - misses (fooled)
  - false alarms (accused a real post of this format)
- The next case is chosen using these numbers (§7.3).

---

## 3. Screens and UI

### 3.1 Visual direction

**Concept: "noir case room around a clean modern feed."**
- **The game frame** looks like a detective's desk at night: deep ink background, a manila case file, rubber stamps, typewriter headings, and the Con as a shadowy character with a smirk.
- **The posts inside the feed** look like a clean, realistic, *generic* social app. That way the fakes are convincing and the noir styling doesn't give anything away.
- **No real platform branding** (no X, Instagram or TikTok look-alikes, no real logos). Outlets appear as text names only.

**Color tokens** (dark theme is the default; light theme below):

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg` | `#12141C` | `#F6F1E7` | Page background (ink / paper) |
| `--surface` | `#1C1F2B` | `#FFFFFF` | Panels |
| `--paper` | `#EFE4CC` | `#EFE4CC` | Manila case-file elements |
| `--feed-card` | `#FFFFFF` | `#FFFFFF` | Post cards (always light, like a real app) |
| `--text` | `#ECEAE4` | `#1B1B1F` | Primary text |
| `--muted` | `#9A9AA6` | `#5E5E68` | Secondary text |
| `--real` | `#2F9E6A` | `#22804F` | Trusted / Caught |
| `--doctored` | `#D2453A` | `#B8322A` | Doctored stamp / Fooled |
| `--alarm` | `#E3A42B` | `#B57D10` | False alarm |
| `--con` | `#8B5CF6` | `#6D3FD8` | The Con's voice, workshop accents |
| `--focus` | `#7FB2FF` | `#1F5FD1` | Keyboard focus ring |

Outcomes always use **color + icon + word**, never color alone.

**Typography:**
- Display/headings: **Special Elite** (typewriter). Use it for case titles, stamps and the Con's lines.
- UI/body: **Inter**.
- Post cards: the system UI font stack, so they feel like a real app.
- Numbers and data tables: **IBM Plex Mono**.
- All of these are Google Fonts.

**Motion:**
- Typewriter text for the Con.
- Rubber-stamp "thunk" when a verdict is set: scale 1.3 → 1.0 with a slight rotation, 150ms.
- The chart axis morphs from fake to honest in the reveal: 800ms ease-out.
- The workshop panel's checklist ticks in live.
- Respect `prefers-reduced-motion`: replace motion with a simple fade.

**The Con (character):**
- A flat illustration or SVG of a figure in a fedora and long coat, face in shadow, one visible smirk, and a purple (`--con`) accent: a tie or a glint in the eye.
- Shown small in a bottom dock during play and large on the briefing and reveal screens.
- Speech bubbles are dark, with a purple left border and typewriter font.

**In-game watermark (safety):**
- **Every** post card, real or doctored, has a faint case-file frame and a footer strip: `CASE #0412 · TRAINING MATERIAL`.
- Any screenshot is identifiable as game content, and the uniform frame doesn't reveal which posts are fake.
- After the reveal, doctored posts also get a large red **DOCTORED** stamp built into the rendered card.

### 3.2 Screen list
1. **Title / Home**
2. **Briefing**
3. **Investigation** (the main screen)
4. **Reveal**
5. **Dossier** (player profile)
6. **Casebook** (trick library)
7. **The Con's Workshop** (a side panel on Investigation and Reveal, plus a full-screen view)
8. **Editor's Desk:** case queue and case review

### 3.3 Title / Home
- The main logo, with the tagline *"Don't believe everything. Don't doubt everything."* The Con stands in a doorway of light.
- **Logo:** a cute black-and-white salt shaker character, tilted mid-shake with three grains popping out the top.
  - The domed cap is its head: dot eyes, a tiny smile, soft gray blush.
  - The glass body says "grain of salt" in Cooper Black, converted to outlines.
  - Every line is the same chunky weight.
  - It stays monochrome on purpose. Use the `-light` or `-dark` variant to match the theme.
  - Files: `frontend/public/` (web) and the team's Illustrator folder, outside this repo (Illustrator source and generator).
  - Variants: the main logo (name on the body), an icon (wavy salt line instead of the name: favicon, spinner, empty states), and a horizontal wordmark (top bar, Devpost).
- Primary button: **"Open today's case"**, labeled with the case number: *Case #0412 · NJ power bills*.
- Secondary buttons: **Casebook**, **Dossier**, **Editor's Desk**.
- Streak flame and Detective rating badge in the top right (stretch: streaks).
- A "How it works" strip with three icons: *Investigate → Decide → See the trick*.

### 3.4 Briefing
- A manila folder slides open. On the left is the Con with a speech bubble. On the right is the case card:
  - Case title
  - The real topic summary, one line
  - Posts: 4 · Clues: 🔍🔍🔍 · Timer: 1:30 (demo only)
  - The rule: *"Some posts may be doctored. Maybe none are."*
- Button: **"Start investigating."**

### 3.5 Investigation (desktop wireframe)

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│ ◉ GRAIN OF SALT  Case #0412 · NJ power bills        🔍🔍🔍  ⏱ 1:30   [Workshop ▸] │
├─────────────────────────────────────────────────┬─────────────────────────────────┤
│  THE FEED                                         │  EVIDENCE KIT                   │
│  ┌─────────────────────────────────────────────┐  │  Post 2 selected                │
│  │ ◯ Jersey Bill Watch  @jerseybills · 2d       │  │  [📄 Open source]     –1 🔍     │
│  │ "NJ power prices up 27% in one year!"        │  │  [📊 Check the data]  –1 🔍     │
│  │ ┌─────────── bar chart ───────────┐          │  │  [👤 Who posted this?] –1 🔍    │
│  │ └─────────────────────────────────┘          │  │ ─────────────────────────────── │
│  │ CASE #0412 · TRAINING MATERIAL               │  │  ┌ Check the data ───────────┐  │
│  │ [ ✓ Real ]  [ ✗ Doctored ▾ ]                 │  │  │ Month     ¢/kWh           │  │
│  └─────────────────────────────────────────────┘  │  │ Apr 2025  19.91           │  │
│  ┌ Post 3 ─────────────────────────────────────┐  │  │ Jul 2026  25.19           │  │
│  │ …                                            │  │  │ Change +26.5%             │  │
│  └─────────────────────────────────────────────┘  │  └───────────────────────────┘  │
├─────────────────────────────────────────────────┴─────────────────────────────────┤
│ (Con) "Take your time. I already took mine."           3 of 4 marked [Submit →]  │
└───────────────────────────────────────────────────────────────────────────────────┘
```

*(The numbers are real EIA data: NJ residential average price in cents per kWh. "Jersey Bill Watch" is a made-up account, and its post is the doctored example. See RESEARCH.md §4.)*

**Layout.**
- Two columns: Feed (about 60%) and Evidence Kit (about 40%).
- A top bar with the case title, clue tokens, timer and a Workshop toggle.
- A bottom dock with the Con's line and the Submit button.

**Post card anatomy.** From top to bottom:
1. Avatar circle, display name, handle, relative time, and a generic "verified" badge if applicable.
2. Body text, with an optional chart or stat block.
3. The watermark footer strip.
4. A verdict row with two segmented buttons, **Real** and **Doctored ▾**.

**Card states.**

| State | Look |
|---|---|
| Unmarked | Neutral border |
| Selected for evidence | Blue focus outline |
| Marked Real | Green outline, small "REAL" stamp at top right |
| Marked Doctored | Red outline, "DOCTORED?" stamp, trick chip shown (e.g. `Misleading chart`) |
| Locked after submit | 70% opacity until the reveal animates |

**Trick picker.** Clicking "Doctored" opens a popover with three chips plus "Not sure". The chosen chip shows on the card. Naming the trick correctly earns bonus points.

**Evidence Kit.**
- With no post selected: *"Select a post, then pick a tool."*
- Tools are disabled once tokens run out (a tooltip explains why).
- Opened evidence stays visible for that post, so it can be re-read for free.
- "Open source" shows the source document with the quoted span highlighted in yellow and the surrounding context visible.
- "Check the data" shows a table plus a small honest chart with a zero baseline and the full date range.

**Timer:** only on in demo / speed mode. In normal play there's no timer.

### 3.6 Investigation (mobile, under 768px)
- A single-column feed with 16px side gutters.
- Tapping a post opens the **Evidence Kit as a bottom sheet** (60% height, drag to expand).
- The verdict row stays on each card.
- A sticky bottom bar holds the clue tokens and Submit.
- The Con's line appears as a small toast above the bar.

### 3.7 Reveal (wireframe)

```
┌──────────────── CASE CLOSED · Score 340 · Detective rating 72 (Inspector) ───────────┐
│ Post 1   ✓ TRUSTED. It was real.                                                     │
│ Post 2   ✗ FOOLED. Misleading chart                                                  │
│   ┌ What you saw ─────────────┐        ┌ The original ─────────────┐                 │
│   │ axis at 19, Apr→Jul window│  ───►  │ same months YoY, axis at 0│                 │
│   └───────────────────────────┘        └───────────────────────────┘                 │
│   The tell: axis from 19¢, and April 2025 vs. July 2026. July to July: +0.3%.        │
│   (Con) "Official-looking charts. Works every time."                                 │
│ Post 3   ⚠ FALSE ALARM. Real. Surprising, but true. (See the source.)                │
│ Post 4   ✓ CAUGHT. Out of context (+50 for naming the trick)                         │
│ ──────────────────────────────────────────────────────────────────────────────────── │
│ The Con has noticed: you trust charts, and you doubt big numbers.                    │
│ [ Next case ]   [ Learn: Misleading charts ]   [ Share  🟩🟥🟨🟩 ]                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- Posts reveal one at a time, about 600ms apart. Each outcome stamp "thunks" in.
- **Side-by-side diffs by trick:**
  - **Out of context:** the cropped quote on the left. On the right, the full passage with restored text highlighted in `--real` at 25% opacity, and removed context underlined.
  - **Misleading chart:** the doctored chart on the left, the honest chart on the right. On click, the left chart's axis animates down to zero.
  - **Cherry-picked stat:** the stat on the left; on the right, the full numbers with the missing denominator or time range highlighted.
- **A clean case** (zero fakes) gets a special full-width banner. The Con says: *"Nothing to catch today. Getting you to doubt everything is my favorite trick of all."*
- **Share card (stretch):** only the emoji grid, the case number and the rating. **Never** the fake content itself.

### 3.8 Dossier (profile)
- A header with the Detective rating (0–100), a rank title, cases solved and the streak.
- One row per trick:
  - **Fooled rate:** a red bar for how often you miss this trick.
  - **False-alarm rate:** an amber bar for how often you accuse honest posts of this format.
  - **Mastery:** 0–3 badge pips.
- A "What the Con thinks of you" quote, generated from the stats.
- Case history: date, topic, score and the outcome grid.

**Rank titles:**

| Rating | Title |
|---|---|
| 0–39 | Rookie |
| 40–59 | Gumshoe |
| 60–79 | Inspector |
| 80–89 | Chief |
| 90–100 | Untouchable |

### 3.9 Casebook (trick library)
A grid of trick cards. Each opens a page built from that trick's `SKILL.md`:
- What it is
- A worked example (real material only)
- **The tell**
- **How to check it**: which evidence tool exposes it, and the real-world equivalent (lateral reading, finding the original, checking the axis)
- "Practice this trick": starts a case weighted to this trick

### 3.10 The Con's Workshop (agent visibility panel)
Slides in from the right on Investigation and Reveal. There's also a full-screen view for the LangChain demo.

```
┌ THE CON'S WORKSHOP ───────────────────── ● live   /   ⟲ replay of run 03:12 ┐
│ PLAN                                                                        │
│  ✓ Find a New Jersey story with numbers                                     │
│  ✓ Collect 6 real sources (with links)                                      │
│  ✓ Choose tricks for this player: misleading chart (weak spot)              │
│  ◐ Forge post 2                                                             │
│  ○ Blind-solve the case                                                     │
│  ○ Send to the editor for approval                                          │
│ SUB-AGENTS                                                                  │
│  Researcher ✓   Forger ● working   Blind solver ○   (lanes with short logs) │
│ FILES                                                                       │
│  cases/2026-11-14-power-bills/sources.json        new                       │
│  cases/2026-11-14-power-bills/answer_key.json     writing…                  │
│  skills/misleading-chart/SKILL.md                 loaded                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Live mode** streams events from a pipeline run.
- **Replay mode** plays back a saved run log (`pipeline_log.jsonl`) at 2–4x speed. The demo uses this to avoid rate limits.
- **During a player's round**, the panel shows *how this case was built*, but **hides the answer key**: the forger's lane says "Forged post ██" until after the reveal.

### 3.11 Editor's Desk
- **Case queue:** a table of draft cases with columns topic, date, tricks used, blind-solver result (pass/fail and difficulty), and status (`draft` / `awaiting approval` / `approved` / `rejected`).
- **Case review:**
  - On the left, a player preview.
  - On the right, the answer key, the diffs, the solver log and the safety checks.
  - Buttons **Approve**, **Edit** (adjust text or remove a post) and **Reject** (with a reason).
- **Topic blocklist settings:** see §8.

### 3.12 Accessibility
- Fully keyboard-playable:
  - Tab moves through posts.
  - `R` / `D` marks Real / Doctored.
  - `1`–`3` picks a trick.
  - `E` opens the Evidence Kit.
- A visible focus ring (`--focus`).
- Every chart has an accessible data table, which is also the "Check the data" evidence, plus an alt-text summary.
- WCAG AA contrast. Outcome states use icon + word + color.
- The Con's typewriter text can be skipped and is announced in full to screen readers (`aria-live="polite"`).

---

## 4. The tricks

**MVP: three tricks.** All of them are applied by **code** to **real material**. The AI chooses *where* to apply them, which keeps them reliable and safe.

| Trick | How it's forged | The tell | Exposed by |
|---|---|---|---|
| **Out-of-context quote** | Take a real quote from a real source and cut it at a point that flips or exaggerates its meaning (e.g. drop "but", "if", "not yet"). | The full passage says something different. | 📄 Open source |
| **Misleading chart** | Take a real dataset and render it with a truncated y-axis, a cherry-picked date window or an uneven scale. | The axis doesn't start at 0, or the time window is suspiciously narrow. | 📊 Check the data |
| **Cherry-picked stat** | State a real number without its denominator or baseline, or pick the one month that supports a claim. | The rate or the full range tells a different story. | 📊 Check the data |

**Real-but-suspicious posts** (the anti-blanket-suspicion ingredient): every case should include at least one real post that *looks* fake, such as a startling but true statistic or a genuine quote that sounds made up. The source confirms it.

**Stretch tricks:** fake expert (made-up account only), emotional framing, impersonation (made-up account copying a real outlet's style, with no logos), and an AI-written post. The taxonomy follows the six *Bad News* techniques (impersonation, emotion, polarization, conspiracy, discrediting, trolling) and the Civic Online Reasoning / lateral-reading curriculum, so it matches the published research.

---

## 5. The Con's voice
- **Personality:** smug, playful, theatrical. Never cruel, never political, never mocks the player's intelligence. Think a stage magician who wants you to learn the trick.
- **Lines are short**, one or two sentences. The game master generates them per case, with a fallback library.

**Example lines:**
- **Briefing:** "NJ power bills. Four posts. I may have touched a few. Or not."
- **Fooled:** "You trusted the chart because it looked official. Everyone does."
- **False alarm:** "That one was real. I didn't even have to lie. You did the work for me."
- **False alarm, repeated:** "A grain of salt, detective. Not the whole shaker."
- **Caught:** "Fine. You saw the axis. I won't be so generous next time."
- **Clean case:** "Nothing to catch today. Getting you to doubt everything is my favorite trick of all."
- **Adapting:** "I've noticed you never open the source. Interesting."

---

## 6. Scoring

**Per post:**

| Outcome | Points |
|---|---|
| Trusted (real, marked real) | +100 |
| Caught (doctored, marked doctored) | +100 |
| Named the trick correctly (bonus on Caught) | +50 |
| Fooled (doctored, marked real) | 0 (logged as a miss) |
| False alarm (real, marked doctored) | −50 (logged as a false alarm) |
| Each unused clue token | +20 |

**Detective rating** (discernment, shown 0–100, over the last 30 posts seen):
```
hit_rate         = caught / doctored_posts_seen
false_alarm_rate = false_alarms / real_posts_seen
rating           = clamp(round(50 + 50 * (hit_rate - false_alarm_rate)), 0, 100)
```
- Someone who marks everything "doctored" ends up near 50, not 100. That's the point.
- **(Stretch)** With the confidence slider, weight each verdict by confidence and show calibration ("you're overconfident on charts").

---

## 7. Architecture

### 7.1 Two halves: build offline, play live

```
OFFLINE PIPELINE (Deep Agents, batch)                     ONLINE GAME (FastAPI)
┌───────────────────────────────────────────┐             ┌──────────────────────────┐
│ Orchestrator (plans with todos)            │   case bank │ Game master               │
│   ├─ Researcher sub-agent → sources.json   │ ──────────► │  - picks case for player  │
│   ├─ Forger sub-agent (loads trick skills) │  approved   │  - serves player view     │
│   │    → case.json, answer_key.json,       │  cases only │  - scores verdicts on the │
│   │      evidence/                         │             │    server                 │
│   ├─ Blind solver sub-agent (no key)       │             │  - writes the Con's lines │
│   │    → solver_log.md (pass/fail, diff.)  │             │  - updates profile.json   │
│   ├─ Safety check (blocklist, rules)       │             └──────────────────────────┘
│   └─ Editor approval (human-in-the-loop)   │
└───────────────────────────────────────────┘
```

Why the split:
- Low latency in play.
- The same daily case for everyone.
- An editor reviews every case before players see it.
- Free-tier rate limits only affect the offline pipeline. **The demo plays pre-built cases.**

### 7.2 The pipeline (Deep Agents features in use)
- **Planning:** the orchestrator writes a todo plan, which the Workshop panel shows. Todos are off by default in deepagents 0.7, so pass `middleware=[TodoListMiddleware()]`.
- **Sub-agents** with isolated context:
  - **Researcher.** Tools: `fetch_rss`, `fetch_article`, `search_wikipedia`, `fetch_open_data`, `save_source`. It may only save **verbatim** quotes and numbers, each with a source URL.
  - **Forger.** Tools: `crop_quote`, `make_chart_spec`, `make_stat_claim`. It loads the trick `SKILL.md` it needs. It never invents quotes from real people.
  - **Blind solver.** It gets only `case.json` and the evidence kit, and tries to solve the case using the same tools the player has.
    - **Can't find the trick:** the case is unfair. The orchestrator revises it, up to 2 retries.
    - **Finds it with no tools:** the case is tagged "easy."
    - **Otherwise:** difficulty is set by the tools used.
    - Use the vision model so it can look at the rendered chart PNG.
- **File system:** everything is written as files under `cases/`, `skills/` and `players/` (see 7.4). A `CompositeBackend` routes those paths to `FilesystemBackend(root_dir=<absolute path>, virtual_mode=True)`, and scratch files stay in state.
- **Skills:** one `SKILL.md` per trick, loaded on demand.
- **Human-in-the-loop:** the pipeline pauses for the editor's approval before a case goes live.
  - A **checkpointer is required** for interrupts (LangGraph; SQLite or in-memory).
  - The pause is created by gating a custom `submit_for_review` tool with `interrupt_on`. The editor's decision resumes the run with approve, edit or reject.
  - For the MVP, approval is a single Approve button.
- **Memory:** player profiles persist and drive which tricks the forger chooses.

### 7.3 Adaptive case selection
For a player's next case:
- **About 20% of cases are clean** (zero fakes).
- **Otherwise, the trick mix is:**
  - 70% from the player's weakest tricks (highest miss rate)
  - 20% from mastered tricks, to check they've retained them
  - 10% a new trick
- **If a trick's false-alarm rate is high**, include *honest* posts in that format (e.g. honest charts) rather than more fakes.
- **Make the adaptation visible:** "The Con has noticed you trust official-looking charts."
- **Daily case:** the same case for everyone that day. Adaptation applies to practice cases.

### 7.4 Files

```
skills/
  out-of-context-quote/SKILL.md
  misleading-chart/SKILL.md
  cherry-picked-stat/SKILL.md
cases/2026-11-14-power-bills/
  sources.json          # real material + URLs (researcher)
  case.json             # player view: posts + evidence references, NO answers
  answer_key.json       # per post: doctored?, trick, original, diff, tell, con_line
  evidence/             # full articles, data tables, account cards
  rendered/             # chart PNGs for the blind solver
  solver_log.md         # blind-solver attempt, tools used, verdict
  pipeline_log.jsonl    # every agent event, for Workshop replay
  status                # draft | awaiting_approval | approved | rejected | live
players/<id>/profile.json   # per-trick shown/miss/false-alarm counts, history, rating
```

**`SKILL.md` structure:**
- Frontmatter: `name`, `description`.
- Sections: Definition · When to use · Forging recipe (allowed operations on real material only) · The tell · How to verify (which evidence tool) · Diff type for the reveal · Con lines · Safety limits.

**`case.json` (player view) sketch:**
```json
{
  "id": "2026-11-14-power-bills",
  "title": "NJ power bills",
  "briefing": "NJ power bills. Four posts. I may have touched a few. Or not.",
  "clue_budget": 3,
  "posts": [
    {
      "id": "p2",
      "author": { "name": "…", "handle": "…", "kind": "outlet|fictional", "verified": false },
      "posted_at": "2026-11-12T14:00:00Z",
      "body": "…",
      "chart": { "type": "bar", "data": [], "y_min": 95 },
      "evidence": { "source": "evidence/p2_source.md", "data": "evidence/p2_data.json", "account": null }
    }
  ]
}
```
**The answer key never goes to the browser before the player submits.** The server scores verdicts and returns the reveal. Otherwise anyone could find the answers in the browser's developer tools.

### 7.5 API

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/cases/today` | Today's case (player view) |
| GET | `/api/cases/{id}` | A case (player view) |
| POST | `/api/cases/{id}/evidence` | Spend a clue token and get evidence for a post and tool |
| POST | `/api/cases/{id}/verdict` | Submit verdicts → reveal payload, score, updated profile |
| GET | `/api/players/{id}` | Profile / dossier |
| POST | `/api/pipeline/run` | Start building a case (editor/admin) |
| GET | `/api/pipeline/runs/{id}/events` | Server-sent event stream (live) or replay of `pipeline_log.jsonl` |
| GET | `/api/editor/queue` | Draft cases |
| POST | `/api/editor/cases/{id}/approve` · `/reject` · `/edit` | Human-in-the-loop decisions |

**Workshop event types:**
- `plan_updated {todos}`
- `subagent_started {name, task}`
- `tool_called {name, summary}`
- `file_written {path}`
- `solver_result {pass, tools_used, difficulty}`
- `awaiting_approval`
- `case_status {status}`

### 7.6 Tech stack
- **Frontend:**
  - React + Vite + TypeScript + Tailwind
  - Recharts for the charts (it can set axis ranges, which the misleading-chart trick needs)
  - Framer Motion or CSS for the stamps and the axis morph
- **Backend:**
  - Python 3.12 and FastAPI
  - `deepagents` 0.7.x, plus `langchain-openrouter` (`ChatOpenRouter`, version 0.2.0 or later). See RESEARCH.md §3 for the 0.7 gotchas.
  - LangGraph checkpointer (SQLite)
  - `feedparser` for news feeds, `httpx`
  - `matplotlib` to render chart PNGs for the solver
  - JSON files for storage (no database)
- **Models** (free, through OpenRouter):

| Job | Model |
|---|---|
| Orchestrator and forger | Nemotron 3 Ultra |
| Blind solver (reads chart images) | Nemotron 3.5 Super VL |
| Small tasks | Nemotron 3.5 Lightning |
| Fallback | Gemini free tier |

- **Model notes:**
  - Pin specific model slugs. Don't use `openrouter/free`.
  - Confirm each model supports tool calling.
- **Environment:** `.env` holds `OPENROUTER_API_KEY` (and optionally `GEMINI_API_KEY`). `.env` is git-ignored.
- **Data sources** (free):
  - NPR and BBC news feeds, plus NJ outlets' feeds where they offer one.
  - Wikipedia.
  - Public datasets: NJ open data portal, Census, BLS.
  - Pick the demo topic so the numbers are easy to get.

---

## 8. Safety rules (judges will ask)
1. **Manipulate real material whenever possible.** Most tricks need no fabrication. The deception is in the framing.
2. **Fully fabricated posts only come from made-up accounts.** Never invent a quote and attribute it to a real person.
   - **Every doctored post comes from a made-up account**, even a crop of a real quote. Never present a doctored version as coming from a real outlet or official.
   - **Real posts** show the outlet's name in plain text, with a link.
   - New Jersey Monitor is CC BY-NC-ND (no derivatives), so use short attributed excerpts only. See RESEARCH.md §4.3.
3. **No real logos or platform branding.** Outlets appear as plain text names.
4. **Every post carries the in-game watermark**, and doctored posts get a DOCTORED stamp after the reveal. Share cards never include fake content.
5. **Topic blocklist:** elections close to voting day, ongoing tragedies, active public-health emergencies, and minors as subjects. The safety check enforces it.
6. **Real posts must be verbatim**, with a link to the source. If the researcher can't verify something, it can't be used.
7. **A human editor approves every case before players see it.**

---

## 9. Scope

**MVP (must work end to end by Sat ~6pm):**
- [ ] 3 trick skills (`SKILL.md`) and the code tools behind them
- [ ] Pipeline: researcher → forger → blind solver → approve button, producing files
- [ ] 5 approved cases on one NJ topic, including one clean case and a real-but-suspicious post
- [ ] Investigation screen: feed, verdicts, trick picker, 2–3 evidence tools, clue tokens
- [ ] Server-side scoring, Detective rating, the reveal with side-by-side diffs and the Con's lines
- [ ] A player profile with per-trick misses and false alarms, and the next case chosen from it
- [ ] Workshop panel (replay mode at minimum)
- [ ] README, Devpost write-up, a 2-minute backup video

**Stretch (in order):**
1. Daily case and an emoji share grid
2. Editor's Desk review screen (full Edit/Reject)
3. Confidence slider and calibration
4. More tricks
5. Photon: play over iMessage
6. Party mode (real-time multiplayer)

---

## 10. Demo (2 minutes)
**Setup:**
- Laptop on the charger, with the case pre-loaded.
- Workshop panel open in replay mode.
- **The demo case has 4 posts on NJ electricity prices:** 1 doctored (misleading chart), 1 real-but-suspicious stat, 2 plainly real. The exact items are in RESEARCH.md §4.2.
- Whatever the judge does, there's a reveal moment: they're either fooled or they wrongly accuse the real one.

| Time | Speaker | Beat |
|---|---|---|
| 0:00–0:10 | A | "Misinformation runs on a handful of tricks. Our AI con artist uses them on you. Want to try?" Hand over the laptop. |
| 0:10–0:50 | Judge plays, B narrates | B, pointing at the Workshop: "A researcher pulled real sources. The forger picked a misleading chart. A blind solver checked the case is catchable." |
| 0:50–1:15 | Reveal | The axis animates down to zero. If they accused the real post: "That one was real. Earlier games train you to doubt everything. Ours trains you to check." |
| 1:15–1:40 | C | Why it matters: the NJ K-12 law; earlier games increased suspicion without improving discernment; a human editor approves every case. |
| 1:40–2:00 | D | Future: daily case, more tricks. "Built on Deep Agents with $0 of AI spend." |

**Sponsor add-ons, about 30 seconds each:**
- **LangChain:** open the case folder, a `SKILL.md`, the solver log, and the approval step.
- **Amazon:** the target user, the README, and the fact that it runs reliably.

**Backups:**
- Offline play from saved cases.
- A recorded video.
- Tested screen mirroring for round 2.

---

## 11. Timeline (deadline Sun 8:00am)

| When | What |
|---|---|
| Fri night | LangChain workshop. Get OpenRouter keys. **One-round test:** can the model make a fake that fools people? Pick the NJ topic and its datasets. Scaffold the repo. |
| Sat morning → 6pm | Pipeline and game UI in parallel, then wire them together. MVP checklist done. |
| Sat evening | Generate and approve the 5 cases. Workshop replay. Polish the reveal animations. |
| Sat night | README, Devpost write-up, backup video, pitch rehearsals with strangers. |
| Sun by 8:00am | Submit: public repo, Devpost, video link, Discord usernames, tracks. |

**Suggested roles (4 people):**
1. **Agent pipeline:** Deep Agents, sub-agents, skills, approval step.
2. **Game UI:** screens, animations, mobile layout.
3. **Content and data:** trick recipes, datasets, chart tools, safety checks, case quality.
4. **Story:** pitch, Devpost, video, user testing, the Con's voice lines.

---

## 12. Open questions
- [x] Name: **Grain of Salt**
- [x] Demo topic: **NJ electricity prices** (backup: NJ minimum wage). See RESEARCH.md §4.
- [ ] Team size and roles
- [ ] OpenRouter free-tier limits: check the FAQ and get a key per teammate
- [ ] NJ information-literacy standards rollout status (for the pitch)

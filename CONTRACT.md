# Grain of Salt: Build Contract

The single source of truth for data formats and the API. The backend, frontend and pipeline all follow it.
Product design is in [SPEC.md](SPEC.md). Research and sources are in [RESEARCH.md](RESEARCH.md).
**If you need to change something here, change this file first and tell the team.**

## 1. Repo layout
```
pyproject.toml            # Python deps (uv). Run `uv sync`.
.env                      # secrets (git-ignored). Copy from .env.example.
backend/app/              # FastAPI game server  → `uv run uvicorn backend.app.main:app --reload --port 8000`
backend/tests/            # pytest
pipeline/                 # Deep Agents case builder → `uv run python -m pipeline.build_case ...`
pipeline/tests/           # pytest (deterministic tools only, no LLM calls)
frontend/                 # Vite + React + TS + Tailwind → `npm run dev` (port 5173, proxies /api to 8000)
scripts/                  # one-off data scripts (EIA fetch, seed cases)
data/
  sources/                # raw public data (e.g. EIA JSON), committed
  skills/<trick>/SKILL.md # one Deep Agents skill per trick
  cases/<case_id>/        # one folder per case (see §2)
  players/<player_id>/profile.json   # git-ignored, created at runtime
```

## 2. Case folder: `data/cases/<case_id>/`

| File | Who reads it | Notes |
|---|---|---|
| `case.json` | Browser (via the API) | Player view. **No answers.** |
| `evidence.json` | Server only | Released one tool at a time via `POST /evidence` |
| `answer_key.json` | Server only | **Never sent before the verdict** |
| `meta.json` | Server, teacher UI | Status, origin, sources |
| `pipeline_log.jsonl` | Workshop panel | Only exists for pipeline-built cases. **Never fabricate one.** |

**Trick ids:** `out-of-context-quote`, `misleading-chart`, `cherry-picked-stat`.
**Evidence tool ids:** `source`, `data`, `account`.

### 2.1 `case.json`
```jsonc
{
  "id": "2026-11-14-power-bills",
  "number": 1,                                  // shown as "Case #0001"
  "title": "Is your power bill really frozen?",
  "topic": "NJ electricity prices",
  "briefing": "Power bills in New Jersey. Four posts. I may have touched a few. Or none.",
  "notice": "Game content: the Con doctors some posts on purpose. Every doctored post is stamped at the reveal.",  // optional; same text on every case, shown in a small footer
  "clue_budget": 3,
  "trick_options": ["out-of-context-quote", "misleading-chart", "cherry-picked-stat"],
  "posts": [
    {
      "id": "p1",
      "author": {
        "name": "New Jersey Monitor",
        "handle": "@NJMonitor",                // display only
        "kind": "outlet",                      // "outlet" | "official" | "person"
        "verified": true,
        "avatar_color": "#2F9E6A"
      },
      "posted_at": "2026-09-24T19:48:00Z",
      "body": "Plain post text (may be empty if the post is only a quote or chart).",
      "quote": { "text": "Exact quoted words.", "speaker": "Ben Hertz-Shargel, NJBPU President" },  // or null
      "chart": {                                // or null
        "type": "bar",                          // "bar" | "line"
        "title": "NJ residential electricity price",
        "unit": "¢/kWh",
        "points": [ { "label": "Apr 2025", "value": 19.91 }, { "label": "Jul 2026", "value": 25.19 } ],
        "y_min": 19,                            // the axis start the post uses (the manipulation, if any)
        "y_max": 26                             // or null for auto
      },
      "source_label": "New Jersey Monitor · Sept 24, 2026",   // or null (no source given)
      "tools": ["source", "account"]            // which evidence tools have content for this post
    }
  ]
}
```
- **Don't reveal answers through the author.** `author.kind` never says "fictional". Made-up accounts use `"person"`, which real posts can also use.

### 2.2 `evidence.json` (server only)
```jsonc
{
  "p1": {
    "source": {
      "outlet": "New Jersey Monitor", "date": "2026-09-24",
      "url": "https://newjerseymonitor.com/2026/09/24/utilities-board-votes-electric-rates/",
      "before": "Context sentence(s) before the highlighted passage.",
      "highlight": "The exact passage the post quotes.",
      "after": "Context sentence(s) after it."
    },
    "data": {
      "title": "NJ residential average electricity price (EIA)", "unit": "¢/kWh",
      "url": "https://www.eia.gov/opendata/",
      "table": [ { "label": "2025-04", "value": 19.91 } ],
      "honest_chart": { "type": "line", "title": "...", "unit": "¢/kWh", "points": [], "y_min": 0, "y_max": null },
      "note": "One-line plain-language note shown under the table."
    },
    "account": {
      "name": "...", "handle": "...", "created": "October 2026", "followers": 1840,
      "verified": false, "bio": "...", "recent_posts": ["...", "..."]
    }
  }
}
```

### 2.3 `answer_key.json` (server only)
```jsonc
{
  "clean_case": false,
  "posts": {
    "p2": {
      "doctored": true,
      "trick": "misleading-chart",
      "tell": "One sentence: what gives it away.",
      "explanation": "Two or three sentences for the reveal.",
      "con_line_fooled": "The Con, when the player was fooled.",
      "con_line_caught": "The Con, when the player caught it.",
      "diff": {
        "type": "chart",                        // "chart" | "quote" | "stat"
        "shown":    { /* chart object as posted */ },
        "original": { /* honest chart object */ }
        // quote diff: { "type":"quote", "shown":"cropped text", "original":"full text", "removed":["word or phrase", ...] }
        // stat diff:  { "type":"stat",  "shown":"claim as posted", "original":"full numbers", "missing":"what was left out" }
      }
    },
    "p1": {
      "doctored": false,
      "suspicious_real": false,                 // true = real but designed to look fake
      "explanation": "Why it's real (cite the source).",
      "con_line_false_alarm": "The Con, when the player accused a real post."
    }
  },
  "con_line_clean": "Only for clean cases: the reveal line."
}
```

### 2.4 `meta.json`
```jsonc
{
  "status": "approved",              // "draft" | "awaiting_approval" | "approved" | "rejected"
  "origin": "seed",                  // "seed" = hand-built by the team | "pipeline" = built by the Deep Agents pipeline
  "daily": true,                     // the case served by /api/cases/today (at most one)
  "difficulty": "medium",            // "easy" | "medium" | "hard" (pipeline sets it from the blind solver)
  "created_at": "2026-11-14T05:00:00Z",
  "tricks": ["misleading-chart"],    // tricks used (empty for clean cases)
  "sources": ["https://..."],
  "rejection_reason": null
}
```

## 3. Player profile: `data/players/<player_id>/profile.json`
```jsonc
{
  "player_id": "abc123",
  "created_at": "...",
  "tricks": {
    "misleading-chart": { "shown": 0, "caught": 0, "missed": 0, "named": 0, "honest_shown": 0, "false_alarms": 0 }
  },
  "recent": [ { "doctored": true, "outcome": "caught", "format": "chart" } ],   // last 30 posts, for the rating
  "history": [ { "case_id": "...", "at": "...", "score": 340, "outcomes": { "p1": "trusted" } } ]
}
```
- **Post format:** `"quote" | "chart" | "stat" | "text"`. A real post's format counts toward `honest_shown` and `false_alarms` for the matching trick. A chart maps to `misleading-chart`, a quote to `out-of-context-quote`, and a stat or text post to `cherry-picked-stat`.

## 4. Scoring (server side)

| Outcome | Points |
|---|---|
| trusted (real, marked real) | +100 |
| caught (doctored, marked doctored) | +100, plus +50 if the trick is named correctly |
| fooled (doctored, marked real) | 0 |
| false_alarm (real, marked doctored) | −50 |
| each unused clue token | +20 |

**Detective rating** (0–100), over `recent` (the last 30 posts):
```
hit_rate = caught / doctored_seen
fa_rate  = false_alarms / real_seen
rating   = clamp(round(50 + 50 * (hit_rate - fa_rate)), 0, 100)
```
- If either denominator is 0, that rate counts as 0.

**Ranks:**

| Rating | Rank |
|---|---|
| 0–39 | Rookie |
| 40–59 | Gumshoe |
| 60–79 | Inspector |
| 80–89 | Chief |
| 90–100 | Untouchable |

## 5. API (all JSON, prefix `/api`)

| Method & path | Body | Returns |
|---|---|---|
| `GET /health` | | `{ "ok": true }` |
| `POST /players` | `{}` | `{ "player_id": "..." }` (creates a profile) |
| `GET /players/{id}` | | profile + `{ "rating", "rank", "per_trick": {trick: {miss_rate, false_alarm_rate, mastery 0-3}} }` |
| `GET /cases` | | `[ { id, number, title, topic, daily, origin, difficulty } ]` (approved only) |
| `GET /cases/today` | | `case.json` of the daily case (or the first approved) |
| `GET /cases/next?player_id=` | | `case.json` chosen adaptively (SPEC §7.3); skips cases this player has finished |
| `GET /cases/{id}` | | `case.json` |
| `POST /cases/{id}/evidence` | `{ player_id, post_id, tool }` | `{ evidence: {...}, clues_left }`. Re-opening a tool is free. **409** when out of clues. |
| `POST /cases/{id}/verdict` | `{ player_id, verdicts: { "p1": { "doctored": bool, "trick": id \| null, "confidence": 0.5-1.0 \| null } } }` | see below |
| `GET /cases/{id}/pipeline-log` | | `[event, ...]` or **404** if none |
| `GET /teacher/queue` | | all cases with `meta` (any status) |
| `GET /teacher/cases/{id}` | | `{ case, evidence, answer_key, meta, solver_log }` |
| `POST /teacher/cases/{id}/approve` | `{}` | `meta` |
| `POST /teacher/cases/{id}/reject` | `{ reason }` | `meta` |

**Verdict response:**
```jsonc
{
  "score": 340, "clue_bonus": 40, "clean_case": false, "con_line_clean": null,
  "results": [
    { "post_id": "p2", "outcome": "fooled", "points": 0, "doctored": true, "trick": "misleading-chart",
      "trick_named_correctly": false, "tell": "...", "explanation": "...", "con_line": "...", "diff": { ... } },
    { "post_id": "p1", "outcome": "trusted", "points": 100, "doctored": false, "suspicious_real": false,
      "explanation": "...", "con_line": null }
  ],
  "rating": 62, "rank": "Inspector",
  "adaptation_message": "The Con has noticed: you trust official-looking charts.",
  "share_grid": "🟩🟥🟨🟩"                     // per post: 🟩 trusted/caught, 🟥 fooled, 🟨 false alarm
}
```

**Clue tokens** are tracked server-side per `(player_id, case_id)`, in memory. Resetting on a server restart is fine.

## 6. `pipeline_log.jsonl` event schema (one JSON object per line)
```jsonc
{ "t": 1.42, "type": "plan_updated",     "todos": [ { "content": "...", "status": "pending|in_progress|completed" } ] }
{ "t": 2.10, "type": "subagent_started", "name": "researcher", "task": "..." }
{ "t": 9.80, "type": "tool_called",      "agent": "researcher", "tool": "fetch_article", "summary": "..." }
{ "t": 9.90, "type": "file_written",     "agent": "forger", "path": "/cases/<id>/case.json" }
{ "t": 14.0, "type": "subagent_finished","name": "researcher", "summary": "..." }
{ "t": 30.0, "type": "solver_result",    "pass": true, "tools_used": ["data"], "difficulty": "medium", "attempt": 1 }
{ "t": 31.0, "type": "awaiting_approval" }
{ "t": 31.5, "type": "case_status",      "status": "awaiting_approval" }
```
- **`"spoiler": true`** on any event: the Workshop panel masks its text until the player's verdict is in.
- **`t`** is seconds since the run started. Replay plays the events back at 2–4× speed.

## 7. v2 additions (see PLAN_V2.md)
Everything in §1–6 stays valid. The v1 feed lives on as "Case Files". These are additions only.

### 7.1 Data
- **New trick id: `edited-detail`** (a number, date or place swapped in a real headline).
  - Its diff type is `"detail"`: `{ "type":"detail", "shown":"…", "original":"…", "changed":[{"from":"1,000","to":"2,000"}] }`.
  - Allowed only on made-up-account posts.
- **New optional fields in `meta.json`:**
  - `"mode": "daily" | "casefile"` (default `"casefile"`);
  - `"daily_date": "YYYY-MM-DD"` (daily cases only);
  - `"theme": "Your Bills"`.
- **New optional field on a `case.json` post:** `"card_style": "headline" | "quote" | "chart" | "stat"`, a display hint for the Daily cards. If it's absent, derive it from the post's contents.
- **Daily cases** have 5 posts, `clue_budget` 3, and 0–3 doctored posts. The briefing states the range ("0–3 doctored today"), never the exact count.
- **Crowd stats:** `data/stats/<case_id>.json` = `{ "posts": { "p1": { "n": 12, "said_doctored": 5, "correct": 9 } } }`. Runtime data, git-ignored.
- **Fool Deck:** `data/fool_deck/<deck_id>.json` holds **real, verified** items only:
  ```jsonc
  {
    "id": "hs-net-increase",
    "kind": "quote",                       // "quote" | "chart" | "stat"
    "post": { /* a case.json post object, real and unedited, author = the real outlet */ },
    "evidence": { /* an evidence.json entry for this post: source / data / account */ },
    "editable": {
      "quote_words": ["Taken", "together", "…"],               // crop: player may DELETE words, never add
      "chart_series": [ { "label": "2025-04", "value": 19.91 } ], // axis/window: the full real series
      "stat": { "full": "…", "droppable": [ { "id": "offset", "text": "…", "shown_without": "…" } ] }
    },
    "tools": ["crop"]                        // subset of "crop" | "axis" | "window" | "drop"
  }
  ```
- **Fool cache:** `data/fool_cache/<sha256>.json`, keyed on the canonical (edited post + evidence). Git-ignored.

### 7.2 Daily API
| Method & path | Body | Returns |
|---|---|---|
| `GET /daily?player_id=` | | `{ case, daily_number, date, theme, already_played, result }`. `case` = case.json. Today = the approved daily with `daily_date == today` (server local date), else the latest `daily_date` ≤ today. `result` = the stored summary if already played. |
| `GET /daily/archive` | | `[ { date, daily_number, title, theme, case_id } ]` |
| `POST /cases/{id}/answer` | `{ player_id, post_id, doctored, trick }` | Records one card and returns its reveal at once: `{ result: <same shape as a verdict results[] item>, crowd: { said_doctored_pct, correct_pct, n } \| null, clues_left }`. `crowd` is null when `n` (including this answer) is below `CROWD_MIN` (env, default 10). **409** if that post is already answered. |
| `POST /cases/{id}/verdict` | `{ player_id, verdicts? }` | If `verdicts` is omitted, uses the recorded answers (422 if any card is unanswered). The §5 response gains the fields below. |

**New fields in the verdict response:**
- `"lean"`: a float from −1 to +1, over the player's recent 30 posts. `lean = false_alarm_rate − miss_rate`, so negative means gullible and positive means paranoid.
- `"lean_label"`:

| lean | label |
|---|---|
| ≤ −0.5 | `Gullible` |
| ≤ −0.15 | `Trusting` |
| < 0.15 | `Balanced` |
| < 0.5 | `Suspicious` |
| ≥ 0.5 | `Paranoid` |

- `"streak"`: consecutive daily dates played. Profile key `daily_played: ["YYYY-MM-DD", …]`.
- `"daily_number"`: an int, or null.
- `"share_text"`: e.g. `"Grain of Salt #3 🧂 4/5 🔥3\n🟩🟩🧂🟥🟩\nBalanced detective"`. Never includes post content.
- **v2 grid emoji** (daily `share_text` and the `share_grid` field):

| Emoji | Meaning |
|---|---|
| 🟩 | trusted (a real post, said real) |
| 🧂 | caught (a fake, said doctored) |
| 🟥 | false_alarm |
| ⬛ | fooled |

  The `4/5` counts correct cards; `🔥3` is the streak.
- **Rarity:** each `answer` result also includes `"rarity": { "correct_pct": 18, "n": 40 } | null` (same `CROWD_MIN` rule). The UI can show "Only 18% got this right."

### 7.3 Con the Con API
| Method & path | Body | Returns |
|---|---|---|
| `GET /fool/deck` | | `[ { id, kind, post, tools, editable } ]`. Evidence is omitted; it's server-side. |
| `POST /fool/judge` | `{ player_id, deck_id, edit }` | see below |

**The `edit` object:** one of
- `{ "type":"none" }`
- `{ "type":"crop", "keep_word_indices":[0,1,5,…] }`
- `{ "type":"axis", "y_min": 19 }`
- `{ "type":"window", "window":["2025-04","2026-07"] }`
- `{ "type":"drop", "drop":"offset" }`

**The response:**
```jsonc
{
  "edited_post": { /* post as the Con sees it: author swapped to a made-up account if changed; watermark stays */ },
  "changed": true,                         // did the edit materially change the post?
  "trick": "out-of-context-quote" | null,  // the trick the player's edit amounts to
  "diff": { /* §2.3 diff, or null */ },
  "con": {
    "checked": ["source"],                 // the ONE evidence tool the Con chose to open
    "verdict": "doctored" | "real",
    "trick_guess": "…" | null,
    "reasoning": ["short line", "short line"],
    "confidence": 0.0-1.0,
    "model": "nvidia/…", "cached": false
  },
  "outcome": "caught" | "fooled_the_con" | "con_false_alarm" | "con_trusted",
  "con_line": "…"                          // a templated quip for the outcome
}
```
- **503 `{ "error": "con_asleep" }`** when there's no API key or the model call fails and nothing is cached. **Never fabricate an AI verdict.**

**Edit rules (enforced in `apply_edit`):**
- crop keeps at least 4 words, in order, deletion only;
- `y_min` must be in [0, the series minimum);
- window months must exist in the series;
- drop ids must exist in `editable.stat.droppable`.

### 7.4 Pipeline functions the backend calls (`pipeline/fool.py`)
- **`apply_edit(deck_item: dict, edit: dict) -> dict`**
  - Deterministic.
  - Returns `{ "edited_post", "changed", "trick", "diff" }`.
  - Raises `ValueError` on an illegal edit.
- **`judge_post(edited_post: dict, evidence: dict) -> dict`**
  - The blind solver, with exactly **one** `open_evidence` call allowed: it chooses which tool.
  - Returns the `con` object above, minus `cached`.
  - Raises `ConAsleep` when there's no key or the model fails.
  - Callers cache via `data/fool_cache/`. Budget: 2 model calls (choose the tool, then the verdict).

## 8. v2.1 additions (polish round, Sat Nov 14)

### 8.1 Con levels (so the Con can be beaten)
`POST /fool/judge` takes an optional `"level": 1 | 2 | 3` (default 3). `judge_post(..., level=)` behaves as follows:

| Level | Name | What the Con gets | Model calls |
|---|---|---|---|
| 1 | Rookie Con | **No evidence.** It judges the post as shown. | 1 (verdict only) |
| 2 | Street Con | **One evidence check**, using the fast fallback model (`nemotron-3.5-lightning:free`) | 2 |
| 3 | Master Con | **One evidence check** with the full models (today's behavior) | 2 |

- The cache key includes the level.
- The response adds `"level"`, plus `"scoreboard": { "by_level": { "1": {"fooled": n, "played": n}, … } }`.
- The `con` object's `checked` is `[]` at level 1.

### 8.2 Grid emoji (replaces §7.2's mapping)

| Emoji | Meaning |
|---|---|
| 🟩 | trusted |
| 🧂 | caught |
| 🟨 | false_alarm |
| 🟥 | fooled |

Stamp colors in the UI match: green, salt/white, amber, red.

**Con the Con outcome words in the UI:**

| Outcome | Wording |
|---|---|
| `caught` | **BUSTED** (the Con caught you) |
| `fooled_the_con` | **FOOLED THE CON** |
| `con_false_alarm` | **FALSE ALARM** |
| `con_trusted` | **TRUSTED** |

### 8.3 One made-up account per deck item
- `GET /fool/deck` items add `"edited_author"`: the made-up account a changed post will show.
- `apply_edit` must use **exactly** that author. It's deterministic per deck item, from a fixed persona list, using invented handles, never realistic personal names.
- The editor's preview shows it, so the account never changes between preview and verdict.

### 8.4 Honest Con lines
- **Daily answers:** if the player marked a post correctly **without opening any evidence for it**, the backend returns a generic line ("Good eye. No receipts needed."), not an answer-key line that claims they checked.
- **Con the Con:** `con_line` must refer only to what actually happened (the edit type, the level, and what the Con checked).

### 8.5 Limits for live AI (env-configurable; cached verdicts are always free and always allowed)

| Variable | Default | Meaning |
|---|---|---|
| `CON_LIVE_DAILY_CAP` | 30 | Live (uncached) judge calls per server day, across everyone |
| `CON_LIVE_PER_PLAYER` | 3 | Live judge rounds per player per day |
| `DEMO_TOKEN` | unset | If the request has the header `X-Demo-Token` equal to it, both caps are skipped (for our demo laptop) |

- **Over a cap:** return `429 {"error":"con_resting","message":"The Con is resting. Try a saved round, or come back tomorrow."}`.
- **The frontend** stores a `?demo=<token>` URL parameter in localStorage and sends it as `X-Demo-Token`.

### 8.6 Public mode (`GOS_PUBLIC=1`)
- **Hide the docs pages:** `/docs`, `/redoc` and `/openapi.json` return 404.
- **Lock the teacher routes:** **all** `/teacher/*` routes require the header `X-Teacher-Token == TEACHER_TOKEN`, otherwise 401. If `GOS_PUBLIC=1` and no `TEACHER_TOKEN` is set, the teacher routes are disabled (404).
- **The frontend Teacher screen** asks for the token once and keeps it in sessionStorage.
- **Rate limit:** `/cases/*/answer` is limited per client IP (loose, about 60 a minute).
- **Without `GOS_PUBLIC`** (local dev and the demo laptop), everything works as it does today.

### 8.7 Entertainment framing and rarity (Krillion-style)
**Rarity bonus.** When a post's crowd stats are shown (`n` ≥ `CROWD_MIN`), a correct answer (trusted or caught) earns a bonus based on how few players got it right:

| `correct_pct` | Label | Bonus |
|---|---|---|
| ≤ 25 | "Rare catch" | +50 |
| ≤ 10 | "One in a shaker" | +100 |

- **Where it appears:** the `answer` result and the verdict `results[]` gain `"rarity_bonus": { "label": "...", "points": n } | null`.
- **Scoring:** the bonus counts toward `score`, using the crowd stats from *before* this answer is counted.
- **Never fake numbers:** below `CROWD_MIN` the bonus is null.

**UI wording:**
- "Teacher" becomes **"Editor's Desk"** ("a human puzzle editor approves every puzzle before it goes live").
- "Case Files (for classrooms)" becomes **"Case Files"** (an archive of extra cases).
- Lead every screen with the game. Media literacy is the payoff, not the pitch.
- Routes and API paths stay the same (`/teacher/*`). Only the labels change.

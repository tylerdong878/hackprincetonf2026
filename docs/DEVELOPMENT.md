# Development notes

The technical details behind the [README](../README.md). The API and data shapes are in [CONTRACT.md](CONTRACT.md).

## Backend

FastAPI game server in `backend/app/`. All routes are under `/api` (CONTRACT §5, §7, §8).

```
uv run python -m uvicorn backend.app.main:app --reload --port 8000   # dev server
uv run python -m pytest backend/tests -q                             # tests
```

**Data and serving:**
- Cases are read from `data/cases/*/` on every request, so the pipeline can add cases live.
- Players only see cases with `meta.status == "approved"`. The Editor's Desk routes (`/api/editor/*`) see everything.
- Player profiles go to `data/players/<id>/profile.json`, and crowd stats to `data/stats/`. Both are git-ignored.
- Set `GOS_DATA_DIR` to use another data folder.
- If `frontend/dist/` exists, it's served at `/` with an SPA fallback, so the demo runs from one server.

**Scoring:**
- Scoring happens on the server, and answer keys never reach the browser before a card is answered.
- Rarity bonus: +50 "Rare catch" at 25% correct or less, +100 "One in a shaker" at 10% or less.
  - It uses the crowd stats from before the answer, and only once `CROWD_MIN` players have answered.

**Con the Con:**
- `POST /api/fool/judge` applies a deterministic edit to a deck post.
- The live judge then rules at level 1, 2 or 3.
- Verdicts are cached in `data/fool_cache/` (git-ignored), and replays of cached verdicts are free.

**Environment** (all optional):

| Variable | Effect |
|---|---|
| `GOS_PUBLIC=1` | Public mode: no `/docs`, `/redoc` or `/openapi.json`; editor routes need `X-Editor-Token`; a per-IP limit on answers (`ANSWER_RATE_PER_MIN`, default 60) |
| `EDITOR_TOKEN` | The `X-Editor-Token` value in public mode. If unset, editor routes are off. The old names still work as aliases: `TEACHER_TOKEN` (read if `EDITOR_TOKEN` is unset), the `X-Teacher-Token` header, `/api/teacher/*`, `#/teacher` and `--hold-for-teacher`. |
| `CON_LIVE_DAILY_CAP` | Live (uncached) Con calls per ET day, everyone together (default 30) |
| `CON_LIVE_PER_PLAYER` | Live Con rounds per player per ET day (default 3) |
| `DEMO_TOKEN` | Requests with a matching `X-Demo-Token` skip both Con caps (the demo laptop: open the site with `?demo=<token>`) |
| `CROWD_MIN` | Answers needed before crowd stats show (default 10) |

## Frontend

Vite + React 19 + TypeScript + Tailwind v4 + Recharts in `frontend/`. The dev server runs on port 5173 and proxies `/api` to the backend on 8000.

```
cd frontend
npm install
npm run dev        # http://localhost:5173 (start the backend first)
npm run build      # typecheck + production build to frontend/dist/ (served by the backend at http://localhost:8000)
```

**Modes:**
- **Daily Grain** (`#/daily`): five cards one at a time, three magnifiers and an instant reveal per card. The end card has the Gullible ↔ Paranoid meter, a streak, the share grid and a countdown to midnight ET.
- **Con the Con** (`#/con`): doctor a real deck post with crop, axis, window or drop, or bluff and leave it real. Then pick a boss: Rookie, Street or Master Con.
- **Case Files** (`#/casefiles`): the longer four-post cases, with the Workshop replay of how the AI built each one.
- **Also:** Stats (`#/dossier`: rating, lean meter, streak, per-trick rates), Tricks (`#/casebook`: a page per trick), and the Editor's Desk (`#/editor`: the approval queue and case review).

**Keyboard:**
- **Daily:** `R` Real, `D` Doctored then `1`–`4` for the trick, `C` Check, Enter for the next card.
- **Case Files:** Tab moves between posts, `R` / `D`, `1`–`4` for the trick, `E` for evidence.

**Design system** (from the designer's Figma file; tokens in `src/index.css`):
- One light newsprint theme: ink `#141414`, newsprint `#F2E8D5`, paper `#FBF7EE`, manila `#E6D3A8`, press red `#C8231B`, ochre `#B9822A`; focus blue `#1F5FD1` only for focus rings and the selected post.
- One hard shadow (4px down-right, solid ink) and 2px ink rules.
- Type: Gloock (the logotype), Bodoni Moda (titles), Oswald (caps headlines, buttons, stamps), Old Standard TT (copy; the Con speaks in its italic). Inter appears only inside post cards, so posts still look like a social app.
- Line icons (`src/components/Icon.tsx`, the designer's SVGs plus `lucide-react`) replace emoji in the UI; the share text keeps emoji.
- The noir Con silhouette and halftone frame are in `src/assets/figma/`.

**Other:**
- The player id lives in `localStorage` (`gos.player_id`). "Start as a new detective" on Home or Stats resets it, which is handy between demo players.
- Sound effects have a mute toggle in the header.
- Shared links show a preview card (`public/og.png` and the `og:` tags in `index.html`).

## Pipeline

The Deep Agents case builder in `pipeline/`. It runs offline; the game only plays saved cases. It needs `OPENROUTER_API_KEY` (or `GEMINI_API_KEY`) in `.env`.

```
uv run python -m pipeline.build_case --topic "NJ electricity prices"                 # interactive editor review
uv run python -m pipeline.build_case --topic "NJ electricity prices" --auto-approve
uv run python -m pipeline.build_case --clean --hold-for-editor    # approve later in the web Editor's Desk
uv run python -m pipeline.build_case --trick misleading-chart     # or --player <id> to target a weak spot
uv run python -m pipeline.build_case --mode daily --daily-date 2026-11-20   # a 5-card Daily Grain
uv run python -m pipeline.build_case --dry-run                    # build the graph, no model calls
uv run python -m pytest pipeline/tests -q                                   # no network, no LLM
```

**Agents:** the **orchestrator** (`create_deep_agent`, planning with todos) delegates through `task` to three sub-agents:
- **Researcher:** reads feeds, pages and EIA data. `save_source` rejects anything that isn't word for word in a document fetched during this run.
- **Forger:** loads `data/skills/<trick>/SKILL.md`. `crop_quote`, `make_chart`, `make_stat_claim` and `edit_detail` doctor real material in code. `write_case` checks CONTRACT §2, the topic blocklist and the made-up-author rule.
- **Blind solver:** a compiled sub-agent with no file tools, only `open_evidence`, `view_chart` and `submit_verdict`. Its input is rebuilt from `case.json`, and it's graded against the answer key in code.

**Files and approval:**
- `CompositeBackend` routes `/cases/` and `/skills/` to `FilesystemBackend`s on `data/`.
- Permissions block reading `answer_key.json` and hand-writing case or skill files through the file tools.
- `submit_for_review` is gated by `interrupt_on` with a checkpointer. The editor can approve, reject with feedback (the agent revises), edit, or hold the case, which leaves `meta.status` at `awaiting_approval`.

**Output per case:**
- `sources.json`
- the four CONTRACT files
- `solver_log.md`
- `rendered/*.png`
- `pipeline_log.jsonl` (CONTRACT §6 events, with spoilers marked)

**Free tier and deadlines:**
- Every request counts, failures included.
- Runs are throttled to `PIPELINE_RPM` (15/min) and capped at `PIPELINE_MAX_CALLS`. A 429 is retried with backoff.
- A daily-cap 429 stops the run, or falls back to Gemini when both keys are set.
- Every model request has a wall-clock deadline: `PIPELINE_CALL_DEADLINE_S` (120 s offline) and `PIPELINE_JUDGE_DEADLINE_S` (20 s for the live judge). On a timeout, the run switches to `PIPELINE_FALLBACK_MODEL`.

**Tracing:** set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` to trace every build ("Grain of Salt · build <case_id>") and every live judgment ("Con the Con · live judge").

**Con the Con (`pipeline/fool.py`):**
- `apply_edit(deck_item, edit)` makes deterministic edits, and a changed post moves to a fixed made-up account.
- `judge_post(edited_post, evidence, level=)` works by level:
  - Level 1: verdict only.
  - Level 2: one evidence check on the fast model.
  - Level 3: one check on the full models.
- The judge sees every post from the same neutral reposter, so it can't tell edits apart by author.

## Nightly builds

`scripts/nightly_build.py` adds one AI-built Daily Grain to the backlog per run. It finds the earliest date in the next 14 days with no daily case, picks that weekday's theme, builds it, and holds it for the Editor's Desk.

```
uv run --env-file .env.build python scripts/nightly_build.py            # build one puzzle
uv run --env-file .env.build python scripts/nightly_build.py --dry-run  # say what it would build
```

- Keep the build key in a separate `.env.build`, so builds never spend the game server's live-judging quota.
- Weekday themes come from `TOPIC_HINTS` in `pipeline/topics.py`: food, sports, science, tech and Jersey Weird. Each topic reads only its listed feeds. Topics without chart data skip the misleading-chart trick.
- Each run is capped at 30 model calls, with 2 held back so the run always reaches the editor instead of stopping as a draft.

## iMessage bot

`backend/imessage/` plays the Daily Grain over iMessage through Photon 2.0. It's a separate process that polls Photon for new texts and plays through the game server's API, so texts and taps share the same scoring and crowd stats.

```
uv run python -m backend.imessage
uv run python -m pytest backend/tests/test_imessage.py -q
```

- **Needs:** `PHOTON_API_KEY` and `PHOTON_PROJECT_ID` (a Photon 2.0 project), and `GOS_API_URL` pointing at the game server (default `http://127.0.0.1:8000`).
- **Commands are loose on purpose:** "play"; REAL / FAKE ("sus", "cap", 👍 and 👎 work too); a trick name ("fake chart"); CHECK source, data or account; HINT; STATS; HELP; STOP to mute reminders.
- **Reminders:** `GOS_NUDGE_HOUR` sets the daily reminder hour in ET (default 9; -1 turns them off).
- **The detective partner** answers free-form texts. It tries Gemini first (`GOS_PARTNER_ORDER`, default `gemini,openrouter`), with `GOS_PARTNER_DAILY` replies per player per day (default 40).
- **Shared Photon lines:** each player must be added to the line and text it first before the bot can reply.
- **Run one copy only,** or every text gets two replies.

## The Con the Con deck

`scripts/build_daily_cases.py` builds the Con the Con deck (`data/fool_deck/`) from a bank of excerpts, each copied word for word. Every live daily comes from the Deep Agents pipeline; the script's old hand-built launch-week dailies are retired and only written with `--with-dailies`.
- `--verify` re-fetches every source page and confirms every excerpt is still on it.
- Every source is listed in [CONTENT_SOURCES.md](CONTENT_SOURCES.md).
- Before writing anything, the builder checks that crops only delete words, that charts match their data, and that no display field (account type, missing label) gives an answer away.

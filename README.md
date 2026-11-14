# hackprincetonf2026

## Backend

FastAPI game server in `backend/app/` (API per CONTRACT.md §5, all under `/api`).

```
uv run uvicorn backend.app.main:app --reload --port 8000   # dev server
uv run pytest backend/tests -q                             # tests
```

- Reads cases from `data/cases/*/` on every request (the pipeline can add cases live). Players only see `meta.status == "approved"`; teacher routes see everything.
- Player profiles go to `data/players/<id>/profile.json` (git-ignored). Set `GOS_DATA_DIR` to use another data folder.
- If `frontend/dist/` exists, it is served at `/` with SPA fallback, so the demo can run from one server.
- Clue budgets are kept in memory per (player, case) and reset on restart or after a verdict.
- Mastery (0-3, per trick, all-time): 3 = caught >= 3 with miss and false-alarm rates <= 25%; 2 = caught >= 2 with miss rate <= 50%; 1 = caught at least once; 0 = never caught.

## Frontend

Vite + React + TypeScript + Tailwind v4 + Recharts in `frontend/`. Dev server on port 5173 proxies `/api` to the backend on 8000.

```
cd frontend
npm install
npm run dev        # http://localhost:5173 (start the backend first)
npm run build      # typecheck + production build to frontend/dist/ (the backend serves it at http://localhost:8000)
```

- Modes: **The Daily Grain** (`#/daily`: five cards one at a time, 3 magnifiers, an instant flip reveal per card, then an end card with the Gullible-to-Paranoid meter, streak, share text and a countdown to midnight ET), **Con the Con** (`#/con`: doctor a real Fool Deck post with crop / axis / window / drop, or bluff, then watch the AI judge rule), and **Case Files** (`#/casefiles`: the v1 four-post feed for classrooms, with the Workshop replay).
- Also: Dossier (lean meter, streak, per-trick rates), Casebook, Teacher queue and case review.
- Keyboard: in the Daily, `R` Real, `D` Doctored then `1`-`4` for the trick, `C` Check, Enter for the next card. In Case Files, Tab moves between posts, `R` / `D`, `1`-`3`, `E` for evidence.
- The player id lives in `localStorage` (`gos.player_id`). "Start as a new detective" on Home or the Dossier resets it, which is handy between demo players.
- Theme follows `prefers-color-scheme` (dark is the default). The logo switches between its `-dark` and `-light` files to match.

## Pipeline

Deep Agents case builder in `pipeline/` (offline; the game only plays saved cases). Needs `OPENROUTER_API_KEY` (or `GEMINI_API_KEY`) in `.env`.

```
uv run python -m pipeline.build_case --topic "NJ electricity prices"                 # interactive teacher review
uv run python -m pipeline.build_case --topic "NJ electricity prices" --auto-approve
uv run python -m pipeline.build_case --clean --hold-for-teacher   # approve later in the web teacher queue
uv run python -m pipeline.build_case --trick misleading-chart     # or --player <id> to target a weak spot
uv run python -m pipeline.build_case --dry-run                    # build the graph, no model calls
uv run pytest pipeline/tests -q                                   # no network, no LLM
```

- **Orchestrator** (`create_deep_agent`, `TodoListMiddleware` plan) delegates via `task` to **researcher** (feeds, pages, EIA; `save_source` rejects anything not verbatim in a document fetched this run), **forger** (loads `data/skills/<trick>/SKILL.md`; `crop_quote` / `make_chart` / `make_stat_claim` doctor real material in code; `write_case` validates CONTRACT §2, the blocklist and the made-up-author rule) and **blind-solver** (a compiled sub-agent with no file tools: only `open_evidence`, `view_chart`, `submit_verdict`; its input is rebuilt from `case.json`, and grading against the answer key happens in code).
- Files: `CompositeBackend` routes `/cases/` and `/skills/` to `FilesystemBackend`s on `data/`; permissions deny reading `answer_key.json` and hand-writing case/skill files through the file tools.
- Human-in-the-loop: `submit_for_review` is gated by `interrupt_on` + `MemorySaver`. Approve, reject with feedback (the agent revises), edit in the terminal, or hold (`meta.status` stays `awaiting_approval`).
- Output per case: `sources.json`, the four CONTRACT files (`origin: "pipeline"`), `solver_log.md`, `rendered/*.png`, and `pipeline_log.jsonl` (CONTRACT §6 events, spoilers marked).
- Free tier: every request is counted (including failures), throttled to `PIPELINE_RPM` (15/min) and capped at `PIPELINE_MAX_CALLS` (45/run); 429s are retried with backoff, a daily-cap 429 stops the run (or falls back to Gemini when both keys are set). A clean run is about 14 requests.
- Deadlines: every model request has a wall-clock deadline (`PIPELINE_CALL_DEADLINE_S`, 120 s offline; `PIPELINE_JUDGE_DEADLINE_S`, 20 s for the live judge). ChatOpenRouter's `timeout` only bounds each network read, so a slow reply can hang without this. On a timeout the run switches to `PIPELINE_FALLBACK_MODEL` (default `nvidia/nemotron-3.5-lightning:free`). `max_retries=0` everywhere. `GEMINI_MODEL` picks the Gemini model (default `gemini-flash-latest`).
- **v2 Daily:** `--mode daily --daily-date YYYY-MM-DD [--theme "..."] [--doctored 0-3]` builds a 5-post Daily Grain (0–3 doctored, planned from the weekday; briefing says "0–3 doctored today"; `meta.mode/daily_date/theme`, `card_style` per post; capped at 25 calls, 1 solver retry). New trick `edited-detail` (`edit_detail` tool + `data/skills/edited-detail/SKILL.md`).
- **v2 Con the Con:** `pipeline/fool.py` has `apply_edit(deck_item, edit)` (deterministic §7.3 edits; a changed post moves to a made-up account) and `judge_post(edited_post, evidence)` (one evidence look, then a verdict; 2 calls, one fallback, raises `ConAsleep`). The judge sees every post from the same neutral reposter, so it can't tell edits apart by author.

"""Grain of Salt game server (CONTRACT §5, §7 and §8).

Run:  uv run uvicorn backend.app.main:app --reload --port 8000
Data: data/ by default; override with the GOS_DATA_DIR env var (or create_app(data_dir=...)).

Env (all optional):
  GOS_PUBLIC=1            public mode (§8.6): no /docs /redoc /openapi.json, Editor's Desk routes need X-Editor-Token,
                          per-IP limit on /cases/*/answer (ANSWER_RATE_PER_MIN, default 60)
  EDITOR_TOKEN            the X-Editor-Token value in public mode (unset -> editor routes are off, 404).
                          Back-compat: TEACHER_TOKEN is read if EDITOR_TOKEN is unset, and X-Teacher-Token is accepted.
  CON_LIVE_DAILY_CAP      live (uncached) Con judge calls per ET day, everyone together (default 30)
  CON_LIVE_PER_PLAYER     live Con judge rounds per player per ET day (default 3)
  DEMO_TOKEN              requests with X-Demo-Token equal to it skip both Con caps (the demo laptop)
  CROWD_MIN               answers needed before crowd stats show (default 10)
"""
from __future__ import annotations

import copy
import os
import random
from datetime import date
from pathlib import Path
from typing import Annotated, Callable

try:  # Load .env before anything reads LangSmith/OpenRouter settings: LangSmith caches its tracing flag on
    # first check, so loading it lazily (inside the first Con the Con call) left live verdicts untraced.
    # override=False keeps variables that are already set (tests turn tracing off this way).
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:  # pragma: no cover
    pass

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path as PathParam, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import con_the_con as ctc
from .con_lines import adaptation_message, honest_result
from .daily import (crowd_view, current_daily, daily_number, dailies, is_daily, rarity_bonus, released, streak,
                    today_et)
from .limits import CON_RESTING, LiveUsage, RateLimiter, client_ip, token_matches
from .models import (AnswerRequest, EvidenceRequest, FoolJudgeRequest, PostVerdict, RejectRequest,
                     VerdictRequest)
from .scoring import (FORMAT_TRICK, lean, lean_label, per_trick, post_format, rank, rating,
                      record_verdict, score_case, score_post, share_text)
from .selection import Candidate, pick_next
from .store import (ID_PATTERN, CaseRecord, Store, is_clean, new_profile, now_iso, read_jsonl,
                    valid_id)
from .views import player_view

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
FOOL_ROUNDS_KEPT = 50

router = APIRouter(prefix="/api")
DOCS_PATHS = {"docs", "redoc", "openapi.json"}


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_today(request: Request) -> date:
    return request.app.state.today()


StoreDep = Annotated[Store, Depends(get_store)]
TodayDep = Annotated[date, Depends(get_today)]
CaseId = Annotated[str, PathParam(pattern=ID_PATTERN)]
PlayerId = Annotated[str, PathParam(pattern=ID_PATTERN)]


def check_player_query(player_id: str | None) -> str | None:
    if player_id and not valid_id(player_id):
        raise HTTPException(422, "Invalid player id")
    return player_id or None


def playable(store: Store, case_id: str, today: date) -> CaseRecord:
    """Approved, and (for a daily) its date has come."""
    rec = store.playable_case(case_id)
    if rec is None or not released(rec, today):
        raise HTTPException(404, "Case not found")
    return rec


def any_case(store: Store, case_id: str) -> CaseRecord:
    rec = store.get_case(case_id)
    if rec is None:
        raise HTTPException(404, "Case not found")
    return rec


def casefiles(store: Store) -> list[CaseRecord]:
    """The v1 Case Files: approved, non-daily cases."""
    return [r for r in store.approved_cases() if not is_daily(r)]


def player_summary(profile: dict, today: date) -> dict:
    r = rating(profile["recent"])
    lv = lean(profile["recent"])
    return {**profile, "rating": r, "rank": rank(r), "per_trick": per_trick(profile["tricks"]),
            "lean": lv, "lean_label": lean_label(lv), "streak": streak(profile["daily_played"], today)}


def candidate(rec: CaseRecord) -> Candidate:
    ak = rec.answer_key()
    keys = ak.get("posts", {})
    honest = {FORMAT_TRICK[post_format(p)] for p in rec.case.get("posts", [])
              if not keys.get(p.get("id"), {}).get("doctored")}
    return Candidate(id=rec.id, number=rec.number, tricks=list(rec.meta.get("tricks") or []),
                     clean=is_clean(ak, rec.meta), honest_tricks=honest)


def find_post(rec: CaseRecord, post_id: str) -> dict:
    post = next((p for p in rec.case.get("posts", []) if p.get("id") == post_id), None)
    if post is None:
        raise HTTPException(404, "Post not found")
    return post


def clues_left(store: Store, rec: CaseRecord, player_id: str) -> int:
    budget = int(rec.case.get("clue_budget") or 0)
    return max(0, budget - len(store.sessions.get((player_id, rec.id), ())))


def looked_at(store: Store, player_id: str, case_id: str, post_id: str) -> bool:
    """Did this player open any evidence for this post (this clue session)?"""
    return any(pid == post_id for pid, _ in store.sessions.get((player_id, case_id), ()))


def card_seed(player_id: str, case_id: str, post_id: str) -> str:
    return f"{player_id}:{case_id}:{post_id}"


def answer_rate_limit(request: Request) -> None:
    """Public mode only (§8.6): a loose per-IP limit on /cases/*/answer."""
    state = request.app.state
    if state.public and not state.answer_limiter.allow(client_ip(request)):
        raise HTTPException(429, "Too many answers from this address. Try again in a minute.")


EDITOR_TOKEN_HEADERS = ("x-editor-token", "x-teacher-token")  # x-teacher-token: old name, kept as an alias


def editor_guard(request: Request) -> None:
    """Public mode only (§8.6): every /editor/* route needs X-Editor-Token; no EDITOR_TOKEN -> routes off."""
    state = request.app.state
    if not state.public:
        return
    if not state.editor_token:
        raise HTTPException(404, "Not found")
    if not any(token_matches(request.headers.get(h), state.editor_token) for h in EDITOR_TOKEN_HEADERS):
        raise HTTPException(401, "Editor token required")


# ---- health & players --------------------------------------------------------

@router.get("/health")
def health():
    return {"ok": True}


@router.post("/players")
def create_player(store: StoreDep):
    return {"player_id": store.create_profile()["player_id"]}


@router.get("/players/{player_id}")
def get_player(player_id: PlayerId, store: StoreDep, today: TodayDep):
    profile = store.load_profile(player_id)
    if profile is None:
        raise HTTPException(404, "Player not found")
    return player_summary(profile, today)


# ---- Case Files (player routes: approved cases only, no answers) --------------

@router.get("/cases")
def list_cases(store: StoreDep):
    return [
        {"id": r.id, "number": r.case.get("number"), "title": r.case.get("title"),
         "topic": r.case.get("topic"), "daily": bool(r.meta.get("daily")),
         "origin": r.meta.get("origin"), "difficulty": r.meta.get("difficulty")}
        for r in casefiles(store)
    ]


@router.get("/cases/today")
def today_case(store: StoreDep):
    cases = casefiles(store)
    if not cases:
        raise HTTPException(404, "No approved cases")
    rec = next((r for r in cases if r.meta.get("daily")), cases[0])
    return player_view(rec.case)


@router.get("/cases/next")
def next_case(store: StoreDep, player_id: str | None = None):
    player_id = check_player_query(player_id)
    profile = (store.load_profile(player_id) if player_id else None) or {}
    cases = casefiles(store)
    # Seeded by player + progress: deterministic, but varies as the player plays.
    rng = random.Random(f"{player_id}:{len(profile.get('history', []))}")
    pick = pick_next([candidate(r) for r in cases], profile, rng)
    if pick is None:
        raise HTTPException(404, "No approved cases")
    return player_view(next(r for r in cases if r.id == pick.id).case)


@router.get("/cases/{case_id}")
def get_case(case_id: CaseId, store: StoreDep, today: TodayDep):
    return player_view(playable(store, case_id, today).case)


@router.post("/cases/{case_id}/evidence")
def open_evidence(case_id: CaseId, body: EvidenceRequest, store: StoreDep, today: TodayDep):
    rec = playable(store, case_id, today)
    post = find_post(rec, body.post_id)
    if body.tool not in post.get("tools", []):
        raise HTTPException(404, "That tool has nothing for this post")
    evidence = rec.evidence().get(body.post_id, {}).get(body.tool)
    if evidence is None:
        raise HTTPException(404, "Evidence missing for this post and tool")
    budget = int(rec.case.get("clue_budget") or 0)
    with store.lock:
        opened = store.sessions.setdefault((body.player_id, case_id), set())
        key = (body.post_id, body.tool)
        if key not in opened:  # re-opening is free
            if len(opened) >= budget:
                raise HTTPException(409, "Out of clue tokens")
            opened.add(key)
        left = max(0, budget - len(opened))
    return {"evidence": evidence, "clues_left": left}


@router.post("/cases/{case_id}/answer", dependencies=[Depends(answer_rate_limit)])
def answer_card(case_id: CaseId, body: AnswerRequest, request: Request, store: StoreDep, today: TodayDep):
    """One card, revealed at once, with crowd stats from real answers only."""
    rec = playable(store, case_id, today)
    post = find_post(rec, body.post_id)
    key = rec.answer_key().get("posts", {}).get(body.post_id, {})
    with store.lock:
        profile = store.load_profile(body.player_id) or new_profile(body.player_id)
        answers = profile["answers"].setdefault(case_id, {})
        if body.post_id in answers or case_id in profile["daily_results"]:
            raise HTTPException(409, "Already answered")
        result, record = score_post(post, key, body.doctored, body.trick)
        looked = looked_at(store, body.player_id, case_id, body.post_id)
        result = honest_result(result, looked, card_seed(body.player_id, case_id, body.post_id))
        correct = record["outcome"] in ("trusted", "caught")
        # §8.7: the bonus uses the crowd stats from BEFORE this answer is counted.
        before = store.case_stats(case_id).get(body.post_id) or {}
        result["rarity_bonus"] = rarity_bonus(before, request.app.state.crowd_min, correct)
        answers[body.post_id] = {"doctored": body.doctored, "trick": body.trick, "at": now_iso(), "checked": looked,
                                 "rarity_bonus": result["rarity_bonus"]}
        store.save_profile(profile)
        counts = store.bump_stats(case_id, body.post_id, said_doctored=body.doctored, correct=correct)
        left = clues_left(store, rec, body.player_id)
    crowd, rarity = crowd_view(counts, request.app.state.crowd_min)
    return {"result": {**result, "rarity": rarity}, "crowd": crowd, "clues_left": left}


@router.post("/cases/{case_id}/verdict")
def submit_verdict(case_id: CaseId, body: VerdictRequest, request: Request, store: StoreDep, today: TodayDep):
    rec = playable(store, case_id, today)
    answer_key = rec.answer_key()
    daily = is_daily(rec)
    with store.lock:
        profile = store.load_profile(body.player_id) or new_profile(body.player_id)
        if daily and case_id in profile["daily_results"]:
            return profile["daily_results"][case_id]  # one play per daily; same result again
        # Recorded per-card answers win: a card already revealed can't be changed afterwards.
        verdicts = dict(body.verdicts or {})
        recorded = profile["answers"].get(case_id, {})
        for pid, a in recorded.items():
            verdicts[pid] = PostVerdict(doctored=a["doctored"], trick=a.get("trick"))
        missing = [p["id"] for p in rec.case.get("posts", []) if p["id"] not in verdicts]
        if missing:
            raise HTTPException(422, f"Missing verdict for post(s): {', '.join(missing)}")
        # The clue session ends with the verdict, so replaying a Case File starts fresh.
        opened = store.sessions.pop((body.player_id, case_id), set())
        # §8.7: a card answered one at a time keeps the bonus it got then; a card judged only here uses today's
        # crowd stats (a verdict doesn't count toward them, so they are "before" this answer).
        stats, crowd_min = store.case_stats(case_id), request.app.state.crowd_min
        rarity = {}
        for post in rec.case.get("posts", []):
            pid = post["id"]
            if pid in recorded:
                rarity[pid] = recorded[pid].get("rarity_bonus")
            else:
                rarity[pid] = rarity_bonus(stats.get(pid) or {}, crowd_min, True)  # applied only if correct
        scored = score_case(rec.case, answer_key, verdicts, clues_used=len(opened), rarity=rarity)
        opened_posts = {pid for pid, _ in opened}
        scored["results"] = [
            honest_result(r, recorded[r["post_id"]]["checked"] if "checked" in recorded.get(r["post_id"], {})
                          else r["post_id"] in opened_posts, card_seed(body.player_id, case_id, r["post_id"]))
            for r in scored["results"]
        ]
        record_verdict(profile, case_id, scored, [tool for _, tool in opened], now_iso())
        if daily:
            if today.isoformat() not in profile["daily_played"]:
                profile["daily_played"].append(today.isoformat())
        else:
            profile["answers"].pop(case_id, None)
        r, lv = rating(profile["recent"]), lean(profile["recent"])
        label, days = lean_label(lv), streak(profile["daily_played"], today)
        number = daily_number(rec, dailies(store.approved_cases())) if daily else None
        response = {k: v for k, v in scored.items() if k != "records"}
        response.update(
            rating=r, rank=rank(r), adaptation_message=adaptation_message(scored, profile),
            lean=lv, lean_label=label, streak=days, daily_number=number,
            share_text=share_text(scored["results"], label, number, days, rec.case.get("number")),
        )
        if daily:
            profile["daily_results"][case_id] = response
        store.save_profile(profile)
    return response


@router.get("/cases/{case_id}/pipeline-log")
def pipeline_log(case_id: CaseId, store: StoreDep):
    # Any status: the Workshop panel may show a case that is still being built.
    events = read_jsonl(store.case_file(case_id, "pipeline_log.jsonl"))
    if events is None:
        raise HTTPException(404, "No pipeline log for this case")
    return events


# ---- the Daily Grain (CONTRACT §7.2) --------------------------------------------

@router.get("/daily")
def get_daily(store: StoreDep, today: TodayDep, player_id: str | None = None):
    player_id = check_player_query(player_id)
    all_dailies = dailies(store.approved_cases())
    rec = current_daily(all_dailies, today)
    if rec is None:
        raise HTTPException(404, "No daily yet")
    profile = store.load_profile(player_id) if player_id else None
    result = profile["daily_results"].get(rec.id) if profile else None
    # Cards this player already answered (and so already saw revealed), for resuming mid-daily.
    keys = rec.answer_key().get("posts", {}) if profile else {}
    answered = {}
    for pid, a in (profile["answers"].get(rec.id, {}) if profile else {}).items():
        post = next((p for p in rec.case.get("posts", []) if p.get("id") == pid), None)
        if post:
            card = score_post(post, keys.get(pid, {}), a["doctored"], a.get("trick"))[0]
            if card["outcome"] in ("trusted", "caught"):
                card["rarity_bonus"] = a.get("rarity_bonus")
            looked = a["checked"] if "checked" in a else looked_at(store, player_id, rec.id, pid)
            answered[pid] = honest_result(card, looked, card_seed(player_id, rec.id, pid))
    return {"case": player_view(rec.case), "daily_number": daily_number(rec, all_dailies),
            "date": rec.meta.get("daily_date"), "theme": rec.meta.get("theme"),
            "already_played": result is not None, "result": result,
            "answered": answered, "clues_left": clues_left(store, rec, player_id or "")}


@router.get("/daily/archive")
def daily_archive(store: StoreDep, today: TodayDep):
    all_dailies = dailies(store.approved_cases())
    return [{"date": d.isoformat(), "daily_number": daily_number(r, all_dailies), "title": r.case.get("title"),
             "theme": r.meta.get("theme"), "case_id": r.id}
            for d, r in reversed(all_dailies) if d <= today]


# ---- Con the Con (CONTRACT §7.3) ------------------------------------------------

def con_asleep() -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": "con_asleep"})


@router.get("/fool/deck")
def fool_deck(store: StoreDep):
    return [ctc.deck_view(item) for item in store.fool_deck()]


@router.post("/fool/judge")
def fool_judge(body: FoolJudgeRequest, request: Request, store: StoreDep, today: TodayDep):
    item = store.fool_item(body.deck_id)
    if item is None:
        raise HTTPException(404, "Deck item not found")
    etype = body.edit.get("type")
    if etype not in ctc.EDIT_TYPES or (etype != "none" and etype not in (item.get("tools") or [])):
        raise HTTPException(422, f"Edit type {etype!r} isn't allowed for this post")
    level = body.level or ctc.DEFAULT_LEVEL
    fool = ctc.load_fool()
    if fool is None:
        return con_asleep()
    try:
        applied = fool.apply_edit(copy.deepcopy(item), copy.deepcopy(body.edit))
    except ValueError as e:
        raise HTTPException(422, str(e))
    edited, evidence = applied["edited_post"], item.get("evidence") or {}
    key = ctc.cache_key(edited, evidence, level)
    con = store.fool_cache_get(key)
    cached = ctc.valid_con(con, level)
    if not cached:  # a live call: cached verdicts are always free and always allowed (§8.5)
        state, day = request.app.state, today.isoformat()
        demo = token_matches(request.headers.get("x-demo-token"), state.demo_token)
        if not state.live_usage.reserve(day, body.player_id, demo):
            return JSONResponse(status_code=429, content=CON_RESTING)
        try:
            con = fool.judge_post(copy.deepcopy(edited), copy.deepcopy(evidence), level=level)
        except Exception:  # ConAsleep, no key, model/network failure
            con = None
        if not ctc.valid_con(con, level):  # never pass off a malformed answer as the Con's verdict
            state.live_usage.release(day, body.player_id, demo)
            return con_asleep()
        con = {k: v for k, v in con.items() if k != "cached"}
        store.fool_cache_put(key, con)
    changed = bool(applied.get("changed"))
    result = ctc.outcome(changed, con["verdict"])
    with store.lock:
        profile = store.load_profile(body.player_id) or new_profile(body.player_id)
        rounds = profile["fool_rounds"]
        rounds.append({"deck_id": body.deck_id, "edit": etype, "level": level, "outcome": result, "at": now_iso()})
        del rounds[:-FOOL_ROUNDS_KEPT]
        store.save_profile(profile)
    return {
        "edited_post": edited, "changed": changed, "trick": applied.get("trick"), "diff": applied.get("diff"),
        "con": {**con, "cached": cached}, "outcome": result, "level": level,
        "con_line": ctc.con_line(result, etype if changed else "none", level, con.get("checked")),
        "scoreboard": ctc.scoreboard(rounds),
    }


# ---- Editor's Desk (all statuses; open locally, token-locked in public mode §8.6) ----------
# Mounted at /api/editor, plus /api/teacher as a hidden alias so old links keep working (see create_app).

editor = APIRouter(dependencies=[Depends(editor_guard)])


@editor.get("/queue")
def editor_queue(store: StoreDep):
    return [
        {"id": r.id, "number": r.case.get("number"), "title": r.case.get("title"),
         "topic": r.case.get("topic"), "meta": r.meta,
         "has_pipeline_log": (r.dir / "pipeline_log.jsonl").is_file(),
         "has_solver_log": (r.dir / "solver_log.md").is_file()}
        for r in store.all_cases()
    ]


@editor.get("/cases/{case_id}")
def editor_case(case_id: CaseId, store: StoreDep):
    rec = any_case(store, case_id)
    return {"case": rec.case, "evidence": rec.evidence(), "answer_key": rec.answer_key(),
            "meta": rec.meta, "solver_log": rec.solver_log()}


@editor.post("/cases/{case_id}/approve")
def approve_case(case_id: CaseId, store: StoreDep):
    with store.lock:
        rec = any_case(store, case_id)
        rec.meta.update(status="approved", rejection_reason=None)
        store.save_meta(rec)
    return rec.meta


@editor.post("/cases/{case_id}/reject")
def reject_case(case_id: CaseId, store: StoreDep, body: RejectRequest | None = None):
    with store.lock:
        rec = any_case(store, case_id)
        rec.meta.update(status="rejected", rejection_reason=(body.reason if body else None) or None)
        store.save_meta(rec)
    return rec.meta


# ---- app ---------------------------------------------------------------------

def spa(full_path: str, request: Request):
    """Serve frontend/dist (if built) with SPA fallback to index.html."""
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(404, "Not found")
    if request.app.state.public and full_path.split("/", 1)[0] in DOCS_PATHS:
        raise HTTPException(404, "Not found")  # public mode: no API docs (§8.6), not even the SPA fallback
    dist = request.app.state.frontend_dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise HTTPException(404, "Frontend not built (npm run build in frontend/). The API is under /api.")
    if full_path:
        target = (dist / full_path).resolve()
        if target.is_file() and target.is_relative_to(dist):
            return FileResponse(target)
    return FileResponse(index)


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def create_app(data_dir: str | Path | None = None, frontend_dist: str | Path | None = None,
               today: Callable[[], date] | None = None, crowd_min: int | None = None,
               public: bool | None = None) -> FastAPI:
    public = env_flag("GOS_PUBLIC") if public is None else public
    docs = {"docs_url": None, "redoc_url": None, "openapi_url": None} if public else {}
    app = FastAPI(title="Grain of Salt", **docs)
    app.state.store = Store(Path(data_dir or os.environ.get("GOS_DATA_DIR") or DEFAULT_DATA_DIR))
    app.state.frontend_dist = Path(frontend_dist or DEFAULT_FRONTEND_DIST)
    app.state.today = today or today_et
    app.state.crowd_min = crowd_min if crowd_min is not None else int(os.environ.get("CROWD_MIN", "10"))
    app.state.public = public
    app.state.editor_token = (os.environ.get("EDITOR_TOKEN", "").strip()
                              or os.environ.get("TEACHER_TOKEN", "").strip()  # old name, still read as a fallback
                              or None)
    app.state.demo_token = os.environ.get("DEMO_TOKEN", "").strip() or None
    app.state.live_usage = LiveUsage(app.state.store.data_dir / "stats" / "con_live_usage.json",
                                     daily_cap=env_int("CON_LIVE_DAILY_CAP", 30),
                                     per_player=env_int("CON_LIVE_PER_PLAYER", 3))
    app.state.answer_limiter = RateLimiter(limit=env_int("ANSWER_RATE_PER_MIN", 60))
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    app.include_router(editor, prefix="/api/editor")
    app.include_router(editor, prefix="/api/teacher", include_in_schema=False)  # old path, hidden alias
    app.add_api_route("/{full_path:path}", spa, methods=["GET"], include_in_schema=False)
    return app


app = create_app()

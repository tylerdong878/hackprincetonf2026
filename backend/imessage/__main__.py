"""Run the iMessage bot:  uv run python -m backend.imessage

Env (.env is loaded):
  PHOTON_API_KEY, PHOTON_PROJECT_ID   required (Photon 2.0 project, key with project:read + project:write)
  PHOTON_AGENT_HANDLE                 the bot's iMessage number; texts to other lines are ignored (optional)
  GOS_API_URL                         the game server (default http://127.0.0.1:8000)
  GOS_NUDGE_HOUR                      ET hour for the daily reminder (default 9; -1 turns reminders off)
  GOS_POLL_SECONDS                    how often to check for new texts (default 2)
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
load_dotenv(REPO / ".env", override=False)

from backend.app.daily import today_et  # noqa: E402

from .engine import Engine, GameAPI, Sessions  # noqa: E402
from .photon_io import PhotonIO, nudge_key  # noqa: E402
from .render import Out  # noqa: E402

log = logging.getLogger("gos.imessage")


def et_hour() -> int:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).hour
    except Exception:
        return datetime.utcnow().hour - 5


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    for name in ("PHOTON_API_KEY", "PHOTON_PROJECT_ID"):
        if not os.environ.get(name):
            print(f"Missing {name} (put it in .env).", file=sys.stderr)
            return 1
    api_url = os.environ.get("GOS_API_URL", "http://127.0.0.1:8000")
    nudge_hour = int(os.environ.get("GOS_NUDGE_HOUR", "9"))
    poll_s = float(os.environ.get("GOS_POLL_SECONDS", "2"))
    state_dir = Path(os.environ.get("GOS_DATA_DIR") or REPO / "data") / "imessage"

    http = httpx.Client(base_url=api_url, timeout=30)
    try:
        http.get("/api/health").raise_for_status()
    except Exception:
        print(f"Game server not reachable at {api_url}. Start it first:\n"
              "  uv run uvicorn backend.app.main:app --port 8000", file=sys.stderr)
        return 1
    engine = Engine(GameAPI(http), Sessions(state_dir / "sessions.json"))
    io = PhotonIO(os.environ["PHOTON_API_KEY"], os.environ["PHOTON_PROJECT_ID"],
                  os.environ.get("PHOTON_AGENT_HANDLE") or None, state_dir / "cursor.json")
    log.info("🧂 Grain of Salt is listening on %s. Text it!", os.environ.get("PHOTON_AGENT_HANDLE") or "your line")
    next_nudge_check = 0.0
    try:
        while True:
            try:
                for msg in io.poll():
                    log.info("<- %s: %s", msg.handle[-4:], msg.text if msg.text is not None else "[attachment]")
                    if msg.text is None:
                        outs = [Out.t("I can only read text for now. Reply REAL or FAKE, or HELP.")]
                    else:
                        outs = engine.handle(msg.handle, msg.text, space_id=msg.space_id, agent_id=msg.agent_id)
                    io.send(msg.space_id, msg.agent_id, outs, msg.id)
                    log.info("-> %s: %d message(s)", msg.handle[-4:], len(outs))
                if nudge_hour >= 0 and time.monotonic() >= next_nudge_check and et_hour() >= nudge_hour:
                    next_nudge_check = time.monotonic() + 60
                    today = today_et()
                    for s, outs in engine.due_nudges(today):
                        io.send(s.space_id, s.agent_id, outs, nudge_key(s.handle, today.isoformat()))
                        log.info("-> %s: daily reminder", s.handle[-4:])
            except KeyboardInterrupt:
                raise
            except Exception:  # one bad poll (network, API hiccup) must not kill the bot
                log.exception("poll failed; retrying")
                time.sleep(5)
            time.sleep(poll_s)
    except KeyboardInterrupt:
        log.info("bye")
    finally:
        io.close()
        http.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app

REPO = Path(__file__).resolve().parents[2]
DEMO = "2026-11-14-power-bills"
CLEAN = "2026-11-14-power-bills-clean"
SEED_CASES = (DEMO, CLEAN)


# Server settings a developer's .env might set (main.py loads .env on import). Tests start from the defaults.
SERVER_ENV = ("GOS_PUBLIC", "TEACHER_TOKEN", "DEMO_TOKEN", "CON_LIVE_DAILY_CAP", "CON_LIVE_PER_PLAYER",
              "ANSWER_RATE_PER_MIN", "CROWD_MIN", "GOS_DATA_DIR")


@pytest.fixture(autouse=True)
def default_server_env(monkeypatch):
    for name in SERVER_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def data_dir(tmp_path):
    """A private copy of the two seed cases, so tests never touch the real data/."""
    d = tmp_path / "data"
    for case_id in SEED_CASES:
        shutil.copytree(REPO / "data" / "cases" / case_id, d / "cases" / case_id)
    return d


@pytest.fixture
def client(data_dir, tmp_path):
    return TestClient(create_app(data_dir=data_dir, frontend_dist=tmp_path / "no-dist"))


@pytest.fixture
def player(client):
    return client.post("/api/players", json={}).json()["player_id"]


def load(data_dir, case_id, name):
    return json.loads((data_dir / "cases" / case_id / name).read_text(encoding="utf-8"))


def save(data_dir, case_id, name, data):
    (data_dir / "cases" / case_id / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def verdicts(real=(), doctored=None):
    """verdicts(real=["p1", "p3"], doctored={"p2": "misleading-chart"})"""
    out = {pid: {"doctored": False, "trick": None, "confidence": None} for pid in real}
    for pid, trick in (doctored or {}).items():
        out[pid] = {"doctored": True, "trick": trick, "confidence": 0.8}
    return out


def submit(client, player, case_id, v):
    return client.post(f"/api/cases/{case_id}/verdict", json={"player_id": player, "verdicts": v})

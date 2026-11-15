"""Skills (parsed by deepagents itself), topic helpers, and the CLI entry points."""

from __future__ import annotations

import random

import pytest

from pipeline.config import SKILLS_DIR, TRICKS
from pipeline.topics import choose_trick, hints_text, make_case_id

SECTIONS = ["## Definition", "## When to use", "## Forging recipe", "## The tell", "## How to verify",
            "## Diff type", "## Con lines", "## Safety limits"]


@pytest.mark.parametrize("trick", TRICKS)
def test_skill_files_parse_with_deepagents(trick):
    from deepagents.middleware.skills import _parse_skill_metadata

    path = SKILLS_DIR / trick / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    meta = _parse_skill_metadata(content, f"/skills/{trick}/SKILL.md", trick)
    assert meta is not None and meta["name"] == trick
    assert 0 < len(meta["description"]) <= 1024
    positions = [content.index(s) for s in SECTIONS]
    assert positions == sorted(positions), "sections in the SPEC §7.4 order"


def test_skills_discovered_through_composite_backend(tmp_path):
    from pipeline.agent import list_skill_names, make_backend
    from pipeline.tests.conftest import make_ctx

    backend = make_backend(make_ctx(tmp_path))
    assert list_skill_names(backend) == sorted(TRICKS)
    # the route strips its prefix, so /skills/x/SKILL.md maps to data/skills/x/SKILL.md
    res = backend.read("/skills/misleading-chart/SKILL.md")
    assert res.error is None and "name: misleading-chart" in res.file_data["content"]
    # and /cases/ is a different root (data/cases), not data/
    assert backend.routes["/cases/"].cwd != backend.routes["/skills/"].cwd


def test_choose_trick_uses_player_memory(tmp_path):
    import json

    prof = tmp_path / "profile.json"
    prof.write_text(json.dumps({"tricks": {
        "misleading-chart": {"shown": 10, "missed": 7},
        "out-of-context-quote": {"shown": 10, "missed": 1},
        "cherry-picked-stat": {"shown": 4, "missed": 1}}}), encoding="utf-8")
    rng = random.Random(1)
    picks = [choose_trick(prof, rng)[0] for _ in range(200)]
    assert picks.count("misleading-chart") / len(picks) > 0.6
    assert choose_trick(None, random.Random(0))[0] in TRICKS


def test_case_id_avoids_collisions(tmp_path):
    from datetime import UTC, datetime

    now = datetime(2026, 11, 14, tzinfo=UTC)
    assert make_case_id("NJ electricity prices", tmp_path, clean=False, now=now) == "2026-11-14-nj-electricity-prices"
    (tmp_path / "2026-11-14-nj-electricity-prices").mkdir()
    assert make_case_id("NJ electricity prices", tmp_path, clean=False, now=now).endswith("-2")
    assert make_case_id("NJ electricity prices", tmp_path, clean=True, now=now).endswith("-clean")


def test_hints_for_demo_topic():
    h = hints_text("NJ electricity prices")
    assert "newjerseymonitor.com/feed" in h and "nj.gov/bpu" in h and "get_eia_series" in h


def test_cli_dry_run(capsys):
    from pipeline.build_case import main

    assert main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Blind-solver isolation: OK" in out
    assert "researcher" in out and "forger" in out and "blind-solver" in out
    assert "skills: ['/skills/'] -> cherry-picked-stat, edited-detail, made-up-story, misleading-chart, out-of-context-quote" in out


def test_cli_refuses_blocklisted_topic(capsys):
    from pipeline.build_case import main

    assert main(["--topic", "election day polling places", "--dry-run"]) == 2
    assert "blocklist" in capsys.readouterr().out


def test_cli_without_key_explains(monkeypatch, capsys):
    from pipeline.build_case import main

    for k in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "PIPELINE_PROVIDER"):
        monkeypatch.setenv(k, "")
    monkeypatch.setattr("pipeline.build_case.load_env", lambda: None)
    monkeypatch.setattr("pipeline.models.load_env", lambda: None)
    assert main(["--auto-approve"]) == 2
    assert "OPENROUTER_API_KEY" in capsys.readouterr().out

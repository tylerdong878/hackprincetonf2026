from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pipeline.config import EIA_FILE, SKILLS_DIR
from pipeline.context import RunContext
from pipeline.events import EventLog
from pipeline.models import CallStats
from pipeline.tests import fixtures as fx
from pipeline.tools.research import fetch_article_impl, fetch_rss_impl, save_source_impl


def make_ctx(tmp_path, **kw) -> RunContext:
    cases = tmp_path / "cases"
    cases.mkdir(parents=True, exist_ok=True)
    defaults = dict(
        case_id="2026-11-14-test-case", topic="NJ electricity prices", trick="misleading-chart",
        cases_dir=cases, skills_dir=SKILLS_DIR, eia_path=EIA_FILE,
        events=EventLog(cases / kw.get("case_id", "2026-11-14-test-case") / "pipeline_log.jsonl"),
        stats=CallStats(max_calls=100, rpm=0), fetch=fx.FakeFetcher(),
        now=datetime(2026, 11, 14, 15, 0, tzinfo=UTC),
        # the research scope (normally the topic's TOPIC_HINTS): the fixture feeds and pages
        feeds=[fx.FEED_URL, fx.FEED2_URL], articles=[fx.PRESS_URL, fx.BLOCKED_URL],
    )
    defaults.update(kw)
    return RunContext(**defaults)


@pytest.fixture
def ctx(tmp_path) -> RunContext:
    return make_ctx(tmp_path)


def research(ctx: RunContext) -> dict[str, str]:
    """Fetch the fixtures and save four sources; returns {name: source_id}."""
    fetch_rss_impl(ctx, fx.FEED_URL, "electricity rates bills")
    fetch_article_impl(ctx, fx.PRESS_URL)
    ids = {}
    for key, url, text, speaker in [
        ("net", fx.STORY_URL, fx.QUOTE_NET, fx.SPEAKER_NET),
        ("ace", fx.STORY_URL, fx.ACE_RISE, None),
        ("peak", fx.STORY2_URL, fx.QUOTE_PEAK, fx.SPEAKER_PEAK),
        ("bpu20", fx.PRESS_URL, fx.BPU_20, None),
    ]:
        out = save_source_impl(ctx, url, text, speaker)
        assert out.startswith("Saved "), out
        ids[key] = out.split()[1]
    return ids


@pytest.fixture
def researched(ctx) -> tuple[RunContext, dict[str, str]]:
    return ctx, research(ctx)

"""Model factory + call accounting for the free tiers.

Defaults (override with env vars):
  PIPELINE_ORCHESTRATOR_MODEL / PIPELINE_RESEARCHER_MODEL / PIPELINE_FORGER_MODEL
      nvidia/nemotron-3-ultra-550b-a55b:free
  PIPELINE_SOLVER_MODEL
      nvidia/nemotron-3.5-super-vl:free            (vision: reads the rendered chart PNG)
  GEMINI_MODEL
      gemini-flash-latest                          (used when only GEMINI_API_KEY is set,
                                                    and as a fallback when both keys are set)
  PIPELINE_MAX_CALLS   45   hard cap on model requests per run (OpenRouter free: 50/day)
  PIPELINE_RPM         15   client-side throttle (OpenRouter free: 20 req/min)

All OpenRouter models are `ChatOpenRouter(..., openrouter_provider={"require_parameters": True})`
so OpenRouter only routes to providers that support tool calling.
"""

from __future__ import annotations

import asyncio
import email.utils
import logging
import os
import threading
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelFallbackMiddleware
from langchain_core.language_models import BaseChatModel

from pipeline.config import load_env

logger = logging.getLogger(__name__)

DEFAULT_MAIN_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
DEFAULT_SOLVER_MODEL = "nvidia/nemotron-3.5-super-vl:free"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"  # override with GEMINI_MODEL (2.5 Flash is closed to new users)
DEFAULT_FALLBACK_MODEL = "nvidia/nemotron-3.5-lightning:free"  # PIPELINE_FALLBACK_MODEL; fast, tool-capable
ROLES = ("orchestrator", "researcher", "forger", "solver")


class CallBudgetExceeded(RuntimeError):
    """The run used up PIPELINE_MAX_CALLS model requests."""


class DailyCapReached(RuntimeError):
    """The provider says the daily free quota is used up (retrying won't help)."""


class NoModelConfigured(RuntimeError):
    """No OPENROUTER_API_KEY or GEMINI_API_KEY in the environment / .env."""


class DeadlineExceeded(TimeoutError):
    """A model call didn't answer within its wall-clock deadline."""


def call_with_deadline(fn: Callable[[], Any], seconds: float | None) -> Any:
    """Run `fn()` with a hard wall-clock deadline.

    ChatOpenRouter's `timeout` does reach httpx, but httpx timeouts are per network step (connect, each read),
    not for the whole request, so a slow response that keeps trickling bytes can hang for minutes. This waits on
    a daemon thread instead; on timeout the request is abandoned (it still counts against the provider quota).
    The caller's contextvars (LangChain/LangGraph run config) are copied into the worker thread.
    """
    if not seconds or seconds <= 0:
        return fn()
    import contextvars

    box: dict[str, Any] = {}
    done = threading.Event()
    run = contextvars.copy_context().run

    def target() -> None:
        try:
            box["value"] = run(fn)
        except BaseException as exc:  # noqa: BLE001  # re-raised in the caller's thread
            box["error"] = exc
        finally:
            done.set()

    threading.Thread(target=target, daemon=True, name="model-call").start()
    if not done.wait(seconds):
        raise DeadlineExceeded(f"no answer within {seconds:.0f}s")
    if "error" in box:
        raise box["error"]
    return box["value"]


# --------------------------------------------------------------------------------------
# Call accounting
# --------------------------------------------------------------------------------------


FINISHER = "orchestrator"  # the agent whose last calls hand the case to the editor (submit_for_review)
FINISH_RESERVE = 2  # model calls only the orchestrator may use: submit_for_review, then its closing line


@dataclass
class CallStats:
    """Shared by every agent in a run: counts requests (including failed ones) and throttles.

    The last `reserve` calls belong to the orchestrator, so a sub-agent that runs long can't use up the budget
    before the hand-off (sub-agents get CallBudgetExceeded at max_calls - reserve).
    """

    max_calls: int = 45
    rpm: float = 15.0
    total: int = 0
    failed: int = 0
    retries: int = 0
    reserve: int = FINISH_RESERVE
    by_agent: Counter = field(default_factory=Counter)
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    _last: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def from_env(cls) -> CallStats:
        return cls(max_calls=int(os.environ.get("PIPELINE_MAX_CALLS", "45")),
                   rpm=float(os.environ.get("PIPELINE_RPM", "15")))

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.total)

    def wait_time(self) -> float:
        if self._last is None or self.rpm <= 0:
            return 0.0
        return max(0.0, 60.0 / self.rpm - (self.clock() - self._last))

    def before_call(self, agent: str) -> None:
        with self._lock:
            if self.total >= self.max_calls:
                raise CallBudgetExceeded(
                    f"Model-call budget used up ({self.total}/{self.max_calls}). "
                    "Raise PIPELINE_MAX_CALLS if your account allows more requests."
                )
            if agent != FINISHER and self.total >= self.max_calls - self.reserve:
                raise CallBudgetExceeded(
                    f"Model-call budget for sub-agents used up ({self.total}/{self.max_calls}); the last "
                    f"{self.reserve} calls are kept for the orchestrator's hand-off."
                )
            delay = self.wait_time()
            if delay > 0:
                self.sleep(delay)
            self._last = self.clock()
            self.total += 1
            self.by_agent[agent] += 1

    def summary(self) -> str:
        parts = ", ".join(f"{k} {v}" for k, v in sorted(self.by_agent.items()))
        return f"{self.total} model requests ({parts}); {self.failed} failed, {self.retries} retried"


def classify_error(exc: BaseException) -> str:
    """'daily' | 'rate' | 'transient' | 'other'."""
    text = " ".join(str(x) for x in (exc, getattr(exc, "body", ""), getattr(exc, "message", ""))).lower()
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    code = getattr(exc, "code", None)
    name = type(exc).__name__.lower()
    is_rate = (
        status == 429 or code == 429 or "toomanyrequests" in name or "ratelimit" in name
        or "rate limit" in text or "rate-limit" in text or "resource_exhausted" in text or "429" in text
    )
    if is_rate:
        daily_markers = ("per-day", "per day", "perday", "free-models-per-day", "daily", "requestsperday")
        return "daily" if any(m in text for m in daily_markers) else "rate"
    if isinstance(status, int) and status >= 500:
        return "transient"
    if isinstance(exc, TimeoutError):  # includes DeadlineExceeded
        return "transient"
    transient_names = ("timeout", "serviceunavailable", "badgateway", "provideroverloaded", "internalserver",
                       "connecterror", "readerror", "remoteprotocolerror", "noresponse", "transporterror",
                       "deadline")
    if any(n in name for n in transient_names):
        return "transient"
    return "other"


def retry_after_seconds(exc: BaseException, now: float | None = None) -> float | None:
    headers = getattr(exc, "headers", None) or getattr(getattr(exc, "response", None), "headers", None)
    if not headers:
        return None
    try:
        ra = headers.get("retry-after")
        if ra:
            try:
                return max(0.0, float(ra))
            except ValueError:
                dt = email.utils.parsedate_to_datetime(ra)
                return max(0.0, dt.timestamp() - (now or time.time()))
        reset = headers.get("x-ratelimit-reset")
        if reset:
            return max(0.0, float(reset) / 1000.0 - (now or time.time()))
    except Exception:  # noqa: BLE001
        return None
    return None


class ModelCallMiddleware(AgentMiddleware):
    """Counts every model request, throttles to PIPELINE_RPM, enforces a wall-clock deadline per request
    (PIPELINE_CALL_DEADLINE_S, default 120), and retries 429s/5xx with backoff.

    A request that misses its deadline is retried on the same model only when no fallback model is configured;
    otherwise it is raised so the (outer) ModelFallbackMiddleware switches models at once.
    """

    def __init__(
        self,
        agent_name: str,
        stats: CallStats,
        retry_delays: tuple[float, ...] = (8.0, 20.0, 45.0),
        max_retry_wait: float = 90.0,
        deadline_s: float | None = None,
        retry_timeouts: bool = True,
    ) -> None:
        super().__init__()
        self.agent_name = agent_name
        self.stats = stats
        self.retry_delays = retry_delays
        self.max_retry_wait = max_retry_wait
        self.deadline_s = deadline_s if deadline_s is not None else float(
            os.environ.get("PIPELINE_CALL_DEADLINE_S", "120"))
        self.retry_timeouts = retry_timeouts

    @property
    def name(self) -> str:  # one per agent stack
        return "ModelCallMiddleware"

    def _delay_for(self, exc: BaseException, attempt_delay: float | None) -> float | None:
        kind = classify_error(exc)
        if kind == "daily":
            raise DailyCapReached(f"Provider daily quota reached: {exc}") from exc
        if attempt_delay is None or kind not in ("rate", "transient"):
            return None
        if isinstance(exc, DeadlineExceeded):
            return 0.0 if self.retry_timeouts else None
        ra = retry_after_seconds(exc)
        return min(self.max_retry_wait, ra if ra is not None else attempt_delay)

    def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        timed_out = False
        for attempt_delay in (*self.retry_delays, None):
            self.stats.before_call(self.agent_name)
            try:
                return call_with_deadline(lambda: handler(request), self.deadline_s)
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, DeadlineExceeded):
                    if timed_out:  # a second timeout on the same model: give up on it
                        self.stats.failed += 1
                        raise
                    timed_out = True
                self.stats.failed += 1
                delay = self._delay_for(exc, attempt_delay)
                if delay is None:
                    raise
                self.stats.retries += 1
                logger.warning("%s: %s; retrying in %.0fs", self.agent_name, type(exc).__name__, delay)
                self.stats.sleep(delay)
        raise RuntimeError("unreachable")  # pragma: no cover

    async def awrap_model_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:
        for attempt_delay in (*self.retry_delays, None):
            self.stats.before_call(self.agent_name)
            try:
                if self.deadline_s and self.deadline_s > 0:
                    return await asyncio.wait_for(handler(request), self.deadline_s)
                return await handler(request)
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, asyncio.TimeoutError) and not isinstance(exc, DeadlineExceeded):
                    exc = DeadlineExceeded(f"no answer within {self.deadline_s:.0f}s")
                self.stats.failed += 1
                delay = self._delay_for(exc, attempt_delay)
                if delay is None:
                    raise
                self.stats.retries += 1
                await asyncio.sleep(delay)
        raise RuntimeError("unreachable")  # pragma: no cover


# --------------------------------------------------------------------------------------
# Model factory
# --------------------------------------------------------------------------------------


@dataclass
class ModelSet:
    provider: str  # "openrouter" | "gemini" | "placeholder" | "scripted"
    models: dict[str, BaseChatModel]
    names: dict[str, str]
    fallback: dict[str, list[BaseChatModel]] = field(default_factory=dict)  # role -> models tried in order
    solver_vision: bool = True
    tool_images: bool = False  # can image blocks go inside ToolMessages for this provider?

    def __getitem__(self, role: str) -> BaseChatModel:
        return self.models[role]

    def middleware_for(self, role: str, agent_name: str, stats: CallStats) -> list[AgentMiddleware]:
        """Fallback chain (outer) + counting/throttling/deadline/retry (inner), for one agent stack."""
        mws: list[AgentMiddleware] = []
        chain = self.fallback.get(role) or []
        if chain:
            mws.append(ModelFallbackMiddleware(*chain))
        mws.append(ModelCallMiddleware(agent_name, stats, retry_timeouts=not chain))
        mws.extend(nemotron_repair_middleware(self.names.get(role, "")))
        return mws


def nemotron_repair_middleware(model_name: str) -> list[AgentMiddleware]:
    """Stateless fixers from deepagents' built-in Nemotron profile (no extra model calls).

    deepagents 0.7.38 registers its Nemotron 3 Ultra harness profile for
    `openrouter:nvidia/nemotron-3-ultra-550b-a55b`, not for the `:free` slug, so we add the
    two zero-cost repair middlewares ourselves: text-form tool calls -> real tool calls, and
    `<think>` tag cleanup. The profile's nudge middlewares are left out (they add model calls).
    """
    if "nemotron" not in model_name.lower():
        return []
    try:
        from deepagents.profiles.harness._nvidia_nemotron_3_ultra import (
            NemotronReasoningTagCleanupMiddleware,
            NemotronTextToolCallParser,
        )
    except ImportError:  # pragma: no cover - private module moved
        return []
    return [NemotronReasoningTagCleanupMiddleware(), NemotronTextToolCallParser()]


def detect_provider() -> str | None:
    load_env()
    forced = os.environ.get("PIPELINE_PROVIDER", "").strip().lower()
    if forced in ("openrouter", "gemini"):
        return forced
    if os.environ.get("OPENROUTER_API_KEY", "").strip():
        return "openrouter"
    if os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip():
        return "gemini"
    return None


def model_names(provider: str) -> dict[str, str]:
    if provider == "gemini":
        g = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        return dict.fromkeys(ROLES, g)
    main = os.environ.get("PIPELINE_MAIN_MODEL", DEFAULT_MAIN_MODEL)
    names = {r: os.environ.get(f"PIPELINE_{r.upper()}_MODEL", main) for r in ("orchestrator", "researcher", "forger")}
    names["solver"] = os.environ.get("PIPELINE_SOLVER_MODEL", DEFAULT_SOLVER_MODEL)
    return names


def make_openrouter(model: str, timeout_ms: int | None = None) -> BaseChatModel:
    from langchain_openrouter import ChatOpenRouter

    kwargs: dict[str, Any] = {
        "model": model,
        "openrouter_provider": {"require_parameters": True},
        "max_retries": 0,  # ModelCallMiddleware owns retries, so every request is counted
        "timeout": timeout_ms or int(os.environ.get("PIPELINE_TIMEOUT_MS", "240000")),
    }
    if effort := os.environ.get("PIPELINE_REASONING_EFFORT"):
        kwargs["reasoning"] = {"effort": effort}
    return ChatOpenRouter(**kwargs)


def make_gemini(model: str, timeout_s: float | None = None) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    kwargs: dict[str, Any] = {"model": model, "google_api_key": key, "max_retries": 0, "temperature": 0.4}
    if timeout_s:
        kwargs["request_timeout"] = timeout_s  # field `timeout`, alias `request_timeout`
    return ChatGoogleGenerativeAI(**kwargs)


def judge_deadline_s() -> float:
    return float(os.environ.get("PIPELINE_JUDGE_DEADLINE_S", "20"))


def make_judge_models(level: int = 3) -> list[tuple[BaseChatModel, str, bool]]:
    """[(model, name, vision), ...] for the live Con judge: a primary model, then ONE fallback.

    OpenRouter, level 3 (and 1): PIPELINE_JUDGE_MODEL (default the solver model, vision) then
    PIPELINE_JUDGE_FALLBACK_MODEL (default nvidia/nemotron-3.5-lightning:free, text only).
    Level 2 (Street Con, CONTRACT §8.1): the same two, swapped, so the fast fallback model is the primary.
    Gemini-only: GEMINI_MODEL at every level. All with max_retries=0 (failed requests count against the free
    daily cap). Raises NoModelConfigured without a key.
    """
    provider = detect_provider()
    if provider is None:
        raise NoModelConfigured("No OPENROUTER_API_KEY or GEMINI_API_KEY: the Con is asleep.")
    http_timeout_ms = int(judge_deadline_s() * 1000)
    if provider == "gemini":
        g = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        return [(make_gemini(g, http_timeout_ms / 1000), g, True)]
    primary = os.environ.get("PIPELINE_JUDGE_MODEL") or model_names("openrouter")["solver"]
    vision = os.environ.get("PIPELINE_SOLVER_VISION", "1") != "0" and "vl" in primary.lower()
    out = [(make_openrouter(primary, http_timeout_ms), primary, vision)]
    fb = os.environ.get("PIPELINE_JUDGE_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL).strip()
    if level == 2:  # Street Con: the fast model judges; the full model is only the fallback
        fb = fb or DEFAULT_FALLBACK_MODEL
        if fb == primary:
            return out
        fb_vision = os.environ.get("PIPELINE_SOLVER_VISION", "1") != "0" and "vl" in fb.lower()
        return [(make_openrouter(fb, http_timeout_ms), fb, fb_vision), *out]
    if fb and fb != primary:
        out.append((make_openrouter(fb, http_timeout_ms), fb, False))
    return out


def make_models(provider: str | None = None) -> ModelSet:
    """Build the per-role models. Raises NoModelConfigured if no key is available."""
    provider = provider or detect_provider()
    if provider is None:
        raise NoModelConfigured(
            "No model key found. Put OPENROUTER_API_KEY (or GEMINI_API_KEY) in .env, "
            "or use --dry-run to build the graph without a model."
        )
    names = model_names(provider)
    if provider == "openrouter":
        models = {r: make_openrouter(n) for r, n in names.items()}
        fallback: dict[str, list[BaseChatModel]] = {r: [] for r in ROLES}
        fb = os.environ.get("PIPELINE_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL).strip()
        if fb:  # a fast free model to switch to on timeouts / errors ("" disables)
            for r in ROLES:
                if names[r] != fb:
                    fallback[r].append(make_openrouter(fb))
        if os.environ.get("GEMINI_API_KEY", "").strip() and os.environ.get("PIPELINE_GEMINI_FALLBACK", "1") != "0":
            g = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
            for r in ROLES:
                fallback[r].append(make_gemini(g))
        fallback = {r: chain for r, chain in fallback.items() if chain}
        vision = os.environ.get("PIPELINE_SOLVER_VISION", "1") != "0"
        # ChatOpenRouter forwards ToolMessage content unformatted, so images ride in the
        # solver's first (human) message instead of inside tool results.
        return ModelSet("openrouter", models, names, fallback, solver_vision=vision, tool_images=False)
    if provider == "gemini":
        models = {r: make_gemini(n) for r, n in names.items()}
        return ModelSet("gemini", models, names, {}, solver_vision=True, tool_images=True)
    raise ValueError(f"unknown provider {provider!r}")


def placeholder_models() -> ModelSet:
    """Models for --dry-run: the graph builds, but any call raises."""
    from pipeline.fakes import PlaceholderChatModel

    names = model_names("openrouter")
    models = {r: PlaceholderChatModel(model_name=f"dry-run:{names[r]}") for r in ROLES}
    return ModelSet("placeholder", models, names, {}, solver_vision=True, tool_images=False)

"""Game JSON -> text messages (and chart PNGs). No game logic here."""
from __future__ import annotations

from dataclasses import dataclass

TRICK_LABELS = {
    "out-of-context-quote": "Out of context",
    "misleading-chart": "Misleading chart",
    "cherry-picked-stat": "Cherry-picked stat",
    "edited-detail": "Edited detail",
}
TOOL_LABELS = {"source": "📄 source", "data": "📊 data", "account": "👤 account"}
OUTCOME_HEAD = {
    "caught": "🧂 Caught it! That one was doctored.",
    "trusted": "🟩 Right. That one's real.",
    "fooled": "🟥 Got you. That one was doctored.",
    "false_alarm": "🟨 False alarm. That one's real.",
}


@dataclass(frozen=True)
class Out:
    """One outgoing iMessage: text, or a PNG image."""
    text: str | None = None
    image: bytes | None = None

    @staticmethod
    def t(text: str) -> "Out":
        return Out(text=text)


def trick_label(trick: str | None) -> str:
    if not trick:
        return "Not sure"
    return TRICK_LABELS.get(trick, trick.replace("-", " ").capitalize())


def chart_png(chart: dict) -> bytes | None:
    try:
        from pipeline.charts import render_chart_png
        return render_chart_png(chart)
    except Exception:  # matplotlib missing or a malformed chart: fall back to text only
        return None


def chart_text(chart: dict) -> str:
    unit = chart.get("unit") or ""
    pts = ", ".join(f"{p['label']}: {p['value']:g}" for p in chart.get("points", []))
    return f"📈 {chart.get('title', 'Chart')} ({unit}): {pts}"


def author_line(author: dict) -> str:
    tick = " ✔︎" if author.get("verified") else ""
    return f"{author.get('name', '?')}{tick} {author.get('handle', '')}".strip()


def card(post: dict, index: int, total: int, clues_left: int) -> list[Out]:
    lines = [f"Post {index + 1}/{total}", "", author_line(post.get("author") or {}), post.get("body") or ""]
    quote = post.get("quote")
    if quote:
        lines += ["", f"“{quote.get('text', '')}”", f"— {quote.get('speaker', '')}"]
    if post.get("source_label"):
        lines += ["", post["source_label"]]
    out = [Out.t("\n".join(lines).strip())]
    chart = post.get("chart")
    if chart:
        png = chart_png(chart)
        out.append(Out(image=png) if png else Out.t(chart_text(chart)))
    tools = [TOOL_LABELS.get(t, t) for t in post.get("tools") or []]
    hint = "REAL or FAKE?"
    if clues_left and tools:
        hint += f"  (or CHECK: {', '.join(tools)} · {clues_left} 🔍 left)"
    out.append(Out.t(hint))
    return out


def trick_question(options: list[str]) -> Out:
    lines = ["Which trick?"] + [f"{i}. {trick_label(t)}" for i, t in enumerate(options, 1)] + ["0. Not sure"]
    return Out.t("\n".join(lines))


def evidence(tool: str, ev: dict, clues_left: int) -> list[Out]:
    out: list[Out] = []
    if tool == "source":
        head = " · ".join(x for x in (ev.get("outlet"), ev.get("date")) if x)
        body = " ".join(x for x in (ev.get("before"), f"»{ev.get('highlight', '')}«", ev.get("after")) if x)
        out.append(Out.t(f"📄 Original source{f' ({head})' if head else ''}:\n\n{body}\n\n{ev.get('url', '')}".strip()))
    elif tool == "data":
        text = f"📊 {ev.get('title', 'The data')}"
        if ev.get("note"):
            text += f"\n\n{ev['note']}"
        out.append(Out.t(text))
        honest = ev.get("honest_chart")
        if honest:
            png = chart_png(honest)
            out.append(Out(image=png) if png else Out.t(chart_text(honest)))
        elif ev.get("table"):
            rows = ev["table"][-8:]
            out.append(Out.t("\n".join(f"{r['label']}: {r['value']:g}" for r in rows)))
    elif tool == "account":
        bits = [f"👤 {author_line(ev)}"]
        if ev.get("bio"):
            bits.append(ev["bio"])
        facts = []
        if ev.get("created"):
            facts.append(f"joined {ev['created']}")
        if ev.get("followers") is not None:
            facts.append(f"{ev['followers']:,} followers")
        if facts:
            bits.append(" · ".join(facts))
        if ev.get("recent_posts"):
            bits.append("Recent posts:\n" + "\n".join(f"• {p}" for p in ev["recent_posts"][:3]))
        out.append(Out.t("\n".join(bits)))
    else:
        out.append(Out.t(str(ev)[:800]))
    out.append(Out.t(f"{clues_left} 🔍 left. REAL or FAKE?"))
    return out


def reveal(result: dict, guessed_trick: str | None) -> list[Out]:
    outcome = result.get("outcome")
    lines = [OUTCOME_HEAD.get(outcome, "Revealed.")]
    trick = result.get("trick")
    if result.get("doctored") and trick:
        if outcome == "caught" and result.get("trick_named_correctly"):
            lines[0] += f" And you named the trick: {trick_label(trick)}."
        else:
            lines[0] += f" The trick: {trick_label(trick)}."
    points = result.get("points")
    if isinstance(points, int):
        bonus = result.get("rarity_bonus")
        lines[0] += f" ({'+' if points >= 0 else ''}{points}{f', +{bonus} rare' if bonus else ''})"
    if result.get("tell"):
        lines += ["", result["tell"]]
    if result.get("con_line"):
        lines += ["", f"🎭 The Con: “{result['con_line']}”"]
    out = [Out.t("\n".join(lines))]
    diff = result.get("diff") or {}
    if diff.get("type") == "chart" and isinstance(diff.get("original"), dict):
        png = chart_png(diff["original"])
        out.append(Out(image=png) if png else Out.t("Honest version: " + chart_text(diff["original"])))
    elif isinstance(diff.get("original"), str) and isinstance(diff.get("shown"), str):
        out.append(Out.t(f"What they showed: {diff['shown']}\n\nThe original: {diff['original']}"))
    return out


def intro(daily: dict) -> Out:
    case = daily["case"]
    theme = daily.get("theme")
    head = f"🧂 Grain of Salt Daily #{daily.get('daily_number')}" + (f" · {theme}" if theme else "")
    return Out.t(f"{head}\n\n{case.get('briefing', '')}\n\nReply REAL or FAKE to each post.".strip())


def finish(verdict: dict) -> list[Out]:
    lines = [f"Done! Score {verdict.get('score', 0)} · {verdict.get('rank', '')}".strip(" ·")]
    if verdict.get("adaptation_message"):
        lines += ["", verdict["adaptation_message"]]
    lines += ["", "Next Daily at midnight ET. Text STATS for your dossier."]
    return [Out.t("\n".join(lines)), Out.t(verdict.get("share_text", ""))]


def stats(player: dict) -> Out:
    lines = [f"🕵️ {player.get('rank', 'Detective')} · rating {player.get('rating', 0)}",
             f"🔥 Streak: {player.get('streak', 0)} day(s)",
             f"Lean: {player.get('lean_label', 'Balanced')}"]
    per = player.get("per_trick") or {}
    shown = {t: v for t, v in per.items() if (v.get("miss_rate") or v.get("false_alarm_rate") or v.get("mastery"))}
    if shown:
        lines.append("")
        for t, v in shown.items():
            stars = "★" * int(v.get("mastery") or 0) + "☆" * (3 - int(v.get("mastery") or 0))
            lines.append(f"{stars} {trick_label(t)}: missed {round(100 * (v.get('miss_rate') or 0))}%")
    return Out.t("\n".join(lines))


COMMANDS = ("Commands:\n"
            "• REAL or FAKE (add the trick number: FAKE 2)\n"
            "• CHECK to spend a 🔍 on evidence (CHECK SOURCE / DATA / ACCOUNT)\n"
            "• PLAY to start or resume today's Daily\n"
            "• STATS for your streak and weak spots\n"
            "• STOP / REMIND to pause or resume the daily reminder\n"
            "• RESET to start over as a new detective\n"
            "• HELP to see this list again")

HELP = ("🧂 Grain of Salt: spot the doctored post.\n"
        "Every day: 5 real-looking posts, 0–3 of them doctored.\n\n" + COMMANDS)

WELCOME = ("Hi, detective. 🧂 I'm Grain of Salt.\n\n"
           "Each day I'll text you 5 posts about real news. Some are doctored: a cropped quote, a squashed "
           "chart axis, a cherry-picked number. Your job: REAL or FAKE.\n\n" + COMMANDS + "\n\nHere's today's.")

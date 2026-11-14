"""Render a CONTRACT chart object to PNG (matplotlib, Agg) so the vision solver sees what players see.

The y-axis range is reproduced exactly (y_min / y_max), including truncated axes: that axis
crop is the trick the solver has to notice, so the renderer must not "fix" it.
Style: one series, one hue, recessive grid, no legend (the title names the series),
values labelled on bars and on the first/last point of a line.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SERIES = "#2a78d6"


def render_chart_png(chart: dict[str, Any], path: Path | None = None, *, dpi: int = 110) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [p["label"] for p in chart["points"]]
    values = [float(p["value"]) for p in chart["points"]]
    y_min = float(chart.get("y_min") or 0.0)
    y_max = chart.get("y_max")
    if y_max is None:
        top = max(values)
        y_max = top + (top - y_min) * 0.12 if top > y_min else top + 1
    unit = chart.get("unit", "")

    fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=dpi)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    x = list(range(len(values)))
    if chart.get("type") == "line":
        ax.plot(x, values, color=SERIES, linewidth=2, marker="o", markersize=4 if len(x) > 12 else 6)
        for i in {0, len(values) - 1}:
            ax.annotate(f"{values[i]:g}", (x[i], values[i]), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=9, color=INK)
        step = max(1, len(labels) // 8)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(labels[::step], fontsize=8, color=INK_2, rotation=0)
    else:
        width = 0.5 if len(values) <= 3 else 0.7
        # Bars start at the axis floor (y_min), exactly like a chart app with a cropped axis.
        bars = ax.bar(x, [v - y_min for v in values], bottom=y_min, width=width, color=SERIES, edgecolor=SURFACE,
                      linewidth=2)
        for b, v in zip(bars, values, strict=True):
            ax.annotate(f"{v:g}", (b.get_x() + b.get_width() / 2, v), textcoords="offset points", xytext=(0, 4),
                        ha="center", fontsize=10, color=INK)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=9, color=INK_2)
    ax.set_ylim(y_min, float(y_max))
    ax.set_ylabel(unit, fontsize=9, color=INK_2)
    ax.set_title(chart.get("title", ""), fontsize=11, color=INK, loc="left")
    ax.tick_params(axis="y", labelsize=8, colors=INK_2, length=0)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=SURFACE)
    plt.close(fig)
    data = buf.getvalue()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data

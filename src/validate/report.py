"""Render the E1-E9 results as a Markdown report and small SVG figures.

There is no plotting library in the project's dependency set (numpy/pandas only),
so figures are built as plain SVG by hand. Deterministic: the same results give
the same bytes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

WIDTH = 640
HEIGHT = 340
PAD_LEFT = 64
PAD_RIGHT = 16
PAD_TOP = 24
PAD_BOTTOM = 56


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _svg_bars(figure: Mapping[str, Any]) -> str:
    categories = [str(c) for c in figure["categories"]]
    series = list(figure["series"])
    reference = figure.get("reference")
    plot_w = WIDTH - PAD_LEFT - PAD_RIGHT
    plot_h = HEIGHT - PAD_TOP - PAD_BOTTOM

    values = [v for s in series for v in s["values"] if v is not None]
    if reference is not None:
        values.append(float(reference))
    top = max(values) if values else 1.0
    top = top * 1.1 if top > 0 else 1.0

    def y(value: float) -> float:
        return PAD_TOP + plot_h * (1.0 - value / top)

    group_w = plot_w / max(len(categories), 1)
    bar_w = group_w * 0.8 / max(len(series), 1)
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
            f'width="{WIDTH}" height="{HEIGHT}" role="img">'
        ),
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        # axes
        f'<line x1="{PAD_LEFT}" y1="{PAD_TOP}" x2="{PAD_LEFT}" y2="{PAD_TOP + plot_h}" stroke="#333"/>',
        f'<line x1="{PAD_LEFT}" y1="{PAD_TOP + plot_h}" x2="{WIDTH - PAD_RIGHT}" y2="{PAD_TOP + plot_h}" stroke="#333"/>',
    ]
    # y gridlines
    for step in range(5):
        value = top * step / 4
        gy = y(value)
        parts.append(
            f'<line x1="{PAD_LEFT}" y1="{gy:.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{gy:.1f}" stroke="#eee"/>'
        )
        parts.append(
            f'<text x="{PAD_LEFT - 6}" y="{gy + 4:.1f}" font-size="11" text-anchor="end" fill="#555">{_fmt(round(value, 4))}</text>'
        )
    if reference is not None:
        ry = y(float(reference))
        parts.append(
            f'<line x1="{PAD_LEFT}" y1="{ry:.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{ry:.1f}" '
            f'stroke="#c0392b" stroke-dasharray="4 3"/>'
        )
    palette = ["#2c6e9b", "#d68910", "#7d3c98", "#117a65"]
    for ci, category in enumerate(categories):
        cx = PAD_LEFT + group_w * (ci + 0.5)
        parts.append(
            f'<text x="{cx:.1f}" y="{PAD_TOP + plot_h + 18}" font-size="12" text-anchor="middle" fill="#333">{category}</text>'
        )
        for si, s in enumerate(series):
            value = s["values"][ci] if ci < len(s["values"]) else None
            if value is None:
                continue
            bx = cx - (bar_w * len(series)) / 2 + bar_w * si
            by = y(float(value))
            parts.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w * 0.9:.1f}" '
                f'height="{PAD_TOP + plot_h - by:.1f}" fill="{palette[si % len(palette)]}"/>'
            )
            parts.append(
                f'<text x="{bx + bar_w * 0.45:.1f}" y="{by - 4:.1f}" font-size="10" text-anchor="middle" fill="#333">{_fmt(value)}</text>'
            )
    # legend + axis label
    lx = PAD_LEFT
    for si, s in enumerate(series):
        parts.append(
            f'<rect x="{lx}" y="{PAD_TOP - 16}" width="10" height="10" fill="{palette[si % len(palette)]}"/>'
        )
        parts.append(
            f'<text x="{lx + 14}" y="{PAD_TOP - 7}" font-size="11" fill="#333">{s["label"]}</text>'
        )
        lx += 120
    if figure.get("y_label"):
        parts.append(
            f'<text x="14" y="{PAD_TOP + plot_h / 2:.1f}" font-size="11" fill="#555" '
            f'transform="rotate(-90 14 {PAD_TOP + plot_h / 2:.1f})" text-anchor="middle">{figure["y_label"]}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _svg_lines(figure: Mapping[str, Any]) -> str:
    xs = [str(x) for x in figure["x"]]
    series = list(figure["series"])
    reference = figure.get("reference")
    plot_w = WIDTH - PAD_LEFT - PAD_RIGHT
    plot_h = HEIGHT - PAD_TOP - PAD_BOTTOM

    values = [v for s in series for v in s["values"] if v is not None]
    if reference is not None:
        values.append(float(reference))
    lo = min(values) if values else 0.0
    hi = max(values) if values else 1.0
    if hi == lo:
        hi = lo + 1.0
    span = hi - lo

    def y(value: float) -> float:
        return PAD_TOP + plot_h * (1.0 - (value - lo) / span)

    step_x = plot_w / max(len(xs) - 1, 1)
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
            f'width="{WIDTH}" height="{HEIGHT}" role="img">'
        ),
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<line x1="{PAD_LEFT}" y1="{PAD_TOP}" x2="{PAD_LEFT}" y2="{PAD_TOP + plot_h}" stroke="#333"/>',
        f'<line x1="{PAD_LEFT}" y1="{PAD_TOP + plot_h}" x2="{WIDTH - PAD_RIGHT}" y2="{PAD_TOP + plot_h}" stroke="#333"/>',
    ]
    for step in range(5):
        value = lo + span * step / 4
        gy = y(value)
        parts.append(f'<line x1="{PAD_LEFT}" y1="{gy:.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{gy:.1f}" stroke="#eee"/>')
        parts.append(
            f'<text x="{PAD_LEFT - 6}" y="{gy + 4:.1f}" font-size="11" text-anchor="end" fill="#555">{_fmt(round(value, 4))}</text>'
        )
    if reference is not None:
        ry = y(float(reference))
        parts.append(
            f'<line x1="{PAD_LEFT}" y1="{ry:.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{ry:.1f}" '
            f'stroke="#c0392b" stroke-dasharray="4 3"/>'
        )
    palette = ["#2c6e9b", "#d68910", "#7d3c98", "#117a65"]
    for i, label in enumerate(xs):
        px = PAD_LEFT + step_x * i
        parts.append(
            f'<text x="{px:.1f}" y="{PAD_TOP + plot_h + 18}" font-size="11" text-anchor="middle" fill="#333">{label}</text>'
        )
    for si, s in enumerate(series):
        points = []
        for i, value in enumerate(s["values"]):
            if value is None:
                continue
            points.append((PAD_LEFT + step_x * i, y(float(value))))
        if points:
            path = " ".join(
                ("M" if i == 0 else "L") + f"{px:.1f} {py:.1f}" for i, (px, py) in enumerate(points)
            )
            parts.append(f'<path d="{path}" fill="none" stroke="{palette[si % len(palette)]}" stroke-width="2"/>')
        for px, py in points:
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="{palette[si % len(palette)]}"/>')
    lx = PAD_LEFT
    for si, s in enumerate(series):
        parts.append(f'<rect x="{lx}" y="{PAD_TOP - 16}" width="10" height="10" fill="{palette[si % len(palette)]}"/>')
        parts.append(f'<text x="{lx + 14}" y="{PAD_TOP - 7}" font-size="11" fill="#333">{s["label"]}</text>')
        lx += 120
    if figure.get("x_label"):
        parts.append(
            f'<text x="{PAD_LEFT + plot_w / 2:.1f}" y="{HEIGHT - 8}" font-size="11" fill="#555" text-anchor="middle">{figure["x_label"]}</text>'
        )
    if figure.get("y_label"):
        parts.append(
            f'<text x="14" y="{PAD_TOP + plot_h / 2:.1f}" font-size="11" fill="#555" '
            f'transform="rotate(-90 14 {PAD_TOP + plot_h / 2:.1f})" text-anchor="middle">{figure["y_label"]}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render_svg(figure: Mapping[str, Any] | None) -> str:
    """Render a figure spec to SVG text (``bars`` or ``lines``)."""
    if not figure:
        return ""
    if figure["kind"] == "bars":
        return _svg_bars(figure)
    if figure["kind"] == "lines":
        return _svg_lines(figure)
    raise ValueError(f"unknown figure kind: {figure['kind']!r}")


def _md_table(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "_(no table)_"
    columns = list(rows[0].keys())
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(_fmt(row.get(column)) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def render_markdown(results: Mapping[str, Any]) -> str:
    """The whole report as Markdown, with figures linked by relative path."""
    data = results["data"]
    lines = [
        "# Validation report — E1–E9",
        "",
        (
            "Pre-registered experiments from `docs/TESTING.md` §9, run by "
            "`tools/experiments.py` over the served detections. Deterministic and "
            "network-free; regenerate with `python -m tools.experiments`."
        ),
        "",
        f"- **Source:** `{results['source']}`",
        f"- **Rows:** {data['rows']:,}",
        f"- **Date range:** {data['date_range'][0]} … {data['date_range'][1]}",
        f"- **VIIRS join (first detection):** {data['viirs_join']}",
        f"- **Parameters:** `{results['params_hash']}`",
        "",
        (
            "Synthetic numbers are labelled as such and are never evidence. "
            "Experiments that could not run report a limitation instead of a number."
        ),
        "",
    ]
    for experiment in results["experiments"]:
        # The report lives in docs/; figures live under validation/figures/.
        figure_path = f"../validation/figures/{experiment['id']}.svg"
        lines += [
            f"## {experiment['id']} — {experiment['title']}",
            "",
            f"**Question.** {experiment['question']}",
            "",
            f"**Decision rule.** {experiment['decision_rule']}",
            "",
            f"**Verdict:** `{experiment['verdict']}`",
            "",
        ]
        if experiment["metrics"]:
            lines += ["**Metrics.**", "", _md_table([experiment["metrics"]]), ""]
        if experiment["table"]:
            lines += [_md_table(experiment["table"]), ""]
        if experiment["figure"]:
            lines += [f"![{experiment['id']}]({figure_path})", ""]
        if experiment["notes"]:
            lines += ["**Notes / limitations.**", ""]
            lines += [f"- {note}" for note in experiment["notes"]]
            lines += [""]
    return "\n".join(lines)


__all__: Sequence[str] = ("render_markdown", "render_svg")

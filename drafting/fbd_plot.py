"""Plot a textbook free-body diagram (FBD) for the chair cross-rail.

Mermaid has no arrowhead, support, or dimension primitive, so the FBD is
rendered with matplotlib instead. All forces come from the deterministic
solver in :mod:`drafting.beam_diagram` -- nothing is hand-entered.

Usage::

    python -m drafting.fbd_plot
    python -m drafting.fbd_plot --format png --scale 2
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import Circle, Polygon, Rectangle

from drafting.beam_diagram import SimplySupportedRail

DEFAULT_OUTDIR = Path("Project/chair/diagrams")

INK = "#0f172a"
MUTED = "#64748b"
BEAM = "#334155"
REACTION = "#1d4ed8"
LOAD = "#b91c1c"
DIM = "#0f172a"

# Thai-capable font stack; falls back silently if unavailable.
plt.rcParams["font.family"] = ["Tahoma", "DejaVu Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


def _support_pinned(ax: Axes, x: float, y: float, size: float, label: str) -> None:
    """Pinned support: triangle on a hatched ground line."""
    tri = [
        (x, y),
        (x - size, y - size),
        (x + size, y - size),
    ]
    ax.add_patch(
        Polygon(tri, closed=True, facecolor="#e2e8f0", edgecolor=BEAM, linewidth=1.6, zorder=4)
    )
    ground_y = y - size
    ax.plot(
        [x - size * 1.7, x + size * 1.7], [ground_y, ground_y], color=BEAM, linewidth=2.0, zorder=4
    )
    n = 7
    for i in range(n):
        gx = x - size * 1.7 + (2 * size * 1.7) * i / (n - 1)
        ax.plot(
            [gx, gx - size * 0.42],
            [ground_y, ground_y - size * 0.42],
            color=MUTED,
            linewidth=1.0,
            zorder=4,
        )
    ax.text(
        x, ground_y - size * 0.95, label, ha="center", va="top", fontsize=8.5, color=MUTED, zorder=4
    )


def _support_roller(ax: Axes, x: float, y: float, size: float, label: str) -> None:
    """Roller support: triangle on rollers."""
    tri = [
        (x, y),
        (x - size, y - size),
        (x + size, y - size),
    ]
    ax.add_patch(
        Polygon(tri, closed=True, facecolor="#e2e8f0", edgecolor=BEAM, linewidth=1.6, zorder=4)
    )
    base = y - size
    for k in (-0.6, 0.0, 0.6):
        cx = x + k * size
        ax.add_patch(
            Circle(
                (cx, base - size * 0.22),
                size * 0.20,
                facecolor="white",
                edgecolor=BEAM,
                linewidth=1.2,
                zorder=4,
            )
        )
    gy = base - size * 0.42
    ax.plot([x - size * 1.5, x + size * 1.5], [gy, gy], color=BEAM, linewidth=2.0, zorder=4)
    n = 7
    for i in range(n):
        gx = x - size * 1.5 + (2 * size * 1.5) * i / (n - 1)
        ax.plot(
            [gx, gx - size * 0.40], [gy, gy - size * 0.40], color=MUTED, linewidth=1.0, zorder=4
        )
    ax.text(x, gy - size * 0.85, label, ha="center", va="top", fontsize=8.5, color=MUTED, zorder=4)


def _arrow(
    ax: Axes,
    x: float,
    y0: float,
    y1: float,
    color: str,
    label: str,
    label_dx: float = 0.0,
    label_dy: float = 0.0,
    ha: str = "center",
    va: str = "bottom",
) -> None:
    """Force arrow from ``y0`` to ``y1`` with a label at the tip."""
    ax.annotate(
        "",
        xy=(x, y1),
        xytext=(x, y0),
        arrowprops=dict(
            arrowstyle="-|>,head_width=0.32,head_length=0.7",
            color=color,
            linewidth=2.4,
            shrinkA=0,
            shrinkB=0,
            zorder=6,
        ),
    )
    ax.text(
        x + label_dx,
        y1 + label_dy,
        label,
        ha=ha,
        va=va,
        fontsize=11,
        fontweight="bold",
        color=color,
        zorder=7,
    )


def _dim_line(ax: Axes, x0: float, x1: float, y: float, text: str) -> None:
    """Horizontal dimension line with end ticks and a centred label."""
    ax.annotate(
        "",
        xy=(x1, y),
        xytext=(x0, y),
        arrowprops=dict(
            arrowstyle="<|-|>,head_width=0.22,head_length=0.5",
            color=DIM,
            linewidth=1.1,
            shrinkA=0,
            shrinkB=0,
            zorder=5,
        ),
    )
    ax.plot([x0, x0], [y - 14, y + 14], color=DIM, linewidth=1.0, zorder=5)
    ax.plot([x1, x1], [y - 14, y + 14], color=DIM, linewidth=1.0, zorder=5)
    ax.text(
        (x0 + x1) / 2.0,
        y + 10,
        text,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color=DIM,
        zorder=6,
        bbox=dict(boxstyle="round,pad=0.28", fc="white", ec="none"),
    )


def plot_fbd(
    rail: SimplySupportedRail, outdir: Path = DEFAULT_OUTDIR, fmt: str = "png", scale: float = 2.0
) -> Path:
    """Render the FBD for ``rail`` and return the written image path."""
    L = rail.span_mm
    a = rail.a_mm
    r1, r2 = rail.r1_n, rail.r2_n
    p = rail.p_n
    rail.verify_equilibrium()

    beam_h = max(L * 0.035, 12.0)
    up = p * 0.62  # reaction arrow length
    down = p * 0.60  # load arrow length

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    ax.set_aspect("equal")
    ax.axis("off")

    # Beam
    ax.add_patch(
        Rectangle(
            (0.0, -beam_h / 2),
            L,
            beam_h,
            facecolor="#cbd5e1",
            edgecolor=BEAM,
            linewidth=2.0,
            zorder=3,
        )
    )

    # Supports
    sup = L * 0.030
    _support_pinned(ax, 0.0, -beam_h / 2, sup, "A (เสาต้น)")
    _support_roller(ax, L, -beam_h / 2, sup, "B (เสาปลาย)")

    # Reactions (upward)
    _arrow(ax, 0.0, beam_h / 2, beam_h / 2 + up, REACTION, f"R₁ = {r1:g} N", label_dy=6)
    _arrow(ax, L, beam_h / 2, beam_h / 2 + up, REACTION, f"R₂ = {r2:g} N", label_dy=6)

    # Load (downward) at midspan
    _arrow(ax, a, beam_h / 2 + down, beam_h / 2, LOAD, f"P = {p:g} N", label_dy=-6, va="top")

    # Dimensions
    _dim_line(ax, 0.0, a, -beam_h / 2 - sup * 2.1 - 46, f"a = {a:g} mm")
    _dim_line(ax, a, L, -beam_h / 2 - sup * 2.1 - 46, f"L − a = {L - a:g} mm")
    _dim_line(ax, 0.0, L, -beam_h / 2 - sup * 2.1 - 108, f"L = {L:g} mm")

    # Station labels
    for xs, txt in ((0.0, "x = 0"), (a, f"x = {a:g}"), (L, f"x = {L:g}")):
        ax.text(
            xs, beam_h / 2 + 16, txt, ha="center", va="bottom", fontsize=9, color=MUTED, zorder=6
        )

    # Axis frame (the "x-y coordinate" reference)
    ax.annotate(
        "",
        xy=(L * 1.06, -beam_h / 2 - 128),
        xytext=(0.0, -beam_h / 2 - 128),
        arrowprops=dict(
            arrowstyle="-|>,head_width=0.28,head_length=0.6", color=INK, linewidth=1.4, zorder=5
        ),
    )
    ax.annotate(
        "",
        xy=(-L * 0.06, beam_h / 2 + up + L * 0.10),
        xytext=(-L * 0.06, -beam_h / 2 - 128),
        arrowprops=dict(
            arrowstyle="-|>,head_width=0.28,head_length=0.6", color=INK, linewidth=1.4, zorder=5
        ),
    )
    ax.text(
        L * 1.07,
        -beam_h / 2 - 128,
        "x",
        ha="left",
        va="center",
        fontsize=11,
        fontstyle="italic",
        color=INK,
        zorder=6,
    )
    ax.text(
        -L * 0.06,
        beam_h / 2 + up + L * 0.10,
        "y",
        ha="center",
        va="bottom",
        fontsize=11,
        fontstyle="italic",
        color=INK,
        zorder=6,
    )
    ax.text(
        0.0,
        beam_h / 2 + up + L * 0.16,
        "คานโครงเบาะ — แผนภาพแรงอิสระ (FBD)",
        ha="center",
        va="bottom",
        fontsize=13,
        fontweight="bold",
        color=INK,
        zorder=6,
    )

    ax.set_xlim(-L * 0.14, L * 1.14)
    ax.set_ylim(-beam_h / 2 - 150, beam_h / 2 + up + L * 0.24)

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"fbd_cross_rail.{fmt}"
    fig.savefig(out, dpi=150 * scale, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--format", choices=("png", "svg", "both"), default="both")
    ap.add_argument("--scale", type=float, default=2.0)
    args = ap.parse_args(argv)

    rail = SimplySupportedRail(span_mm=480.0, point_load_n=650.0)
    fmts = ("png", "svg") if args.format == "both" else (args.format,)
    for f in fmts:
        out = plot_fbd(rail, outdir=args.outdir, fmt=f, scale=args.scale)
        print(f"[ok] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Dimensioned sketch of the chair's four pan dimensions + seat height.

Explains, in one picture, which numbers are sizes of the pan (a box) and
which is a position of the whole chair relative to the floor.
Run:  python -m drafting.dim_sketch
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Rectangle

plt.rcParams["font.family"] = ["Tahoma", "DejaVu Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

INK = "#0f172a"
MUTED = "#64748b"
DIM = "#b91c1c"
THICK = "#1d4ed8"
LOAD = "#7c3aed"
PAN_FILL = "#e2e8f0"

W, D, H, T = 480.0, 460.0, 450.0, 22.0
OUT = Path("Project/chair/diagrams/dim_sketch.png")


def dim_v(
    ax: plt.Axes,
    x: float,
    y0: float,
    y1: float,
    text: str,
    color: str = DIM,
    off: float = 0.0,
) -> None:
    ax.annotate(
        "",
        xy=(x, y1),
        xytext=(x, y0),
        arrowprops=dict(
            arrowstyle="<|-|>,head_width=0.2,head_length=0.5",
            color=color,
            lw=1.2,
            shrinkA=0,
            shrinkB=0,
        ),
    )
    for yy in (y0, y1):
        ax.plot([x - 14, x + 14], [yy, yy], color=color, lw=1.0)
    ax.text(
        x + off,
        (y0 + y1) / 2,
        text,
        ha="left",
        va="center",
        fontsize=10,
        color=color,
        fontweight="bold",
    )


def dim_h(ax: plt.Axes, y: float, x0: float, x1: float, text: str, color: str = DIM) -> None:
    ax.annotate(
        "",
        xy=(x1, y),
        xytext=(x0, y),
        arrowprops=dict(
            arrowstyle="<|-|>,head_width=0.2,head_length=0.5",
            color=color,
            lw=1.2,
            shrinkA=0,
            shrinkB=0,
        ),
    )
    for xx in (x0, x1):
        ax.plot([xx, xx], [y - 14, y + 14], color=color, lw=1.0)
    ax.text(
        (x0 + x1) / 2,
        y + 18,
        text,
        ha="center",
        va="bottom",
        fontsize=10,
        color=color,
        fontweight="bold",
    )


fig, ax = plt.subplots(figsize=(13, 7.5))
ax.set_aspect("equal")
ax.axis("off")

# ---------------- FRONT VIEW (X-Z) : width + height + thickness ----------------
ax.text(
    -40,
    H * 0.62,
    "มุมมองด้านหน้า  FRONT VIEW  (X-Z)",
    fontsize=12,
    fontweight="bold",
    color=INK,
    ha="left",
)

ax.add_patch(Rectangle((0, H - T), W, T, facecolor=PAN_FILL, edgecolor=THICK, lw=2.0, zorder=3))
dim_h(ax, H + 90, 0, W, f"Seat width = {W:g} mm   (แนว X)", DIM)
dim_v(ax, -70, 0, H, f"Seat height\n{H:g} mm", LOAD)
dim_v(ax, W + 70, H - T, H, f"Pan\nthickness\n{T:g} mm", THICK)

# columns
for cx in (30, W - 30):
    ax.plot([cx, cx - 27.5], [H - T, 0], color="#334155", lw=5, zorder=2)
    ax.plot([cx - 45, cx - 15], [0, 0], color="#334155", lw=3, zorder=2)

# splay arc
ax.add_patch(Arc((30, H - T), 190, 190, theta1=270, theta2=286, color=LOAD, lw=1.6, zorder=4))
ax.text(120, H - T + 30, "splay 3.5°\n(เสาเอียงออก)", fontsize=9, color=LOAD, ha="left", va="bottom")
ax.plot([30, 30], [H - T, H - T + 95], color=MUTED, lw=1.0, ls=":", zorder=4)
ax.text(30, H - T + 100, "แนวดิ่ง", fontsize=8, color=MUTED, ha="center")

# ---------------- SIDE VIEW (Y-Z) : depth ----------------
ox = W + 330
ax.text(
    ox - 40,
    H * 0.62,
    "มุมมองด้านข้าง  SIDE VIEW  (Y-Z)",
    fontsize=12,
    fontweight="bold",
    color=INK,
    ha="left",
)
ax.add_patch(Rectangle((ox, H - T), D, T, facecolor=PAN_FILL, edgecolor=THICK, lw=2.0, zorder=3))
dim_h(ax, H + 90, ox, ox + D, f"Seat depth = {D:g} mm   (แนว Y)", DIM)

# backrest
ax.plot([ox + D, ox + D + 95], [H - T, H - T + 250], color="#334155", lw=5, zorder=2)

ax.set_xlim(-150, ox + D + 190)
ax.set_ylim(-40, H + 210)

ax.text(
    -150,
    H * 0.30,
    "3 ขนาดแรก = ขนาดของเบาะเอง (กล่อง)\nSeat width / depth / thickness  →  ขนาดเบาะ",
    fontsize=10.5,
    color=DIM,
    ha="left",
    va="top",
    linespacing=1.6,
)
ax.text(
    -150,
    H * 0.30 - 78,
    "อีก 1 ขนาด = ตำแหน่งของเก้าอี้ทั้งตัว\nSeat height  →  วัดจากพื้นถึงหน้าเบาะ",
    fontsize=10.5,
    color=LOAD,
    ha="left",
    va="top",
    linespacing=1.6,
)

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=140, bbox_inches="tight", facecolor="white")
print(f"[ok] {OUT}")

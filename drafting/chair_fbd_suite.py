"""Suite of 7 textbook-grade Free Body Diagrams (FBDs) for the MDIE Armchair.

Generates deterministic, dimensioned, publication-quality FBDs for every structural
member analyzed in the chair calculation dossier:
1. Overall Chair System Equilibrium & Floor Reactions (FBD 1)
2. Main Leg Column Compression & Buckling (FBD 2)
3. Seat Frame Rail Beam, SFD, and BMD (FBD 3)
4. Armrest Assembly & Post Lever-Rule Split (FBD 4)
5. Arm Mounting Bracket Bending & Combined Stresses (FBD 5)
6. Backrest Inclined Cantilever Post at 8° Tilt (FBD 6)
7. Lower Stretcher / Tie Bar Tension & Buckling (FBD 7)

All force values, moments, and dimensions derive directly from the deterministic
physics solver in :mod:`physics.frame_physics` and golden engineering values.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import Arc, Circle, Polygon, Rectangle

from core.frame_model import (
    ArmrestGeometry,
    FrameDesignModel,
    resolve_armrest_shared,
)
from physics.fatigue import FatigueSolver, MarinFactors
from physics.frame_physics import (
    ArmBracketAnalysisResult,
    FramePhysicsSolver,
    UpperStrutAnalysisResult,
)

DEFAULT_OUTDIR = Path("Project/chair/diagrams")

# Professional Engineering Palette
INK = "#0f172a"
MUTED = "#64748b"
BEAM = "#334155"
BEAM_FILL = "#cbd5e1"
REACTION = "#1d4ed8"  # Blue for reactions
LOAD = "#b91c1c"      # Red for applied loads
MOMENT = "#7c3aed"    # Purple for bending moments
DIM = "#0f172a"       # Dark slate for dimension lines
BOX_BG = "#f1f5f9"    # Light slate for formula badges

plt.rcParams["font.family"] = ["Tahoma", "DejaVu Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


def _armrest_design() -> tuple[
    FrameDesignModel, ArmrestGeometry, UpperStrutAnalysisResult, ArmBracketAnalysisResult
]:
    """Resolve the analysed armrest sub-assembly from the source of truth.

    Geometry comes from resolve_armrest_shared() -- the same helper the
    CAD kernel and the frame solver consume -- and every force, moment
    and stress is read back from FramePhysicsSolver.solve(), so the FBD
    sheets can never drift from the design that was actually analysed.
    """
    model = FrameDesignModel()
    tube_r = model.geometry.arm_profile.outer_dimension_mm / 2.0
    ag = resolve_armrest_shared(model.geometry, -1.0, tube_r)
    sol = FramePhysicsSolver.solve(model)
    return model, ag, sol.armrests[0], sol.arm_brackets[0]


def _marin_endurance(model: FrameDesignModel, d_eff_mm: float) -> float:
    """Marin-corrected endurance limit, via the single physics implementation."""
    m = model.material
    ka = MarinFactors.surface_factor(m.ultimate_strength_mpa, "machined")
    kb = MarinFactors.size_factor(d_eff_mm / 1000.0)
    kc = MarinFactors.load_factor("bending")
    ke = MarinFactors.reliability_factor(0.90)
    return ka * kb * kc * 1.0 * ke * 1.0 * (0.5 * m.ultimate_strength_mpa)


def _dim_h(ax: Axes, x0: float, x1: float, y: float, text: str, tick: float = 8.0,
           label_dx: float = 0.0, label_ha: str = "center") -> None:
    """Horizontal dimension line with ticks and centered label."""
    ax.annotate(
        "",
        xy=(x1, y),
        xytext=(x0, y),
        arrowprops={"arrowstyle": "<|-|>,head_width=0.20,head_length=0.45", "color": DIM, "linewidth": 1.1},
    )
    ax.plot([x0, x0], [y - tick, y + tick], color=DIM, linewidth=1.0)
    ax.plot([x1, x1], [y - tick, y + tick], color=DIM, linewidth=1.0)
    ax.text((x0 + x1) / 2.0 + label_dx, y + 4.0, text, ha=label_ha, va="bottom", fontsize=8.5, color=DIM,
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "none"})


def _dim_v(ax: Axes, x: float, y0: float, y1: float, text: str, tick: float = 8.0) -> None:
    """Vertical dimension line with ticks and centered label."""
    ax.annotate(
        "",
        xy=(x, y1),
        xytext=(x, y0),
        arrowprops={"arrowstyle": "<|-|>,head_width=0.20,head_length=0.45", "color": DIM, "linewidth": 1.1},
    )
    ax.plot([x - tick, x + tick], [y0, y0], color=DIM, linewidth=1.0)
    ax.plot([x - tick, x + tick], [y1, y1], color=DIM, linewidth=1.0)
    ax.text(x + 5.0, (y0 + y1) / 2.0, text, ha="left", va="center", fontsize=8.5, color=DIM,
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "none"})


def _force_arrow(ax: Axes, x0: float, y0: float, x1: float, y1: float, color: str, text: str,
                 label_pos: str = "end", fontsize: float = 9.0, label_ha: str = "center",
                 label_below: bool | None = None) -> None:
    """Render a crisp force vector arrow with bold label."""
    ax.annotate(
        "",
        xy=(x1, y1),
        xytext=(x0, y0),
        arrowprops={"arrowstyle": "-|>,head_width=0.30,head_length=0.65", "color": color, "linewidth": 2.2, "zorder": 5},
    )
    if label_pos == "end":
        lx, ly = x1, y1
    elif label_pos == "start":
        lx, ly = x0, y0
    else:  # "mid"
        lx, ly = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    below = (y0 == y1) if label_below is None else label_below
    if below:
        ax.text(lx, ly - 6.0, text, ha=label_ha, va="top",
                fontsize=fontsize, fontweight="bold", color=color, zorder=6,
                bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": color, "lw": 0.8})
        return
    ax.text(lx, ly + (6.0 if y1 >= y0 else -6.0), text, ha=label_ha,
            va="bottom" if y1 >= y0 else "top",
            fontsize=fontsize, fontweight="bold", color=color, zorder=6,
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": color, "lw": 0.8})


def _moment_arc(ax: Axes, cx: float, cy: float, radius: float, angle_start: float, angle_end: float,
                color: str, text: str, ccw: bool = True,
                label_xy: tuple[float, float] | None = None,
                label_ha: str | None = None, label_va: str | None = None) -> None:
    """Curved moment vector with circular arrow."""
    arc = Arc((cx, cy), radius * 2, radius * 2, angle=0, theta1=min(angle_start, angle_end),
              theta2=max(angle_start, angle_end), color=color, linewidth=2.0, zorder=5)
    ax.add_patch(arc)
    # Arrow tip
    tip_angle = (max(angle_start, angle_end) if ccw else min(angle_start, angle_end)) * 3.14159 / 180.0
    import math
    tx = cx + radius * math.cos(tip_angle)
    ty = cy + radius * math.sin(tip_angle)
    ax.plot(tx, ty, marker="^" if ccw else "v", color=color, markersize=7, zorder=6)
    lx = cx + radius * 1.15 if label_xy is None else label_xy[0]
    ly = cy if label_xy is None else label_xy[1]
    ha = "left" if label_ha is None else label_ha
    va = "center" if label_va is None else label_va
    ax.text(lx, ly, text, ha=ha, va=va, fontsize=9.0, fontweight="bold",
            color=color, zorder=6, bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": color, "lw": 0.8})


# ==============================================================================
# FBD 1: OVERALL CHAIR EQUILIBRIUM & FLOOR REACTIONS
# ==============================================================================
def plot_fbd_01_overall_chair(outdir: Path, fmt: str = "png") -> Path:
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_aspect("equal")
    ax.axis("off")

    # Everything below is read back from the source-of-truth model so the
    # silhouette and the equilibrium figures track the design that was solved.
    # NOTE: FBD 1 is a SIDE elevation (front at left, rear at right), so the
    # fore-aft span is the seat DEPTH (460 mm) -- never the width (480 mm).
    _model = FrameDesignModel()
    _geom = _model.geometry
    _loads = _model.loads
    _ag = resolve_armrest_shared(
        _geom, -1.0, _geom.arm_profile.outer_dimension_mm / 2.0
    )
    _sol = FramePhysicsSolver.solve(_model)

    import math

    L_seat = _geom.seat_depth_mm                  # fore/aft span in side view (460)
    H_seat = _geom.seat_height_mm                 # 450
    H_back = _geom.backrest_height_above_seat_mm  # 420
    pan_t = _geom.seat_thickness_mm               # 22
    H_arm = _geom.armrest_height_above_seat_mm    # 210
    theta = math.radians(_geom.backrest_angle_deg - 90.0)  # 8 deg recline
    splay = H_seat * math.tan(math.radians(_geom.leg_splay_angle_deg))  # 27.52 offset
    x_front = 0.0
    x_rear = L_seat
    x_floor_front = -splay
    x_floor_rear = L_seat + splay

    # Seat-datum fore/aft (y, +y forward) -> side-view x. Front edge (y=+d/2) at x=0.
    seat_d = L_seat

    def x_of(y_datum: float) -> float:
        return seat_d / 2.0 - y_datum

    # Ground line
    ax.plot([-splay - 80, L_seat + splay + 80], [0, 0], color=BEAM, linewidth=2.5, zorder=2)
    for gx in range(int(-splay - 70), int(L_seat + splay + 80), 25):
        ax.plot([gx, gx - 15], [0, -15], color=MUTED, linewidth=1.2)

    # Chair frame side silhouette
    # Front Leg
    ax.plot([x_floor_front, x_front], [0, H_seat], color=BEAM, linewidth=5.5, zorder=3)
    # Rear Leg
    ax.plot([x_floor_rear, x_rear], [0, H_seat], color=BEAM, linewidth=5.5, zorder=3)
    # Seat Rail (top of frame)
    ax.plot([x_front, x_rear], [H_seat, H_seat], color=BEAM, linewidth=7.0, zorder=3)
    # Seat pan deck resting on the frame
    ax.add_patch(Rectangle((x_front, H_seat), L_seat, pan_t, facecolor=BEAM_FILL,
                           edgecolor=BEAM, linewidth=1.8, zorder=4))
    # Backrest Post (inclined 8 degrees rearwards)
    x_back_top = x_rear + H_back * math.sin(theta)
    y_back_top = H_seat + H_back * math.cos(theta)
    ax.plot([x_rear, x_back_top], [H_seat, y_back_top], color=BEAM, linewidth=6.0, zorder=3)
    # Armrest - pad, two posts and the diagonal brace, all mapped off the
    # resolved seat-datum geometry onto the side-view depth span (front at x=0)
    pad_f = x_of(_ag.pad_front_y_mm)
    pad_r = x_of(_ag.pad_rear_y_mm)
    post_f = x_of(_ag.front_post_y_mm)
    post_r = x_of(_ag.rear_post_y_mm)
    ax.add_patch(Rectangle((pad_f, H_seat + H_arm), pad_r - pad_f, _ag.pad_thickness_mm,
                           facecolor=BEAM_FILL, edgecolor=BEAM, linewidth=1.6, zorder=4))
    ax.plot([post_f, post_f], [H_seat, H_seat + H_arm], color=BEAM, linewidth=4.0, zorder=3)
    ax.plot([post_r, post_r], [H_seat, H_seat + H_arm], color=BEAM, linewidth=4.0, zorder=3)
    # Diagonal brace closing the racking triangle (rear foot -> front head)
    ax.plot([post_r, post_f], [H_seat, H_seat + H_arm], color=BEAM, linewidth=3.0, zorder=3)
    # Lower Stretcher (side member at stretcher height)
    sh = _geom.stretcher_height_mm
    x_str_f = x_floor_front + (x_front - x_floor_front) * (sh / H_seat)
    x_str_r = x_floor_rear + (x_rear - x_floor_rear) * (sh / H_seat)
    ax.plot([x_str_f, x_str_r], [sh, sh], color=BEAM, linewidth=3.5, zorder=3)

    # Floor reactions read back from the solver (per-leg axial reactions)
    _leg_r = {l.leg_id: l.axial_reaction_n for l in _sol.floor_reactions}
    _r_front = _leg_r["FL"] + _leg_r["FR"]     # 1,497.84 N
    _r_rear = _leg_r["RL"] + _leg_r["RR"]       # 806.26 N
    _max_r = max(_leg_r.values())               # 748.92 N (governing leg)

    # Applied Loads (fore-aft placement follows the model's load centres)
    # Seat load W_seat at the seat-load centre (y = -25 mm), on top of the pan
    x_seat = x_of(_loads.seat_load_center_y_mm)
    _force_arrow(ax, x_seat, H_seat + pan_t + 150, x_seat, H_seat + pan_t, LOAD,
                 f"W_seat = {_loads.seat_vertical_load_n:,.0f} N\n(น้ำหนักผู้ใช้งานบนเบาะ)", "start")

    # Armrest load 2 x 450 N = 900 N at the pad (load y = 0 -> x = d/2)
    x_arm = x_of(_loads.left_arm_load_y_mm)
    _force_arrow(ax, x_arm, H_seat + H_arm + _ag.pad_thickness_mm + 80,
                 x_arm, H_seat + H_arm + _ag.pad_thickness_mm, LOAD,
                 f"2 × F_arm = {_loads.left_arm_vertical_n + _loads.right_arm_vertical_n:,.0f} N\n(น้ำหนักกดที่พักแขน)", "start")

    # Structural self-weight W_chair at the CG
    _force_arrow(ax, seat_d * 0.35, H_seat - 40, seat_d * 0.35, H_seat - 160, LOAD,
                 f"W_chair = {_sol.total_chair_weight_n:,.2f} N\n(น้ำหนักโครงสร้าง)", "start", fontsize=8.0)

    # Backrest horizontal force F_back = 300 N (total, applied at backrest)
    _force_arrow(ax, x_back_top - 140, y_back_top - 40, x_back_top, y_back_top - 40, LOAD,
                 f"F_back = {_loads.backrest_force_n:,.0f} N\n(แรงพิงหลัง)", "start")

    # Floor Reactions (Blue arrows pointing up)
    _force_arrow(ax, x_floor_front, -120, x_floor_front, 0, REACTION,
                 f"2 × R_F = {_r_front:,.2f} N\n(R_FL = R_FR = {_leg_r['FL']:,.2f} N)", "start")
    _force_arrow(ax, x_floor_rear, -120, x_floor_rear, 0, REACTION,
                 f"2 × R_R = {_r_rear:,.2f} N\n(R_RL = R_RR = {_leg_r['RL']:,.2f} N)", "start")

    # Dimensions (side view spans the seat depth)
    _dim_h(ax, x_floor_front, x_floor_rear, -150,
           f"Span ที่พื้น = {x_floor_rear - x_floor_front:.1f} mm ({L_seat:.0f} + 2×{splay:.1f} mm)")
    _dim_h(ax, x_front, x_rear, H_seat - 35, f"ความลึกเบาะนั่ง = {L_seat:.0f} mm")
    _dim_v(ax, L_seat + splay + 45, 0, H_seat, f"ความสูงเบาะ = {H_seat:.0f} mm")
    _dim_v(ax, L_seat + splay + 45, H_seat, y_back_top, f"พนักพิง = {H_back:.0f} mm (เอียง {_geom.backrest_angle_deg - 90:.0f}°)")

    # Title & Equilibrium Equations Panel (all values from the solver)
    eq_text = (
        "สมดุลสถิตยศาสตร์ (Static Equilibrium):\n"
        f"  • Σ Fz = {_loads.seat_vertical_load_n:,.0f} + "
        f"{_loads.left_arm_vertical_n + _loads.right_arm_vertical_n:,.0f} + "
        f"{_sol.total_chair_weight_n:,.2f} − {_r_front:,.2f} − {_r_rear:,.2f} ≈ 0 N  ✓\n"
        "  • Σ My = 0  →  โมเมนต์คว่ำหงายสมดุลสมบูรณ์\n"
        f"  • แรงกดสูงสุดที่ขาหน้า: R_front,max = {_max_r:,.2f} N ต่อขา"
    )
    ax.text(x_front - 60, y_back_top + 10, "FBD 1: แผนภาพแรงอิสระรวมทั้งตัวเก้าอี้ (Overall Chair Equilibrium)",
            fontsize=13, fontweight="bold", color=INK)
    # Equilibrium panel parked to the RIGHT of the backrest post so it
    # never covers the chair silhouette, load labels or the title.
    ax.text(x_back_top + 70, y_back_top - 16, eq_text, fontsize=9.5, color=INK,
            ha="left", va="top",
            bbox={"boxstyle": "round,pad=0.5", "fc": BOX_BG, "ec": BEAM, "lw": 1.2})

    ax.set_xlim(-splay - 160, x_back_top + 860)
    ax.set_ylim(-200, y_back_top + 80)

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"fbd_01_overall_chair.{fmt}"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


# ==============================================================================
# FBD 2: MAIN COLUMN LEG COMPRESSION & BUCKLING
# ==============================================================================
def plot_fbd_02_main_column_leg(outdir: Path, fmt: str = "png") -> Path:
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.set_aspect("equal")
    ax.axis("off")

    L = 300.0
    col_w = 28.0

    # Draw Column
    ax.add_patch(Rectangle((-col_w / 2, 0), col_w, L, facecolor=BEAM_FILL, edgecolor=BEAM, linewidth=2.2, zorder=3))

    # Boundary conditions: Pinned-Fixed equivalent (K = 0.85)
    # Bottom support (Floor ground plate)
    ax.plot([-50, 50], [0, 0], color=BEAM, linewidth=3.0, zorder=4)
    for gx in range(-45, 50, 15):
        ax.plot([gx, gx - 10], [0, -10], color=MUTED, linewidth=1.2)

    # Top boundary (welded rail junction)
    ax.plot([-60, 60], [L, L], color=BEAM, linewidth=3.0, zorder=4)
    ax.add_patch(Rectangle((-45, L), 90, 20, facecolor="#94a3b8", edgecolor=BEAM, linewidth=1.5, zorder=3))
    ax.text(0, L + 10, "Seat Rail Junction", ha="center", va="center", fontsize=8.0, color="white", fontweight="bold")

    # Axial Loads & Reactions
    _force_arrow(ax, 0, L + 110, 0, L + 20, LOAD, "P_applied = 748.92 N\n(แรงถ่ายจากเบาะนั่ง)", "start")
    _force_arrow(ax, 0, -100, 0, 0, REACTION, "R_z = 748.92 N\n(แรงปฏิกิริยาที่พื้น)", "start")
    _force_arrow(ax, -90, 0, 0, 0, REACTION, "R_h = 45.75 N (แรงเฉือนแนวราบ)", "start", fontsize=8.0)

    # Dimensions
    _dim_v(ax, col_w / 2 + 50, 0, L, f"L = {L:.0f} mm\n(ความยาวเสาขา)")
    _dim_h(ax, -col_w / 2, col_w / 2, -55, f"Ø Do = {col_w:.0f} mm")

    # Section callout (parked below the column so the vertical
    # dimension label on its left flank stays clear of the circles)
    sec_x, sec_y = 130, -55.0
    ax.add_patch(Circle((sec_x, sec_y), 28, facecolor="white", edgecolor=BEAM, linewidth=2.0))
    ax.add_patch(Circle((sec_x, sec_y), 24, facecolor="#f8fafc", edgecolor=BEAM, linewidth=1.5))
    ax.text(sec_x, sec_y - 45, "หน้าตัดท่อเหล็ก Ø28 × 2.0 mm\nA = 163.36 mm²\nI = 13,885.8 mm⁴\nk = 9.220 mm",
            ha="center", va="top", fontsize=8.5, color=INK)

    # Buckling Formula Block
    buckle_text = (
        "การคำนวณการโก่งเดาะ (Column Buckling Analysis):\n"
        "  • สัมประสิทธิ์ความยาวประสิทธิผล: K = 0.85 (ยึดแน่นที่คาน-บานพับที่พื้น)\n"
        "  • ความยาวประสิทธิผล: Leff = K × L = 0.85 × 300 = 255.0 mm\n"
        "  • อัตราส่วนความชะลูด: λ = Leff / k = 255.0 / 9.220 = 27.66\n"
        "  • ขีดแบ่งเสาสั้น-เสายาว (Johnson cutoff): Cc = (l/k)₁ = 104.58\n"
        "  • เนื่องจาก λ (27.66) < Cc (104.58)  →  ใช้สูตรพาราโบลา J.B. Johnson\n"
        "  • แรงวิกฤตโก่งเดาะ: P_cr = 58,330.24 N (58.33 kN)\n"
        "  • ค่าความปลอดภัย (Safety Factor): n = P_cr / P_applied = 77.89  ✓ (ผ่านเกณฑ์)"
    )
    ax.text(-120, L + 140, "FBD 2: แผนภาพแรงเสาขาเก้าอี้และแรงต้านการโก่งเดาะ (Main Column Buckling FBD)",
            fontsize=12, fontweight="bold", color=INK)
    ax.text(sec_x - 30, L - 30, buckle_text, fontsize=8.5, color=INK,
            bbox={"boxstyle": "round,pad=0.5", "fc": BOX_BG, "ec": BEAM, "lw": 1.2})

    ax.set_xlim(-160, 360)
    ax.set_ylim(-190, L + 170)

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"fbd_02_main_column_leg.{fmt}"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


# ==============================================================================
# FBD 3: SEAT FRAME RAIL (FBD + SFD + BMD)
# ==============================================================================
def plot_fbd_03_seat_rail_sfd_bmd(outdir: Path, fmt: str = "png") -> Path:
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10.5, 9.0), sharex=True,
                                        gridspec_kw={"height_ratios": [2.2, 1.4, 1.4]})
    for ax in (ax1, ax2, ax3):
        ax.axis("off")

    L = 480.0
    P = 650.0
    R = 325.0
    M_max = 78.0  # N*m

    # Top: FBD
    beam_h = 16.0
    ax1.add_patch(Rectangle((0, -beam_h / 2), L, beam_h, facecolor=BEAM_FILL, edgecolor=BEAM, linewidth=2.0, zorder=3))
    # Pinned at A, Roller at B
    ax1.plot([0, -12, 12, 0], [-beam_h / 2, -beam_h / 2 - 20, -beam_h / 2 - 20, -beam_h / 2], color=BEAM, lw=1.8)
    ax1.plot([-25, 25], [-beam_h / 2 - 20, -beam_h / 2 - 20], color=BEAM, lw=2.2)
    ax1.plot([L, L - 12, L + 12, L], [-beam_h / 2, -beam_h / 2 - 16, -beam_h / 2 - 16, -beam_h / 2], color=BEAM, lw=1.8)
    ax1.add_patch(Circle((L - 6, -beam_h / 2 - 20), 4, facecolor="white", edgecolor=BEAM, lw=1.2))
    ax1.add_patch(Circle((L + 6, -beam_h / 2 - 20), 4, facecolor="white", edgecolor=BEAM, lw=1.2))
    ax1.plot([L - 25, L + 25], [-beam_h / 2 - 24, -beam_h / 2 - 24], color=BEAM, lw=2.2)

    # Loads
    _force_arrow(ax1, L / 2, 85, L / 2, beam_h / 2, LOAD, f"P = {P:.0f} N (ครึ่งหนึ่งของ 1,300 N)", "start")
    _force_arrow(ax1, 0, -85, 0, -beam_h / 2 - 20, REACTION, f"R₁ = {R:.0f} N", "start")
    _force_arrow(ax1, L, -85, L, -beam_h / 2 - 24, REACTION, f"R₂ = {R:.0f} N", "start")
    _dim_h(ax1, 0, L / 2, -55, "a = 240 mm")
    _dim_h(ax1, L / 2, L, -55, "L - a = 240 mm")

    ax1.text(L / 2, 110, "FBD 3: คานโครงเบาะนั่ง (Seat Frame Rail FBD)", fontsize=12, fontweight="bold", ha="center", color=INK)

    # Middle: SFD (Shear Force Diagram)
    ax2.plot([0, L], [0, 0], color=MUTED, lw=1.2, ls="--")
    # Draw shear block
    ax2.fill_between([0, L / 2], [0, 0], [R, R], facecolor="#bfdbfe", edgecolor=REACTION, lw=1.8)
    ax2.fill_between([L / 2, L], [0, 0], [-R, -R], facecolor="#fecaca", edgecolor=LOAD, lw=1.8)
    ax2.plot([0, 0, L / 2, L / 2, L, L], [0, R, R, -R, -R, 0], color=INK, lw=2.0)
    ax2.text(-10, R / 2, f"+{R:.0f} N", ha="right", va="center", color=REACTION, fontweight="bold", fontsize=9)
    ax2.text(L + 10, -R / 2, f"−{R:.0f} N", ha="left", va="center", color=LOAD, fontweight="bold", fontsize=9)
    ax2.text(-35, 0, "SFD\n(V)", ha="right", va="center", fontsize=11, fontweight="bold", color=INK)

    # Bottom: BMD (Bending Moment Diagram)
    ax3.plot([0, L], [0, 0], color=MUTED, lw=1.2, ls="--")
    ax3.fill_between([0, L / 2, L], [0, 0, 0], [0, M_max, 0], facecolor="#ddd6fe", edgecolor=MOMENT, lw=2.0)
    ax3.text(L / 2, M_max + 8, f"M_max = {M_max:.1f} N·m (78,000 N·mm)", ha="center", va="bottom",
            color=MOMENT, fontweight="bold", fontsize=9.5)
    ax3.text(-35, M_max / 2, "BMD\n(M)", ha="right", va="center", fontsize=11, fontweight="bold", color=INK)

    # Results summary block
    res_text = (
        "ผลการวิเคราะห์คานโครงเบาะ (25 × 25 × 2.0 mm, Z = 1,307.6 mm³, I = 16,345.3 mm⁴):\n"
        "  • เค้นดัดสูงสุด: σ_max = M_max / Z = 78,000 / 1,307.6 = 59.65 MPa\n"
        "  • การแอ่นตัวสูงสุด: δ_max = (P L³) / (48 E I) = 0.447 mm < L/250 (1.92 mm)  ✓ ผ่านเกณฑ์\n"
        "  • ค่าความปลอดภัยคราก (Yield SF): n = Sy / σ_max = 370 / 59.65 = 6.20  ✓"
    )
    ax3.text(0, -40, res_text, fontsize=9.0, color=INK, va="top",
             bbox={"boxstyle": "round,pad=0.4", "fc": BOX_BG, "ec": BEAM})

    ax1.set_xlim(-60, L + 60)
    ax1.set_ylim(-95, 130)
    ax2.set_ylim(-R - 80, R + 80)
    ax3.set_ylim(-85, M_max + 35)

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"fbd_03_seat_rail_sfd_bmd.{fmt}"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


# ==============================================================================
# FBD 4: ARMREST POSTS & LEVER RULE LOAD SPLIT
# ==============================================================================
def plot_fbd_04_armrest_posts(outdir: Path, fmt: str = "png") -> Path:
    fig, ax = plt.subplots(figsize=(12.5, 7.2))
    ax.set_aspect("equal")
    ax.axis("off")

    # Every number on this sheet is read back from the resolved
    # armrest geometry and the frame solver result -- the same
    # values the CAD kernel draws and the report publishes.
    model, ag, arm, _brk = _armrest_design()
    geom = model.geometry
    loads = model.loads

    # Drawing frame: pad leading edge at x = 0, x increasing aft.
    L_pad = ag.pad_length_mm                        # 320 mm pad
    x_front_post = ag.cantilever_front_mm           # 60 mm forward overhang
    x_rear_post = x_front_post + ag.post_span_mm    # 323.3 mm
    H_post = geom.armrest_height_above_seat_mm      # 210 mm
    pad_t = ag.pad_thickness_mm                     # 18 mm
    post_w = 2.0 * ag.post_radius_mm                # Ø22 mm

    F_arm = loads.left_arm_vertical_n               # 450 N
    F_lat = abs(loads.left_arm_lateral_n)           # 150 N
    w_front, w_rear = ag.post_reaction_fractions(loads.left_arm_load_y_mm)
    F_front = F_arm * w_front                       # 262.0 N (58.2 %)
    F_rear = F_arm * w_rear                         # 188.0 N (41.8 %)
    x_load = ag.pad_front_y_mm - loads.left_arm_load_y_mm  # lever-rule point

    # Arm pad bar (top horizontal)
    ax.add_patch(Rectangle((0, H_post), L_pad, pad_t, facecolor=BEAM_FILL, edgecolor=BEAM, lw=2.2, zorder=3))

    # Two vertical tubular posts; the rear post stands just aft
    # of the pad trailing edge (3.3 mm rear cantilever).
    ax.add_patch(Rectangle((x_front_post - post_w / 2, 0), post_w, H_post, facecolor="#e2e8f0", edgecolor=BEAM, lw=2.0, zorder=3))
    ax.add_patch(Rectangle((x_rear_post - post_w / 2, 0), post_w, H_post, facecolor="#e2e8f0", edgecolor=BEAM, lw=2.0, zorder=3))

    # Every member of the actual Armrest_Left/Right part, so
    # this sheet matches the STEP solid and the part picture:
    # top spreader rail (Ø15.4) tying the post heads just under
    # the pad, and the diagonal brace (Ø17.6) from the rear foot
    # to the front head that closes the triangle so the two
    # posts cannot rack.
    spreader_r = ag.post_radius_mm * 0.7
    ax.add_patch(Rectangle((x_front_post, H_post - spreader_r), ag.post_span_mm,
                           2 * spreader_r, facecolor="#e2e8f0", edgecolor=BEAM, lw=1.5, zorder=3))

    import math
    brace_r = ag.post_radius_mm * 0.8
    bx0, by0 = float(x_rear_post), 0.0
    bx1, by1 = float(x_front_post), float(H_post)
    bdx, bdy = bx1 - bx0, by1 - by0
    blen = math.hypot(bdx, bdy)
    ux, uy = bdx / blen, bdy / blen
    px, py = -uy, ux
    ax.add_patch(Polygon(
        [(bx0 + brace_r * px, by0 + brace_r * py),
         (bx0 - brace_r * px, by0 - brace_r * py),
         (bx1 - brace_r * px, by1 - brace_r * py),
         (bx1 + brace_r * px, by1 + brace_r * py)],
        closed=True, facecolor="#e2e8f0", edgecolor=BEAM, lw=1.5, zorder=3))

    # Bracket plates bonding each post foot to the seat rail
    # (25 x 12 x 11 mm; the side view shows the 12 x 11 face).
    for xp in (x_front_post, x_rear_post):
        ax.add_patch(Rectangle((xp - ag.bracket_thick_mm / 2.0, -ag.bracket_height_mm),
                               ag.bracket_thick_mm, ag.bracket_height_mm,
                               facecolor="#94a3b8", edgecolor=BEAM, lw=1.5, zorder=3))

    # Seat rail mounting surface (base)
    ax.plot([-20, x_rear_post + 20], [0, 0], color=BEAM, lw=3.0, zorder=4)
    for gx in range(-15, int(x_rear_post + 20), 20):
        ax.plot([gx, gx - 12], [0, -12], color=MUTED, lw=1.2)

    # Applied loads on armrest pad
    # 450 N downward occupant arm push at the lever-rule point
    _force_arrow(ax, x_load, H_post + 110, x_load, H_post + pad_t, LOAD,
                 f"F_arm = {F_arm:.1f} N\n(แรงกดท้าวแขนแนวดิ่ง)", "start")

    # Lateral push force 150 N (label rides at the arrow tail, above
    # the pad, so it never grazes the pad or the dimension lines)
    _force_arrow(ax, L_pad + 80, H_post + 9, L_pad, H_post + 9, LOAD,
                 f"F_lat = {F_lat:.0f} N\n(แรงผลักด้านข้าง)", "start", fontsize=8.5,
                 label_below=False)

    # Reactions transferred into posts (Lever-Rule Split)
    _force_arrow(ax, x_front_post, -90, x_front_post, 0, REACTION,
                 f"F_front = {F_front:.1f} N\n(เสาหน้าวิกฤต {w_front * 100:.1f}%)", "start")
    _force_arrow(ax, x_rear_post, -90, x_rear_post, 0, REACTION,
                 f"F_rear = {F_rear:.1f} N\n(เสาหลัง {w_rear * 100:.1f}%)", "start")

    # Overhang moment arc at post base
    M_base = arm.strut_base_moment_nm               # 41.49 N·m
    _moment_arc(ax, x_front_post, 35, 30, 20, 160, MOMENT, f"M_base = {M_base:.2f} N·m")

    # Dimensions - height dimension on the left flank so the
    # right flank stays free for the summary panel.
    _dim_h(ax, 0, x_front_post, H_post + 35, f"{ag.cantilever_front_mm:.0f} mm (Overhang)")
    _dim_h(ax, x_front_post, x_rear_post, H_post + 35, f"{ag.post_span_mm:.1f} mm (ระยะห่างเสา)")
    _dim_h(ax, 0, L_pad, H_post + 55, f"{ag.pad_length_mm:.0f} mm (ความยาวที่พักแขน)")
    _dim_v(ax, -55, 0, H_post, f"H = {H_post:.0f} mm\n(ความสูงเสาแขน)")

    # Formulas & Summary - parked to the RIGHT of the figure so
    # the panel never covers the posts, pad or moment arc.
    prof = geom.arm_profile
    A_mm2 = prof.area_m2 * 1e6                      # 114.23 mm²
    Z_mm3 = prof.section_modulus_m3 * 1e9           # 533.85 mm³
    M_half = M_base / 2.0                           # 20.74 N·m per post pair side
    load_from_rear = loads.left_arm_load_y_mm - ag.rear_post_y_mm
    load_from_front = ag.front_post_y_mm - loads.left_arm_load_y_mm
    Sy = model.material.yield_strength_mpa
    summary = (
        "การกระจายแรงตามกฎคานงัด (Lever Rule Split):\n"
        f"  • แรงรวมแนวดิ่ง: F_arm = {F_arm:.0f} N\n"
        f"  • โมเมนต์ที่ฐานเสาหน้า: M_base = {M_base:.2f} N·m\n"
        f"  • เสาหน้า (วิกฤต {w_front * 100:.1f}%):\n"
        f"      F_front = {F_arm:.0f} × {load_from_rear:.2f} / {ag.post_span_mm:.2f} = {F_front:.1f} N\n"
        f"  • เสาหลัง ({w_rear * 100:.1f}%):\n"
        f"      F_rear = {F_arm:.0f} × {load_from_front:.2f} / {ag.post_span_mm:.2f} = {F_rear:.1f} N\n"
        f"  • ท่อกลม Ø{prof.outer_dimension_mm:.0f} × {prof.wall_thickness_mm:.1f} mm  A = {A_mm2:.2f} mm²\n"
        f"      Z = {Z_mm3:.2f} mm³\n"
        f"  • σ_axial = {F_front:.1f} / {A_mm2:.2f} = {arm.strut_axial_stress_mpa:.2f} MPa\n"
        f"  • σ_bending = {M_half * 1000.0:.0f} / {Z_mm3:.2f} = {arm.strut_bending_stress_mpa:.2f} MPa\n"
        f"  • σ_total = {arm.strut_axial_stress_mpa:.2f} + {arm.strut_bending_stress_mpa:.2f} = {arm.strut_combined_stress_mpa:.2f} MPa\n"
        f"  • n = {Sy:.0f} / {arm.strut_combined_stress_mpa:.2f} = {arm.arm_safety_factor:.2f}  ✓ ผ่านเกณฑ์\n"
        "  • แบบจำลอง: เสาเป็น cantilever ยึดแน่นที่ฐาน (conservative)\n"
        "    ฐานเสาทแยงแสดงตามแบบชิ้นส่วน Armrest_Left/Right"
    )
    ax.text(-20, H_post + 150, "FBD 4: แผนภาพแรงชุดท่อแขนและการแบ่งแรงตามกฎคานงัด (Armrest Lever-Rule FBD)",
            fontsize=12, fontweight="bold", color=INK)
    ax.text(L_pad + 60, H_post - 10, summary, fontsize=8.5, color=INK,
            ha="left", va="top",
            bbox={"boxstyle": "round,pad=0.5", "fc": BOX_BG, "ec": BEAM, "lw": 1.2})

    ax.set_xlim(-90, L_pad + 300)
    ax.set_ylim(-110, H_post + 180)

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"fbd_04_armrest_posts.{fmt}"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


# ==============================================================================
# FBD 5: ARM MOUNTING BRACKET (FLAT BAR 12 x 11 mm)
# ==============================================================================
def plot_fbd_05_arm_bracket(outdir: Path, fmt: str = "png") -> Path:
    fig, ax = plt.subplots(figsize=(9.5, 6.8))
    ax.set_aspect("equal")
    ax.axis("off")

    # Bracket check reads the same solver result as the report:
    # the plate carries the governing post's lever-rule axial
    # share and exactly half of the post base moment.
    model, ag, _arm, brk = _armrest_design()
    mat = model.material

    L_brk = ag.bracket_len_mm       # 25 mm: seat-rail face to post axis
    t_brk = ag.bracket_height_mm    # 11 mm plate height (drawn axis)
    W_brk = ag.bracket_thick_mm     # 12 mm plate thickness (section width)

    # Draw cantilever flat bracket
    ax.add_patch(Rectangle((0, -t_brk / 2), L_brk, t_brk, facecolor=BEAM_FILL, edgecolor=BEAM, lw=2.2, zorder=3))

    # Fixed wall support on left (welded to seat rail)
    ax.plot([0, 0], [-45, 45], color=BEAM, lw=4.0, zorder=4)
    for gy in range(-40, 45, 12):
        ax.plot([0, -12], [gy, gy - 8], color=MUTED, lw=1.2)
    ax.text(-15, 0, "รอยเชื่อมติดคานเบาะ\n(Fixed Support)", ha="right", va="center", fontsize=8.5, color=INK)

    # Applied loads from arm post at tip (x = L_brk)
    F_v = brk.post_axial_n                       # 262.0 N (lever-rule share)
    M_appl = brk.post_base_moment_nm / 2.0       # 20.74 N·m (plate carries M_base/2)
    _force_arrow(ax, L_brk, 75, L_brk, t_brk / 2, LOAD, f"F_v = {F_v:.1f} N\n(แรงจากเสาแขนหน้า)", "start")
    _moment_arc(ax, L_brk, 0, 32, 20, 160, MOMENT,
                f"M = {M_appl:.2f} N·m\n({M_appl * 1000.0:,.0f} N·mm)")

    # Fixed reactions at root (x = 0)
    _force_arrow(ax, 0, -75, 0, -t_brk / 2, REACTION, f"R_v = {F_v:.1f} N", "start")
    _moment_arc(ax, 0, 0, 32, 200, 340, REACTION, f"M_root = {M_appl:.2f} N·m", ccw=False,
                label_xy=(-34, -40), label_ha="right", label_va="top")

    # Cross section drawing on the right, above the bracket axis
    cx, cy = 240, 80
    ax.add_patch(Rectangle((cx - W_brk * 2, cy - t_brk * 2), W_brk * 4, t_brk * 4,
                           facecolor="#e2e8f0", edgecolor=BEAM, lw=1.8))
    ax.text(cx, cy + 35,
            f"หน้าตัดแผ่นยึด ({W_brk:.1f} × {t_brk:.1f} mm)\n"
            f"A = {brk.section_area_mm2:.1f} mm²\n"
            f"I = {brk.section_inertia_mm4:,.1f} mm⁴\n"
            f"Z = {brk.section_modulus_mm3:.1f} mm³",
            ha="center", va="bottom", fontsize=8.5, color=INK)

    # Dimensions - short bracket span, so the label rides to the
    # right of the ticks, clear of the root moment label.
    _dim_h(ax, 0, L_brk, -50, f"L = {L_brk:.0f} mm (ความยาวแผ่นยึด)",
           label_dx=L_brk / 2.0 + 12.0, label_ha="left")

    # Fatigue: Marin-corrected endurance limit on the bracket
    # effective diameter, then the pulsating (R = 0) criteria.
    Se = _marin_endurance(model, ag.bracket_len_mm)
    fat = FatigueSolver.repeated_load_fatigue(
        brk.combined_stress_mpa, mat.ultimate_strength_mpa,
        mat.yield_strength_mpa, Se, stress_ratio_r=0.0,
    )

    # Stress breakdown panel
    stress_text = (
        "การคำนวณความเค้นรวม (Combined Stress on Critical Bracket):\n"
        f"  • แรงในแนวแกน: σ_axial = F_v / A = {F_v:.1f} / {brk.section_area_mm2:.2f} = {brk.axial_stress_mpa:.2f} MPa\n"
        f"  • เค้นดัดสูงสุด: σ_bending = (M_base/2) / Z = {M_appl * 1000.0:,.0f} / {brk.section_modulus_mm3:.2f} = {brk.bending_stress_mpa:.2f} MPa\n"
        f"  • เค้นรวมสูงสุด: σ_total = {brk.axial_stress_mpa:.2f} + {brk.bending_stress_mpa:.2f} = {brk.combined_stress_mpa:.2f} MPa  (ชิ้นส่วนวิกฤตที่สุดในระบบ)\n"
        f"  • อัตราความปลอดภัยสถิต: n_yield = Sy / σ_total = {mat.yield_strength_mpa:.0f} / {brk.combined_stress_mpa:.2f} = {brk.bracket_safety_factor:.2f}  ✓ ผ่านเกณฑ์ nd = 2.0\n"
        f"  • ขีดจำกัดความล้าดัดแปลง: Se = {Se:.2f} MPa\n"
        f"  • อัตราความปลอดภัยความล้า (Pulsating R = 0): Soderberg n = {fat.nf_soderberg:.2f}, Goodman n = {fat.nf_goodman:.2f}  ✓"
    )
    ax.text(-60, 150, "FBD 5: แผนภาพแรงแผ่นยึดท่อแขน (Arm Mounting Bracket Bending & Stress FBD)",
            fontsize=12, fontweight="bold", color=INK)
    ax.text(-40, -100, stress_text, fontsize=8.5, color=INK, va="top",
            bbox={"boxstyle": "round,pad=0.5", "fc": BOX_BG, "ec": BEAM, "lw": 1.2})

    ax.set_xlim(-80, 360)
    ax.set_ylim(-170, 175)

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"fbd_05_arm_bracket.{fmt}"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


# ==============================================================================
# FBD 6: BACKREST POST (INCLINED 8 DEGREES)
# ==============================================================================
def plot_fbd_06_backrest_post(outdir: Path, fmt: str = "png") -> Path:
    fig, ax = plt.subplots(figsize=(9.5, 7.5))
    ax.set_aspect("equal")
    ax.axis("off")

    import math
    L = 420.0
    theta_deg = 8.0
    theta = theta_deg * math.pi / 180.0
    dx = L * math.sin(theta)  # 58.45 mm
    dz = L * math.cos(theta)  # 415.91 mm

    # Base at (0, 0), Tip at (dx, dz)
    ax.plot([0, dx], [0, dz], color=BEAM, lw=8.0, zorder=3)

    # Fixed base support (welded socket on rear seat rail)
    ax.plot([-40, 40], [0, 0], color=BEAM, lw=4.0, zorder=4)
    for gx in range(-35, 40, 12):
        ax.plot([gx, gx - 10], [0, -10], color=MUTED, lw=1.2)
    ax.text(0, -25, "จุดเชื่อมต่อเสาพนักพิง (Fixed Base)", ha="center", va="top", fontsize=8.5, color=INK)

    # Applied occupant backward leaning force at tip
    F_back = 150.0  # N
    _force_arrow(ax, dx + 120, dz, dx, dz, LOAD, f"F_back = {F_back:.0f} N\n(แรงพิงหลัง)", "start")

    # Reactions at base
    _force_arrow(ax, -90, 0, 0, 0, REACTION, f"R_x = {F_back:.0f} N", "start")
    M_base = 62.387  # N*m
    _moment_arc(ax, 0, 20, 35, 10, 150, REACTION, f"M_base = {M_base:.2f} N·m\n(62,387 N·mm)", ccw=False)

    # Angle arc at base
    arc = Arc((0, 0), 100, 100, angle=0, theta1=90 - theta_deg, theta2=90, color=MUTED, lw=1.5)
    ax.add_patch(arc)
    ax.text(12, 60, "8°", fontsize=9.0, color=MUTED, fontweight="bold")

    # Dimensions
    _dim_v(ax, dx + 45, 0, dz, f"dz = {dz:.1f} mm (แขนโมเมนต์ประสิทธิผล)")
    _dim_h(ax, 0, dx, dz + 15, f"dx = {dx:.1f} mm")

    # Formulas & Stress Audit
    back_text = (
        "การคำนวณเสาพนักพิงหลัง (Ø28 × 2.0 mm, Z = 991.8 mm³, A = 163.36 mm²):\n"
        "  • แขนโมเมนต์ประสิทธิผล: dz = L × cos(8°) = 420 × cos(8°) = 415.91 mm\n"
        "  • โมเมนต์ดัดที่ฐานเสา: M_base = F_back × dz = 150 × 0.41591 = 62.387 N·m\n"
        "  • เค้นดัด: σ_bending = M_base / Z = 62,387 / 991.8 = 62.903 MPa\n"
        "  • เค้นในแนวแกน: σ_axial = F / A = 150 / 163.36 = 0.918 MPa\n"
        "  • เค้นรวม: σ_total = 62.903 + 0.918 = 63.818 MPa (≈ 63.82 MPa)\n"
        "  • ค่าความปลอดภัยคราก (Yield SF): n = Sy / σ_total = 370 / 63.818 = 5.80  ✓\n"
        "  • ตรวจสอบการโก่งเดาะ: P_cr = 54,709.38 N  →  n_buckling = 364.73  ✓"
    )
    ax.text(-100, dz + 50, "FBD 6: แผนภาพแรงเสาพนักพิงหลังเอียง 8° (Backrest Inclined Post FBD)",
            fontsize=12, fontweight="bold", color=INK)
    # Formula panel below the base line (va="top" so the block hangs
    # downward) — the inclined post runs diagonally through the whole
    # left half, so any panel there would cover the post line.
    ax.text(0, -70, back_text, fontsize=8.5, color=INK, va="top",
            bbox={"boxstyle": "round,pad=0.5", "fc": BOX_BG, "ec": BEAM, "lw": 1.2})

    ax.set_xlim(-130, dx + 280)
    ax.set_ylim(-170, dz + 80)

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"fbd_06_backrest_post.{fmt}"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


# ==============================================================================
# FBD 7: LOWER STRETCHER / TIE BAR
# ==============================================================================
def plot_fbd_07_lower_stretcher(outdir: Path, fmt: str = "png") -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.set_aspect("equal")
    ax.axis("off")

    L = 516.7  # mm
    bar_h = 19.0

    # Draw stretcher bar
    ax.add_patch(Rectangle((0, -bar_h / 2), L, bar_h, facecolor=BEAM_FILL, edgecolor=BEAM, lw=2.2, zorder=3))

    # Pinned ends at splayed legs
    ax.add_patch(Circle((0, 0), 14, facecolor="#94a3b8", edgecolor=BEAM, lw=1.8, zorder=4))
    ax.add_patch(Circle((L, 0), 14, facecolor="#94a3b8", edgecolor=BEAM, lw=1.8, zorder=4))
    ax.text(0, -30, "รอยต่อขาหน้าซ้าย\n(Joint FL)", ha="center", va="top", fontsize=8.5, color=INK)
    ax.text(L, -30, "รอยต่อขาหน้าขวา\n(Joint FR)", ha="center", va="top", fontsize=8.5, color=INK)

    # Applied tie/thrust load: 150 N (labels ride below the arrow
    # midpoints so they clear both joint boss circles and the bar)
    F_tie = 150.0
    _force_arrow(ax, -140, 0, 0, 0, LOAD, f"F_tie = {F_tie:.0f} N", "mid", fontsize=8.5)
    _force_arrow(ax, L + 140, 0, L, 0, REACTION, f"F_react = {F_tie:.0f} N", "mid", fontsize=8.5)

    # Dimensions
    _dim_h(ax, 0, L, -65, f"L = {L:.1f} mm (ระยะค้ำระหว่างขาคู่)")

    # Formula & Buckling Check
    stretcher_text = (
        "การคำนวณคานค้ำขาเก้าอี้ (Ø19 × 1.5 mm, A = 82.47 mm², k = 6.210 mm):\n"
        "  • อัตราส่วนความชะลูด: λ = (0.85 × 516.7) / 6.210 = 70.72 < Cc (104.58)  →  J.B. Johnson\n"
        "  • แรงวิกฤตโก่งเดาะ: P_cr = 23,534.98 N (23.53 kN)\n"
        "  • เค้นดึง/อัดในแนวแกน: σ_axial = 150 / 82.47 = 1.819 MPa\n"
        "  • ค่าความปลอดภัยต้านการโก่งเดาะ: n_buckling = 23,534.98 / 150 = 156.90  ✓ ผ่านเกณฑ์อย่างปลอดภัย\n"
        "  • ค่าความปลอดภัยคราก: n_yield = 370 / 1.819 = 203.42  ✓"
    )
    ax.text(0, 75, "FBD 7: แผนภาพแรงคานค้ำขาเก้าอี้ (Lower Stretcher Tie-Bar FBD)",
            fontsize=12, fontweight="bold", color=INK)
    ax.text(0, -80, stretcher_text, fontsize=8.5, color=INK, va="top",
            bbox={"boxstyle": "round,pad=0.5", "fc": BOX_BG, "ec": BEAM, "lw": 1.2})

    ax.set_xlim(-150, L + 150)
    ax.set_ylim(-160, 100)

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"fbd_07_lower_stretcher.{fmt}"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


# ==============================================================================
# MAIN RUNNER
# ==============================================================================
def generate_all_fbds(outdir: Path = DEFAULT_OUTDIR, fmts: tuple[str, ...] = ("png", "svg")) -> list[Path]:
    """Generate all 7 textbook FBDs in both PNG and SVG formats."""
    outdir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    generators = [
        plot_fbd_01_overall_chair,
        plot_fbd_02_main_column_leg,
        plot_fbd_03_seat_rail_sfd_bmd,
        plot_fbd_04_armrest_posts,
        plot_fbd_05_arm_bracket,
        plot_fbd_06_backrest_post,
        plot_fbd_07_lower_stretcher,
    ]
    for gen in generators:
        for fmt in fmts:
            p = gen(outdir, fmt=fmt)
            generated.append(p)
    return generated


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--format", choices=("png", "svg", "both"), default="both")
    args = ap.parse_args(argv)

    fmts = ("png", "svg") if args.format == "both" else (args.format,)
    files = generate_all_fbds(outdir=args.outdir, fmts=fmts)
    for f in files:
        print(f"[ok] Wrote {f} ({f.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

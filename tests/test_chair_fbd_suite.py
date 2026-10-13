"""Regression tests: the FBD suite must draw from the source-of-truth model.

Each assertion below fails without the corresponding fix:

* FBD 1 originally rendered its SIDE elevation using the seat WIDTH (480 mm)
  as the fore-aft span and carried a stale tipping factor (2.45) and a
  half-magnitude backrest thrust (150 N).  A side view must span the seat
  DEPTH (460 mm) and read every force/factor straight from the solver.
* FBD 3 mislabelled the seat-rail section as a 30 x 15 x 1.5 rectangular tube
  while quoting the numbers of the real 25 x 25 x 2.0 square tube.
* FBD 7 drew the 516.7 mm width-direction bar but labelled a front->rear
  (depth) pair of joints.
"""
from pathlib import Path

from drafting.chair_fbd_suite import (
    plot_fbd_01_overall_chair,
    plot_fbd_03_seat_rail_sfd_bmd,
    plot_fbd_07_lower_stretcher,
)


def _svg(fn, tmp_path: Path) -> str:
    return fn(tmp_path, fmt="svg").read_text(encoding="utf-8")


def test_fbd01_side_view_spans_seat_depth(tmp_path):
    s = _svg(plot_fbd_01_overall_chair, tmp_path)
    # Correct depth-based fore-aft span and the matching floor span.
    assert "460 mm" in s
    assert "515.0 mm" in s
    # ... never the width-based values the fix removed.
    assert "535.0 mm" not in s
    assert "480 mm" not in s


def test_fbd01_reads_solver_forces_and_factors(tmp_path):
    s = _svg(plot_fbd_01_overall_chair, tmp_path)
    # Tipping was removed from the FBD (REF scope = closed-form member sizing only).
    assert "n_tip" not in s
    # Backrest thrust is the total applied load (300 N), not the per-post 150 N.
    assert "F_back = 300" in s


def test_fbd03_section_matches_square_tube_profile(tmp_path):
    s = _svg(plot_fbd_03_seat_rail_sfd_bmd, tmp_path)
    # frame_profile is a 25 x 25 x 2.0 square tube (I = 16,345.3 mm^4).
    assert "25 × 25 × 2.0" in s
    assert "30 × 15 × 1.5" not in s


def test_fbd07_labels_name_the_width_stretcher(tmp_path):
    s = _svg(plot_fbd_07_lower_stretcher, tmp_path)
    # L = 516.7 mm is the front (width) bar between FL and FR, so the end
    # joints must be the two front legs, not a front->rear (depth) pair.
    assert "(Joint FL)" in s
    assert "(Joint FR)" in s
    assert "Joint RL/RR" not in s

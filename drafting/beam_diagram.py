"""
Mermaid V / M beam-diagram generator for the seat-frame rail.

Emits ``xychart-beta`` diagrams whose ordinates come from the Macaulay
singularity function, and whose headline values are cross-checked against the
deterministic solver in :mod:`physics.frame_physics`.

Singularity function for a simply supported rail of span ``L`` carrying a
central point load ``P`` (reactions ``R1 = R2 = P/2``)::

    V(x) = R1<x-0>^0 - P<x-L/2>^0 + R2<x-L>^0
    M(x) = R1<x-0>^1 - P<x-L/2>^1 + R2<x-L>^1

Usage::

    python -m drafting.beam_diagram            # print to stdout
    python -m drafting.beam_diagram --inject   # splice into the report
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

# Allow `python -m drafting.beam_diagram` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.frame_model import FrameDesignModel
from physics.frame_physics import FramePhysicsSolver

REPORT_MD = Path("Project/chair/chair_design_report.md")


def _force_utf8_stdout() -> None:
    """Thai labels cannot encode to cp1252; make stdout/stderr UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        try:
            # reconfigure() exists only on TextIOWrapper, not every stream.
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _mac(x: float, a: float, power: int) -> float:
    """
    Macaulay bracket ``<x - a>^power``.

    Uses the *just inside* convention (``>=``): the force applied exactly at
    ``x = a`` is counted, so shear starts at ``+R1`` rather than 0 and the
    right-hand reaction closes the diagram back to 0.
    """
    d = x - a
    return (d**power) if d >= 0.0 else 0.0


class SimplySupportedRail:
    """Simply supported rail with a single central point load."""

    def __init__(self, span_mm: float, point_load_n: float) -> None:
        self.span_mm = float(span_mm)
        self.p_n = float(point_load_n)
        self.r1_n = self.p_n / 2.0
        self.r2_n = self.p_n / 2.0
        self.a_mm = self.span_mm / 2.0

    def shear(self, x_mm: float) -> float:
        return (
            self.r1_n * _mac(x_mm, 0.0, 0)
            - self.p_n * _mac(x_mm, self.a_mm, 0)
            + self.r2_n * _mac(x_mm, self.span_mm, 0)
        )

    def moment(self, x_mm: float) -> float:
        return (
            self.r1_n * _mac(x_mm, 0.0, 1)
            - self.p_n * _mac(x_mm, self.a_mm, 1)
            + self.r2_n * _mac(x_mm, self.span_mm, 1)
        )

    def moment_max(self) -> float:
        """Peak midspan moment ``P*L/4`` (N.mm)."""
        return self.p_n * self.span_mm / 4.0

    def stations(self, divisions: int = 8) -> list[float]:
        if divisions < 2:
            raise ValueError("divisions must be >= 2")
        return [self.span_mm * i / divisions for i in range(divisions + 1)]

    def verify_equilibrium(self, tol: float = 1e-9) -> tuple[float, float]:
        """Return ``(sum_Fy, sum_M_at_0)``; both must vanish."""
        sum_fy = self.r1_n - self.p_n + self.r2_n
        sum_m = -self.p_n * self.a_mm + self.r2_n * self.span_mm
        if abs(sum_fy) > tol or abs(sum_m) > tol:
            raise AssertionError(f"equilibrium violated: sum_Fy={sum_fy}, sum_M={sum_m}")
        return sum_fy, sum_m


def _fmt(values: Sequence[float]) -> str:
    return ", ".join(f"{v:g}" for v in values)


def _mermaid(
    title: str, x: Sequence[float], y: Sequence[float], y_label: str, y_min: float, y_max: float
) -> str:
    return (
        "```mermaid\n"
        "xychart-beta\n"
        f'    title "{title}"\n'
        f'    x-axis "ตำแหน่ง x (mm)" [{_fmt(x)}]\n'
        f'    y-axis "{y_label}" {y_min:g} --> {y_max:g}\n'
        f"    line [{_fmt(y)}]\n"
        "```"
    )


def _fbd_image_ref(rail: SimplySupportedRail) -> str:
    """
    Markdown image reference for the free-body diagram.

    The FBD is a plotted drawing, not Mermaid: Mermaid has no arrowhead,
    support, hatch, or dimension primitive, so ``drafting.fbd_plot``
    renders it with matplotlib from this same solver result.
    """
    rel = "diagrams/fbd_cross_rail.png"
    return (
        f"![แผนภาพแรงอิสระ (FBD) ของคานโครงเบาะ]({rel})\n\n"
        "> แผนภาพที่ 1 — FBD คานโครงเบาะ เสียดยืนปลายซ้ายแบบหมุด (pinned, A) "
        f"และปลายขวาแบบลูกกลิ้ง (roller, B)  L = {rail.span_mm:g} mm, "
        f"P = {rail.p_n:g} N\n"
        "> สร้างจากผล solver ใน `drafting/beam_diagram.py` "
        "โดย `drafting/fbd_plot.py`"
    )


FBD_IMAGE_RE = re.compile(
    r"!\[แผนภาพแรงอิสระ \(FBD\) ของคานโครงเบาะ\]\(diagrams/fbd_cross_rail\.png\)"
    r".*?`drafting/fbd_plot\.py`",
    re.DOTALL,
)


def build_blocks(divisions: int = 8) -> tuple[str, str, str, SimplySupportedRail]:
    """Build both Mermaid blocks and assert they match the deterministic solver."""
    model = FrameDesignModel()
    result = FramePhysicsSolver.solve(model)

    span_mm = model.geometry.seat_width_mm
    p_n = model.loads.seat_vertical_load_n / 2.0
    rail = SimplySupportedRail(span_mm, p_n)
    rail.verify_equilibrium()

    # Cross-check the closed form against the solver (unit conversion only).
    solver_m_nm = result.seat_frame.rail_bending_moment_nm
    closed_m_nm = rail.moment_max() / 1e3  # N.mm -> N.m
    assert abs(closed_m_nm - solver_m_nm) < 1e-6, (
        f"M_max mismatch: closed form {closed_m_nm:.6f} N.m vs solver {solver_m_nm:.6f} N.m"
    )

    z_mm3 = model.geometry.frame_profile.section_modulus_m3 * 1e9
    sigma_mpa = rail.moment_max() / z_mm3  # N.mm / mm^3 = N/mm^2 = MPa
    assert abs(sigma_mpa - result.seat_frame.rail_bending_stress_mpa) < 1e-6, (
        f"sigma mismatch: closed form {sigma_mpa:.6f} MPa "
        f"vs solver {result.seat_frame.rail_bending_stress_mpa:.6f} MPa"
    )

    x = rail.stations(divisions)
    v = [rail.shear(xi) for xi in x]
    m = [rail.moment(xi) for xi in x]

    v_span = max(abs(min(v)), abs(max(v)))
    v_pad = v_span * 0.2
    m_span = max(m) * 1.05

    v_block = _mermaid(
        "แผนภาพแรงเฉือน V (คานโครงเบาะ, ช่วง 480 mm)",
        x,
        v,
        "แรงเฉือน V (N)",
        -(v_span + v_pad),
        v_span + v_pad,
    )
    m_block = _mermaid(
        "แผนภาพโมเมนต์ดัด M (คานโครงเบาะ, ช่วง 480 mm)",
        x,
        m,
        "โมเมนต์ M (N·mm)",
        0.0,
        m_span,
    )
    fbd_block = _fbd_image_ref(rail)
    return v_block, m_block, fbd_block, rail


BLOCK_RE = re.compile(
    r"```mermaid\nxychart-beta\n\s*title \"แผนภาพแรงเฉือน.*?"
    r"```\s*```mermaid\nxychart-beta\n\s*title \"แผนภาพโมเมนต์ดัด.*?```",
    re.DOTALL,
)

FBD_RE = None  # removed: the FBD is a plotted image, not a Mermaid block


def inject(blocks: str, path: Path = REPORT_MD) -> bool:
    """Replace the existing Mermaid pair in the report. True if rewritten."""
    text = path.read_text(encoding="utf-8")
    if not BLOCK_RE.search(text):
        raise SystemExit(
            f"could not locate the existing Mermaid diagram pair in {path}; "
            "run without --inject and paste manually"
        )
    path.write_text(BLOCK_RE.sub(lambda _: blocks, text, count=1), encoding="utf-8")
    return True


def inject_fbd(block: str, path: Path = REPORT_MD) -> bool:
    """Insert or replace the FBD image reference. True if the file was written."""
    text = path.read_text(encoding="utf-8")
    if FBD_IMAGE_RE.search(text):
        new = FBD_IMAGE_RE.sub(lambda _: block, text, count=1)
    else:
        # Place it just before the shear-force chart.
        anchor = "```mermaid\nxychart-beta"
        if anchor not in text:
            raise SystemExit(
                f"no insertion point found in {path}; run without --inject and paste manually"
            )
        new = text.replace(anchor, f"{block}\n\n{anchor}", 1)
    path.write_text(new, encoding="utf-8")
    return True


def main(argv: Sequence[str] | None = None) -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inject", action="store_true", help=f"splice the blocks into {REPORT_MD}")
    ap.add_argument(
        "--divisions",
        type=int,
        default=8,
        help="number of span divisions (default 8 -> 60 mm steps)",
    )
    args = ap.parse_args(argv)

    v_block, m_block, fbd_block, rail = build_blocks(args.divisions)
    blocks = f"{v_block}\n\n{m_block}"

    if args.inject:
        from drafting.fbd_plot import plot_fbd

        outdir = REPORT_MD.parent / "diagrams"
        for f in ("png", "svg"):
            img = plot_fbd(rail, outdir=outdir, fmt=f)
            print(f"rendered {img}", file=sys.stderr)
        inject(blocks)
        inject_fbd(fbd_block)
        print(f"injected into {REPORT_MD}", file=sys.stderr)
    else:
        print(blocks)

    # Provenance summary on stderr so stdout stays a clean Mermaid fragment.
    print(
        f"span={rail.span_mm:g} mm  P={rail.p_n:g} N  "
        f"R1=R2={rail.r1_n:g} N  M_max={rail.moment_max():g} N.mm  "
        f"equilibrium OK (solver cross-check passed)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

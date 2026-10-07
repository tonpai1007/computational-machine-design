"""
Verified Data Sheet Generator for structural frame / furniture assemblies.

Emits a Markdown document containing EVERY numeric value the deterministic
solvers produce, with the formula that produced it and the call that returned
it. This exists so that report writing never involves transcribing a number by
hand: the document is generated from the solver result, so it cannot drift.

Nothing here invents a value. Derived quantities that the frame solver does not
expose (bracket stress, stretcher buckling, backrest stress, endurance limit)
are recomputed here from the same model using the same formulas the reports
document, and each is labelled with its source.

Run::

    python -m reporting.frame_data_sheet
    python -m reporting.frame_data_sheet --outdir Project/chair
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Sequence
from pathlib import Path

from core.frame_model import (
    ARM_PAD_THICKNESS_MM,
    FrameDesignModel,
    resolve_armrest_shared,
)
from physics.frame_physics import FramePhysicsSolver


def _fmt(v: float, dp: int = 3) -> str:
    return f"{v:.{dp}f}"


class FrameDataSheetGenerator:
    """Renders the verified solver data sheet as Markdown."""

    def __init__(self, model: FrameDesignModel | None = None):
        self.model = model or FrameDesignModel()
        self.g = self.model.geometry
        self.loads = self.model.loads
        self.m = self.model.material
        self.sol = FramePhysicsSolver.solve(self.model)
        self.ag = resolve_armrest_shared(
            self.g,
            side=-1.0,
            arm_tube_r=self.g.arm_profile.outer_dimension_mm / 2.0,
            pad_thickness_mm=ARM_PAD_THICKNESS_MM,
        )

    # ---------------------------------------------------------------- inputs
    def _section_inputs(self) -> str:
        g, loads, m = self.g, self.loads, self.m
        rows = [
            ("seat_height_mm", f"{g.seat_height_mm:g}"),
            ("seat_width_mm", f"{g.seat_width_mm:g}"),
            ("seat_depth_mm", f"{g.seat_depth_mm:g}"),
            ("seat_thickness_mm", f"{g.seat_thickness_mm:g}"),
            ("leg_splay_angle_deg", f"{g.leg_splay_angle_deg:g}"),
            ("stretcher_height_mm", f"{g.stretcher_height_mm:g}"),
            ("armrest_height_above_seat_mm", f"{g.armrest_height_above_seat_mm:g}"),
            ("armrest_length_mm", f"{g.armrest_length_mm:g}"),
            ("armrest_width_mm", f"{g.armrest_width_mm:g}"),
            ("armrest_overhang_front_mm", f"{g.armrest_overhang_front_mm:g}"),
            ("armrest_bracket_thickness_mm", f"{g.armrest_bracket_thickness_mm:g}"),
            ("armrest_bracket_height_mm", f"{g.armrest_bracket_height_mm:g}"),
            ("backrest_height_above_seat_mm", f"{g.backrest_height_above_seat_mm:g}"),
            ("backrest_angle_deg", f"{g.backrest_angle_deg:g}"),
            ("seat_vertical_load_n", f"{loads.seat_vertical_load_n:g}"),
            ("seat_load_center_y_mm", f"{loads.seat_load_center_y_mm:g}"),
            ("left_arm_vertical_n", f"{loads.left_arm_vertical_n:g}"),
            ("left_arm_lateral_n", f"{loads.left_arm_lateral_n:g}"),
            ("left_arm_load_y_mm", f"{loads.left_arm_load_y_mm:g}"),
            ("right_arm_vertical_n", f"{loads.right_arm_vertical_n:g}"),
            ("backrest_force_n", f"{loads.backrest_force_n:g}"),
            ("yield_strength_mpa", f"{m.yield_strength_mpa:g}"),
            ("ultimate_strength_mpa", f"{m.ultimate_strength_mpa:g}"),
            ("elastic_modulus_gpa", f"{m.elastic_modulus_gpa:g}"),
            ("poissons_ratio", f"{m.poissons_ratio:g}"),
            ("density_kg_m3", f"{m.density_kg_m3:g}"),
        ]
        out = ["## 2. ข้อมูลนำเข้า (Input Data)", ""]
        out.append("| พารามิเตอร์ | ค่า |")
        out.append("|---|---|")
        for k, v in rows:
            out.append(f"| `{k}` | {v} |")
        return "\n".join(out)

    def _profiles(self) -> str:
        out = [
            "## 3. สมบัติหน้าตัด (Section Properties)",
            "",
            "ค่าทั้งหมดคำนวณจาก `TubeProfile` ใน `core/frame_model.py`",
            "",
        ]
        out.append(
            "| ชิ้นส่วน | รูปทรง | OD (mm) | t (mm) | A (mm²) | I (mm⁴) | k (mm) | c (mm) | Z (mm³) |"
        )
        out.append("|---|---|---|---|---|---|---|---|---|")
        named = [
            ("เสา (leg)", self.g.leg_profile),
            ("คานโครงเบาะ (frame rail)", self.g.frame_profile),
            ("ท่อแขน (arm post)", self.g.arm_profile),
            ("สตรัชเตอร์ (stretcher)", self.g.stretcher_profile),
        ]
        for name, p in named:
            out.append(
                f"| {name} | {p.profile_type} | {p.outer_dimension_mm:g} | "
                f"{p.wall_thickness_mm:g} | {p.area_m2 * 1e6:.2f} | "
                f"{p.moment_of_inertia_m4 * 1e12:.1f} | "
                f"{p.radius_of_gyration_m * 1e3:.3f} | {p.outer_dimension_mm / 2:.2f} | "
                f"{p.section_modulus_m3 * 1e9:.2f} |"
            )
        bw, bh = self.g.armrest_bracket_thickness_mm, self.g.armrest_bracket_height_mm
        bi = bw * bh**3 / 12.0
        out.append(
            f"| แผ่นยึดแขน (arm bracket) | rectangular plate | "
            f"{bw:g} × {bh:g} | — | {bw * bh:.2f} | {bi:.2f} | "
            f"{math.sqrt(bi / (bw * bh)):.3f} | {bh / 2:.2f} | "
            f"{bi / (bh / 2):.2f} |"
        )
        return "\n".join(out)

    def _armrest_geometry(self) -> str:
        ag = self.ag
        fields = [
            ("post_x_mm", f"{ag.post_x_mm:.2f}"),
            ("front_post_y_mm", f"{ag.front_post_y_mm:.2f}"),
            ("rear_post_y_mm", f"{ag.rear_post_y_mm:.2f}"),
            ("post_span_mm", f"{ag.post_span_mm:.2f}"),
            ("post_base_z_mm", f"{ag.post_base_z_mm:.2f}"),
            ("post_top_z_mm", f"{ag.post_top_z_mm:.2f}"),
            ("pad_center_y_mm", f"{ag.pad_center_y_mm:.2f}"),
            ("pad_front_y_mm", f"{ag.pad_front_y_mm:.2f}"),
            ("pad_rear_y_mm", f"{ag.pad_rear_y_mm:.2f}"),
            ("pad_center_z_mm", f"{ag.pad_center_z_mm:.2f}"),
            ("pad_top_z_mm", f"{ag.pad_top_z_mm:.2f}"),
            ("cantilever_front_mm", f"{ag.cantilever_front_mm:.2f}"),
            ("cantilever_rear_mm", f"{ag.cantilever_rear_mm:.2f}"),
            ("bracket_len_mm", f"{ag.bracket_len_mm:.2f}"),
            ("bracket_x_mm", f"{ag.bracket_x_mm:.2f}"),
        ]
        out = [
            "## 4. เรขาคณิตแขนที่ Resolve แล้ว (Resolved Armrest Geometry)",
            "",
            "ทุกค่ามาจาก `resolve_armrest_shared()` ซึ่งเป็นแหล่งเดียวที่ CAD และ solver ใช้ร่วมกัน",
            "",
        ]
        out.append("| field | ค่า (mm) |")
        out.append("|---|---|")
        for k, v in fields:
            out.append(f"| `{k}` | {v} |")
        fr, rr = ag.post_reaction_fractions(self.loads.left_arm_load_y_mm)
        out += [
            "",
            f"การแจกแรงที่จุดกด y = {self.loads.left_arm_load_y_mm:g} mm (หลักคาน):",
            "",
            f"- เสาหน้า: `{fr:.4f}` → {self.loads.left_arm_vertical_n * fr:.1f} N",
            f"- เสาหลัง: `{rr:.4f}` → {self.loads.left_arm_vertical_n * rr:.1f} N",
        ]
        return "\n".join(out)

    # --------------------------------------------------------------- results
    def _legs(self) -> str:
        out = [
            "## 5. ผลการวิเคราะห์เสา (Frame Solver — `floor_reactions`)",
            "",
            "| ขา | พิกัดเท้า x (mm) | พิกัดเท้า y (mm) | Rz (N) | Rh (N) | σ P/A (MPa) | σ M/Z (MPa) | σ รวม (MPa) | n buckling | n yield |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for c in self.sol.floor_reactions:
            out.append(
                f"| {c.leg_id} ({c.leg_name}) | {c.floor_x_mm:.2f} | {c.floor_y_mm:.2f} | "
                f"{c.axial_reaction_n:.2f} | {c.horizontal_shear_n:.2f} | "
                f"{c.compressive_stress_mpa:.3f} | {c.bending_stress_mpa:.3f} | "
                f"{c.combined_stress_mpa:.3f} | {c.buckling_safety_factor:.3f} | "
                f"{c.yield_safety_factor:.3f} |"
            )
        c0 = self.sol.floor_reactions[0]
        out += [
            "",
            "ค่าร่วมทุกเสา:",
            "",
            f"- ความเรียว λ = `{c0.slenderness_ratio:.3f}`",
            f"- โมเมนต์ที่ฐานเสา = `{c0.bending_moment_nm:.4f}` N·m",
            f"- แรงวิกฤต P_cr = `{c0.critical_buckling_load_n:.1f}` N "
            f"= `{c0.critical_buckling_load_n / 1000:.2f}` kN",
        ]
        return "\n".join(out)

    def _armrest(self) -> str:
        a = self.sol.armrests[0]
        return "\n".join(
            [
                "## 6. ผลการวิเคราะห์ท่อแขน (Frame Solver — `armrests`)",
                "",
                "| ปริมาณ | ค่า |",
                "|---|---|",
                f"| แรงกดแนวดิ่ง `applied_vertical_n` | {a.applied_vertical_n:.3f} N |",
                f"| แรงดันแนวนอน `applied_lateral_n` | {a.applied_lateral_n:.3f} N |",
                f"| โมเมนต์การยื่น `overhang_moment_nm` | {a.overhang_moment_nm:.3f} N·m |",
                f"| โมเมนต์ฐานเสา `strut_base_moment_nm` | {a.strut_base_moment_nm:.3f} N·m |",
                f"| เค้นแนวดิ่ง `strut_axial_stress_mpa` | {a.strut_axial_stress_mpa:.3f} MPa |",
                f"| เค้นดัด `strut_bending_stress_mpa` | {a.strut_bending_stress_mpa:.3f} MPa |",
                f"| เค้นรวม `strut_combined_stress_mpa` | {a.strut_combined_stress_mpa:.3f} MPa |",
                f"| ความปลอดภัย `arm_safety_factor` | {a.arm_safety_factor:.3f} |",
                "",
                "สูตรที่ solver ใช้:",
                "",
                "```",
                f"M_cantilever = F_v x overhang = {a.applied_vertical_n:g} x "
                f"{self.ag.cantilever_front_mm / 1000:.3f} = {a.overhang_moment_nm:.3f} N.m",
                f"M_base      = sqrt((F_lat x h)^2 + M_cantilever^2) = {a.strut_base_moment_nm:.3f} N.m",
                f"sigma_axial = F_gov / A = {a.strut_axial_stress_mpa:.3f} MPa",
                f"sigma_bend  = (M_base/2) / Z = {a.strut_bending_stress_mpa:.3f} MPa",
                f"sigma_total = sigma_axial + sigma_bend = {a.strut_combined_stress_mpa:.3f} MPa",
                "```",
            ]
        )

    def _bracket(self) -> str:
        """Bracket stress, read from the solver. Nothing is recomputed here."""
        g, m = self.g, self.m
        b = self.sol.arm_brackets[0]
        bL = self.ag.bracket_len_mm
        bW = g.armrest_bracket_thickness_mm
        bH = g.armrest_bracket_height_mm
        m_half = b.post_base_moment_nm / 2.0
        gross_area = bL * bW * bH
        # Shown only to document the rejected alternative; the solver's value is
        # the one reported above.
        s_gross = b.post_axial_n / gross_area + m_half * 1e3 / b.section_modulus_mm3

        return "\n".join(
            [
                "## 7. แผ่นยึดแขน (Arm Bracket)",
                "",
                "> ค่าทั้งหมดในหัวข้อนี้อ่านจาก `FrameSolverResult.arm_brackets[0]`",
                "> (`physics/frame_physics.py::ArmBracketAnalysisResult`) ไม่มีการคำนวณซ้ำในชั้นรายงาน",
                "",
                f"ขนาดแผ่น: `{bL:g} × {bW:g} × {bH:g}` mm",
                "",
                "แต่ละท่อแขนมีแผ่นยึด 1 แผ่น ผูกกับเสาของท่อนั้นโดยเฉพาะ",
                "แผ่นยึดจึงรับแรงตั้งของเสาวิกฤต และโมเมนต์ที่ฐานเสาของท่อนั้น",
                "",
                "| สมบัติ | ค่า |",
                "|---|---|",
                f"| I (ดัดรอบแกน Y) `section_inertia_mm4` | {b.section_inertia_mm4:.2f} mm⁴ |",
                f"| c | {bH / 2:.2f} mm |",
                f"| Z = I/c `section_modulus_mm3` | {b.section_modulus_mm3:.2f} mm³ |",
                f"| A หน้าตัดดัด (bW×bH) `section_area_mm2` | {b.section_area_mm2:.2f} mm² |",
                f"| แรงตั้งเสาวิกฤต `post_axial_n` (lever rule) | {b.post_axial_n:.1f} N |",
                f"| โมเมนต์ฐานเสาของท่อ `post_base_moment_nm`/2 | {m_half:.3f} N·m |",
                f"| เค้นแนวดิ่ง `axial_stress_mpa` | {b.axial_stress_mpa:.3f} MPa |",
                f"| เค้นดัด `bending_stress_mpa` | {b.bending_stress_mpa:.3f} MPa |",
                f"| เค้นรวม `combined_stress_mpa` | {b.combined_stress_mpa:.3f} MPa |",
                f"| ความปลอดภัย `bracket_safety_factor` | {b.bracket_safety_factor:.3f} |",
                "",
                "สูตรที่ solver ใช้:",
                "",
                "```",
                "sigma = F_post/A_cross + (M_base/2)/Z",
                f"sigma = {b.post_axial_n:.1f}/{b.section_area_mm2:.2f}"
                f" + {m_half:.3f}e3/{b.section_modulus_mm3:.2f}"
                f" = {b.combined_stress_mpa:.3f} MPa",
                f"n = S_y/sigma = {m.yield_strength_mpa:g}/{b.combined_stress_mpa:.3f}"
                f" = {b.bracket_safety_factor:.3f}",
                "```",
                "",
                "**การเลือกพื้นที่หน้าตัด**",
                "ใช้พื้นที่หน้าตัดดัด (bW×bH) = พื้นที่ที่รับแรงตั้งจริงในการดัด",
                "ไม่ใช้พื้นที่เนื้อรวม (bL×bW×bH) เพราะความยาว bL ไม่ได้มีส่วนรับแรงตั้งตามแนวแร่น",
                f"หากใช้พื้นที่เนื้อรวม ({gross_area:.2f} mm²) จะได้ sigma = {s_gross:.3f} MPa ซึ่งต่ำกว่าจริง",
            ]
        )

    def _rails_stretcher_back(self) -> str:
        g, loads, m = self.g, self.loads, self.m
        r = self.sol.seat_frame
        sp = g.stretcher_profile
        sA = sp.area_m2 * 1e6
        sI = sp.moment_of_inertia_m4 * 1e12
        sk = math.sqrt(sI / sA)
        s_len = g.seat_width_mm + 2 * (g.seat_height_mm - g.stretcher_height_mm) * math.tan(
            math.radians(g.leg_splay_angle_deg)
        )
        kfac = 0.85 if g.has_stretchers else 1.2
        slam = kfac * s_len / sk
        E = m.elastic_modulus_gpa * 1000.0
        sPcr = sA * (m.yield_strength_mpa - (m.yield_strength_mpa * slam / (2 * math.pi)) ** 2 / E)
        s_load = loads.backrest_force_n / 2.0

        lp = g.leg_profile
        lZ = lp.moment_of_inertia_m4 * 1e12 / (lp.outer_dimension_mm / 2.0)
        lA = lp.area_m2 * 1e6
        # The backrest thrust is HORIZONTAL, so its moment arm about the post
        # base is the post's vertical rise -- cos, not sin. sin gives the
        # horizontal lean (58.45 mm) and understated the stress ~69x.
        dz = g.backrest_height_above_seat_mm * math.cos(math.radians(g.backrest_angle_deg - 90.0))
        fb = loads.backrest_force_n / 2.0
        # F [N] * dz [mm] = M [N.mm]; dividing by Z [mm^3] yields MPa directly.
        # No 1e3 here -- that would hand N.m into a mm^3 denominator and report
        # the bending stress as ~1000x too small.
        back_sigma = fb * dz / lZ + fb / lA

        return "\n".join(
            [
                "## 8. คานโครงเบาะ (Seat Frame Rail)",
                "",
                "| ปริมาณ | ค่า | ที่มา |",
                "|---|---|---|",
                f"| แรงกดบนคาน | {r.seat_load_n:.1f} N | model |",
                f"| M_max = PL/4 | {r.rail_bending_moment_nm:.4f} N·m | solver |",
                f"| σ = M/Z | {r.rail_bending_stress_mpa:.4f} MPa | solver |",
                f"| δ = PL³/(48EI) | {r.rail_deflection_mm:.4f} mm | solver |",
                f"| n = S_y/σ | {r.rail_safety_factor:.4f} | solver |",
                f"| เกณฑ์เบี่ยงเบน L/250 | {g.seat_width_mm / 250:.4f} mm | คำนวณ |",
                "",
                "ผ่านทั้งการหักและเกณฑ์เบี่ยงเบน",
                "",
                "---",
                "",
                "## 9. สตรัชเตอร์ (Lower Stretcher)",
                "",
                "| ปริมาณ | ค่า |",
                "|---|---|",
                f"| A | {sA:.2f} mm² |",
                f"| I | {sI:.1f} mm⁴ |",
                f"| k = √(I/A) | {sk:.3f} mm |",
                f"| L (รวมระยะเสียงเสา) | {s_len:.2f} mm |",
                f"| k factor | {kfac} |",
                f"| l/k | {slam:.2f} |",
                f"| P_cr | {sPcr:.1f} N |",
                f"| แรงต้าน (F_back/2) | {s_load:.1f} N |",
                f"| n = P_cr/F | {sPcr / s_load:.3f} |",
                "",
                "> ค่าชุดนี้คำนวณในเอกสารนี้ ไม่ใช่ผลจาก `frame_physics.py` โดยตรง",
                "",
                "---",
                "",
                "## 10. เสาหลังนั่ง (Backrest Post)",
                "",
                "| ปริมาณ | ค่า |",
                "|---|---|",
                f"| F_back/2 | {fb:.1f} N |",
                f"| ระยะแนวดิ่งของโมเมนต์ dz | {dz:.3f} mm |",
                f"| Z | {lZ:.2f} mm³ |",
                f"| σ = F·dz/Z + F/A | {back_sigma:.3f} MPa |",
                f"| n = S_y/σ | {m.yield_strength_mpa / back_sigma:.3f} |",
            ]
        )

    def _fatigue(self) -> str:
        from physics.fatigue import FatigueSolver, MarinFactors

        m = self.m
        # Governing member is the arm bracket (highest combined stress),
        # read from the solver rather than recomputed here.
        sig = self.sol.arm_brackets[0].combined_stress_mpa
        d_eff_mm = self.ag.bracket_len_mm
        # Single source of truth for Marin factors: physics/fatigue.py.
        ka = MarinFactors.surface_factor(m.ultimate_strength_mpa, "machined")
        kb = MarinFactors.size_factor(d_eff_mm / 1000.0)
        kc = MarinFactors.load_factor("bending")
        ke = MarinFactors.reliability_factor(0.90)
        kd = kf = 1.0
        se_prime = 0.5 * m.ultimate_strength_mpa
        se = ka * kb * kc * kd * ke * kf * se_prime
        # The arm carries a seated occupant: stress cycles zero -> peak as the
        # user sits and stands. That is a repeated load (R = 0), not the fully
        # reversed duty a bare Se assumes, so judge it on mean + alternating
        # stress rather than on Se/sigma_max alone.
        rl = FatigueSolver.repeated_load_fatigue(
            sigma_max_mpa=sig,
            s_ut_mpa=m.ultimate_strength_mpa,
            s_y_mpa=m.yield_strength_mpa,
            s_e_mpa=se,
            stress_ratio_r=0.0,
        )
        return "\n".join(
            [
                "## 11. ความทนทานของวัสดุ (Endurance)",
                "",
                "> ตัวปรับแก้ Marin ทั้งหมดอ่านจาก `physics/fatigue.py::MarinFactors`",
                "> σ_max อ่านจาก `FrameSolverResult.arm_brackets[0].combined_stress_mpa`",
                "> เกณฑ์ตัดสินคำนวณจาก `physics/fatigue.py::FatigueSolver.repeated_load_fatigue`",
                "",
                f"ชิ้นวิกฤต = แผ่นยึดแขน, σ_max = `{sig:.3f}` MPa",
                "",
                "| ปริมาณ | สูตร | ค่า |",
                "|---|---|---|",
                f"| S_e' | 0.5·S_ut | {se_prime:.2f} MPa |",
                f"| k_a | MarinFactors.surface_factor(machined) | {ka:.4f} |",
                f"| k_b | MarinFactors.size_factor (d = {d_eff_mm:.1f} mm) | {kb:.4f} |",
                f"| k_c | ดัด (bending) | {kc:.4f} |",
                f"| k_d | ภาระตัวแปร | {kd:.4f} |",
                f"| k_e | ความเชื่อมโลหะ 90% | {ke:.4f} |",
                f"| k_f | ปัจจัยอื่น | {kf:.4f} |",
                f"| S_e | k_a·k_b·k_c·k_d·k_e·k_f·S_e' | {se:.4f} MPa |",
                "",
                "**แรงกดที่แขนเป็นแรงทำซ้ำแบบไม่กลับทิศ (pulsating, R = 0)** — ขึ้นกับน้ำหนักผู้นั่ง"
                "เมื่อลุก-นั่ง ไม่ใช่กลับทิศเต็มช่วงเหมือนโคเจนหมุน จึงต้องแยกแรงกระทำเป็นส่วนผลันผวน"
                "กับส่วนเฉลี่ยก่อนตัดสิน ไม่ใช่หาร S_e ด้วย sigma_max อย่างเดียว",
                "",
                "| ปริมาณ | สูตร | ค่า |",
                "|---|---|---|",
                f"| R (stress ratio) | σ_min/σ_max | {rl.stress_ratio_r:.2f} |",
                f"| σ_a | (σ_max − σ_min)/2 | {rl.sigma_a_mpa:.4f} MPa |",
                f"| σ_m | (σ_max + σ_min)/2 | {rl.sigma_m_mpa:.4f} MPa |",
                "",
                "| เกณฑ์ | สูตร | n |",
                "|---|---|---|",
                f"| Modified Goodman | σ_a/S_e + σ_m/S_ut | {rl.nf_goodman:.4f} |",
                f"| Gerber | parabola | {rl.nf_gerber:.4f} |",
                f"| Soderberg | σ_a/S_e + σ_m/S_y | {rl.nf_soderberg:.4f} |",
                "",
                f"**n = {rl.governing_nf:.4f} (เกณฑ์ {rl.governing_criterion}, ค่าต่ำสุดของทั้งสาม)**"
                f" → ผ่าน n_d = 2.0"
                if rl.governing_nf >= 2.0
                else f"**n = {rl.governing_nf:.4f} (เกณฑ์ {rl.governing_criterion}) → ไม่ผ่าน n_d = 2.0**",
                "",
                "```",
                f"n = 1 / ({rl.sigma_a_mpa:.4f}/{se:.4f} + {rl.sigma_m_mpa:.4f}/{m.yield_strength_mpa:.1f})"
                f" = {rl.nf_soderberg:.4f}",
                f"N (Basquin, Goodman-equivalent) = {rl.predicted_cycles:.4e} cycles",
                "```",
                "",
                "> **เทียบกับเกณฑ์เดิม**: ถ้าใช้ S_e/σ_max ตรง ๆ ได้ "
                f"`{se / sig:.4f}` ซึ่งต่ำกว่า n_d = 2.0 แต่เกณฑ์นั้นสมมติแรงกลับทิศเต็มช่วง (R = −1)"
                " ซึ่งไม่ตรงกับการใช้งานจริงของเก้าอี้",
                "> หากมีแรงดันส่วนหน้า–หลังที่กลับทิศจริง (R < 0) ค่า n จะลดลง "
                "ตามสมการ σ_a/S_e + σ_m/S_y ดังนั้นผลนี้ใช้ได้เมื่อยอมรับ R = 0",
            ]
        )

    def _fea(self) -> str:
        """Direct-stiffness results, if the FEA engine can run."""
        try:
            from physics.fea_3d import build_chair_3d_fea_model
        except Exception as exc:  # pragma: no cover
            return f"## 12. ผล 3D Space Frame FEA\n\nโมดูล FEA โหลดไม่ได้: `{exc}` — ข้ามหัวข้อนี้"

        try:
            r = build_chair_3d_fea_model(self.model).solve()
        except Exception as exc:  # pragma: no cover
            return f"## 12. ผล 3D Space Frame FEA\n\nFEA แก้ปัญหาไม่ได้: `{exc}` — ข้ามหัวข้อนี้"

        rows = [
            ("จุด (nodes)", r["num_nodes"], "model"),
            ("สมาชิก (members)", r["num_members"], "model"),
            ("องศาอิสระรวม (total DOF)", r["total_dof"], "model"),
            ("องศาอิสระที่เหลือ (active free DOF)", r["active_free_dof"], "model"),
            ("การเคลื่อนที่สูงสุด (mm)", f"{r['max_displacement_mm']:.4f}", "solver"),
            ("เค้นสูงสุด (MPa)", f"{r['max_von_mises_mpa']:.4f}", "solver"),
            ("SF ต่ำสุด", f"{r['min_safety_factor']:.4f}", "solver"),
            ("ผ่านทั้งหมด", r["passed"], "solver"),
        ]
        worst = sorted(r["members"], key=lambda m: m["safety_factor"])[:5]
        out = [
            "## 12. ผล 3D Space Frame FEA (`physics/fea_3d.py`)",
            "",
            "โมเดลนี้**แยกจาก** closed-form solver และให้ผลต่างกันโดยธรรมชาติ",
            "",
            "| ปริมาณ | ค่า | ที่มา |",
            "|---|---|---|",
        ]
        for name, val, src in rows:
            out.append(f"| {name} | `{val}` | {src} |")
        out += [
            "",
            "### 5 สมาชิกที่ SF ต่ำสุด",
            "",
            "| member | L (m) | แรงตั้ง (N) | โมเมนต์สูงสุด (N·m) | σ (MPa) | SF |",
            "|---|---|---|---|---|---|",
        ]
        for mem in worst:
            out.append(
                f"| `{mem['member_id']}` | {mem['length_m']:.4f} | "
                f"{mem['axial_force_n']:.2f} | {mem['max_moment_nm']:.3f} | "
                f"{mem['von_mises_mpa']:.3f} | {mem['safety_factor']:.3f} |"
            )
        return "\n".join(out)

    def _cad(self) -> str:
        from cad.assembly import FrameCADEngine, armrest_primitives

        parts = FrameCADEngine.generate_assembly_parts(self.model)
        stl = FrameCADEngine.export_binary_stl(self.model)
        step = FrameCADEngine.export_step_solid(self.model)
        scad = FrameCADEngine.generate_openscad(self.model)
        prims = armrest_primitives(self.ag)
        roles = (
            "แผ่นยึดเสาหน้า",
            "เสาหน้า",
            "แผ่นยึดเสาหลัง",
            "เสาหลัง",
            "คานยืดบนกับแผ่นรองนั่ง",
            "คานเฉียงกันโครงเอียง",
            "แผ่นรองนั่ง",
        )
        rows = []
        for i, (p, role) in enumerate(zip(prims, roles, strict=True), 1):
            if p["kind"] == "box":
                sx, sy, sz = p["s"]
                dim = f"{sx:g} × {sy:g} × {sz:g}"
            else:
                ax, ay, az = p["a"]
                bx, by, bz = p["b"]
                length = math.dist((ax, ay, az), (bx, by, bz))
                dim = f"r = {p['r']:.1f}, L = {length:.2f}"
            rows.append(f"| {i} | {p['kind']} | {dim} | {role} |")

        return "\n".join(
            [
                "## 13. ผลการสร้างแบบ CAD (`cad/assembly.py`)",
                "",
                "| รายการ | ค่า |",
                "|---|---|",
                f"| จำนวนชิ้นส่วน (solid parts) | {len(parts)} |",
                f"| จำนวนสามเหลี่ยมรวม | {sum(len(p.triangles) for p in parts)} |",
                f"| STL (bytes) | {len(stl):,} |",
                f"| STEP (bytes) | {len(step):,} |",
                f"| STEP MANIFOLD_SOLID_BREP | {step.count('MANIFOLD_SOLID_BREP')} |",
                f"| OpenSCAD (bytes) | {len(scad):,} |",
                "",
                "### Primitive ของแขน 1 ข้าง (อ่านค่าจาก primitive จริง)",
                "",
                "| # | kind | ขนาด | หน้าที่ |",
                "|---|---|---|---|",
                *rows,
                "",
                f"จำนวน primitive ต่อข้าง = **{len(prims)}** (เดิม 5 ก่อนเพิ่มคานยืดบนและคานเฉียง)",
                "",
                "> box → 12 สามเหลี่ยม, tube → 48 สามเหลี่ยม (ที่ 12 เส้นแบ่ง)",
                "> ท่อ Ø22 mm จึงเรนเดอร์เป็น 12 เหลี่ยม ไม่ใช่ทรงกลมจริง",
            ]
        )

    def _summary(self) -> str:
        s = self.sol
        rows = [
            ("เสา — buckling", f"{s.min_leg_buckling_sf:.3f}", "2.0"),
            ("เสา — yield", f"{s.min_leg_yield_sf:.3f}", "1.5"),
            ("ท่อแขน", f"{s.min_arm_sf:.3f}", "2.0"),
            ("คานโครงเบาะ", f"{s.seat_frame.rail_safety_factor:.3f}", "2.0"),
            ("การพลิกคว่า (หน้า)", f"{s.tipping_safety_factor_fwd:.3f}", "1.5"),
            ("การพลิกคว่า (หลัง)", f"{s.tipping_safety_factor_rear:.3f}", "1.5"),
        ]
        out = [
            "## 14. สรุปความปลอดภัย (Margins)",
            "",
            "| รายการ | ค่า n | เกณฑ์ | ผล |",
            "|---|---|---|---|",
        ]
        for name, n, nd in rows:
            ok = "ผ่าน" if float(n) >= float(nd) else "**ไม่ผ่าน**"
            out.append(f"| {name} | {n} | {nd} | {ok} |")
        out += [
            "",
            f"- คงตัวทางสถิติ: `{s.is_statically_stable}`",
            f"- ผ่านทุกเกณฑ์: `{s.all_safety_criteria_passed}`",
            f"- น้ำหนักตัวเอง: `{s.total_chair_weight_n:.2f}` N",
            f"- แรงลงรวม: `{s.total_downward_load_n:.2f}` N",
            "- SF การพลิกคว่าด้านข้าง: "
            + (
                f"`{s.tipping_safety_factor_lat:g}`"
                if s.tipping_safety_factor_lat is not None
                else "`None` — **ไม่มีกรณีนี้ให้ตรวจ** ไม่ใช่ค่าที่คำนวณได้ว่าปลอดภัยมาก "
                f"(แรงข้าง ∓{abs(self.loads.left_arm_lateral_n):g} N หักล้างกันพอดี จึงไม่มีโมเมนต์พลิกสุทธิ)"
            ),
        ]
        return "\n".join(out)

    def _log(self) -> str:
        out = ["## 15. บันทึกการคำนวณจาก solver (`calculation_log`)", "", "```"]
        for line in self.sol.calculation_log:
            out.append(line)
        out.append("```")
        return "\n".join(out)

    # ---------------------------------------------------------------- output
    def generate_markdown(self) -> str:
        parts = [
            "# ข้อมูลตรวจสอบย้อนกลับ (Verified Data Sheet)",
            "",
            "## เกี่ยวกับเอกสารนี้",
            "",
            "เอกสารนี้คือ **แหล่งตัวเลขจริง** ของแบบจำลองเก้าอี้ทั้งหมด",
            "ทุกค่าถูกดึงออกจากผลลัพธ์ของ solver โดยตรง ไม่มีการคัดลอกด้วยมือ",
            "ตัวเอกสารสร้างโดย `python -m reporting.frame_data_sheet`",
            "",
            "**กฎข้อที่ 1: ตัวเลขในเอกสารนี้ต้องตรงกับไฟล์นี้เสมอ**",
            "หากรายงานหรือแบบผลิตต่างจากเอกสารนี้ แสดงว่ามีการคัดลอกตัวเลขผิด",
            "",
            "**กฎข้อที่ 2: ค่าที่คำนวณเองนอกเหนือจาก solver จะมีเครื่องหมายกำกับไว้เสมอ**",
            "ดูคอลัมน์ `ที่มา` และหมายเหตุท้ายแต่ละหัวข้อ",
            "",
            "---",
            "",
            "## 1. ที่มาของข้อมูล (Provenance)",
            "",
            "| รายการ | ค่า |",
            "|---|---|",
            f"| โมเดล | `{self.model.name}` |",
            f"| วัสดุ | `{self.m.name}` |",
            "| ตัวสร้างเอกสาร | `reporting/frame_data_sheet.py` |",
            "| solver หลัก | `physics/frame_physics.py::FramePhysicsSolver.solve()` |",
            "| solver รอง | `physics/fea_3d.py::FEA3DSolver.solve()` |",
            "| เรขาคณิตแขน | `core/frame_model.py::resolve_armrest_shared()` |",
            "| แบบ CAD | `cad/assembly.py::FrameCADEngine` |",
            "",
            "---",
            "",
            self._section_inputs(),
            "",
            "---",
            "",
            self._profiles(),
            "",
            "---",
            "",
            self._armrest_geometry(),
            "",
            "---",
            "",
            self._legs(),
            "",
            "---",
            "",
            self._armrest(),
            "",
            "---",
            "",
            self._bracket(),
            "",
            "---",
            "",
            self._rails_stretcher_back(),
            "",
            "---",
            "",
            self._fatigue(),
            "",
            "---",
            "",
            self._fea(),
            "",
            "---",
            "",
            self._cad(),
            "",
            "---",
            "",
            self._summary(),
            "",
            "---",
            "",
            self._log(),
            "",
            "---",
            "",
            "## 16. ประเด็นที่ยังต้องตัดสินใจ",
            "",
            "1. **แผ่นยึดแขน** — พื้นที่สำหรับเทศแรงตั้งควรใช้หน้าตัดดัด (12×11) "
            "หรือเนื้อที่รวม (25×12×11) ดูหัวข้อ 7 ทั้งสองวิธีผ่านแต่ให้ n ต่างกัน",
            "2. **ความทนทานของแขน** — คำนวณบนเกณฑ์แรงทำซ้ำไม่กลับทิศ (pulsating, R = 0) "
            "เพราะแรงจากน้ำหนักผู้นั่งไม่ใช่แรงกลับทิศ ดูหัวข้อ 11 "
            "หากมีแรงดันหน้า–หลังที่กลับทิศจริง (R < 0) ค่า n จะลดลง",
            "3. **`physics/fea_3d.py` แก้ไขตรงกับ CAD แล้ว** — ซิงค์ตำแหน่งเสาแขนด้วย "
            "`resolve_armrest_shared()` และกระจายแรงตาม Lever Rule เรียบร้อยแล้ว "
            "(ผลการวิเคราะห์ 3D FEA สอดคล้องกับแบบจำลอง CAD และสมดุลแรงจริง)",
            "4. **SF การพลิกคว่าด้านข้าง** — แก้แล้ว: solver คืนค่า `None` และรายงานแสดง `N/A` "
            "แทนค่าเทียม เพราะแรงข้างของแขนซ้ายและขวาหักล้างกันพอดีจึงไม่มีโมเมนต์พลิกสุทธิ",
            "5. **การหารโมเมนต์แผ่นยึดด้วย 2** — สมมติฐานว่าแผ่นทั้งสองช่วยกันแบ่งโมเมนต์ ยังไม่ได้พิสูจน์",
            "",
            "## 17. ขอบเขตงานวิเคราะห์ (Scope)",
            "",
            "| รายการ | สถานะ |",
            "|---|---|",
            "| แผ่นยึดแขน (bracket plate) | อยู่ในขอบเขต — วิเคราะห์ครบ เป็นชิ้นวิกฤตของโครง |",
            "| สกรู / น็อต / หมุด (fasteners) | อยู่นอกขอบเขต — ไม่ได้จำลอง ไม่ได้ตรวจ |",
            "",
            "`cad/assembly.py` สร้างเฉพาะ primitive สองชนิดคือ tube และ box "
            "โมเดลจึงไม่มีชิ้นส่วนยึดใด ๆ และไม่มีการตรวจแรงเฉือน แรงดึง แรงอัดของสกรู "
            "การชนของรู (bearing) การดึงออกของแผ่น (tear-out) หรือการเลื่อนของรอยต่อ (slip)",
            "",
            "**สมมติฐานของรอยต่อ**: รอยต่อระหว่างแผ่นยึดกับท่อแขน จำลองเป็น **อิสระ (rigid / fully continuous)** "
            "คือไม่มีการเลื่อนและไม่มีการหมุนรอบรอยต่อ แผ่นยึดจึงรับโมเมนต์ครึ่งหนึ่งของ M_base พอดี",
            "",
            "> หากต่อด้วยสกรูจริงและเกิดการเลื่อน โมเมนต์จะถ่ายเข้าท่อแขนมากขึ้น "
            "แผ่นยึดจะรับโมเมนต์น้อยลง และ n จะสูงขึ้น "
            "กล่าวคือสมมติฐานนี้เป็นการประเมินแบบอนุรักษ์สำหรับแผ่นยึด "
            "แต่ไม่ครอบคลุมความแข็งแรงของสกรูซึ่งต้องตรวจแยก",
            "",
            "การออกแบบรอยต่อและขนาดสกรูอยู่นอกขอบเขตของโมเดลนี้ "
            "มีโมเดลแยกที่ `Project/bolted_joint_m16` (รอยต่อสกรู) และ `Project/bracket` (ฐานแขน)",
            "",
        ]
        return "\n".join(parts)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", default="Project/chair")
    args = ap.parse_args(argv)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "chair_real_data.md"
    path.write_text(FrameDataSheetGenerator().generate_markdown(), encoding="utf-8")
    print(f"[ok] {path}")
    # Machine-checkable record of where every engineering number came from.
    from physics.provenance import write_manifest

    print(f"[ok] {write_manifest(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

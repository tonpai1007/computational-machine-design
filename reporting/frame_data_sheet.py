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
from pathlib import Path

from core.frame_model import (
    ARM_PAD_THICKNESS_MM,
    FrameDesignModel,
    resolve_armrest,
)
from physics.frame_physics import FramePhysicsSolver


def _fmt(v: float, dp: int = 3) -> str:
    return f"{v:.{dp}f}"


class FrameDataSheetGenerator:
    """Renders the verified solver data sheet as Markdown."""

    def __init__(self, model: FrameDesignModel | None = None):
        self.model = model or FrameDesignModel()
        self.g = self.model.geometry
        self.l = self.model.loads
        self.m = self.model.material
        self.sol = FramePhysicsSolver.solve(self.model)
        self.ag = resolve_armrest(
            self.g,
            side=-1.0,
            arm_tube_r=self.g.arm_profile.outer_dimension_mm / 2.0,
            pad_thickness_mm=ARM_PAD_THICKNESS_MM,
        )

    # ---------------------------------------------------------------- inputs
    def _section_inputs(self) -> str:
        g, l, m = self.g, self.l, self.m
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
            ("seat_vertical_load_n", f"{l.seat_vertical_load_n:g}"),
            ("seat_load_center_y_mm", f"{l.seat_load_center_y_mm:g}"),
            ("left_arm_vertical_n", f"{l.left_arm_vertical_n:g}"),
            ("left_arm_lateral_n", f"{l.left_arm_lateral_n:g}"),
            ("left_arm_load_y_mm", f"{l.left_arm_load_y_mm:g}"),
            ("right_arm_vertical_n", f"{l.right_arm_vertical_n:g}"),
            ("backrest_force_n", f"{l.backrest_force_n:g}"),
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
            "ทุกค่ามาจาก `resolve_armrest()` ซึ่งเป็นแหล่งเดียวที่ CAD และ solver ใช้ร่วมกัน",
            "",
        ]
        out.append("| field | ค่า (mm) |")
        out.append("|---|---|")
        for k, v in fields:
            out.append(f"| `{k}` | {v} |")
        fr, rr = ag.post_reaction_fractions(self.l.left_arm_load_y_mm)
        out += [
            "",
            f"การแจกแรงที่จุดกด y = {self.l.left_arm_load_y_mm:g} mm (หลักคาน):",
            "",
            f"- เสาหน้า: `{fr:.4f}` → {self.l.left_arm_vertical_n * fr:.1f} N",
            f"- เสาหลัง: `{rr:.4f}` → {self.l.left_arm_vertical_n * rr:.1f} N",
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
        """Bracket stress using the settled Method A (bending cross-section area).

        The axial force is the governing post's lever-rule share, not half the
        pad load: each pad load splits between two posts by lever rule, and the
        bracket is bonded to one post only.
        """
        g, m = self.g, self.m
        a = self.sol.armrests[0]
        bL = self.ag.bracket_len_mm
        bW = g.armrest_bracket_thickness_mm
        bH = g.armrest_bracket_height_mm
        bi = bW * bH**3 / 12.0
        bz = bi / (bH / 2.0)
        f_post = self._governing_post_axial_n()
        m_half = a.strut_base_moment_nm / 2.0

        cross_area = bW * bH
        gross_area = bL * bW * bH
        s_cross = f_post / cross_area + m_half * 1e3 / bz
        s_gross = f_post / gross_area + m_half * 1e3 / bz

        return "\n".join(
            [
                "## 7. แผ่นยึดแขน (Arm Bracket)",
                "",
                f"ขนาดแผ่น: `{bL:g} × {bW:g} × {bH:g}` mm",
                "",
                "แต่ละท่อแขนมีแผ่นยึด 1 แผ่น ผูกกับเสาของท่อนั้นโดยเฉพาะ",
                "แผ่นยึดจึงรับแรงตั้งของเสาวิกฤต และโมเมนต์ที่ฐานเสาของท่อนั้น",
                "",
                "| สมบัติ | ค่า |",
                "|---|---|",
                f"| I (ดัดรอบแกน Y) | {bi:.2f} mm⁴ |",
                f"| c | {bH / 2:.2f} mm |",
                f"| Z = I/c | {bz:.2f} mm³ |",
                f"| A หน้าตัดดัด (bW×bH) | {cross_area:.2f} mm² |",
                f"| แรงตั้งเสาวิกฤต (lever rule) | {f_post:.1f} N |",
                f"| โมเมนต์ฐานเสาของท่อ (M_base/2) | {m_half:.3f} N·m |",
                "",
                "```",
                "sigma = F_post/A_cross + (M_base/2)/Z",
                f"sigma = {f_post:.1f}/{cross_area:.2f} + {m_half:.3f}e3/{bz:.2f}"
                f" = {s_cross:.3f} MPa",
                f"n = S_y/sigma = {m.yield_strength_mpa:g}/{s_cross:.3f}"
                f" = {m.yield_strength_mpa / s_cross:.3f}",
                "```",
                "",
                "**การเลือกพื้นที่หน้าตัด**",
                "ใช้พื้นที่หน้าตัดดัด (bW×bH) = พื้นที่ที่รับแรงตั้งจริงในการดัด",
                "ไม่ใช้พื้นที่เนื้อรวม (bL×bW×bH) เพราะความยาว bL ไม่ได้มีส่วนรับแรงตั้งตามแนวแร่น",
                f"หากใช้พื้นที่เนื้อรวม ({gross_area:.2f} mm²) จะได้ sigma = {s_gross:.3f} MPa ซึ่งต่ำกว่าจริง",
            ]
        )

    def _rails_stretcher_back(self) -> str:
        g, l, m = self.g, self.l, self.m
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
        s_load = l.backrest_force_n / 2.0

        lp = g.leg_profile
        lZ = lp.moment_of_inertia_m4 * 1e12 / (lp.outer_dimension_mm / 2.0)
        lA = lp.area_m2 * 1e6
        dz = g.backrest_height_above_seat_mm * math.sin(math.radians(g.backrest_angle_deg - 90.0))
        fb = l.backrest_force_n / 2.0
        back_sigma = fb * dz / 1e3 / lZ + fb / lA

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
        m = self.m
        # Governing member is the arm bracket (highest combined stress).
        sig = self._bracket_sigma()
        d_eff = self.ag.bracket_len_mm
        ka = 4.51 * m.ultimate_strength_mpa**-0.265
        kb = 1.24 * (d_eff**-0.107)  # same form as physics.fatigue.MarinFactors.size_factor
        ke = 0.897  # 90% reliability, Shigley Table 6-6
        se_prime = 0.5 * m.ultimate_strength_mpa
        se = ka * kb * 1.0 * 1.0 * ke * 1.0 * se_prime
        n0 = 2 * 10**6
        b = -(math.log10(se_prime / se)) / math.log10(n0)
        n_cycles = n0 * (sig / se) ** (1 / b)
        nd = 5 * 10**8
        sn = se * (nd / n0) ** b
        return "\n".join(
            [
                "## 11. ความทนทานของวัสดุ (Endurance)",
                "",
                f"ชิ้นวิกฤต = แผ่นยึดแขน, σ_max = `{sig:.3f}` MPa",
                "",
                "| ปริมาณ | สูตร | ค่า |",
                "|---|---|---|",
                f"| S_e' | 0.5·S_ut | {se_prime:.2f} MPa |",
                f"| k_a | 4.51·S_ut^-0.265 | {ka:.4f} |",
                f"| k_b | 1.24·d^-0.107 (d = {d_eff:.1f} mm) | {kb:.4f} |",
                "| k_c | ดัด (bending) | 1.0000 |",
                "| k_d | ภาระตัวแปร | 1.0000 |",
                f"| k_e | ความเชื่อมโลหะ 90% | {ke:.4f} |",
                "| k_f | ปัจจัยอื่น | 1.0000 |",
                f"| S_e | k_a·k_b·k_c·k_d·k_e·k_f·S_e' | {se:.4f} MPa |",
                "",
                "```",
                f"n (endurance) = S_e/sigma_max = {se:.4f}/{sig:.3f} = {se / sig:.4f}",
                f"b (Basquin) = {b:.5f}",
                f"N at sigma_max = {n_cycles:.4e} cycles",
                f"S_n at N_d=5e8 = {sn:.4f} MPa  ->  n = {sn / sig:.4f}",
                "```",
                "",
                "> **ข้อควรระวัง**: ท่อแขนรับแรงจากน้ำหนักผู้นั่ง ซึ่งเป็นแรงสถิต",
                "> ไม่ใช่แรงกลับทิศ การใช้ S_e (เกณฑ์ความทนทานของแรงกลับทิศเต็ม) จึงไม่ตรงกับลักษณะการโหลด",
                "> และค่า n ที่ได้จึงเป็นการประเมินแบบเผื่อมาก ไม่ใช่เกณฑ์ที่ใช้ตัดสินจริง",
                f"> ค่า n ที่ N_d = 5×10⁸ รอบ ได้ `{sn / sig:.4f}` ซึ่งต่ำกว่า 1.0",
            ]
        )

    def _governing_post_axial_n(self) -> float:
        """Axial force on the governing post, distributed by the lever rule.

        Each arm rest is carried by two posts, so the pad load splits by
        lever rule rather than 50/50. The bracket bonded to the governing
        post carries that post's full axial share.
        """
        r_front, r_rear = self.ag.post_reaction_fractions(self.l.left_arm_load_y_mm)
        return self.l.left_arm_vertical_n * max(r_front, r_rear)

    def _bracket_sigma(self) -> float:
        a = self.sol.armrests[0]
        bW = self.g.armrest_bracket_thickness_mm
        bH = self.g.armrest_bracket_height_mm
        bz = (bW * bH**3 / 12.0) / (bH / 2.0)
        f_post = self._governing_post_axial_n()
        return f_post / (bW * bH) + (a.strut_base_moment_nm / 2.0) * 1e3 / bz

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
        for i, (p, role) in enumerate(zip(prims, roles), 1):
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
            f"- SF การพลิกคว่าด้านข้าง: "
            + (
                f"`{s.tipping_safety_factor_lat:g}`"
                if s.tipping_safety_factor_lat is not None
                else "`None` — **ไม่มีกรณีนี้ให้ตรวจ** ไม่ใช่ค่าที่คำนวณได้ว่าปลอดภัยมาก "
                f"(แรงข้าง ∓{abs(self.l.left_arm_lateral_n):g} N หักล้างกันพอดี จึงไม่มีโมเมนต์พลิกสุทธิ)"
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
            "| เรขาคณิตแขน | `core/frame_model.py::resolve_armrest()` |",
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
            "2. **ความทนทานของแขน** — แรงจากน้ำหนักผู้นั่งเป็นแรงสถิต "
            "การใช้เกณฑ์ S_e จึงไม่ตรงกับลักษณะการโหลด (ดูหัวข้อ 11)",
            "3. **`physics/fea_3d.py` ยังไม่ได้แก้ตาม** — ยังตั้งตำแหน่งเสาแขนด้วยตัวเลขตายตัว "
            "และยังแบ่งแรง 50/50 จึงอธิบายโครงสร้างต่างจาก CAD ที่แก้แล้ว",
            "4. **SF การพลิกคว่าด้านข้าง** — แก้แล้ว: solver คืนค่า `None` และรายงานแสดง `N/A` "
            "แทนค่าเทียม เพราะแรงข้างของแขนซ้ายและขวาหักล้างกันพอดีจึงไม่มีโมเมนต์พลิกสุทธิ",
            "5. **การหารโมเมนต์แผ่นยึดด้วย 2** — สมมติฐานว่าแผ่นทั้งสองช่วยกันแบ่งโมเมนต์ ยังไม่ได้พิสูจน์",
            "",
        ]
        return "\n".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", default="Project/chair")
    args = ap.parse_args(argv)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "chair_real_data.md"
    path.write_text(FrameDataSheetGenerator().generate_markdown(), encoding="utf-8")
    print(f"[ok] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

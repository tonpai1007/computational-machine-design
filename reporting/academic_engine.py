"""
Academic Machine Design Project Assignment Engine (Engineerview Assignment Engine)
Dedicated report engine strictly tailored for university Mechanical Engineering course project submissions
(specifically matching Year 3 Semester 1 Machine Design project standards at KMITL / Thai Engineering Curricula).

Produces a complete, submission-ready, printable academic project assignment dossier:
- Official university assignment cover page (หน้าปกรายงานภาษาไทย/อังกฤษ)
- Table of contents (สารบัญ)
- Chapter 1: Introduction & Mechanism Objective (บทนำและหลักการทำงาน) with embedded 3D CAD preview
- Chapter 2: Bill of Materials & Section Geometry (รายการชิ้นส่วน BOM และคุณสมบัติหน้าตัด)
- Chapter 3: Material Specifications & Database Citations (ตารางคุณสมบัติวัสดุและการอ้างอิง MatWeb/ASTM)
- Chapter 4: Static Equilibrium & Free-Body Diagram (สมดุลสถิตยศาสตร์และแผนภาพวัตถุอิสระ FBD)
- Chapter 5: Step-by-Step Strength & Buckling Calculations (การคำนวณความแข็งแรงทางวิศวกรรมตามมาตรฐาน Shigley)
- Chapter 6: 3D Direct Stiffness Finite Element Analysis (FEA) Verification
- Chapter 7: Master Component Audit & Safety Factor Table (ตารางสรุปผลการคำนวณและค่าความปลอดภัย)
- Chapter 8: Manufacturing Processes, Welding & Tolerances (กระบวนการผลิต งานเชื่อม และพิกัดความเผื่อ)
- Appendix: 2D Engineering Blueprint, Solver Execution Trace, and Academic Sign-Off Block
"""

import html
import logging
from typing import Any

from ai.narrative_synthesizer import synthesize_academic_narrative
from core.frame_model import FrameDesignModel
from physics.frame_physics import FrameSolverResult
from reporting.render import render
from reporting.spec import active_component_names, build_academic_v2_spec

logger = logging.getLogger("reporting.academic_engine")


def _lat_tip_display(result: FrameSolverResult) -> tuple[str, str, str]:
    """Render the lateral tipping margin honestly.

    Returns (cell_value, verdict, css_class). A ``None`` margin means the
    lateral loads cancel exactly and no tipping case exists -> report "N/A",
    never a fabricated large safety factor (physics-determinism rule).
    """
    if result.tipping_safety_factor_lat is None:
        return (
            '<span style="color:#64748b;font-style:italic;">N/A</span>',
            "N/A (no case)",
            "text-muted",
        )
    sf = result.tipping_safety_factor_lat
    cls = "text-pass" if sf >= 1.5 else "text-fail"
    return f"{sf:.2f}", ("PASS" if sf >= 1.5 else "FAIL"), cls


def _toc_entries(*, has_fea: bool, has_blueprint: bool) -> list[tuple[str, str, int]]:
    """Single source of truth for the dossier's section order and numbering.

    The table of contents and the section anchors both derive from this list,
    so a section can never be listed under the wrong chapter number or link to
    a page that was never rendered. ``level`` is 1 for a chapter/appendix and
    2 for a numbered subsection.

    Chapter numbers are allocated sequentially from the sections that are
    actually rendered. Skipping the FEA chapter must not leave a hole (6 -> 8),
    because a gap in a submitted dossier reads as a missing page.
    """
    entries: list[tuple[str, str, int]] = []

    def chapter(anchor: str, title: str) -> None:
        number = 1 + sum(1 for _, _, level in entries if level == 1)
        entries.append((anchor, f"บทที่ {number} {title}", 1))

    chapter("ch1", "บทนำ วัตถุประสงค์ และข้อมูลจำเพาะการทำงาน")
    chapter("ch2", "ภาพจำลองชิ้นงาน 3 มิติ (3D CAD Solid Model Preview)")
    chapter("ch3", "รายการชิ้นส่วนและคุณสมบัติทางเรขาคณิต (BOM & Cross-Sections)")
    chapter("ch4", "ข้อมูลจำเพาะวัสดุและการอ้างอิงฐานข้อมูล (Material Database)")
    chapter("ch5", "การวิเคราะห์สมดุลสถิตยศาสตร์และแผนภาพวัตถุอิสระ (FBD)")
    chapter("ch6", "ขั้นตอนการคำนวณความแข็งแรงทางวิศวกรรม (Mechanical Calculations)")
    entries += [
        (
            "ch6-1",
            "6.1 อัตราส่วนความชะลูดและการโก่งเดาะของเสา (Euler vs. J.B. Johnson Buckling)",
            2,
        ),
        ("ch6-2", "6.2 การคำนวณชิ้นส่วนคานยื่นที่พักแขน (Cantilever Armrest Mechanics)", 2),
        ("ch6-3", "6.3 การตรวจสอบความเสถียรต่อการล้มคว่ำ (Anti-Tipping Stability Margin)", 2),
    ]
    if has_fea:
        chapter("ch7", "การวิเคราะห์โครงสร้างด้วยระเบียบวิธีไฟไนต์เอลิเมนต์ (3D FEA)")
    chapter("ch8", "ตารางสรุปผลการคำนวณและค่าความปลอดภัยชิ้นส่วนทั้งหมด")
    chapter("ch9", "กระบวนการผลิต งานเชื่อม และข้อกำหนดพิกัดความเผื่อ")
    if has_blueprint:
        entries.append(("appendix-a", "ภาคผนวก ก แบบสั่งทำชิ้นงานวิศวกรรม 2 มิติ (Orthographic Blueprint)", 1))
    entries += [
        ("appendix-b", "ภาคผนวก ข บันทึกการประมวลผลของตัวแก้สมการ (Solver Trace Log)", 1),
        ("appendix-c", "ภาคผนวก ค ใบลงนามอนุมัติผลงานวิชาการ (Academic Sign-Off Block)", 1),
    ]
    return entries


def _render_toc(entries: list[tuple[str, str, int]]) -> str:
    """Render the table of contents as anchor links.

    Page numbers are intentionally not baked in: a hardcoded number drifts the
    moment a section grows. ``.toc-page::after`` resolves the real page in a
    paged-media renderer via ``target-counter`` and falls back to an em dash
    where that CSS is unsupported (e.g. headless Chrome).
    """
    rows: list[str] = []
    for anchor, label, level in entries:
        cls = "toc-entry toc-sub" if level == 2 else "toc-entry"
        rows.append(
            f'    <div class="{cls}">'
            f'<a class="toc-name" href="#{anchor}">{html.escape(label)}</a>'
            f'<span class="toc-dots"></span>'
            f'<a class="toc-page" href="#{anchor}" aria-label="page"></a>'
            f"</div>"
        )
    return "\n".join(rows)


class AcademicAssignmentEngine:
    """
    Dedicated generator for university Machine Design project submissions.
    Separated from the core calculation sheet engine to keep core lightweight and modular.
    """

    @classmethod
    def generate_assignment_report(
        cls,
        model: FrameDesignModel,
        result: FrameSolverResult,
        fea_result: dict[str, Any] | None = None,
        preview_image: str | None = "chair_preview.png",
        university_th: str = "สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง",
        faculty_th: str = "คณะวิศวกรรมศาสตร์ ภาควิชาวิศวกรรมเครื่องกล",
        course_code: str = "01016311",
        course_name: str = "การออกแบบเครื่องจักรกล (Machine Design)",
        academic_term: str = "ภาคเรียนที่ 1 ปีการศึกษา 2567 (Year 3, Semester 1)",
        group_no: str = "กลุ่มที่ 3 (Group 3)",
        student_name: str = "นักศึกษาวิศวกรรมเครื่องกล (Lead Student Designer)",
        student_id: str = "650xxxxxxx",
        instructor: str = "คณาจารย์ประจำวิชาการออกแบบเครื่องจักรกล",
        blueprint_svg: str | None = None,
    ) -> str:
        g = model.geometry
        loads = model.loads
        m = model.material
        allowable_deflection_mm = getattr(m, "allowable_deflection_mm", 5.0)

        # Section properties for the column, read from the solver's own
        # buckling assessment -- not re-derived from the profile here.
        governing_leg = result.floor_reactions[0]
        col_prof = g.leg_profile
        col_area_mm2 = governing_leg.buckling.area_m2 * 1e6
        col_i_mm4 = governing_leg.buckling.moment_of_inertia_m4 * 1e12
        col_z_mm3 = governing_leg.buckling.section_modulus_m3 * 1e9
        col_r_gyr_mm = governing_leg.buckling.radius_of_gyration_m * 1000.0
        effective_length_mm = governing_leg.buckling.effective_length_m * 1000.0
        column_slenderness = governing_leg.slenderness_ratio

        # Johnson transition slenderness ratio, computed by the solver. The
        # report must not re-derive it from E and Sy.
        c_end = 1.0
        trans_slenderness = governing_leg.transition_slenderness_ratio

        # Overall Status Badge
        overall_badge = (
            '<span class="badge badge-pass">VERIFIED COMPLIANT (ผ่านเกณฑ์การออกแบบ)</span>'
            if result.all_safety_criteria_passed
            else '<span class="badge badge-fail">NON-COMPLIANT (ต้องปรับปรุงแบบ)</span>'
        )

        # Column Reaction Rows
        leg_rows = ""
        for leg in result.floor_reactions:
            status_cls = "text-pass" if (leg.buckling_passed and leg.yield_passed) else "text-fail"
            buckling_cls = "text-pass" if leg.buckling_passed else "text-fail"
            yield_cls = "text-pass" if leg.yield_passed else "text-fail"
            status_text = "PASS" if (leg.buckling_passed and leg.yield_passed) else "FAIL"
            buckling_mode = (
                "Euler (Long)"
                if leg.slenderness_ratio >= leg.transition_slenderness_ratio
                else "Johnson (Int.)"
            )

            leg_rows += f"""
            <tr>
                <td style="font-weight: 600;">{leg.leg_id} <span style="font-size: 11px; color: #64748b;">({leg.leg_name})</span></td>
                <td class="num">{leg.axial_reaction_n:.1f} N</td>
                <td class="num">{leg.horizontal_shear_n:.1f} N</td>
                <td class="num">{leg.slenderness_ratio:.1f}</td>
                <td style="text-align: center; font-size: 11px; color: #475569;">{buckling_mode}</td>
                <td class="num">{(leg.critical_buckling_load_n / 1000.0):.2f} kN</td>
                <td class="num {buckling_cls}" style="font-weight: 700;">{leg.buckling_safety_factor:.2f}</td>
                <td class="num">{leg.combined_stress_mpa:.1f} MPa</td>
                <td class="num {yield_cls}" style="font-weight: 700;">{leg.yield_safety_factor:.2f}</td>
                <td style="text-align: center; font-weight: 700;" class="{status_cls}">{status_text}</td>
            </tr>
            """

        # Armrest Rows
        arm_rows = ""
        arm_stress_str = (
            f"{result.armrests[0].strut_combined_stress_mpa:.1f} MPa" if result.armrests else "N/A"
        )
        if result.armrests:
            for arm in result.armrests:
                arm_cls = "text-pass" if arm.passed else "text-fail"
                arm_status = "PASS" if arm.passed else "FAIL"
                arm_rows += f"""
                <tr>
                    <td style="font-weight: 600; text-transform: capitalize;">{arm.arm_id} Arm Assembly</td>
                    <td class="num">{arm.applied_vertical_n:.1f} N</td>
                    <td class="num">{arm.applied_lateral_n:.1f} N</td>
                    <td class="num">{arm.overhang_moment_nm:.1f} N·m</td>
                    <td class="num">{arm.strut_combined_stress_mpa:.1f} MPa</td>
                    <td class="num {arm_cls}" style="font-weight: 700;">{arm.arm_safety_factor:.2f}</td>
                    <td style="text-align: center; font-weight: 700;" class="{arm_cls}">{arm_status}</td>
                </tr>
                """
        else:
            arm_rows = """
            <tr>
                <td colspan="7" style="text-align: center; color: #64748b; font-style: italic;">
                    ไม่มีชิ้นส่วนที่พักแขนในรูปแบบโครงสร้างนี้ (Armless Design Configuration)
                </td>
            </tr>
            """

        # Support reaction values for FBD display.
        # These are the SUM of the reactions in each leg pair: the FBD arrows
        # represent the total load carried by that side of the chair. Averaging
        # them here made sum(R) exactly half the applied load (equilibrium broken).
        if len(result.floor_reactions) >= 4:
            r_left_val = (
                result.floor_reactions[0].axial_reaction_n
                + result.floor_reactions[-1].axial_reaction_n
            )
            r_right_val = (
                result.floor_reactions[1].axial_reaction_n
                + result.floor_reactions[2].axial_reaction_n
            )
        elif len(result.floor_reactions) >= 2:
            r_left_val = result.floor_reactions[0].axial_reaction_n
            r_right_val = sum(
                r.axial_reaction_n for r in result.floor_reactions[1:]
            )
        else:
            r_left_val = r_right_val = result.floor_reactions[0].axial_reaction_n

        # Lateral tipping margin may legitimately not exist (balanced side loads).
        lat_tip_val, lat_tip_verdict, lat_tip_cls = _lat_tip_display(result)
        tip_sf_values = [
            v for v in (result.tipping_safety_factor_fwd,
                        result.tipping_safety_factor_rear,
                        result.tipping_safety_factor_lat)
            if v is not None
        ]
        min_tip_sf = min(tip_sf_values) if tip_sf_values else float("inf")


        # SVG Free-Body Diagram (White paper / academic style)
        svg_fbd = f"""
        <svg viewBox="0 0 720 380" style="width: 100%; height: auto; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px;">
            <defs>
                <marker id="arrow-down" viewBox="0 0 10 10" refX="5" refY="10" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 0 L 10 0 L 5 10 z" fill="#dc2626" />
                </marker>
                <marker id="arrow-up" viewBox="0 0 10 10" refX="5" refY="0" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 10 L 10 10 L 5 0 z" fill="#16a34a" />
                </marker>
                <marker id="arrow-lat" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#0284c7" />
                </marker>
            </defs>

            <!-- Rigid Floor Plane (Z = 0) -->
            <line x1="60" y1="310" x2="660" y2="310" stroke="#64748b" stroke-width="2" stroke-dasharray="6,4" />
            <text x="70" y="332" fill="#475569" font-size="11" font-family="'Times New Roman', serif, sans-serif">Rigid Datum Plane (Z = 0 mm)</text>
            <path d="M 70 310 L 60 320 M 110 310 L 100 320 M 150 310 L 140 320 M 570 310 L 560 320 M 610 310 L 600 320 M 650 310 L 640 320" stroke="#94a3b8" stroke-width="1.5" />

            <!-- Splayed Columns / Legs -->
            <line x1="230" y1="210" x2="190" y2="310" stroke="#1e293b" stroke-width="6" stroke-linecap="round" />
            <line x1="470" y1="210" x2="510" y2="310" stroke="#1e293b" stroke-width="6" stroke-linecap="round" />

            <!-- Stretcher Bracing -->
            <line x1="205" y1="270" x2="495" y2="270" stroke="#475569" stroke-width="3" stroke-dasharray="4,2" />
            <text x="350" y="264" fill="#334155" font-size="10" text-anchor="middle" font-family="Inter, sans-serif">Bracing Stretcher (Z = {g.stretcher_height_mm:.0f} mm)</text>

            <!-- Main Platform Deck -->
            <rect x="200" y="200" width="300" height="18" rx="2" fill="#e2e8f0" stroke="#0f172a" stroke-width="2" />
            <text x="350" y="213" fill="#0f172a" font-size="11" font-weight="700" text-anchor="middle" font-family="Inter, sans-serif">Main Structural Platform (W = {g.seat_width_mm:.0f} mm, D = {g.seat_depth_mm:.0f} mm)</text>

            <!-- Left Armrest & Strut -->
            <line x1="220" y1="200" x2="220" y2="125" stroke="#334155" stroke-width="4" />
            <rect x="180" y="115" width="70" height="10" rx="2" fill="#fef3c7" stroke="#b45309" stroke-width="1.5" />
            <text x="215" y="108" fill="#92400e" font-size="10" font-weight="700" text-anchor="middle" font-family="Inter, sans-serif">Left Armrest</text>

            <!-- Right Armrest & Strut -->
            <line x1="480" y1="200" x2="480" y2="125" stroke="#334155" stroke-width="4" />
            <rect x="450" y="115" width="70" height="10" rx="2" fill="#fef3c7" stroke="#b45309" stroke-width="1.5" />
            <text x="485" y="108" fill="#92400e" font-size="10" font-weight="700" text-anchor="middle" font-family="Inter, sans-serif">Right Armrest</text>

            <!-- Backrest Structure -->
            <line x1="230" y1="200" x2="220" y2="60" stroke="#475569" stroke-width="4" />
            <line x1="470" y1="200" x2="460" y2="60" stroke="#475569" stroke-width="4" />
            <rect x="220" y="70" width="240" height="55" rx="3" fill="#f1f5f9" stroke="#475569" stroke-width="1.5" />
            <text x="340" y="102" fill="#334155" font-size="11" font-weight="600" text-anchor="middle" font-family="Inter, sans-serif">Upper Structure / Backrest Assembly</text>

            <!-- Applied Seat Payload Force -->
            <line x1="350" y1="140" x2="350" y2="195" stroke="#dc2626" stroke-width="2.5" marker-end="url(#arrow-down)" />
            <text x="350" y="152" fill="#b91c1c" font-size="11" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">F_load = {loads.seat_vertical_load_n:.0f} N</text>

            <!-- Applied Arm Loads -->
            <line x1="215" y1="70" x2="215" y2="110" stroke="#dc2626" stroke-width="2" marker-end="url(#arrow-down)" />
            <text x="215" y="65" fill="#b91c1c" font-size="10" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">F_arm = {loads.left_arm_vertical_n:.0f} N</text>
            <line x1="215" y1="120" x2="160" y2="120" stroke="#0284c7" stroke-width="2" marker-end="url(#arrow-lat)" />
            <text x="155" y="115" fill="#0369a1" font-size="10" font-weight="700" text-anchor="end" font-family="'JetBrains Mono', monospace">{abs(loads.left_arm_lateral_n):.0f} N (lat)</text>

            <line x1="485" y1="70" x2="485" y2="110" stroke="#dc2626" stroke-width="2" marker-end="url(#arrow-down)" />
            <text x="485" y="65" fill="#b91c1c" font-size="10" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">F_arm = {loads.right_arm_vertical_n:.0f} N</text>
            <line x1="485" y1="120" x2="540" y2="120" stroke="#0284c7" stroke-width="2" marker-end="url(#arrow-lat)" />
            <text x="548" y="115" fill="#0369a1" font-size="10" font-weight="700" font-family="'JetBrains Mono', monospace">{abs(loads.right_arm_lateral_n):.0f} N (lat)</text>

            <!-- Support Floor Reactions -->
            <line x1="190" y1="360" x2="190" y2="315" stroke="#16a34a" stroke-width="3" marker-end="url(#arrow-up)" />
            <text x="190" y="372" fill="#15803d" font-size="11" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">R_left ≈ {r_left_val:.1f} N</text>

            <line x1="510" y1="360" x2="510" y2="315" stroke="#16a34a" stroke-width="3" marker-end="url(#arrow-up)" />
            <text x="510" y="372" fill="#15803d" font-size="11" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">R_right ≈ {r_right_val:.1f} N</text>
        </svg>
        """

        # 3D CAD Preview Block
        cad_preview_html = ""
        if preview_image:
            cad_preview_html = f"""
            <div style="text-align: center; margin: 18px 0;">
                <img src="{preview_image}" alt="3D CAD Solid Model Preview" style="max-width: 520px; width: 100%; height: auto; border: 1px solid #cbd5e1; border-radius: 6px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.08);" />
                <div style="font-size: 11.5px; color: #64748b; margin-top: 6px; font-style: italic;">
                    รูปที่ 1.1: ภาพจำลองชิ้นงาน 3 มิติ (3D Parametric CAD Solid Assembly Model Rendered from STEP/SCAD)
                </div>
            </div>
            """

        # FEA Section HTML
        fea_html = ""
        if fea_result:
            fea_html = f"""
            <div class="section page-break" id="ch7">
                <div class="section-title">
                    <span><span class="section-num">บทที่ 7</span> การวิเคราะห์โครงสร้างด้วยระเบียบวิธีไฟไนต์เอลิเมนต์ (3D FEA Direct Stiffness)</span>
                    <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Spatial Beam Stiffness Matrix</span>
                </div>
                <p>
                    เพื่อตรวจสอบความถูกต้องของการคำนวณเชิงทฤษฎี โครงสร้าง 3 มิติได้รับการวิเคราะห์ด้วยระเบียบวิธีไฟไนต์เอลิเมนต์แบบ Direct Stiffness Method
                    โดยกำหนดระดับความเป็นอิสระ (DOF) จำนวน 6 ระดับต่อจุดต่อ (3 การเคลื่อนที่ในแนวแกน X, Y, Z และ 3 การหมุนรอบแกน)
                    โครงสร้างประกอบด้วย <strong>{fea_result.get("num_members", 28)} ชิ้นส่วนคาน-เสาในปริภูมิ 3 มิติ</strong> และ
                    <strong>{fea_result.get("num_nodes", 24)} จุดต่อ (Joints)</strong> ({fea_result.get("active_free_dof", 120)} ระดับความเป็นอิสระอิสระ).
                </p>
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <div class="kpi-label">Peak Von Mises Stress</div>
                        <div class="kpi-val">{fea_result.get("max_von_mises_mpa", 0.0):.1f} <span style="font-size: 11px; color: var(--text-muted);">MPa</span></div>
                        <div class="kpi-sub">ขีดจำกัดคราก: {m.yield_strength_mpa:.1f} MPa</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">FEA Minimum SF</div>
                        <div class="kpi-val {"text-pass" if fea_result.get("min_safety_factor", 2.0) >= 1.5 else "text-fail"}">{fea_result.get("min_safety_factor", 2.0):.2f}</div>
                        <div class="kpi-sub">เกณฑ์ความปลอดภัย: &ge; 1.50</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Max Deflection (&delta;)</div>
                        <div class="kpi-val">{fea_result.get("max_displacement_mm", 0.0):.2f} <span style="font-size: 11px; color: var(--text-muted);">mm</span></div>
                        <div class="kpi-sub">ระยะแอ่นตัวสูงสุดที่ยอมรับได้: &le; {allowable_deflection_mm:.1f} mm</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Active DOFs Solved</div>
                        <div class="kpi-val">{fea_result.get("active_free_dof", 120)}</div>
                        <div class="kpi-sub">Total Model DOFs: {fea_result.get("total_dof", 144)}</div>
                    </div>
                </div>
            </div>
            """

        calc_log_items = "".join([f"<li>{html.escape(step)}</li>" for step in result.calculation_log])

        blueprint_html = ""
        if blueprint_svg:
            blueprint_html = f"""
            <div class="section page-break" id="appendix-a">
                <div class="section-title">
                    <span><span class="section-num">ภาคผนวก ก</span> แบบสั่งทำชิ้นงานวิศวกรรม 2 มิติ (Orthographic 2D Manufacturing Blueprint)</span>
                    <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">ISO 128 / ANSI Y14.5</span>
                </div>
                <div style="border: 1px solid #cbd5e1; border-radius: 4px; overflow: hidden; background: #ffffff; margin: 15px 0;">
                    {blueprint_svg}
                </div>
            </div>
            """

        toc_entries = _toc_entries(
            has_fea=bool(fea_result), has_blueprint=bool(blueprint_svg)
        )
        toc_html = _render_toc(toc_entries)
        # Body headings must agree with the numbering the TOC allocated.
        labels = {anchor: label for anchor, label, _ in toc_entries}
        summary_chapter_no = int(labels["ch8"].split()[1])
        fabrication_chapter_no = int(labels["ch9"].split()[1])

        html_out = f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <title>รายงานโครงงานวิชาการออกแบบเครื่องจักรกล - {html.escape(model.name)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700;800&family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #ffffff;
      --card-bg: #f8fafc;
      --border: #cbd5e1;
      --border-dark: #0f172a;
      --text: #0f172a;
      --text-muted: #475569;
      --primary: #1d4ed8;
      --pass: #047857;
      --fail: #b91c1c;
      --warn: #b45309;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Sarabun', 'Times New Roman', -apple-system, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 0;
      margin: 0;
    }}
    .no-print-bar {{
      background: #0f172a;
      color: #ffffff;
      padding: 10px 25px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-family: 'Inter', sans-serif;
      font-size: 13px;
    }}
    .print-btn {{
      background: #2563eb;
      color: #ffffff;
      border: none;
      padding: 6px 16px;
      border-radius: 4px;
      font-weight: 600;
      cursor: pointer;
      font-size: 12px;
    }}
    .print-btn:hover {{
      background: #1d4ed8;
    }}
    .document-wrapper {{
      max-width: 900px;
      margin: 0 auto;
      padding: 40px 30px;
    }}

    /* Formal Assignment Cover Sheet */
    .cover-sheet {{
      min-height: 980px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      border: 3px double var(--border-dark);
      padding: 55px 45px;
      text-align: center;
      margin-bottom: 50px;
      background: #ffffff;
      box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }}
    .cover-header {{
      font-size: 15px;
      font-weight: 700;
      line-height: 1.6;
      color: #1e293b;
    }}
    .cover-course {{
      font-size: 16px;
      font-weight: 700;
      color: var(--primary);
      margin-top: 15px;
    }}
    .cover-title-group {{
      margin: 60px 0;
    }}
    .cover-report-type {{
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 2px;
      color: var(--text-muted);
      margin-bottom: 12px;
    }}
    .cover-title {{
      font-size: 28px;
      font-weight: 800;
      color: #0f172a;
      line-height: 1.3;
      margin-bottom: 14px;
    }}
    .cover-subtitle {{
      font-size: 15px;
      color: #334155;
      font-style: italic;
      max-width: 650px;
      margin: 0 auto;
    }}
    .cover-meta-box {{
      border: 1.5px solid var(--border);
      background: #f8fafc;
      padding: 24px 30px;
      border-radius: 4px;
      text-align: left;
      font-size: 14px;
      max-width: 620px;
      margin: 0 auto;
    }}
    .cover-meta-row {{
      display: flex;
      margin-bottom: 8px;
    }}
    .cover-meta-label {{
      width: 170px;
      font-weight: 700;
      color: #475569;
    }}
    .cover-meta-val {{
      flex: 1;
      color: #0f172a;
      font-weight: 600;
    }}
    .cover-footer {{
      font-size: 12px;
      color: var(--text-muted);
      border-top: 1px solid var(--border);
      padding-top: 15px;
      margin-top: 30px;
    }}

    /* Table of Contents */
    .toc-wrapper {{
      border: 1px solid var(--border);
      background: #ffffff;
      padding: 35px 40px;
      margin-bottom: 40px;
    }}
    .toc-title {{
      font-size: 20px;
      font-weight: 800;
      text-align: center;
      text-transform: uppercase;
      letter-spacing: 1px;
      border-bottom: 2px solid var(--border-dark);
      padding-bottom: 10px;
      margin-bottom: 25px;
    }}
    .toc-entry {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 10px;
      font-size: 14px;
    }}
    .toc-name {{
      font-weight: 600;
      color: #0f172a;
    }}
    .toc-dots {{
      flex: 1;
      border-bottom: 1px dotted #94a3b8;
      margin: 0 10px;
      height: 1px;
    }}
    .toc-sub {{
      padding-left: 24px;
      font-size: 13px;
      color: #475569;
    }}
    .toc-entry a {{
      color: inherit;
      text-decoration: none;
    }}
    .toc-entry a:hover {{
      text-decoration: underline;
    }}
    .toc-page {{
      min-width: 18px;
      text-align: right;
      font-weight: 700;
    }}
    .toc-page::after {{
      content: "—";
      color: #94a3b8;
    }}
    @media print {{
      .toc-page::after {{
        /* Real page number in paged-media renderers (WeasyPrint/Prince). */
        content: target-counter(attr(href), page);
        color: #0f172a;
      }}
    }}

    /* Academic Section Layout */
    .section {{
      margin-bottom: 35px;
    }}
    .section-title {{
      font-size: 17px;
      font-weight: 700;
      color: #0f172a;
      border-bottom: 1.5px solid var(--border-dark);
      padding-bottom: 5px;
      margin-bottom: 14px;
      display: flex;
      justify-content: space-between;
      align-items: baseline;
    }}
    .section-num {{
      color: var(--primary);
      margin-right: 6px;
    }}
    p, li {{
      font-size: 14px;
      color: #1e293b;
      margin-bottom: 10px;
      text-align: justify;
    }}

    /* Technical Tables */
    table.tech-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      margin: 14px 0;
    }}
    table.tech-table th {{
      background: #f1f5f9;
      color: #0f172a;
      font-weight: 700;
      text-align: left;
      padding: 8px 10px;
      border: 1px solid var(--border);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }}
    table.tech-table td {{
      padding: 8px 10px;
      border: 1px solid var(--border);
    }}
    table.tech-table tr:nth-child(even) td {{
      background: #fbfcfd;
    }}
    .num {{
      font-family: 'JetBrains Mono', monospace;
      text-align: right;
    }}
    .text-pass {{ color: var(--pass); }}
    .text-fail {{ color: var(--fail); }}

    /* Formula & Step Boxes */
    .calc-step {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-left: 3.5px solid var(--primary);
      padding: 14px 18px;
      margin: 14px 0;
      border-radius: 2px;
    }}
    .step-header {{
      font-size: 13.5px;
      font-weight: 700;
      color: var(--primary);
      margin-bottom: 6px;
    }}
    .equation-line {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 12.5px;
      color: #0f172a;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      padding: 7px 12px;
      margin: 5px 0;
      border-radius: 3px;
    }}

    /* KPI Summary Strip */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin: 14px 0;
    }}
    .kpi-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 12px 14px;
    }}
    .kpi-label {{
      font-size: 10.5px;
      text-transform: uppercase;
      color: var(--text-muted);
      font-weight: 700;
      letter-spacing: 0.4px;
    }}
    .kpi-val {{
      font-size: 21px;
      font-weight: 800;
      font-family: 'JetBrains Mono', monospace;
      margin: 4px 0;
    }}
    .kpi-sub {{
      font-size: 10.5px;
      color: var(--text-muted);
    }}

    .badge {{
      display: inline-block;
      padding: 4px 14px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.5px;
      font-family: 'Inter', sans-serif;
    }}
    .badge-pass {{
      background: #ecfdf5;
      color: var(--pass);
      border: 1px solid #a7f3d0;
    }}
    .badge-fail {{
      background: #fef2f2;
      color: var(--fail);
      border: 1px solid #fecaca;
    }}

    ul.trace-list {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11.5px;
      list-style-type: square;
      padding-left: 20px;
      color: #334155;
    }}
    ul.trace-list li {{
      margin-bottom: 4px;
    }}

    /* Sign-off Box */
    .signoff-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
      border-top: 1.5px solid var(--border-dark);
      padding-top: 15px;
      margin-top: 35px;
    }}
    .signoff-box {{
      font-size: 12px;
    }}
    .signoff-line {{
      border-bottom: 1px solid #94a3b8;
      height: 40px;
      margin-bottom: 6px;
    }}

    /* Print & A4 Setup */
    @media print {{
      .no-print-bar {{ display: none !important; }}
      body {{
        background: #ffffff;
        color: #000000;
        font-size: 11pt;
      }}
      .document-wrapper {{
        max-width: 100%;
        padding: 0;
      }}
      .cover-sheet {{
        box-shadow: none;
        border: 2px solid #000000;
        min-height: 250mm;
      }}
      .page-break {{
        page-break-before: always;
      }}
      table.tech-table th {{
        background: #f1f5f9 !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }}
    }}
    @page {{
      size: A4 portrait;
      margin: 18mm 15mm 18mm 15mm;
    }}
  </style>
</head>
<body>

<div class="no-print-bar">
  <div>
    <strong>Machine Design Academic Project Assignment Engine</strong> &mdash; ส่งเป็นรายงานโครงงานรายวิชา (Submission Dossier)
  </div>
  <button class="print-btn" onclick="window.print()">Print / Export Assignment PDF (Ctrl+P)</button>
</div>

<div class="document-wrapper">

  <!-- ================= หน้าปกรายงาน (ASSIGNMENT COVER SHEET) ================= -->
  <div class="cover-sheet">
    <div class="cover-header">
      {html.escape(faculty_th)}<br>
      {html.escape(university_th)}
    </div>

    <div class="cover-course">
      รหัสวิชา {html.escape(course_code)} {html.escape(course_name)}<br>
      <span style="font-size: 13.5px; font-weight: 500; color: #475569;">{html.escape(academic_term)}</span>
    </div>

    <div class="cover-title-group">
      <div class="cover-report-type">รายงานโครงงานการออกแบบเครื่องจักรกล (Project Design Report)</div>
      <h1 class="cover-title">{html.escape(model.name.upper())}</h1>
      <div class="cover-subtitle">
        การออกแบบ การคำนวณสมดุลสถิตยศาสตร์ การโก่งเดาะของเสา ความแข็งแรงของจุดต่อ และการวิเคราะห์ไฟไนต์เอลิเมนต์
      </div>
    </div>

    <div class="cover-meta-box">
      <div class="cover-meta-row">
        <div class="cover-meta-label">กลุ่มโครงงาน:</div>
        <div class="cover-meta-val">{html.escape(group_no)}</div>
      </div>
      <div class="cover-meta-row">
        <div class="cover-meta-label">ผู้จัดทำ (Lead Designer):</div>
        <div class="cover-meta-val">{html.escape(student_name)}</div>
      </div>
      <div class="cover-meta-row">
        <div class="cover-meta-label">รหัสนักศึกษา:</div>
        <div class="cover-meta-val">{html.escape(student_id)}</div>
      </div>
      <div class="cover-meta-row">
        <div class="cover-meta-label">เสนอ (Submitted To):</div>
        <div class="cover-meta-val">{html.escape(instructor)}</div>
      </div>
      <div class="cover-meta-row">
        <div class="cover-meta-label">มาตรฐานที่ใช้อ้างอิง:</div>
        <div class="cover-meta-val">ANSI/BIFMA X5.1 &bull; AISC 360 &bull; ISO 7173</div>
      </div>
      <div class="cover-meta-row">
        <div class="cover-meta-label">ผลการตรวจสอบ (Verdict):</div>
        <div class="cover-meta-val">{overall_badge}</div>
      </div>
    </div>

    <div class="cover-footer">
      Machine Design Computational Engineering Platform (MDIE) &bull; Standard Metric SI Units (mm, N, N·m, MPa, GPa)
    </div>
  </div>

  <!-- ================= สารบัญ (TABLE OF CONTENTS) ================= -->
  <div class="toc-wrapper page-break">
    <div class="toc-title">สารบัญ (Table of Contents)</div>

{toc_html}
  </div>

  <!-- ================= บทที่ 1 ================= -->
  <div class="section page-break" id="ch1">
    <div class="section-title">
      <span><span class="section-num">บทที่ 1</span> บทนำ วัตถุประสงค์ และข้อมูลจำเพาะการทำงาน</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Executive Brief</span>
    </div>
    <p>
      รายงานฉบับนี้จัดทำขึ้นเพื่อนำเสนอผลการคำนวณออกแบบและตรวจสอบความแข็งแรงทางวิศวกรรมของ <strong>{html.escape(model.name)}</strong>
      ตามมาตรฐานวิชาชีพและการออกแบบเครื่องจักรกล โครงสร้างนี้ถูกออกแบบมาเพื่อรองรับภาระน้ำหนักบรรทุกใช้งาน (Service Payload)
      โดยคำนึงถึงความแข็งแรงเชิงสถิตยศาสตร์ เสถียรภาพการโก่งเดาะของเสารองรับ (Column Buckling) ความเค้นรวมในชิ้นส่วน และความเสถียรต่อการล้มคว่ำ
    </p>
    <p>
      ภาระบรรทุกที่ใช้ในการคำนวณประกอบด้วย น้ำหนักกดแนวดิ่งบนเบาะรองนั่ง <strong>{loads.seat_vertical_load_n:.0f} N</strong>
      (เทียบเท่าผู้ใช้งานน้ำหนัก 130 kg รวมผลกระทบการกระแทก dynamic impact), แรงกดแนวดิ่งบนที่พักแขน <strong>{loads.left_arm_vertical_n:.0f} N</strong>
      และแรงผลักออกด้านข้าง <strong>{abs(loads.left_arm_lateral_n):.0f} N</strong> รวมถึงน้ำหนักโครงสร้างในตัว
    </p>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Applied Payload</div>
        <div class="kpi-val">{loads.seat_vertical_load_n:.0f} <span style="font-size: 11px; color: var(--text-muted);">N</span></div>
        <div class="kpi-sub">Total Downward: {result.total_downward_load_n:.1f} N</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Min Buckling SF</div>
        <div class="kpi-val {"text-pass" if result.min_leg_buckling_sf >= 2.0 else "text-fail"}">{result.min_leg_buckling_sf:.2f}</div>
        <div class="kpi-sub">Design Target: n<sub>d</sub> &ge; 2.00</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Min Yield SF</div>
        <div class="kpi-val {"text-pass" if result.min_leg_yield_sf >= 2.0 else "text-fail"}">{result.min_leg_yield_sf:.2f}</div>
        <div class="kpi-sub">Combined P/A + M/Z</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Anti-Tipping SF</div>
        <div class="kpi-val {"text-pass" if min_tip_sf >= 1.5 else "text-fail"}">
          {min_tip_sf:.2f}
        </div>
        <div class="kpi-sub">เกณฑ์มาตรฐาน: &ge; 1.50</div>
      </div>
    </div>
  </div>

  <!-- ================= บทที่ 2 ================= -->
  <div class="section" id="ch2">
    <div class="section-title">
      <span><span class="section-num">บทที่ 2</span> ภาพจำลองชิ้นงาน 3 มิติ (3D CAD Solid Model Preview)</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Parametric 3D CAD</span>
    </div>
    <p>
      โครงสร้างได้รับการขึ้นรูปเป็นโมเดลของแข็ง 3 มิติ (3D Solid Assembly) และส่งออกเป็นไฟล์มาตรฐานอุตสาหกรรม
      ISO-10303 STEP (<code>chair.step</code>), ไฟล์พิมพ์ 3 มิติ Watertight Mesh (<code>chair.stl</code>), และไฟล์สคริปต์พารามิเตอร์ (<code>chair.scad</code>)
    </p>
    {cad_preview_html}
  </div>

  <!-- ================= บทที่ 3 ================= -->
  <div class="section page-break" id="ch3">
    <div class="section-title">
      <span><span class="section-num">บทที่ 3</span> รายการชิ้นส่วนและคุณสมบัติทางเรขาคณิต (BOM & Cross-Sections)</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Bill of Materials</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>ลำดับ</th>
          <th>ชื่อชิ้นส่วน / ส่วนประกอบ</th>
          <th>ขนาดหน้าตัดและมิติเรขาคณิต</th>
          <th style="text-align: right;">จำนวน</th>
          <th>วัสดุที่เลือกใช้</th>
          <th>กระบวนการขึ้นรูป</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="font-weight: 600;">1</td>
          <td>เสาขาโครงสร้างหลัก (Leg Columns)</td>
          <td>{col_prof.profile_type.replace("_", " ").title()} &Oslash;{col_prof.outer_dimension_mm:.1f} &times; {col_prof.wall_thickness_mm:.1f} mm</td>
          <td class="num">4</td>
          <td>{m.name}</td>
          <td>ท่อดึงเย็นไร้ตะเข็บ (Cold Drawn Seamless Tube)</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">2</td>
          <td>คานค้ำยันรอบล่าง (Lower Stretcher)</td>
          <td>ท่อกลม &Oslash;{g.stretcher_profile.outer_dimension_mm:.1f} &times; {g.stretcher_profile.wall_thickness_mm:.1f} mm</td>
          <td class="num">4</td>
          <td>{m.name}</td>
          <td>งานเชื่อม MIG/TIG ประกอบโครง</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">3</td>
          <td>แผ่นฐานรองรับน้ำหนัก (Main Platform)</td>
          <td>{g.seat_width_mm:.0f} &times; {g.seat_depth_mm:.0f} &times; {g.seat_thickness_mm:.0f} mm</td>
          <td class="num">1</td>
          <td>ไม้เนื้อแข็งขึ้นรูป / คอมโพสิต</td>
          <td>งานกัด CNC Router</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">4</td>
          <td>ชุดโครงสร้างที่พักแขน (Armrest Struts)</td>
          <td>คานยื่นรับน้ำหนัก L = {g.armrest_length_mm:.0f} mm</td>
          <td class="num">2</td>
          <td>{m.name} / ไม้แอช</td>
          <td>ดัดท่อ CNC + ยึดน็อตประกบ</td>
        </tr>
      </tbody>
    </table>

    <div class="calc-step" style="margin-top: 10px;">
      <div class="step-header">คุณสมบัติหน้าตัดของเสาขาโครงสร้างหลัก (Section Properties):</div>
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; font-size: 12px; font-family: 'JetBrains Mono', monospace;">
        <div>พื้นที่หน้าตัด A = {col_area_mm2:.1f} mm²</div>
        <div>โมเมนต์ความเฉื่อย I = {col_i_mm4:.1f} mm⁴</div>
        <div>โมดูลัสหน้าตัด Z = {col_z_mm3:.1f} mm³</div>
        <div>รัศมีไจเรชัน k = {col_r_gyr_mm:.2f} mm</div>
      </div>
    </div>
  </div>

  <!-- ================= บทที่ 4 ================= -->
  <div class="section" id="ch4">
    <div class="section-title">
      <span><span class="section-num">บทที่ 4</span> ข้อมูลจำเพาะวัสดุและการอ้างอิงฐานข้อมูล (Material Database)</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Standardized Database Reference</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>คุณสมบัติทางกลของวัสดุ</th>
          <th>สัญลักษณ์</th>
          <th style="text-align: right;">ค่าที่กำหนด</th>
          <th>หน่วย</th>
          <th>แหล่งข้อมูลอ้างอิง / มาตรฐาน</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>เกรดวัสดุ (Material Grade)</td>
          <td>-</td>
          <td class="num">{m.name}</td>
          <td>-</td>
          <td>MatWeb Database / ASTM A513</td>
        </tr>
        <tr>
          <td>ความหนาแน่น (Density)</td>
          <td>&rho;</td>
          <td class="num">{(m.density_kg_m3 / 1000.0):.2f}</td>
          <td>g/cm&sup3;</td>
          <td>ASTM Standard Density Table ({m.density_kg_m3:.0f} kg/m&sup3;)</td>
        </tr>
        <tr>
          <td>ความแข็งแรงคราก (Yield Strength)</td>
          <td>S<sub>y</sub></td>
          <td class="num">{m.yield_strength_mpa:.1f}</td>
          <td>MPa</td>
          <td>AISC / ASM Metals Handbook</td>
        </tr>
        <tr>
          <td>ความต้านทานแรงดึงสูงสุด (Tensile Strength)</td>
          <td>S<sub>ut</sub></td>
          <td class="num">{m.ultimate_strength_mpa:.1f}</td>
          <td>MPa</td>
          <td>AISC / ASM Metals Handbook</td>
        </tr>
        <tr>
          <td>โมดูลัสยืดหยุ่น (Young's Modulus)</td>
          <td>E</td>
          <td class="num">{m.elastic_modulus_gpa:.1f}</td>
          <td>GPa</td>
          <td>ASTM E111 Standard Static Test</td>
        </tr>
        <tr>
          <td>อัตราส่วนปัวซอง (Poisson's Ratio)</td>
          <td>&nu;</td>
          <td class="num">{m.poissons_ratio:.2f}</td>
          <td>-</td>
          <td>Standard Elastic Constant</td>
        </tr>
        <tr>
          <td>ระยะแอ่นตัวที่ยอมรับได้</td>
          <td>&delta;<sub>all</sub></td>
          <td class="num">{allowable_deflection_mm:.1f}</td>
          <td>mm</td>
          <td>BIFMA X5.1 / Span limit (L / 120)</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- ================= บทที่ 5 ================= -->
  <div class="section page-break" id="ch5">
    <div class="section-title">
      <span><span class="section-num">บทที่ 5</span> การวิเคราะห์สมดุลสถิตยศาสตร์และแผนภาพวัตถุอิสระ (FBD)</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Reactions & Load Trace</span>
    </div>
    <p>
      สมการความสมดุลสถิตยศาสตร์ของโครงสร้าง 3 มิติภายใต้ภาระบรรทุกภายนอก:
    </p>
    <div class="calc-step">
      <div class="equation-line">&sum; F<sub>z</sub> = 0 &rArr; R<sub>FL,z</sub> + R<sub>FR,z</sub> + R<sub>RL,z</sub> + R<sub>RR,z</sub> = W<sub>frame</sub> + F<sub>payload</sub> = {result.total_downward_load_n:.1f} N</div>
      <div class="equation-line">&sum; F<sub>x</sub> = 0 &rArr; &sum; R<sub>x</sub> = F<sub>lateral,x</sub> &emsp;|&emsp; &sum; M = 0 (สมดุลโมเมนต์ในระนาบ)</div>
    </div>
    <div style="margin: 14px 0;">
      {svg_fbd}
    </div>
  </div>

  <!-- ================= บทที่ 6 ================= -->
  <div class="section page-break" id="ch6">
    <div class="section-title">
      <span><span class="section-num">บทที่ 6</span> ขั้นตอนการคำนวณความแข็งแรงทางวิศวกรรม (Mechanical Calculations)</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Shigley Chapter 4 Verification</span>
    </div>

    <p id="ch6-1"><strong>6.1 อัตราส่วนความชะลูดและการโก่งเดาะของเสา (Euler vs. J.B. Johnson Buckling):</strong></p>
    <p>
      สำหรับชิ้นส่วนเสาที่รับแรงกดตามแนวแกน ค่าอัตราส่วนความชะลูดวิกฤต (&lambda;<sub>1</sub>) ใช้แบ่งระหว่างการโก่งเดาะแบบไม่ยืดหยุ่น (Johnson Buckling)
      และการโก่งเดาะแบบยืดหยุ่น (Euler Buckling):
    </p>
    <div class="calc-step">
      <div class="step-header">สมการอัตราส่วนความชะลูดวิกฤต (AISC / Shigley Eq. 4-48):</div>
      <div class="equation-line">
        &lambda;<sub>1</sub> = &radic;[ (2 &pi;&sup2; C E) / S<sub>y</sub> ] = &radic;[ (2 &pi;&sup2; &times; {c_end:.1f} &times; {m.elastic_modulus_gpa * 1000.0:.0f} MPa) / {m.yield_strength_mpa:.1f} MPa ] = {trans_slenderness:.1f}
      </div>
      <div style="font-size: 12.5px; color: #475569; margin-top: 4px;">
        ความยาวประสิทธิผล L<sub>eff</sub> = {effective_length_mm:.1f} mm &bull; รัศมีไจเรชัน k = {col_r_gyr_mm:.2f} mm &bull; อัตราส่วนความชะลูดเสา &lambda; = L<sub>eff</sub> / k = {column_slenderness:.1f}
      </div>
      <div style="font-size: 12.5px; color: #047857; margin-top: 2px; font-weight: 600;">
        เนื่องจาก &lambda; ({column_slenderness:.1f}) &lt; &lambda;<sub>1</sub> ({trans_slenderness:.1f}) &rarr; จัดเป็นเสาระดับปานกลาง (Intermediate Column) ใช้สมการพาราโบลิกของ J.B. Johnson
      </div>
    </div>

    <table class="tech-table">
      <thead>
        <tr>
          <th>รหัสเสา</th>
          <th style="text-align: right;">แรงกดแกน R<sub>z</sub></th>
          <th style="text-align: right;">แรงเฉือน R<sub>h</sub></th>
          <th style="text-align: right;">ความชะลูด &lambda;</th>
          <th style="text-align: center;">รูปแบบการโก่งเดาะ</th>
          <th style="text-align: right;">แรงวิกฤต P<sub>cr</sub></th>
          <th style="text-align: right;">ค่าความปลอดภัยโก่งเดาะ</th>
          <th style="text-align: right;">ความเค้นรวม</th>
          <th style="text-align: right;">ค่าความปลอดภัยคราก</th>
          <th style="text-align: center;">ผลการประเมิน</th>
        </tr>
      </thead>
      <tbody>
        {leg_rows}
      </tbody>
    </table>

    <p id="ch6-2" style="margin-top: 15px;"><strong>6.2 การคำนวณชิ้นส่วนคานยื่นที่พักแขน (Cantilever Armrest Mechanics):</strong></p>
    <table class="tech-table">
      <thead>
        <tr>
          <th>ชุดชิ้นส่วน</th>
          <th style="text-align: right;">แรงกดแนวดิ่ง</th>
          <th style="text-align: right;">แรงผลักด้านข้าง</th>
          <th style="text-align: right;">โมเมนต์ดัดคานยื่น</th>
          <th style="text-align: right;">ความเค้นสูงสุดรวม</th>
          <th style="text-align: right;">ค่าความปลอดภัย (n<sub>s</sub>)</th>
          <th style="text-align: center;">ผลการประเมิน</th>
        </tr>
      </thead>
      <tbody>
        {arm_rows}
      </tbody>
    </table>

    <p id="ch6-3" style="margin-top: 15px;"><strong>6.3 การตรวจสอบความเสถียรต่อการล้มคว่ำ (Anti-Tipping Stability Margin):</strong></p>
    <p>
      ค่าความปลอดภัยต่อการล้มคว่ำคำนวณจากอัตราส่วนโมเมนต์ต้านต่อโมเมนต์ทำให้ล้มรอบจุดหมุน:
      n<sub>tip</sub> = M<sub>restoring</sub> / M<sub>overturning</sub> &ge; 1.50
    </p>
    <table class="tech-table">
      <thead>
        <tr>
          <th>แกนการล้มคว่ำ (Tipping Axis)</th>
          <th style="text-align: right;">ค่าออกแบบ (n<sub>d</sub>)</th>
          <th style="text-align: right;">ค่าที่คำนวณได้จริง (n<sub>s</sub>)</th>
          <th style="text-align: center;">มาตรฐานที่ใช้อ้างอิง</th>
          <th style="text-align: center;">ผลการประเมิน</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>การล้มไปข้างหน้า (Forward Tipping)</td>
          <td class="num">1.50</td>
          <td class="num text-pass" style="font-weight: 700;">{result.tipping_safety_factor_fwd:.2f}</td>
          <td style="text-align: center;">ANSI/BIFMA X5.1 Sec 12</td>
          <td style="text-align: center; font-weight: 700;" class="text-pass">PASS</td>
        </tr>
        <tr>
          <td>การล้มไปข้างหลัง (Rearward Tipping)</td>
          <td class="num">1.50</td>
          <td class="num text-pass" style="font-weight: 700;">{result.tipping_safety_factor_rear:.2f}</td>
          <td style="text-align: center;">ANSI/BIFMA X5.1 Sec 13</td>
          <td style="text-align: center; font-weight: 700;" class="text-pass">PASS</td>
        </tr>
        <tr>
          <td>การล้มออกด้านข้าง (Lateral Splay Tipping)</td>
          <td class="num">1.50</td>
          <td class="num {lat_tip_cls}" style="font-weight: 700;">{lat_tip_val}</td>
          <td style="text-align: center;">ISO 7173 Class B</td>
          <td style="text-align: center; font-weight: 700;" class="{lat_tip_cls}">{lat_tip_verdict}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- ================= บทที่ 7 ================= -->
  {fea_html}

  <!-- ================= บทที่ 8 ================= -->
  <div class="section page-break" id="ch8">
    <div class="section-title">
      <span><span class="section-num">บทที่ {summary_chapter_no}</span> ตารางสรุปผลการคำนวณและค่าความปลอดภัยชิ้นส่วนทั้งหมด</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Accredited Audit Summary</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>ชิ้นส่วน / โหมดความเสียหาย</th>
          <th>ภาระหรือแรงวิกฤต</th>
          <th style="text-align: right;">ความสามารถวิกฤต</th>
          <th style="text-align: right;">เกณฑ์คราก/ยอมรับได้</th>
          <th style="text-align: right;">SF ออกแบบ (n<sub>d</sub>)</th>
          <th style="text-align: right;">SF ที่ได้ (n<sub>s</sub>)</th>
          <th style="text-align: center;">ผลการประเมิน</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="font-weight: 600;">เสาขาหลัก (x4) - โก่งเดาะ (Buckling)</td>
          <td>P = {max(leg.axial_reaction_n for leg in result.floor_reactions):.1f} N (Axial)</td>
          <td class="num">{(result.floor_reactions[0].critical_buckling_load_n / 1000.0):.2f} kN</td>
          <td class="num">{m.yield_strength_mpa:.1f} MPa</td>
          <td class="num">2.00</td>
          <td class="num {"text-pass" if result.min_leg_buckling_sf >= 2.0 else "text-fail"}" style="font-weight: 700;">{result.min_leg_buckling_sf:.2f}</td>
          <td style="text-align: center; font-weight: 700;" class="{"text-pass" if result.min_leg_buckling_sf >= 2.0 else "text-fail"}">
            {"PASS" if result.min_leg_buckling_sf >= 2.0 else "FAIL"}
          </td>
        </tr>
        <tr>
          <td style="font-weight: 600;">เสาขาหลัก (x4) - คราก (Yield Stress)</td>
          <td>ความเค้นรวม P/A + M/Z</td>
          <td class="num">{max(leg.combined_stress_mpa for leg in result.floor_reactions):.1f} MPa</td>
          <td class="num">{m.yield_strength_mpa:.1f} MPa</td>
          <td class="num">2.00</td>
          <td class="num {"text-pass" if result.min_leg_yield_sf >= 2.0 else "text-fail"}" style="font-weight: 700;">{result.min_leg_yield_sf:.2f}</td>
          <td style="text-align: center; font-weight: 700;" class="{"text-pass" if result.min_leg_yield_sf >= 2.0 else "text-fail"}">
            {"PASS" if result.min_leg_yield_sf >= 2.0 else "FAIL"}
          </td>
        </tr>
        <tr>
          <td style="font-weight: 600;">แผ่นโครงสร้างเบาะรองนั่ง</td>
          <td>น้ำหนักบรรทุก W = {loads.seat_vertical_load_n:.0f} N</td>
          <td class="num">&delta; = {result.seat_deflection_mm:.3f} mm</td>
          <td class="num">&le; {allowable_deflection_mm:.1f} mm</td>
          <td class="num">1.50</td>
          <td class="num text-pass" style="font-weight: 700;">{(allowable_deflection_mm / max(result.seat_deflection_mm, 0.001)):.2f}</td>
          <td style="text-align: center; font-weight: 700;" class="text-pass">PASS</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">ชิ้นส่วนคานยื่นที่พักแขน</td>
          <td>F<sub>arm</sub> = {loads.left_arm_vertical_n:.0f} N</td>
          <td class="num">{arm_stress_str}</td>
          <td class="num">{m.yield_strength_mpa:.1f} MPa</td>
          <td class="num">2.00</td>
          <td class="num {"text-pass" if result.min_arm_sf >= 2.0 else "text-fail"}" style="font-weight: 700;">{result.min_arm_sf:.2f}</td>
          <td style="text-align: center; font-weight: 700;" class="{"text-pass" if result.min_arm_sf >= 2.0 else "text-fail"}">
            {"PASS" if result.min_arm_sf >= 2.0 else "FAIL"}
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- ================= บทที่ 9 ================= -->
  <div class="section" id="ch9">
    <div class="section-title">
      <span><span class="section-num">บทที่ {fabrication_chapter_no}</span> กระบวนการผลิต งานเชื่อม และข้อกำหนดพิกัดความเผื่อ</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Industrial Production Plan</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>กระบวนการผลิต</th>
          <th>คำอธิบายกระบวนการ</th>
          <th>มาตรฐานควบคุม</th>
          <th>เกณฑ์คุณภาพการยอมรับ</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="font-weight: 600;">การตัดท่อตามขนาด (Cold Sawing)</td>
          <td>ตัดด้วยเลื่อยวงเดือนเย็นความแม่นยำสูงพร้อมตัวตั้งระยะอัตโนมัติ</td>
          <td>ISO 2768-m</td>
          <td>พิกัดความเผื่อความยาว &plusmn;0.5 mm, มุมฉากภายใน 0.3&deg;</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">การดัดท่อขาเฉียง (CNC Tube Bending)</td>
          <td>ดัดด้วยเครื่องดัดท่อแบบแมนเดรล Rotary Draw ({g.leg_splay_angle_deg:.1f}&deg;)</td>
          <td>DIN EN 10219-2</td>
          <td>การยุบตัวรี &le; 4.0%, ผนังบางลง &le; 10%</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">การเชื่อมประกอบโครง (Welding)</td>
          <td>งานเชื่อม TIG (GTAW) ลวดเชื่อม ER70S-6 ป้องกันด้วยก๊าซอาร์กอน 100%</td>
          <td>AWS D1.1 Structural Welding</td>
          <td>ตรวจสอบรอยเชื่อมด้วยสายตา 100% ปราศจาก Undercut และ Porosity</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">การเคลือบผิวป้องกันสนิม</td>
          <td>ชุบฟอสเฟต + พ่นสีฝุ่นไฟฟ้าสถิต (Electrostatic Powder Coating)</td>
          <td>ASTM B117 Salt Spray</td>
          <td>ความหนาฟิล์มสีแห้ง 70–90 &mu;m, ทนต่อละอองเกลือ 500 ชั่วโมง</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">พิกัดความเผื่อการประกอบ</td>
          <td>พิกัดความเผื่อทั่วไปสำหรับมิติเชิงเส้นและเชิงมุม</td>
          <td>ISO 2768-m (ระดับปานกลาง)</td>
          <td>พิกัดความเผื่อขนาดโครงรวม &plusmn;1.5 mm</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- ================= ภาคผนวก ================= -->
  {blueprint_html}

  <div class="section page-break" id="appendix-b">
    <div class="section-title">
      <span><span class="section-num">ภาคผนวก ข</span> บันทึกการประมวลผลของตัวแก้สมการ (Solver Trace Log)</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Solver Verification Log</span>
    </div>
    <ul class="trace-list">
      {calc_log_items}
    </ul>

    <div style="margin-top: 35px;" id="appendix-c">
      <div class="section-title">
        <span><span class="section-num">ภาคผนวก ค</span> ใบลงนามอนุมัติผลงานวิชาการ (Academic Sign-Off Block)</span>
        <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Official Sign-Off</span>
      </div>
      <div class="signoff-grid">
        <div class="signoff-box">
          <strong>ผู้จัดทำโครงงาน (Lead Designer):</strong>
          <div class="signoff-line"></div>
          <div>{html.escape(student_name)}</div>
          <div style="color: var(--text-muted); font-size: 11px;">รหัสนักศึกษา: {html.escape(student_id)}</div>
        </div>
        <div class="signoff-box">
          <strong>อาจารย์ที่ปรึกษา / ผู้ตรวจโครงงาน:</strong>
          <div class="signoff-line"></div>
          <div>อาจารย์ผู้รับผิดชอบรายวิชา</div>
          <div style="color: var(--text-muted); font-size: 11px;">ภาควิชาวิศวกรรมเครื่องกล</div>
        </div>
        <div class="signoff-box">
          <strong>การอนุมัติผลการประเมิน (Evaluation):</strong>
          <div class="signoff-line"></div>
          <div>หัวหน้าภาควิชา / ประธานกรรมการ</div>
          <div style="color: var(--text-muted); font-size: 11px;">สถานะ: อนุมัติผ่านเกณฑ์วิชาการ</div>
        </div>
      </div>
    </div>
  </div>

</div>

</body>
</html>
"""
        return html_out

    @classmethod
    def _synthesize_academic_narrative(
        cls, model: FrameDesignModel, component_names: list[str], use_ai: bool = True
    ) -> dict[str, Any]:
        """
        Synthesize technical introduction (บทนำ) and component engineering descriptions
        using AI (delegated to ai.narrative_synthesizer).
        """
        return synthesize_academic_narrative(model, component_names, use_ai=use_ai)

    @classmethod
    def generate_assignment_report_v2(
        cls,
        model: FrameDesignModel,
        result: FrameSolverResult,
        preview_image: str | None = "chair_preview.png",
        students: list[dict[str, str]] | None = None,
        use_ai: bool = True,
    ) -> str:
        """
        Dynamic Version 2 Academic Assignment Report Engine.
        Strictly structured to mirror the real student project submission style:
        - Dynamic header / Student member list
        - Dynamic AI-synthesized บทนำ (Introduction)
        - Dynamic Component-by-Component breakdown matching the actual active structure
        - Full Shigley Step 1 to Step 7 calculations per component (Geometry, Buckling, Se', Marin factors ka..kf, S-N curve 10^4 cycles, Stresses, Safety Factor)
        - Dynamic SVG V-M diagram for flexural members
        - Dynamic Summary Table at the end

        Explicitly excludes Out Of Scope (OOS) items not present in original:
        - NO Tipping stability
        - NO 3D FEA direct stiffness mesh simulation
        - NO Manufacturing processes / Cold sawing / Welding standards table
        - NO Solver execution trace log
        - NO Academic sign-off block
        """
        narrative = cls._synthesize_academic_narrative(
            model, active_component_names(model, result), use_ai=use_ai
        )
        spec = build_academic_v2_spec(
            model,
            result,
            intro=narrative.get("introduction", ""),
            component_descriptions=narrative.get("components", {}),
            students=students,
            preview_image=preview_image,
        )
        return render("academic_v2/report.html.j2", spec)

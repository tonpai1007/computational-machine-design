"""Typed, renderer-agnostic report specifications.

A spec is plain data: numbers, labels and flags extracted from the design model
and the deterministic solver result. Templates own layout and numeric
precision; the spec owns the values. Nothing in this module formats a number
for display, so the same spec can feed an HTML dossier, a Markdown data sheet
or a future DOCX renderer without a second copy of the physics.

The rule from ``AGENTS.md`` applies here too: every engineering number must
come from ``FrameSolverResult``. The builders below only select and group
solver fields -- they never derive a stress, a safety factor or an endurance
limit.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.frame_model import FrameDesignModel, resolve_armrest_shared
from physics.frame_physics import FrameSolverResult


class StudentSpec(BaseModel):
    name: str = ""
    student_id: str = ""


class MaterialSpec(BaseModel):
    name: str
    density_g_cm3: float
    ultimate_strength_mpa: float
    yield_strength_mpa: float
    elastic_modulus_gpa: float
    poissons_ratio: float


class SummaryRowSpec(BaseModel):
    """One row of the dossier's final safety-factor table."""

    name: str
    design_factor: float
    safety_factor: float
    passed: bool


class LegSpec(BaseModel):
    part_no: int
    count: int
    description: str
    thickness_m: float
    length_m: float
    outer_diameter_m: float
    inner_diameter_m: float
    outer_diameter_mm: float
    area_m2: float
    inertia_m4: float
    radius_of_gyration_m: float
    k_factor: float
    effective_length_m: float
    slenderness: float
    transition_slenderness: float
    end_condition_c: float
    is_slender: bool
    critical_load_n: float
    critical_load_kn: float
    sigma_f_prime_mpa: float
    endurance_limit_prime_mpa: float
    surface_factor_ka: float
    size_factor_kb: float
    load_factor_kc: float
    temperature_factor_kd: float
    reliability_factor_ke: float
    other_factor_kf: float
    endurance_limit_mpa: float
    fatigue_strength_coefficient_mpa: float
    fatigue_strength_exponent: float
    fatigue_strength_at_1e4_mpa: float
    fatigue_strength_ratio_percent: float
    fatigue_yield_strength_mpa: float
    max_reaction_n: float
    axial_stress_mpa: float
    max_combined_stress_mpa: float
    buckling_safety_factor: float
    yield_safety_factor: float


class RailSpec(BaseModel):
    part_no: int
    description: str
    thickness_m: float
    width_m: float
    height_m: float
    span_m: float
    profile_outer_mm: float
    profile_wall_mm: float
    area_m2: float
    inertia_m4: float
    extreme_fibre_m: float
    section_modulus_m3: float
    applied_load_n: float
    support_reaction_n: float
    max_moment_nm: float
    max_bending_stress_mpa: float
    max_shear_stress_mpa: float
    max_principal_stress_mpa: float
    deflection_mm: float
    deflection_limit_mm: float
    deflection_ok: bool
    size_factor_kb: float
    load_factor_kc: float
    endurance_limit_mpa: float
    fatigue_strength_at_1e4_mpa: float
    fatigue_strength_ratio_percent: float
    fatigue_yield_strength_mpa: float
    safety_factor: float
    seat_load_n: float


class StretcherSpec(BaseModel):
    part_no: int
    description: str
    thickness_m: float
    length_m: float
    outer_diameter_m: float
    inner_diameter_m: float
    profile_outer_mm: float
    profile_wall_mm: float
    area_m2: float
    inertia_m4: float
    extreme_fibre_m: float
    section_modulus_m3: float
    radius_of_gyration_m: float
    k_factor: float
    effective_length_m: float
    slenderness: float
    transition_slenderness: float
    is_johnson: bool
    axial_force_n: float
    critical_load_n: float
    critical_load_kn: float
    axial_stress_mpa: float
    yield_safety_factor: float
    buckling_safety_factor: float
    governing_safety_factor: float
    backrest_force_n: float


class ArmSpec(BaseModel):
    part_no: int
    description: str
    thickness_m: float
    outer_diameter_m: float
    inner_diameter_m: float
    outer_diameter_mm: float
    profile_wall_mm: float
    overhang_m: float
    area_m2: float
    area_mm2: float
    inertia_m4: float
    extreme_fibre_m: float
    section_modulus_m3: float
    section_modulus_mm3: float
    front_post_y_mm: float
    rear_post_y_mm: float
    load_y_mm: float
    front_fraction: float
    rear_fraction: float
    governing_post_force_n: float
    rear_post_force_n: float
    applied_vertical_n: float
    applied_lateral_n: float
    post_height_m: float
    cantilever_moment_nm: float
    base_moment_nm: float
    axial_stress_mpa: float
    bending_stress_mpa: float
    combined_stress_mpa: float
    size_factor_kb: float
    load_factor_kc: float
    endurance_limit_mpa: float
    fatigue_strength_at_1e4_mpa: float
    fatigue_strength_ratio_percent: float
    fatigue_yield_strength_mpa: float
    safety_factor: float


class BracketSpec(BaseModel):
    part_no: int
    length_mm: float
    thickness_mm: float
    height_mm: float
    inertia_mm4: float
    extreme_fibre_mm: float
    section_modulus_mm3: float
    section_area_mm2: float
    post_axial_n: float
    post_base_moment_nm: float
    axial_stress_mpa: float
    bending_stress_mpa: float
    combined_stress_mpa: float
    safety_factor: float
    surface_factor_ka: float
    size_factor_kb: float
    load_factor_kc: float
    temperature_factor_kd: float
    reliability_factor_ke: float
    other_factor_kf: float
    endurance_limit_mpa: float
    endurance_safety_factor: float


class AcademicV2Spec(BaseModel):
    """Everything the v2 assignment dossier needs, with no HTML in it."""

    title: str
    design_name: str
    students: list[StudentSpec] = Field(default_factory=list)
    intro_paragraphs: list[str] = Field(default_factory=list)
    preview_image: str | None = None
    cad_caption: str = "รูปจำลอง 3 มิติโครงสร้าง (3D Parametric CAD Solid Assembly Model)"
    material: MaterialSpec
    self_weight_n: float
    total_downward_load_n: float
    legs: LegSpec
    rail: RailSpec
    stretcher: StretcherSpec | None = None
    arm: ArmSpec | None = None
    bracket: BracketSpec | None = None
    summary_rows: list[SummaryRowSpec] = Field(default_factory=list)


def active_component_names(model: FrameDesignModel, result: FrameSolverResult) -> list[str]:
    """The components actually present in this model, for the narrative prompt."""
    g = model.geometry
    names = [f"เสาขาโครงสร้างหลัก ({g.num_legs} ขา)", "คานโครงสร้างรองรับเบาะนั่ง"]
    if g.has_stretchers:
        names.append("คานค้ำยันรอบล่าง")
    if g.has_arms and result.armrests:
        names.append("ชุดโครงสร้างคานยื่นที่พักแขน")
        names.append("แผ่นยึดเสาพักแขน")
    return names


def _material_spec(model: FrameDesignModel) -> MaterialSpec:
    m = model.material
    return MaterialSpec(
        name=m.name,
        density_g_cm3=m.density_kg_m3 / 1000.0,
        ultimate_strength_mpa=m.ultimate_strength_mpa,
        yield_strength_mpa=m.yield_strength_mpa,
        elastic_modulus_gpa=m.elastic_modulus_gpa,
        poissons_ratio=m.poissons_ratio,
    )


def _leg_spec(
    model: FrameDesignModel, result: FrameSolverResult, part_no: int, description: str
) -> LegSpec:
    g = model.geometry
    leg = result.floor_reactions[0]
    buck, fatigue = leg.buckling, leg.fatigue
    governing = max(result.floor_reactions, key=lambda r: r.axial_reaction_n)
    profile = g.leg_profile
    return LegSpec(
        part_no=part_no,
        count=g.num_legs,
        description=description,
        thickness_m=profile.wall_thick_m,
        length_m=buck.length_m,
        outer_diameter_m=profile.outer_dim_m,
        inner_diameter_m=max(0.0, profile.outer_dim_m - 2.0 * profile.wall_thick_m),
        outer_diameter_mm=profile.outer_dimension_mm,
        area_m2=buck.area_m2,
        inertia_m4=buck.moment_of_inertia_m4,
        radius_of_gyration_m=buck.radius_of_gyration_m,
        k_factor=buck.k_factor,
        effective_length_m=buck.effective_length_m,
        slenderness=buck.slenderness_ratio,
        transition_slenderness=buck.transition_slenderness_ratio,
        end_condition_c=buck.end_condition_c,
        is_slender=buck.is_slender_euler,
        critical_load_n=buck.critical_buckling_load_n,
        critical_load_kn=buck.critical_buckling_load_n / 1000.0,
        sigma_f_prime_mpa=fatigue.fatigue_strength_prime_mpa,
        endurance_limit_prime_mpa=fatigue.endurance_limit_prime_mpa,
        surface_factor_ka=fatigue.surface_factor_ka,
        size_factor_kb=fatigue.size_factor_kb,
        load_factor_kc=fatigue.load_factor_kc,
        temperature_factor_kd=fatigue.temperature_factor_kd,
        reliability_factor_ke=fatigue.reliability_factor_ke,
        other_factor_kf=fatigue.other_factor_kf,
        endurance_limit_mpa=fatigue.endurance_limit_mpa,
        fatigue_strength_coefficient_mpa=fatigue.fatigue_strength_coefficient_mpa,
        fatigue_strength_exponent=fatigue.fatigue_strength_exponent,
        fatigue_strength_at_1e4_mpa=fatigue.fatigue_strength_at_1e4_mpa,
        fatigue_strength_ratio_percent=fatigue.fatigue_strength_ratio_percent,
        fatigue_yield_strength_mpa=fatigue.fatigue_yield_strength_mpa,
        max_reaction_n=governing.axial_reaction_n,
        axial_stress_mpa=governing.compressive_stress_mpa,
        max_combined_stress_mpa=max(r.combined_stress_mpa for r in result.floor_reactions),
        buckling_safety_factor=result.min_leg_buckling_sf,
        yield_safety_factor=result.min_leg_yield_sf,
    )


def _rail_spec(
    model: FrameDesignModel, result: FrameSolverResult, part_no: int, description: str
) -> RailSpec:
    g = model.geometry
    frame = g.frame_profile
    rail = result.seat_frame
    beam, fatigue = rail.beam, rail.fatigue
    return RailSpec(
        part_no=part_no,
        description=description,
        thickness_m=frame.wall_thick_m,
        width_m=frame.outer_dim_m,
        height_m=frame.outer_dim_m,
        span_m=beam.span_m,
        profile_outer_mm=frame.outer_dimension_mm,
        profile_wall_mm=frame.wall_thickness_mm,
        area_m2=beam.section_area_m2,
        inertia_m4=beam.moment_of_inertia_m4,
        extreme_fibre_m=beam.extreme_fibre_m,
        section_modulus_m3=beam.section_modulus_m3,
        applied_load_n=beam.applied_load_n,
        support_reaction_n=beam.support_reaction_n,
        max_moment_nm=beam.max_moment_nm,
        max_bending_stress_mpa=beam.max_bending_stress_mpa,
        max_shear_stress_mpa=beam.max_shear_stress_mpa,
        max_principal_stress_mpa=beam.max_principal_stress_mpa,
        deflection_mm=beam.deflection_mm,
        deflection_limit_mm=beam.deflection_limit_mm,
        deflection_ok=beam.deflection_passed,
        size_factor_kb=fatigue.size_factor_kb,
        load_factor_kc=fatigue.load_factor_kc,
        endurance_limit_mpa=fatigue.endurance_limit_mpa,
        fatigue_strength_at_1e4_mpa=fatigue.fatigue_strength_at_1e4_mpa,
        fatigue_strength_ratio_percent=fatigue.fatigue_strength_ratio_percent,
        fatigue_yield_strength_mpa=fatigue.fatigue_yield_strength_mpa,
        safety_factor=rail.rail_safety_factor,
        seat_load_n=model.loads.seat_vertical_load_n,
    )


def _stretcher_spec(
    model: FrameDesignModel, result: FrameSolverResult, part_no: int, description: str
) -> StretcherSpec | None:
    g = model.geometry
    if not (g.has_stretchers and result.stretchers):
        return None
    stretcher = result.stretchers[0]
    buck = stretcher.buckling
    profile = g.stretcher_profile
    return StretcherSpec(
        part_no=part_no,
        description=description,
        thickness_m=profile.wall_thick_m,
        length_m=buck.length_m,
        outer_diameter_m=profile.outer_dim_m,
        inner_diameter_m=max(0.0, profile.outer_dim_m - 2.0 * profile.wall_thick_m),
        profile_outer_mm=profile.outer_dimension_mm,
        profile_wall_mm=profile.wall_thickness_mm,
        area_m2=buck.area_m2,
        inertia_m4=buck.moment_of_inertia_m4,
        extreme_fibre_m=buck.extreme_fibre_m,
        section_modulus_m3=buck.section_modulus_m3,
        radius_of_gyration_m=buck.radius_of_gyration_m,
        k_factor=buck.k_factor,
        effective_length_m=buck.effective_length_m,
        slenderness=buck.slenderness_ratio,
        transition_slenderness=buck.transition_slenderness_ratio,
        is_johnson=not buck.is_slender_euler,
        axial_force_n=stretcher.axial_force_n,
        critical_load_n=buck.critical_buckling_load_n,
        critical_load_kn=buck.critical_buckling_load_n / 1000.0,
        axial_stress_mpa=stretcher.axial_stress_mpa,
        yield_safety_factor=stretcher.yield_safety_factor,
        buckling_safety_factor=buck.buckling_safety_factor,
        governing_safety_factor=stretcher.governing_safety_factor,
        backrest_force_n=model.loads.backrest_force_n,
    )


def _arm_spec(
    model: FrameDesignModel, result: FrameSolverResult, part_no: int, description: str
) -> ArmSpec | None:
    g = model.geometry
    if not (g.has_arms and result.armrests):
        return None
    arm = result.armrests[0]
    fatigue = arm.fatigue
    profile = g.arm_profile
    ag = resolve_armrest_shared(g)
    outer_m = profile.outer_dim_m
    inner_m = max(0.0, outer_m - 2.0 * profile.wall_thick_m)
    return ArmSpec(
        part_no=part_no,
        description=description,
        thickness_m=profile.wall_thick_m,
        outer_diameter_m=outer_m,
        inner_diameter_m=inner_m,
        outer_diameter_mm=profile.outer_dimension_mm,
        profile_wall_mm=profile.wall_thickness_mm,
        overhang_m=arm.overhang_m,
        area_m2=arm.section_area_m2,
        area_mm2=arm.section_area_m2 * 1e6,
        inertia_m4=arm.moment_of_inertia_m4,
        extreme_fibre_m=arm.extreme_fibre_m,
        section_modulus_m3=arm.section_modulus_m3,
        section_modulus_mm3=arm.section_modulus_m3 * 1e9,
        front_post_y_mm=ag.front_post_y_mm,
        rear_post_y_mm=ag.rear_post_y_mm,
        load_y_mm=arm.load_y_mm,
        front_fraction=arm.front_reaction_fraction,
        rear_fraction=arm.rear_reaction_fraction,
        governing_post_force_n=arm.governing_axial_n,
        rear_post_force_n=arm.rear_axial_n,
        applied_vertical_n=arm.applied_vertical_n,
        applied_lateral_n=arm.applied_lateral_n,
        post_height_m=arm.post_height_m,
        cantilever_moment_nm=arm.overhang_moment_nm,
        base_moment_nm=arm.strut_base_moment_nm,
        axial_stress_mpa=arm.strut_axial_stress_mpa,
        bending_stress_mpa=arm.strut_bending_stress_mpa,
        combined_stress_mpa=arm.strut_combined_stress_mpa,
        size_factor_kb=fatigue.size_factor_kb,
        load_factor_kc=fatigue.load_factor_kc,
        endurance_limit_mpa=fatigue.endurance_limit_mpa,
        fatigue_strength_at_1e4_mpa=fatigue.fatigue_strength_at_1e4_mpa,
        fatigue_strength_ratio_percent=fatigue.fatigue_strength_ratio_percent,
        fatigue_yield_strength_mpa=fatigue.fatigue_yield_strength_mpa,
        safety_factor=arm.arm_safety_factor,
    )


def _bracket_spec(
    model: FrameDesignModel, result: FrameSolverResult, part_no: int
) -> BracketSpec | None:
    if not result.arm_brackets:
        return None
    bracket = result.arm_brackets[0]
    fatigue = bracket.fatigue
    g = model.geometry
    ag = resolve_armrest_shared(g)
    return BracketSpec(
        part_no=part_no,
        length_mm=ag.bracket_len_mm,
        thickness_mm=g.armrest_bracket_thickness_mm,
        height_mm=g.armrest_bracket_height_mm,
        inertia_mm4=bracket.section_inertia_mm4,
        extreme_fibre_mm=bracket.extreme_fibre_mm,
        section_modulus_mm3=bracket.section_modulus_mm3,
        section_area_mm2=bracket.section_area_mm2,
        post_axial_n=bracket.post_axial_n,
        post_base_moment_nm=bracket.post_base_moment_nm,
        axial_stress_mpa=bracket.axial_stress_mpa,
        bending_stress_mpa=bracket.bending_stress_mpa,
        combined_stress_mpa=bracket.combined_stress_mpa,
        safety_factor=bracket.bracket_safety_factor,
        surface_factor_ka=fatigue.surface_factor_ka,
        size_factor_kb=fatigue.size_factor_kb,
        load_factor_kc=fatigue.load_factor_kc,
        temperature_factor_kd=fatigue.temperature_factor_kd,
        reliability_factor_ke=fatigue.reliability_factor_ke,
        other_factor_kf=fatigue.other_factor_kf,
        endurance_limit_mpa=fatigue.endurance_limit_mpa,
        endurance_safety_factor=fatigue.endurance_safety_factor or 0.0,
    )


def build_academic_v2_spec(
    model: FrameDesignModel,
    result: FrameSolverResult,
    *,
    intro: str = "",
    component_descriptions: dict[str, str] | None = None,
    students: list[dict[str, str]] | None = None,
    preview_image: str | None = None,
) -> AcademicV2Spec:
    """Collect every value the v2 dossier renders into one plain-data object."""
    descriptions = component_descriptions or {}
    g = model.geometry
    part_no = 1
    summary: list[SummaryRowSpec] = []

    legs = _leg_spec(
        model,
        result,
        part_no,
        descriptions.get(
            "columns",
            f"ทำหน้าที่ถ่ายทอดน้ำหนักบรรทุกแนวดิ่งทั้งหมดลงสู่พื้นผิวสัมผัส จัดวางจำนวน {g.num_legs} เสา",
        ),
    )
    summary.append(
        SummaryRowSpec(
            name=f"{part_no}. เสาขาโครงสร้างหลัก (Buckling Pcr)",
            design_factor=2.00,
            safety_factor=legs.buckling_safety_factor,
            passed=legs.buckling_safety_factor >= 2.0,
        )
    )
    summary.append(
        SummaryRowSpec(
            name="   เสาขาโครงสร้างหลัก (Yield Stress)",
            design_factor=1.50,
            safety_factor=legs.yield_safety_factor,
            passed=legs.yield_safety_factor >= 1.5,
        )
    )
    part_no += 1

    rail = _rail_spec(
        model,
        result,
        part_no,
        descriptions.get(
            "seat_rails",
            "ทำหน้าที่รองรับแรงกดกระจายตัวสม่ำเสมอด้านบนและส่งถ่ายแรงไปยังหัวเสารองรับ",
        ),
    )
    summary.append(
        SummaryRowSpec(
            name=f"{part_no}. คานโครงสร้างรองรับเบาะนั่ง",
            design_factor=2.00,
            safety_factor=rail.safety_factor,
            passed=rail.safety_factor >= 2.0,
        )
    )
    part_no += 1

    stretcher = _stretcher_spec(
        model,
        result,
        part_no,
        descriptions.get(
            "stretchers",
            "ทำหน้าที่ยึดตรึงระหว่างเสาโครงสร้างเพื่อลดความยาวประสิทธิผลของเสา "
            "และรับแรงดันตามแกนจากพลังหลังนั่ง โดยการโก่งเดาะเป็นตัวกำหนดความแข็งแรง",
        ),
    )
    if stretcher is not None:
        summary.append(
            SummaryRowSpec(
                name=f"{part_no}. คานค้ำยันรอบล่าง (Stretcher)",
                design_factor=2.00,
                safety_factor=stretcher.governing_safety_factor,
                passed=stretcher.governing_safety_factor >= 2.0,
            )
        )
        part_no += 1

    arm = _arm_spec(
        model,
        result,
        part_no,
        descriptions.get(
            "armrests", "ทำหน้าที่รองรับแรงกดแนวดิ่งและแรงผลักด้านข้างจากแขนผู้ใช้งาน"
        ),
    )
    bracket = None
    if arm is not None:
        summary.append(
            SummaryRowSpec(
                name=f"{part_no}. ชุดโครงสร้างคานยื่นที่พักแขน",
                design_factor=2.00,
                safety_factor=arm.safety_factor,
                passed=arm.safety_factor >= 2.0,
            )
        )
        part_no += 1
        bracket = _bracket_spec(model, result, part_no)
        if bracket is not None:
            summary.append(
                SummaryRowSpec(
                    name=f"{part_no}. แผ่นยึดเสาพักแขน",
                    design_factor=2.00,
                    safety_factor=bracket.safety_factor,
                    passed=bracket.safety_factor >= 2.0,
                )
            )
            part_no += 1

    resolved_preview = (
        preview_image if preview_image and Path(preview_image).exists() else None
    )
    return AcademicV2Spec(
        title=f"รายงานโครงงานการออกแบบเครื่องจักรกล - {model.name}",
        design_name=model.name,
        students=[
            StudentSpec(name=s.get("name", ""), student_id=s.get("id", ""))
            for s in (students or [])
        ],
        intro_paragraphs=intro.split("\n\n"),
        preview_image=resolved_preview,
        material=_material_spec(model),
        self_weight_n=result.total_chair_weight_n,
        total_downward_load_n=result.total_downward_load_n,
        legs=legs,
        rail=rail,
        stretcher=stretcher,
        arm=arm,
        bracket=bracket,
        summary_rows=summary,
    )

"""Deterministic member-level checks shared by the frame solver and its reports.

Everything a report displays has to be produced here (or in the solver). A
renderer may format a number; it must never derive one. These are the checks
that used to live inside ``reporting/academic_engine.py`` and
``reporting/frame_data_sheet.py``: section properties, Euler/Johnson buckling,
Marin-corrected endurance limits, Basquin S-N constants, the simply supported
beam check for the seat rails, and the compression check for the stretchers.

Authority: Physics verifies.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from core.frame_model import StructuralMaterial, TubeProfile
from physics.buckling import ColumnBuckling
from physics.fatigue import FatigueSolver, MarinFactors, RepeatedLoadResult


class FatigueAssessment(BaseModel):
    """Marin-corrected endurance limit and the Basquin S-N curve constants.

    A report prints these; it must not re-derive ``Se`` from ``Sut`` itself,
    because a second copy of the Marin chain is how the bracket numbers drifted
    between the dossier and the data sheet.
    """

    ultimate_strength_mpa: float
    yield_strength_mpa: float
    endurance_limit_prime_mpa: float = Field(..., description="Se' = 0.5 Sut (MPa)")
    fatigue_strength_prime_mpa: float = Field(..., description="sigma_f' = 1.5 Sut (MPa)")
    surface_factor_ka: float
    size_factor_kb: float
    load_factor_kc: float
    temperature_factor_kd: float
    reliability_factor_ke: float
    other_factor_kf: float
    endurance_limit_mpa: float = Field(..., description="Fully corrected Se (MPa)")
    fatigue_strength_coefficient_mpa: float = Field(..., description="Basquin a (MPa)")
    fatigue_strength_exponent: float = Field(..., description="Basquin b")
    fatigue_strength_at_1e4_mpa: float = Field(..., description="Sf at N = 1e4 (MPa)")
    fatigue_strength_ratio_percent: float = Field(..., description="Sf / Sut x 100")
    fatigue_yield_strength_mpa: float = Field(..., description="Sy' = (Sf / Sut) Sy (MPa)")
    stress_mpa: float | None = Field(
        default=None, description="Peak stress the endurance limit is compared against (MPa)"
    )
    endurance_safety_factor: float | None = Field(
        default=None, description="Se / stress_mpa (dimensionless)"
    )
    repeated_load: RepeatedLoadResult | None = Field(
        default=None,
        description="Pulsating (R = 0) Goodman/Gerber/Soderberg assessment at stress_mpa",
    )


def assess_fatigue(
    material: StructuralMaterial,
    *,
    diameter_mm: float,
    load_type: str = "bending",
    reliability: float = 0.90,
    surface_type: str = "machined",
    stress_mpa: float | None = None,
    stress_ratio_r: float = 0.0,
) -> FatigueAssessment:
    """Build the complete fatigue assessment for one member.

    ``diameter_mm`` is the member's governing section dimension: the tube OD for
    a round member, or the plate length for the arm bracket (the dimension the
    data sheet has always used for ``kb``).
    """
    sut = float(material.ultimate_strength_mpa)
    sy = float(material.yield_strength_mpa)

    se_prime = 0.5 * sut
    sigma_f_prime = 1.5 * sut

    ka = MarinFactors.surface_factor(sut, surface_type)
    kb = MarinFactors.size_factor(diameter_mm / 1000.0)
    kc = MarinFactors.load_factor(load_type)
    kd = 1.0
    ke = MarinFactors.reliability_factor(reliability)
    kf = 1.0

    se = ka * kb * kc * kd * ke * kf * se_prime

    # Basquin S-N curve through (10^3, f Sut) and (10^6, Se), f = 0.9.
    f_factor = 0.90
    a_coeff = ((f_factor * sut * 1e6) ** 2) / (se * 1e6) / 1e6
    b_exp = -(1.0 / 3.0) * math.log10((f_factor * sut) / se)
    sf = a_coeff * (10000.0**b_exp)
    sf_ratio = (sf / sut) * 100.0
    sy_fatigue = (sf / sut) * sy

    n_endurance: float | None = None
    repeated: RepeatedLoadResult | None = None
    if stress_mpa is not None:
        n_endurance = se / stress_mpa if stress_mpa > 0.0 else None
        repeated = FatigueSolver.repeated_load_fatigue(
            sigma_max_mpa=stress_mpa,
            s_ut_mpa=sut,
            s_y_mpa=sy,
            s_e_mpa=se,
            stress_ratio_r=stress_ratio_r,
        )

    return FatigueAssessment(
        ultimate_strength_mpa=sut,
        yield_strength_mpa=sy,
        endurance_limit_prime_mpa=se_prime,
        fatigue_strength_prime_mpa=sigma_f_prime,
        surface_factor_ka=ka,
        size_factor_kb=kb,
        load_factor_kc=kc,
        temperature_factor_kd=kd,
        reliability_factor_ke=ke,
        other_factor_kf=kf,
        endurance_limit_mpa=se,
        fatigue_strength_coefficient_mpa=a_coeff,
        fatigue_strength_exponent=b_exp,
        fatigue_strength_at_1e4_mpa=sf,
        fatigue_strength_ratio_percent=sf_ratio,
        fatigue_yield_strength_mpa=sy_fatigue,
        stress_mpa=stress_mpa,
        endurance_safety_factor=n_endurance,
        repeated_load=repeated,
    )


class BucklingAssessment(BaseModel):
    """Euler/Johnson column check plus the section data it was run on."""

    length_m: float
    effective_length_m: float
    k_factor: float
    area_m2: float
    moment_of_inertia_m4: float
    radius_of_gyration_m: float
    section_modulus_m3: float
    extreme_fibre_m: float
    slenderness_ratio: float
    transition_slenderness_ratio: float
    end_condition_c: float
    is_slender_euler: bool
    critical_buckling_load_n: float
    applied_load_n: float
    buckling_safety_factor: float
    passed: bool
    formula_used: str
    calculation_notes: str


def assess_buckling(
    profile: TubeProfile,
    material: StructuralMaterial,
    *,
    length_m: float,
    applied_load_n: float,
    k_factor: float = 1.0,
    min_safety_factor: float = 2.0,
) -> BucklingAssessment:
    """Run :class:`ColumnBuckling` and attach the section properties it used."""
    result = ColumnBuckling.calculate(
        elastic_modulus_pa=material.elastic_modulus_gpa * 1e9,
        yield_strength_pa=material.yield_strength_mpa * 1e6,
        area_m2=profile.area_m2,
        moment_of_inertia_m4=profile.moment_of_inertia_m4,
        length_m=length_m,
        applied_load_n=applied_load_n,
        k_factor=k_factor,
        min_safety_factor=min_safety_factor,
    )
    return BucklingAssessment(
        length_m=length_m,
        effective_length_m=k_factor * length_m,
        k_factor=k_factor,
        area_m2=profile.area_m2,
        moment_of_inertia_m4=profile.moment_of_inertia_m4,
        radius_of_gyration_m=profile.radius_of_gyration_m,
        section_modulus_m3=profile.section_modulus_m3,
        extreme_fibre_m=profile.outer_dim_m / 2.0,
        slenderness_ratio=result.slenderness_ratio,
        transition_slenderness_ratio=result.transition_slenderness_cc,
        end_condition_c=result.end_condition_c,
        is_slender_euler=result.is_slender_euler,
        critical_buckling_load_n=result.critical_buckling_load_n,
        applied_load_n=result.applied_load_n,
        buckling_safety_factor=result.buckling_safety_factor,
        passed=result.passed,
        formula_used=result.formula_used,
        calculation_notes=result.calculation_notes,
    )


class BeamAssessment(BaseModel):
    """Simply supported beam with a central point load: ``M = PL/4``.

    This is the seat-rail idealisation. The shear and principal stresses are
    included because the dossier reports them, and they must come from the same
    run as the bending stress.
    """

    span_m: float
    applied_load_n: float
    support_reaction_n: float
    max_moment_nm: float
    section_area_m2: float
    moment_of_inertia_m4: float
    extreme_fibre_m: float
    section_modulus_m3: float
    web_area_m2: float
    max_bending_stress_mpa: float
    max_shear_stress_mpa: float
    max_principal_stress_mpa: float
    deflection_mm: float
    deflection_limit_mm: float
    deflection_safety_factor: float
    deflection_passed: bool
    yield_safety_factor: float
    passed: bool


def assess_simply_supported_beam(
    profile: TubeProfile,
    material: StructuralMaterial,
    *,
    span_m: float,
    applied_load_n: float,
    deflection_limit_mm: float,
    min_safety_factor: float = 2.0,
) -> BeamAssessment:
    """Central point load on a simply supported span, checked for bending and sag."""
    p = float(applied_load_n)
    reaction = p / 2.0
    m_max = (p * span_m) / 4.0

    extreme_fibre_m = profile.outer_dim_m / 2.0
    sigma_bend_mpa = (m_max / max(profile.section_modulus_m3, 1e-12)) / 1e6

    # Web area carrying the vertical shear: two walls of the tube.
    web_area_m2 = 2.0 * profile.outer_dim_m * max(profile.wall_thick_m, 1e-9)
    tau_max_mpa = (reaction / max(web_area_m2, 1e-12)) / 1e6
    sigma_principal_mpa = (sigma_bend_mpa / 2.0) + math.sqrt(
        (sigma_bend_mpa / 2.0) ** 2 + tau_max_mpa**2
    )

    deflection_m = (p * (span_m**3)) / (
        48.0
        * (material.elastic_modulus_gpa * 1e9)
        * max(profile.moment_of_inertia_m4, 1e-12)
    )
    deflection_mm = deflection_m * 1000.0
    deflection_sf = deflection_limit_mm / max(deflection_mm, 0.001)
    deflection_passed = deflection_mm < deflection_limit_mm

    sf = material.yield_strength_mpa / max(sigma_bend_mpa, 0.01)
    return BeamAssessment(
        span_m=span_m,
        applied_load_n=p,
        support_reaction_n=reaction,
        max_moment_nm=m_max,
        section_area_m2=profile.area_m2,
        moment_of_inertia_m4=profile.moment_of_inertia_m4,
        extreme_fibre_m=extreme_fibre_m,
        section_modulus_m3=profile.section_modulus_m3,
        web_area_m2=web_area_m2,
        max_bending_stress_mpa=sigma_bend_mpa,
        max_shear_stress_mpa=tau_max_mpa,
        max_principal_stress_mpa=sigma_principal_mpa,
        deflection_mm=deflection_mm,
        deflection_limit_mm=deflection_limit_mm,
        deflection_safety_factor=deflection_sf,
        deflection_passed=deflection_passed,
        yield_safety_factor=sf,
        passed=(sf >= min_safety_factor and deflection_passed),
    )


class CompressionMemberAssessment(BaseModel):
    """Axial compression member: buckling governs, yield is reported alongside."""

    member_id: str
    length_m: float
    axial_force_n: float
    buckling: BucklingAssessment
    axial_stress_mpa: float
    yield_safety_factor: float
    governing_safety_factor: float
    passed: bool


def assess_compression_member(
    profile: TubeProfile,
    material: StructuralMaterial,
    *,
    member_id: str,
    length_m: float,
    axial_force_n: float,
    k_factor: float = 1.0,
    min_safety_factor: float = 2.0,
) -> CompressionMemberAssessment:
    """Buckling + axial yield for a strut such as the lower stretcher."""
    buckling = assess_buckling(
        profile,
        material,
        length_m=length_m,
        applied_load_n=axial_force_n,
        k_factor=k_factor,
        min_safety_factor=min_safety_factor,
    )
    sigma = (abs(axial_force_n) / max(profile.area_m2, 1e-12)) / 1e6
    sf_yield = material.yield_strength_mpa / max(sigma, 0.01)
    governing = min(sf_yield, buckling.buckling_safety_factor)
    return CompressionMemberAssessment(
        member_id=member_id,
        length_m=length_m,
        axial_force_n=abs(axial_force_n),
        buckling=buckling,
        axial_stress_mpa=sigma,
        yield_safety_factor=sf_yield,
        governing_safety_factor=governing,
        passed=(governing >= min_safety_factor),
    )


class BackrestPostAssessment(BaseModel):
    """Horizontal backrest thrust bending a post about its base.

    The thrust is horizontal, so its moment arm is the post's vertical rise
    ``cos(tilt)``, not the horizontal lean ``sin(tilt)``.
    """

    applied_force_n: float
    moment_arm_mm: float
    section_area_mm2: float
    section_modulus_mm3: float
    bending_stress_mpa: float
    axial_stress_mpa: float
    combined_stress_mpa: float
    safety_factor: float
    passed: bool


def assess_backrest_post(
    profile: TubeProfile,
    material: StructuralMaterial,
    *,
    backrest_force_n: float,
    height_above_seat_mm: float,
    angle_deg: float,
    min_safety_factor: float = 2.0,
) -> BackrestPostAssessment:
    """Split the backrest thrust across two posts and check combined stress."""
    force = abs(backrest_force_n) / 2.0
    arm_mm = height_above_seat_mm * math.cos(math.radians(angle_deg - 90.0))

    area_mm2 = profile.area_m2 * 1e6
    z_mm3 = profile.moment_of_inertia_m4 * 1e12 / max(profile.outer_dimension_mm / 2.0, 1e-9)

    sigma_bend = force * arm_mm / max(z_mm3, 1e-12)
    sigma_axial = force / max(area_mm2, 1e-12)
    combined = sigma_bend + sigma_axial
    sf = material.yield_strength_mpa / max(combined, 0.01)
    return BackrestPostAssessment(
        applied_force_n=force,
        moment_arm_mm=arm_mm,
        section_area_mm2=area_mm2,
        section_modulus_mm3=z_mm3,
        bending_stress_mpa=sigma_bend,
        axial_stress_mpa=sigma_axial,
        combined_stress_mpa=combined,
        safety_factor=sf,
        passed=(sf >= min_safety_factor),
    )

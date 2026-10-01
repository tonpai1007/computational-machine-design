"""
MDIE Open-Ended Generative Engineering Agent
Generates parametric CAD, solves deterministic physics, and outputs technical 2D blueprints
on the fly from any natural language prompt.
"""

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from cad.gears_cad import GearCADGenerator
from cad.springs_cad import SpringCADGenerator
from components.bolted_joints import BoltedJointSpecification
from components.gears import GearPairSpecification
from components.power_screws import PowerScrewSpecification
from components.springs import SpringSpecification
from drafting.blueprint_2d import Blueprint2DGenerator
from materials.database import MaterialDatabase
from physics.bolted_joints import BoltedJointSolver

# Specialized physics engines for exact closed-form standards
from physics.gears import GearSolver
from physics.power_screws import PowerScrewSolver
from physics.springs import SpringSolver

# Preferred (catalogue) size series, ascending. A designer specifies a standard
# size rather than an arbitrary one, so when a prompt does not name a size the
# solver walks these upward until its own deterministic criteria are satisfied.
GEAR_MODULES_MM: tuple[float, ...] = (1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0)
SPRING_WIRE_DIAMETERS_MM: tuple[float, ...] = (
    0.8,
    1.0,
    1.2,
    1.6,
    2.0,
    2.5,
    3.0,
    3.5,
    4.0,
    5.0,
    6.0,
    8.0,
    10.0,
    12.0,
)
POWER_SCREW_DIAMETERS_MM: tuple[float, ...] = (
    10.0,
    12.0,
    16.0,
    20.0,
    24.0,
    28.0,
    32.0,
    40.0,
    50.0,
    60.0,
    70.0,
    80.0,
)
BOLT_DESIGNATIONS: tuple[str, ...] = (
    "M6",
    "M8",
    "M10",
    "M12",
    "M14",
    "M16",
    "M20",
    "M24",
    "M30",
    "M36",
    "M42",
    "M48",
    "M56",
    "M64",
)

# Rectangular solid-section heights (mm), ascending. The open-ended synthesis
# path models an unclassified request as a solid rectangular cantilever
# (section b = h/2) and walks these standard heights until the deterministic
# stress criterion passes. Every candidate is solved by the real formula.
BEAM_SECTION_HEIGHTS_MM: tuple[float, ...] = (
    6.0,
    8.0,
    10.0,
    12.0,
    16.0,
    20.0,
    25.0,
    30.0,
    40.0,
    50.0,
    60.0,
    80.0,
    100.0,
    120.0,
    160.0,
    200.0,
)


class GenerativeDesignResult(BaseModel):
    title: str
    category: str
    material_name: str
    yield_strength_mpa: float
    max_stress_mpa: float
    min_safety_factor: float
    passed: bool
    verdict: str
    scad_code: str
    blueprint_svg: str
    report_html: str
    key_metrics: dict[str, Any] = {}
    recommendations: list[str] = []


class GenerativeEngineeringAgent:
    """
    On-the-fly agent that translates any mechanical prompt into
    parametric 3D CAD, deterministic stress verification, and 2D engineering blueprints.
    """

    @staticmethod
    def _select_size(sizes, solve_fn, passed_fn, requested=None, order_key=None):
        """Pick the smallest catalogue size whose solver result passes.

        This is the design move an engineer makes by hand: size the part from a
        rule of thumb, solve it, and step up the standard size until the
        deterministic criteria are met. Every candidate is solved by the real
        solver, so the returned result is verified, never estimated.

        ``order_key`` maps a candidate to a sortable magnitude. It is required
        for non-numeric series (bolt designations sort wrongly as plain
        strings - "M16" would precede "M6").

        Returns ``(result, size, tried, pinned)`` where ``tried`` is the ordered
        list of ``(size, result)`` attempts and ``pinned`` is True when an
        explicitly requested size was honoured. If nothing passes, the largest
        attempted size is returned so the caller can report an honest failure.
        """
        key = order_key or (lambda s: s)
        ordered = sorted(sizes, key=key)
        tried: list[tuple[Any, Any]] = []

        if requested is not None:
            first = solve_fn(requested)
            tried.append((requested, first))
            if passed_fn(first):
                return first, requested, tried, True

        for size in ordered:
            if requested is not None and key(size) <= key(requested):
                continue
            result = solve_fn(size)
            tried.append((size, result))
            if passed_fn(result):
                return result, size, tried, False

        size, result = tried[-1]
        return result, size, tried, requested is not None

    # Keyword families handled by dedicated closed-form solvers. Order matters:
    # a lead/power-screw request must be claimed before the generic fastener
    # family, otherwise the "screw" keyword would route it to the bolt solver.
    SPECIALIZED_KEYWORDS = (
        ("gears", ("gear", "pinion", "sprocket", "gearbox")),
        ("springs", ("spring", "coil spring", "suspension spring")),
        ("power_screws", ("lead screw", "power screw", "acme screw", "ball screw", "jack screw")),
        ("fasteners", ("bolt", "screw joint", "flange bolt", "preload", "tightening torque")),
    )

    @classmethod
    def specialized_family(cls, prompt: str) -> str | None:
        """Return the dedicated solver family for a prompt, or ``None``.

        This is the single source of truth for "does MDIE have a real solver
        for this request?", shared by the routing below and by the CLI so an
        out-of-scope request is declined instead of silently synthesised.
        """
        p = prompt.lower().strip()
        for family, keywords in cls.SPECIALIZED_KEYWORDS:
            if any(w in p for w in keywords):
                return family
        return None

    @classmethod
    def is_specialized(cls, prompt: str) -> bool:
        """True when a dedicated closed-form solver handles this prompt."""
        return cls.specialized_family(prompt) is not None

    @classmethod
    def process(cls, prompt: str, output_dir: Path | None = None) -> GenerativeDesignResult:
        """
        Main pipeline: routes to a specialized closed-form solver when one
        exists, otherwise deterministically synthesises a generic element.
        """
        p_lower = prompt.lower().strip()
        family = cls.specialized_family(prompt)

        if family == "gears":
            return cls._solve_gear_generative(prompt, p_lower)
        if family == "springs":
            return cls._solve_spring_generative(prompt, p_lower)
        if family == "power_screws":
            return cls._solve_power_screw_generative(prompt, p_lower)
        if family == "fasteners":
            return cls._solve_bolted_joint_generative(prompt, p_lower)

        # General open-ended synthesis for a generic, unclassified element.
        return cls._synthesize_on_the_fly(prompt, p_lower)

    @classmethod
    def _solve_gear_generative(cls, prompt: str, p_lower: str) -> GenerativeDesignResult:
        """Dynamically extract gear parameters and solve via AGMA/ISO engine."""
        power_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kw|kilowatt)", p_lower)
        power_kw = float(power_match.group(1)) if power_match else 15.0

        rpm_match = re.search(r"(\d+(?:\.\d+)?)\s*rpm", p_lower)
        rpm = float(rpm_match.group(1)) if rpm_match else 1500.0

        ratio_match = re.search(r"(?:ratio|reduction)\s*(\d+(?:\.\d+)?)", p_lower)
        ratio = float(ratio_match.group(1)) if ratio_match else 3.0

        is_helical = "helical" in p_lower
        helix_deg = 20.0 if is_helical else 0.0

        # Pinion & Gear tooth counts
        z1 = 20
        z2 = int(round(z1 * ratio))

        material_id = "AISI_4140_QT" if "steel" in p_lower or "4140" in p_lower else "AISI_1045"

        # Honour an explicitly requested module; otherwise start from the
        # power-based rule of thumb and step up until the gear passes.
        mod_match = re.search(r"module\s*(?:of\s*)?(\d+(?:\.\d+)?)", p_lower)
        requested_mn = float(mod_match.group(1)) if mod_match else None
        if requested_mn is None:
            if power_kw > 30:
                requested_mn = 4.0
            elif power_kw > 10:
                requested_mn = 3.0
            else:
                requested_mn = 2.0

        def _solve_mn(candidate_mn: float):
            spec = GearPairSpecification(
                name="Parametric_Gear_Transmission",
                gear_type="helical" if is_helical else "spur",
                power_kw=power_kw,
                pinion_speed_rpm=rpm,
                pinion_teeth=z1,
                gear_teeth=z2,
                normal_module_mm=candidate_mn,
                helix_angle_deg=helix_deg,
                material_id=material_id,
            )
            return spec, GearSolver.solve(spec)

        res, mn, tried, pinned = cls._select_size(
            GEAR_MODULES_MM,
            _solve_mn,
            lambda r: r[1].stress.all_safety_criteria_passed,
            requested=requested_mn,
        )
        spec = res[0]
        steps = ", ".join(f"m{s:g}" for s, _ in tried)
        res = res[1]

        scad_code = GearCADGenerator.generate_scad(res)
        blueprint_svg = Blueprint2DGenerator.generate_gear_blueprint_svg(res, theme="blueprint")

        report_html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Gear Verification Report</title>
  <style>
    body {{ background: #030712; color: #f3f4f6; font-family: sans-serif; padding: 20px; }}
    .card {{ background: #111827; border: 1px solid #374151; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
    .metric {{ font-size: 24px; font-weight: bold; color: #38bdf8; }}
  </style>
</head>
<body>
  <h1>{spec.name} &mdash; AGMA 2001-D04 / ISO 6336 Verification</h1>
  <div class="card">
    <div>Verdict: <strong>{res.stress.verdict}</strong></div>
    <div>Pinion Bending SF: <span class="metric">{res.stress.bending_safety_factor_pinion:.2f}</span></div>
    <div>Contact Pitting SF: <span class="metric">{res.stress.contact_safety_factor:.2f}</span></div>
    <div>Pitch Diameter: {res.geometry.pitch_diameter_pinion_mm:.1f} mm / {res.geometry.pitch_diameter_gear_mm:.1f} mm</div>
    <div>Center Distance: <strong>{res.geometry.center_distance_mm:.2f} mm</strong></div>
  </div>
</body>
</html>"""

        return GenerativeDesignResult(
            title=f"{spec.gear_type.capitalize()} Gear Pair (Module {mn} mm, {power_kw:.1f} kW)",
            category="Power Transmission",
            material_name=res.material_name,
            yield_strength_mpa=res.yield_strength_mpa,
            max_stress_mpa=max(
                res.stress.bending_stress_pinion_mpa, res.stress.contact_pitting_stress_mpa
            ),
            min_safety_factor=min(
                res.stress.bending_safety_factor_pinion, res.stress.contact_safety_factor
            ),
            passed=res.stress.all_safety_criteria_passed,
            verdict=res.stress.verdict,
            scad_code=scad_code,
            blueprint_svg=blueprint_svg,
            report_html=report_html,
            key_metrics={
                "Power (kW)": power_kw,
                "Pinion Speed (RPM)": rpm,
                "Module Tried": steps,
                "Selected Module (mm)": mn,
                "Center Distance (mm)": res.geometry.center_distance_mm,
                "Bending SF": res.stress.bending_safety_factor_pinion,
                "Contact SF": res.stress.contact_safety_factor,
            },
            recommendations=res.stress.recommendations,
        )

    @classmethod
    def _solve_spring_generative(cls, prompt: str, p_lower: str) -> GenerativeDesignResult:
        """Dynamically extract spring requirements and solve via Shigley/DIN 2089 engine."""
        force_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:n|newton)", p_lower)
        max_f = float(force_match.group(1)) if force_match else 250.0

        dia_match = re.search(r"(\d+(?:\.\d+)?)\s*mm\s*(?:wire|diameter)?", p_lower)
        requested_d = float(dia_match.group(1)) if dia_match else (3.0 if max_f > 150 else 2.0)

        def _solve_d(candidate_d: float):
            spec = SpringSpecification(
                name="Helical_Compression_Spring",
                wire_diameter_d_mm=candidate_d,
                active_coils_na=8.0,
                max_operating_force_n=max_f,
                min_operating_force_n=max_f * 0.2,
            )
            return spec, SpringSolver.solve(spec)

        res, wire_d, tried, pinned = cls._select_size(
            SPRING_WIRE_DIAMETERS_MM,
            _solve_d,
            lambda r: r[1].all_criteria_passed,
            requested=requested_d,
        )
        spec = res[0]
        steps = ", ".join(f"d{s:g}" for s, _ in tried)
        res = res[1]
        scad_code = SpringCADGenerator.generate_scad(res)

        # Clean generic SVG blueprint for spring
        svg_blueprint = f"""<svg viewBox="0 0 1000 650" xmlns="http://www.w3.org/2000/svg" font-family="Consolas, monospace">
  <rect width="1000" height="650" fill="#091424" />
  <rect x="30" y="30" width="940" height="590" fill="none" stroke="#38bdf8" stroke-width="2" />
  <text x="50" y="70" fill="#38bdf8" font-size="18" font-weight="bold">MACHINE DESIGN INTELLIGENCE ENGINE &mdash; HELICAL SPRING BLUEPRINT</text>
  <text x="50" y="100" fill="#94a3b8" font-size="12">Specification: Wire d={res.geometry.wire_diameter_mm} mm | Mean D={res.geometry.mean_diameter_mm} mm | Outer Do={res.geometry.outer_diameter_mm} mm</text>
  <text x="50" y="125" fill="#94a3b8" font-size="12">Spring Rate k={res.spring_rate_k_n_mm:.2f} N/mm | Free Length L0={res.geometry.free_length_l0_mm:.1f} mm | Solid Ls={res.geometry.solid_length_ls_mm:.1f} mm</text>
  <!-- Spring Outline Schematic -->
  <line x1="300" y1="200" x2="300" y2="450" stroke="#ef4444" stroke-width="1.2" stroke-dasharray="10,3,3,3" />
  <rect x="250" y="200" width="100" height="{res.geometry.free_length_l0_mm * 2.5:.0f}" fill="rgba(56,189,248,0.15)" stroke="#38bdf8" stroke-width="2" />
  <text x="300" y="500" fill="#38bdf8" font-size="14" text-anchor="middle">FREE LENGTH: {res.geometry.free_length_l0_mm:.1f} mm</text>
  <!-- Title Block -->
  <rect x="570" y="470" width="400" height="150" fill="#091424" stroke="#38bdf8" stroke-width="1.5" />
  <text x="585" y="500" fill="#38bdf8" font-size="13" font-weight="bold">TITLE: HELICAL COMPRESSION SPRING</text>
  <text x="585" y="525" fill="#e2e8f0" font-size="11">MATERIAL: ASTM A228 MUSIC WIRE</text>
  <text x="585" y="550" fill="#10b981" font-size="11">SOLID SF: {res.solid_yield_safety_factor:.2f} | FATIGUE SF: {res.fatigue_safety_factor:.2f}</text>
  <text x="585" y="575" fill="#94a3b8" font-size="10">STANDARD: DIN 2089 / SHIGLEY</text>
</svg>"""

        report_html = f"""<!DOCTYPE html>
<html>
<body style="background:#030712; color:#f3f4f6; font-family:sans-serif; padding:20px;">
  <h2>Helical Spring Verification: {res.verdict}</h2>
  <p>Spring Rate: <strong>{res.spring_rate_k_n_mm:.2f} N/mm</strong></p>
  <p>Solid Yield SF: <strong>{res.solid_yield_safety_factor:.2f}</strong></p>
  <p>Fatigue SF: <strong>{res.fatigue_safety_factor:.2f}</strong></p>
</body>
</html>"""

        return GenerativeDesignResult(
            title=f"Helical Spring (d={wire_d} mm, Fmax={max_f:.0f} N)",
            category="Elastic Machine Element",
            material_name=spec.material_name,
            yield_strength_mpa=res.torsional_yield_strength_mpa,
            max_stress_mpa=res.shear_stress_max_mpa,
            min_safety_factor=min(res.solid_yield_safety_factor, res.fatigue_safety_factor),
            passed=res.all_criteria_passed,
            verdict=res.verdict,
            scad_code=scad_code,
            blueprint_svg=svg_blueprint,
            report_html=report_html,
            key_metrics={
                "Spring Rate (N/mm)": res.spring_rate_k_n_mm,
                "Free Length (mm)": res.geometry.free_length_l0_mm,
                "Max Force (N)": max_f,
                "Wire Dia Tried": steps,
                "Selected Wire Dia (mm)": wire_d,
                "Solid Yield SF": res.solid_yield_safety_factor,
                "Fatigue SF": res.fatigue_safety_factor,
            },
            recommendations=res.recommendations,
        )

    @classmethod
    def _solve_bolted_joint_generative(cls, prompt: str, p_lower: str) -> GenerativeDesignResult:
        """Dynamically extract bolted joint requirements and solve via VDI 2230 engine."""
        bolt_match = re.search(r"\b(m[4-9]|m[1-3][0-9])\b", p_lower)
        bolt_desig = bolt_match.group(1).upper() if bolt_match else "M12"

        load_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kn|kilonewton)", p_lower)
        load_n = float(load_match.group(1)) * 1000.0 if load_match else 15000.0

        pclass = "10.9" if "10.9" in p_lower else ("12.9" if "12.9" in p_lower else "8.8")

        def _solve_bolt(candidate: str):
            spec = BoltedJointSpecification(
                name=f"Bolted_Flange_Joint_{candidate}",
                bolt_designation=candidate,
                property_class=pclass,
                applied_max_load_n=load_n,
                clamped_length_mm=45.0,
            )
            return spec, BoltedJointSolver.solve(spec)

        res, bolt_desig, tried, pinned = cls._select_size(
            BOLT_DESIGNATIONS,
            _solve_bolt,
            lambda r: r[1].all_safety_criteria_passed,
            requested=bolt_desig,
            order_key=lambda d: float(d[1:]),
        )
        spec = res[0]
        steps = ", ".join(str(s) for s, _ in tried)
        res = res[1]

        # CAD code for bolt & flange assembly
        scad_code = f"""// MDIE Bolted Joint Assembly: {bolt_desig} Class {pclass}
$fn = 48;
module bolted_joint() {{
    // Clamped plates
    difference() {{
        cube([80, 80, 45], center=true);
        cylinder(r={res.bolt_diameter_mm / 2.0 + 0.5}, h=60, center=true);
    }}
    // Bolt Hex Head
    translate([0, 0, 22.5 + 4])
    cylinder(r={res.bolt_diameter_mm * 0.9}, h=8, center=true, $fn=6);
    // Bolt Shank
    translate([0, 0, -2.5])
    cylinder(r={res.bolt_diameter_mm / 2.0}, h=50, center=true);
    // Nut
    translate([0, 0, -22.5 - 5])
    cylinder(r={res.bolt_diameter_mm * 0.9}, h=10, center=true, $fn=6);
}}
color([0.7, 0.75, 0.8]) bolted_joint();
"""

        svg_blueprint = f"""<svg viewBox="0 0 1000 650" xmlns="http://www.w3.org/2000/svg" font-family="Consolas, monospace">
  <rect width="1000" height="650" fill="#091424" />
  <rect x="30" y="30" width="940" height="590" fill="none" stroke="#38bdf8" stroke-width="2" />
  <text x="50" y="70" fill="#38bdf8" font-size="18" font-weight="bold">BOLTED JOINT & PRELOAD TECHNICAL DRAWING: {bolt_desig} (CLASS {pclass})</text>
  <text x="50" y="100" fill="#94a3b8" font-size="12">Preload Fi = {res.tightening_preload_fi_n:.0f} N | Recommended Torque = {res.recommended_torque_nm:.1f} N*m (K=0.20)</text>
  <text x="50" y="125" fill="#94a3b8" font-size="12">Joint Constant C = {res.joint_constant_c:.3f} | Clamped Member Grip = {spec.clamped_length_mm:.0f} mm</text>
  <!-- Title Block -->
  <rect x="570" y="470" width="400" height="150" fill="#091424" stroke="#38bdf8" stroke-width="1.5" />
  <text x="585" y="500" fill="#38bdf8" font-size="13" font-weight="bold">TITLE: FASTENER & PRELOAD AUDIT</text>
  <text x="585" y="525" fill="#e2e8f0" font-size="11">BOLT: {bolt_desig} CLASS {pclass} (Sp={res.proof_strength_mpa:.0f} MPa)</text>
  <text x="585" y="550" fill="#10b981" font-size="11">SEPARATION SF: {res.separation_safety_factor:.2f} | PROOF SF: {res.proof_load_safety_factor:.2f}</text>
  <text x="585" y="575" fill="#94a3b8" font-size="10">STANDARD: VDI 2230 / ISO 898-1</text>
</svg>"""

        report_html = f"""<!DOCTYPE html>
<html>
<body style="background:#030712; color:#f3f4f6; font-family:sans-serif; padding:20px;">
  <h2>Bolted Joint Verification: {res.verdict}</h2>
  <p>Tightening Torque: <strong>{res.recommended_torque_nm:.1f} N&middot;m</strong></p>
  <p>Separation SF: <strong>{res.separation_safety_factor:.2f}</strong></p>
  <p>Proof Load SF: <strong>{res.proof_load_safety_factor:.2f}</strong></p>
</body>
</html>"""

        return GenerativeDesignResult(
            title=f"Bolted Joint ({bolt_desig} Class {pclass}, Preload {res.tightening_preload_fi_n / 1000:.1f} kN)",
            category="Fasteners & Preload",
            material_name=f"Steel Class {pclass}",
            yield_strength_mpa=res.yield_strength_mpa,
            max_stress_mpa=res.max_total_bolt_load_n / res.tensile_stress_area_mm2,
            min_safety_factor=min(res.separation_safety_factor, res.proof_load_safety_factor),
            passed=res.all_safety_criteria_passed,
            verdict=res.verdict,
            scad_code=scad_code,
            blueprint_svg=svg_blueprint,
            report_html=report_html,
            key_metrics={
                "Bolt Designation": bolt_desig,
                "Bolt Sizes Tried": steps,
                "Preload (N)": res.tightening_preload_fi_n,
                "Tightening Torque (N*m)": res.recommended_torque_nm,
                "Separation SF": res.separation_safety_factor,
                "Proof SF": res.proof_load_safety_factor,
            },
            recommendations=res.recommendations,
        )

    @classmethod
    def _solve_power_screw_generative(cls, prompt: str, p_lower: str) -> GenerativeDesignResult:
        """Dynamically extract power screw requirements and solve via ASME/DIN 103 engine."""
        dia_match = re.search(r"(\d+(?:\.\d+)?)\s*mm", p_lower)
        requested_d = float(dia_match.group(1)) if dia_match else 24.0

        load_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kn|kilonewton)", p_lower)
        load_n = float(load_match.group(1)) * 1000.0 if load_match else 8000.0

        def _solve_d(candidate_d: float):
            spec = PowerScrewSpecification(
                name="Power_Lead_Screw",
                nominal_diameter_d_mm=candidate_d,
                pitch_p_mm=5.0 if candidate_d >= 20 else 4.0,
                axial_load_n=load_n,
                thread_type="acme",
            )
            return spec, PowerScrewSolver.solve(spec)

        res, d_nom, tried, pinned = cls._select_size(
            POWER_SCREW_DIAMETERS_MM,
            _solve_d,
            lambda r: r[1].all_safety_criteria_passed,
            requested=requested_d,
        )
        spec = res[0]
        steps = ", ".join(f"d{s:g}" for s, _ in tried)
        res = res[1]
        pitch = spec.pitch_p_mm

        scad_code = f"""// MDIE Lead Screw Model: d={d_nom} mm, pitch={pitch} mm
$fn = 40;
module lead_screw() {{
    cylinder(r={d_nom / 2.0}, h=300, center=true);
    // Nut
    color([0.85, 0.65, 0.25])
    translate([0, 0, 50])
    difference() {{
        cylinder(r={d_nom * 0.9}, h={spec.nut_length_mm}, center=true);
        cylinder(r={d_nom / 2.0 + 0.2}, h={spec.nut_length_mm + 2}, center=true);
    }}
}}
color([0.75, 0.8, 0.85]) lead_screw();
"""

        svg_blueprint = f"""<svg viewBox="0 0 1000 650" xmlns="http://www.w3.org/2000/svg" font-family="Consolas, monospace">
  <rect width="1000" height="650" fill="#091424" />
  <rect x="30" y="30" width="940" height="590" fill="none" stroke="#38bdf8" stroke-width="2" />
  <text x="50" y="70" fill="#38bdf8" font-size="18" font-weight="bold">LEAD SCREW TECHNICAL BLUEPRINT: d={d_nom:.0f} mm (ACME THREAD)</text>
  <text x="50" y="100" fill="#94a3b8" font-size="12">Torque to Raise: {res.total_torque_raise_nm:.1f} N*m | Efficiency: {res.efficiency_pct:.1f}% | Self-Locking: {res.is_self_locking}</text>
  <text x="50" y="125" fill="#94a3b8" font-size="12">Bronze Nut Bearing Pressure: {res.bearing_pressure_mpa:.1f} MPa (Allowable: 15.0 MPa)</text>
  <!-- Title Block -->
  <rect x="570" y="470" width="400" height="150" fill="#091424" stroke="#38bdf8" stroke-width="1.5" />
  <text x="585" y="500" fill="#38bdf8" font-size="13" font-weight="bold">TITLE: ACME POWER SCREW DRIVE</text>
  <text x="585" y="525" fill="#e2e8f0" font-size="11">LOAD: {load_n / 1000:.1f} kN | MOTOR POWER: {res.required_motor_power_w:.0f} W</text>
  <text x="585" y="550" fill="#10b981" font-size="11">VERDICT: {res.verdict}</text>
  <text x="585" y="575" fill="#94a3b8" font-size="10">STANDARD: ASME B1.5 / DIN 103</text>
</svg>"""

        report_html = f"""<!DOCTYPE html>
<html>
<body style="background:#030712; color:#f3f4f6; font-family:sans-serif; padding:20px;">
  <h2>Power Screw Verification: {res.verdict}</h2>
  <p>Torque to Raise: <strong>{res.total_torque_raise_nm:.1f} N&middot;m</strong></p>
  <p>Efficiency: <strong>{res.efficiency_pct:.1f}%</strong></p>
  <p>Self Locking: <strong>{res.is_self_locking}</strong></p>
</body>
</html>"""

        return GenerativeDesignResult(
            title=f"Acme Lead Screw (d={d_nom} mm, Axial Load {load_n / 1000:.1f} kN)",
            category="Linear Actuator & Drive",
            material_name="Alloy Steel / Bronze Nut",
            yield_strength_mpa=350.0,
            max_stress_mpa=res.axial_direct_stress_mpa,
            min_safety_factor=350.0 / res.axial_direct_stress_mpa
            if res.axial_direct_stress_mpa > 0
            else 999.0,
            passed=res.all_safety_criteria_passed,
            verdict=res.verdict,
            scad_code=scad_code,
            blueprint_svg=svg_blueprint,
            report_html=report_html,
            key_metrics={
                "Diameter (mm)": d_nom,
                "Diameter Tried": steps,
                "Pitch (mm)": pitch,
                "Torque (N*m)": res.total_torque_raise_nm,
                "Power (W)": res.required_motor_power_w,
                "Self-Locking": res.is_self_locking,
            },
            recommendations=res.recommendations,
        )

    @classmethod
    def _synthesize_on_the_fly(cls, prompt: str, p_lower: str) -> GenerativeDesignResult:
        """Deterministically size a generic beam element straight from the prompt.

        There is no closed-form standard for an arbitrary machine element, so
        this path makes exactly one explicit, conservative modelling choice - a
        solid rectangular cantilever, fixed at one end with the load at the free
        end - and then sizes it with the real cantilever formulae. Span, load,
        material and any pin/bolt holes are read from the prompt; anything the
        prompt omits is defaulted and reported as an assumption. Nothing about
        the geometry is hard-coded: the emitted solid is built from the section
        the deterministic solver actually selected.
        """
        assumptions: list[str] = []

        # --- Span (mm) ---------------------------------------------------
        span_match = re.search(r"(\d+(?:\.\d+)?)\s*mm", p_lower)
        if span_match:
            span_mm = float(span_match.group(1))
        else:
            span_mm = 100.0
            assumptions.append("Span not stated; assumed 100 mm (verify before manufacture).")
        span_mm = max(span_mm, 5.0)

        # --- Load (N) ----------------------------------------------------
        load_n: float | None = None
        kn_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kn|kilonewton)", p_lower)
        n_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:n|newton)", p_lower)
        kg_match = re.search(r"(\d+(?:\.\d+)?)\s*kg", p_lower)
        if kn_match:
            load_n = float(kn_match.group(1)) * 1000.0
        elif n_match:
            load_n = float(n_match.group(1))
        elif kg_match:
            load_n = float(kg_match.group(1)) * 9.80665
            assumptions.append("Load stated as mass; converted with g = 9.80665 m/s^2.")
        if load_n is None:
            load_n = 500.0
            assumptions.append("Load not stated; assumed 500 N.")
        load_n = max(load_n, 1.0)

        # --- Material ----------------------------------------------------
        if "stainless" in p_lower or "304" in p_lower:
            mat_id = "AISI_304_SS"
        elif "titanium" in p_lower:
            mat_id = "TI_6AL_4V"
        elif "aluminum" in p_lower or "aluminium" in p_lower or "6061" in p_lower:
            mat_id = "AL_6061_T6"
        elif "4140" in p_lower:
            mat_id = "AISI_4140_QT"
        elif "steel" in p_lower:
            mat_id = "AISI_1045_CD"
        else:
            mat_id = "AISI_1018_CD"
            assumptions.append("Material not stated; assumed AISI 1018 cold-drawn steel.")
        mat = MaterialDatabase.get(mat_id)

        # --- Optional pin / bolt holes ----------------------------------
        hole_dia_mm: float | None = None
        hole_count = 0
        dia_match = re.search(
            r"(\d+(?:\.\d+)?)\s*mm\s*(?:pin\s*|bolt\s*|mounting\s*|through\s*)?holes?", p_lower
        )
        if dia_match:
            hole_dia_mm = float(dia_match.group(1))
        count_match = re.search(
            r"(\d+|two|three|four|five|six)\s*(?:\d+(?:\.\d+)?\s*mm\s*)?"
            r"(?:pin\s*|bolt\s*|mounting\s*)?holes?",
            p_lower,
        )
        if count_match:
            token = count_match.group(1)
            hole_count = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}.get(
                token, 0
            ) or int(token)
        if hole_count and hole_dia_mm is None:
            hole_dia_mm = 8.0
            assumptions.append("Hole diameter not stated; assumed 8 mm.")
        if hole_dia_mm and not hole_count:
            hole_count = 2
        hole_count = min(hole_count, 6)

        # --- Deterministic sizing of a solid rectangular cantilever -----
        #   fixed at x=0, tip load F  ->  M = F*L
        #   section b = h/2, I = b*h^3/12, c = h/2
        #   sigma_b = M*c/I = 6*F*L/(b*h^2)      (bending, outer fibre)
        #   delta   = F*L^3/(3*E*I)              (tip deflection)
        target_sf = 2.0
        span_m = span_mm / 1000.0

        def _solve_height(h_mm: float) -> dict[str, float]:
            h_m = h_mm / 1000.0
            b_m = h_m / 2.0
            moment_nm = load_n * span_m
            inertia_m4 = (b_m * h_m**3) / 12.0
            sigma_mpa = (moment_nm * (h_m / 2.0)) / inertia_m4 / 1e6
            sf_yield = mat.yield_strength_mpa / sigma_mpa if sigma_mpa > 0 else 999.0
            delta_mm = (load_n * span_m**3) / (3.0 * mat.elastic_modulus_pa * inertia_m4) * 1000.0
            return {
                "height_mm": h_mm,
                "width_mm": round(b_m * 1000.0, 1),
                "moment_nm": moment_nm,
                "sigma_mpa": sigma_mpa,
                "sf_yield": sf_yield,
                "deflection_mm": delta_mm,
            }

        section, height_mm, tried, pinned = cls._select_size(
            BEAM_SECTION_HEIGHTS_MM,
            _solve_height,
            lambda r: r["sf_yield"] >= target_sf,
        )
        steps = ", ".join(f"h{h:g}" for h, _ in tried)
        width_mm = section["width_mm"]
        sigma_mpa = section["sigma_mpa"]
        sf_yield = section["sf_yield"]
        deflection_mm = section["deflection_mm"]
        passed = sf_yield >= target_sf

        # --- Parametric OpenSCAD from the SELECTED section (authored, not canned) ---
        hole_scad = ""
        if hole_count and hole_dia_mm:
            r_hole = hole_dia_mm / 2.0
            if hole_count == 2:
                xs = [-span_mm * 0.35, span_mm * 0.35]
            else:
                step = (span_mm * 0.7) / (hole_count - 1)
                xs = [-span_mm * 0.35 + i * step for i in range(hole_count)]
            cylinders = "\n".join(
                f"        translate([{x:.2f}, 0, 0]) "
                f"cylinder(r={r_hole:.2f}, h={width_mm + 4:.2f}, center=true, $fn=32);"
                for x in xs
            )
            hole_scad = (
                f"        // {hole_count} x {hole_dia_mm:g} mm mounting holes (from prompt)\n"
                "        rotate([90, 0, 0])\n"
                "        union() {\n"
                f"{cylinders}\n"
                "        }\n"
            )

        scad_code = f"""// MDIE deterministic synthesis of "{prompt[:60]}"
// Modelling assumption: solid rectangular cantilever, fixed at x=0,
// load applied at the free end.  Section b = h/2.
//   span L = {span_mm:g} mm   load F = {load_n:g} N   material = {mat.name}
//   solver-selected section  b x h = {width_mm:g} x {height_mm:g} mm
$fn = 48;
module synthesized_element() {{
    difference() {{
        // Beam body: length (X) x section width (Y) x section height (Z)
        translate([{span_mm / 2.0:.2f}, 0, 0])
        cube([{span_mm:.2f}, {width_mm:.2f}, {height_mm:.2f}], center=true);
{hole_scad}    }}
}}
color([0.72, 0.76, 0.82]) synthesized_element();
"""

        box_w = min(span_mm * 1.6, 520)
        box_h = max(height_mm * 3.0, 24)
        svg_blueprint = f"""<svg viewBox="0 0 1000 650" xmlns="http://www.w3.org/2000/svg" font-family="Consolas, monospace">
  <rect width="1000" height="650" fill="#091424" />
  <rect x="30" y="30" width="940" height="590" fill="none" stroke="#38bdf8" stroke-width="2" />
  <text x="50" y="70" fill="#38bdf8" font-size="18" font-weight="bold">MDIE DETERMINISTIC SYNTHESIS &#8212; RECTANGULAR CANTILEVER</text>
  <text x="50" y="95" fill="#94a3b8" font-size="12">PROMPT: {prompt[:70]}</text>
  <text x="50" y="150" fill="#e2e8f0" font-size="12">SPAN L = {span_mm:g} mm   |   SECTION b x h = {width_mm:g} x {height_mm:g} mm   |   F = {load_n:g} N</text>
  <rect x="120" y="240" width="{box_w:.0f}" height="{box_h:.0f}" fill="rgba(56,189,248,0.15)" stroke="#38bdf8" stroke-width="2" />
  <text x="120" y="{240 + box_h + 30:.0f}" fill="#38bdf8" font-size="13">CANTILEVER SCHEMATIC (fixed at left end)</text>
  <rect x="560" y="450" width="410" height="170" fill="#091424" stroke="#38bdf8" stroke-width="1.5" />
  <text x="575" y="480" fill="#38bdf8" font-size="13" font-weight="bold">TITLE: ON-THE-FLY SYNTHESIS</text>
  <text x="575" y="505" fill="#e2e8f0" font-size="11">MATERIAL: {mat.name}</text>
  <text x="575" y="530" fill="#e2e8f0" font-size="11">PEAK BENDING: {sigma_mpa:.1f} MPa</text>
  <text x="575" y="555" fill="#10b981" font-size="11">YIELD SF: {sf_yield:.2f} (target {target_sf:.1f})</text>
  <text x="575" y="580" fill="#94a3b8" font-size="10">TIP DEFLECTION: {deflection_mm:.3f} mm</text>
  <text x="575" y="600" fill="#94a3b8" font-size="10">STATUS: {"PASS" if passed else "FAIL"}</text>
</svg>"""

        assumption_html = (
            "".join(f"<li>{a}</li>" for a in assumptions)
            or "<li>All inputs were read from the prompt.</li>"
        )
        report_html = f"""<!DOCTYPE html>
<html>
<body style="background:#030712; color:#f3f4f6; font-family:sans-serif; padding:20px;">
  <h2>Synthesized Rectangular Cantilever: {"PASS" if passed else "FAIL"}</h2>
  <p>Prompt: <em>{prompt}</em></p>
  <p>Model: solid rectangular cantilever (b = h/2), fixed at one end, tip load.</p>
  <p>Span L = <strong>{span_mm:g} mm</strong> &middot; Section b x h = <strong>{width_mm:g} x {height_mm:g} mm</strong> &middot; F = <strong>{load_n:g} N</strong></p>
  <p>Material: <strong>{mat.name}</strong> (Sy = {mat.yield_strength_mpa} MPa)</p>
  <p>Bending moment M = <strong>{section["moment_nm"]:.2f} N&middot;m</strong></p>
  <p>Peak bending stress: <strong>{sigma_mpa:.2f} MPa</strong></p>
  <p>Yield safety factor: <strong>{sf_yield:.2f}</strong> (target {target_sf:.1f})</p>
  <p>Tip deflection: <strong>{deflection_mm:.3f} mm</strong></p>
  <p><strong>Assumptions</strong></p>
  <ul>{assumption_html}</ul>
</body>
</html>"""

        recommendations = list(assumptions) + [
            "Modelled as a solid rectangular cantilever; verify the boundary "
            "condition matches the application.",
            "Every dimension above comes from the deterministic solver, not a rule-of-thumb guess.",
        ]

        return GenerativeDesignResult(
            title=f"Synthesized Rectangular Cantilever (L={span_mm:g} mm, F={load_n:g} N)",
            category="Custom Synthesis",
            material_name=mat.name,
            yield_strength_mpa=mat.yield_strength_mpa,
            max_stress_mpa=round(sigma_mpa, 2),
            min_safety_factor=round(sf_yield, 2),
            passed=passed,
            verdict="PASS" if passed else "FAIL - Stress exceeds allowable",
            scad_code=scad_code,
            blueprint_svg=svg_blueprint,
            report_html=report_html,
            key_metrics={
                "Span (mm)": span_mm,
                "Load (N)": load_n,
                "Section b x h (mm)": f"{width_mm:g} x {height_mm:g}",
                "Section Tried": steps,
                "Material": mat.name,
                "Peak Stress (MPa)": round(sigma_mpa, 2),
                "Safety Factor": round(sf_yield, 2),
                "Tip Deflection (mm)": round(deflection_mm, 3),
            },
            recommendations=recommendations,
        )

"""
MDIE AI Natural Language Parser
Converts unstructured natural language engineering requests into structured EngineeringModel objects.
Integrates Google Gemini API (gemini-3.8-flash) with an offline deterministic heuristic parser fallback.
"""

import json
import os
import re
from typing import Any, TypedDict

from ai.assumptions import AssumptionManager
from core.frame_model import (
    STRUCTURAL_MATERIALS,
    FrameDesignModel,
    FrameGeometry,
    FrameLoads,
    TubeProfile,
)
from core.models import (
    DistributedLoad,
    EngineeringConstraints,
    EngineeringModel,
    PointLoad,
    ShaftSegment,
    Support,
)


def _extract_number_with_unit(
    text: str,
    patterns: list[str],
    default: float,
    label: str = "",
) -> tuple[float, bool]:
    """Try a list of regex patterns; return (value, found)."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1))
                return val, True
            except ValueError:
                continue
    return default, False


def extract_mm(pattern: str, default: float, label: str) -> float:
    """Extract a dimension in millimetres from *pattern* with *default* fallback."""
    m = re.search(pattern, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return default


def extract_kg_to_n(
    pattern: str,
    default_kg: float,
    label: str,
) -> float:
    """Extract *kg* and convert to Newtons (9.81 m/s²)."""
    m = re.search(pattern, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1)) * 9.81
        except ValueError:
            pass
    return default_kg * 9.81


def extract_n(
    pattern: str,
    default: float,
    label: str,
) -> float:
    """Extract force in Newtons from *pattern* with *default* fallback."""
    m = re.search(pattern, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return default


def extract_power(
    text: str,
    default: float | None = None,
) -> tuple[float | None, bool]:
    """Extract power (kW / hp / W) from free-form text.

    Returns ``(power_watts, found)``.
    """
    # kW
    m = re.search(r"(\d+(?:\.\d+)?)\s*kw\\b", text, re.IGNORECASE)
    if m:
        return float(m.group(1)) * 1000.0, True
    # hp
    m = re.search(r"(\d+(?:\.\d+)?)\s*hp\\b", text, re.IGNORECASE)
    if m:
        return float(m.group(1)) * 745.7, True
    # W (but not scientific-notation patterns like 10^5)
    m = re.search(r"(\d+(?:\.\d+)?)\s*w\\b(?!\\s*\\^)", text, re.IGNORECASE)
    if m:
        return float(m.group(1)), True
    return default, False

class ExtractedParameters(TypedDict, total=False):
    """Structured parameters extracted from a natural-language prompt.

    Populated by :func:`extract_from_prompt`.  Keys map directly to fields
    expected by the various domain parsers (shaft, frame, bracket).
    """

    # Shaft parameters
    total_length_mm: float
    outer_diameter_mm: float
    inner_diameter_mm: float
    power_watts: float
    speed_rpm: float
    torque_nm: float
    material_id: str

    # Frame / Chair parameters
    seat_height_mm: float
    seat_width_mm: float
    seat_depth_mm: float
    num_legs: int
    has_arms: bool
    has_backrest: bool
    armrest_height_above_seat_mm: float
    armrest_length_mm: float
    armrest_width_mm: float
    armrest_overhang_front_mm: float
    backrest_height_above_seat_mm: float
    backrest_angle_deg: float
    leg_profile_outer_dimension_mm: float
    leg_profile_wall_thickness_mm: float
    seat_vertical_load_n: float
    left_arm_vertical_n: float
    right_arm_vertical_n: float

def extract_from_prompt(prompt: str) -> ExtractedParameters:
    """Parse dimension and load values from a free-form engineering prompt.

    The function uses deterministic regex patterns to pull out quantities
    (lengths in mm, forces in N, powers in W, etc.) and returns a
    typed ``ExtractedParameters`` dict.  Missing values retain their
    sensible defaults — callers should treat absent keys as *not* set.

    The extracted values are *unit-aware*: all lengths come out in
    millimetres, forces in Newtons, and power in Watts.
    """
    t = prompt.lower()

    # --- Length / Dimension extraction ---
    total_length_mm, _ = _extract_number_with_unit(
        t,
        [
            r"(\d+(?:\.\d+)?)\s*mm\b",
            r"(\d+(?:\.\d+)?)\s*millimeter\b",
            r"(\d+(?:\.\d+)?)\s*(?:long|length)\s*(?:of|:)?\s*(\d+(?:\.\d+)?)\s*mm\b",
            r"(\d+(?:\.\d+)?)\s*m\b(?!^\s*\^)",  # avoid 10^ style
        ],
        default=400.0,
    )

    outer_dia_mm, _ = _extract_number_with_unit(
        t,
        [
            r"(\d+(?:\.\d+)?)\s*mm\b(?:\\s+dia(?:meter)?)?\b",
            r"(\d+(?:\.\d+)?)\s*od\b",
            r"(\d+(?:\.\d+)?)\s*outer\s+diameter\b",
        ],
        default=28.0,
    )

    # --- Power / Speed ---
    power_watts, _ = extract_power(t)
    speed_rpm, _ = _extract_number_with_unit(
        t,
        [r"(\d+(?:\.\d+)?)\s*rpm\b", r"(\d+(?:\.\d+)?)\s*rev\s*min\b"],
        default=0.0,
    )

    # --- Loads (forces) ---
    # Seat load: try kg -> N conversion, then N directly
    seat_load_n, seat_found = _extract_number_with_unit(
        t,
        [
            r"(\d+(?:\.\d+)?)\s*kg\b(?:\\s+(?:seat|person|user|load|weight)?)?",
            r"(\d+(?:\.\d+)?)\s*n\b(?:\\s+(?:seat|person|user|load|weight)?)?",
            r"(\d+(?:\.\d+)?)\s*newton\b(?:\\s+(?:seat|person|user|load|weight)?)?",
        ],
        default=1300.0,
    )
    if not seat_found:
        seat_load_n = 1300.0  # keep default if not found

    arm_load_n, _ = _extract_number_with_unit(
        t,
        [
            r"(\d+(?:\.\d+)?)\s*n\b(?:\\s+(?:arm|armrest)?)?",
            r"(\d+(?:\.\d+)?)\s*newton\b(?:\\s+(?:arm|armrest)?)?",
            r"(\d+(?:\.\d+)?)\s*kg\b(?:\\s+(?:arm|armrest)?)?",
        ],
        default=450.0,
    )

    # --- Geometry-specific dimensions per domain ---
    seat_height_mm, _ = _extract_number_with_unit(
        t,
        [
            r"(\d+(?:\.\d+)?)\s*mm\b(?:\s+seat\s+height)?\b",
            r"(\d+(?:\.\d+)?)\s*seat\s+height\b(?:\s+mm)?\b",
            r"(\d+(?:\.\d+)?)\s*height\b(?:\s+mm)?\b",
        ],
        default=450.0,
    )

    seat_width_mm, _ = _extract_number_with_unit(
        t,
        [r"(\d+(?:\.\d+)?)\s*mm\b(?:\\s+width)?\b", r"(\d+(?:\.\d+)?)\s*width\b(?:\\s+mm)?\b"],
        default=450.0,
    )

    seat_depth_mm, _ = _extract_number_with_unit(
        t,
        [r"(\d+(?:\.\d+)?)\s*mm\b(?:\\s+depth)?\b", r"(\d+(?:\.\d+)?)\s*depth\b(?:\\s+mm)?\b"],
        default=450.0,
    )

    armrest_height_mm, _ = _extract_number_with_unit(
        t,
        [
            r"(\d+(?:\.\d+)?)\s*mm\b(?:\\s+height(?: above seat)?)?\b",
            r"(\d+(?:\.\d+)?)\s*height\b(?:\\s+above\s+seat)?\b(?:\\s+mm)?\b",
        ],
        default=210.0,
    )

    backrest_height_mm, _ = _extract_number_with_unit(
        t,
        [
            r"(\d+(?:\.\d+)?)\s*mm\b(?:\\s+back(?:rest)?)?\\s*height\b",
            r"(\d+(?:\.\d+)?)\s*back(?:rest)?\\s*height\b(?:\\s+mm)?\b",
        ],
        default=420.0,
    )

    backrest_angle_deg, _ = _extract_number_with_unit(
        t,
        [
            r"(\d+(?:\.\d+)?)\s*deg\b(?:\\s+back(?:rest)?)?\\s*angle\b",
            r"(\d+(?:\.\d+)?)\s*angle\b(?:\\s+back(?:rest)?)?\\b(?:\\s+deg)?\b",
        ],
        default=98.0,
    )

    # Leg / tube dimensions (for frame/chair)
    leg_outer_dia_mm, _ = _extract_number_with_unit(
        t,
        [r"(\d+(?:\.\d+)?)\s*mm\b(?:\\s+leg(?: tube)?)?\b", r"(\d+(?:\.\d+)?)\s*dia\b(?:\\s+mm)?\b"],
        default=28.0,
    )

    leg_wall_mm, _ = _extract_number_with_unit(
        t,
        [r"(\d+(?:\.\d+)?)\s*mm\b(?:\\s+wall(?: thickness)?)?\\s+leg\b", r"(\d+(?:\.\d+)?)\s*wall\b(?:\\s+mm)?\\b(?:\\s+leg)?\b"],
        default=2.0,
    )

    # Splay angle
    splay_angle_deg, _ = _extract_number_with_unit(
        t,
        [r"(\d+(?:\.\d+)?)\s*deg\b(?:\\s+splay)?\b", r"(\d+(?:\.\d+)?)\s*splay\b(?:\\s+deg)?\b"],
        default=3.5,
    )

    stretcher_height_mm, _ = _extract_number_with_unit(
        t,
        [r"(\d+(?:\.\d+)?)\s*mm\b(?:\\s+stretcher(?: height)?)?\b", r"(\d+(?:\.\d+)?)\s*stretcher\b(?:\\s+height)?\b(?:\\s+mm)?\b"],
        default=150.0,
    )

    # --- Return the structured dict ---
    return ExtractedParameters(  # type: ignore
        total_length_mm=total_length_mm,
        outer_diameter_mm=outer_dia_mm,
        inner_diameter_mm=outer_dia_mm * 0.6 if "hollow" in t else outer_dia_mm,
        power_watts=power_watts,
        speed_rpm=speed_rpm,
        torque_nm=power_watts / (2 * 3.14159 * speed_rpm / 60) if power_watts and speed_rpm else None,
        material_id="STEEL_1018",  # will be overridden by domain-specific logic
        # Frame / Chair fields
        seat_height_mm=seat_height_mm,
        seat_width_mm=seat_width_mm,
        seat_depth_mm=seat_depth_mm,
        num_legs=4,  # default, detected by classifier
        has_arms="arm" in t or "arms" in t,
        has_backrest="back" in t or "backrest" in t,
        armrest_height_above_seat_mm=armrest_height_mm,
        armrest_length_mm=320.0,  # default, can be overridden
        armrest_width_mm=45.0,  # default, can be overridden
        armrest_overhang_front_mm=60.0,  # default, can be overridden
        backrest_height_above_seat_mm=backrest_height_mm,
        backrest_angle_deg=backrest_angle_deg,
        leg_profile_outer_dimension_mm=leg_outer_dia_mm,
        leg_profile_wall_thickness_mm=leg_wall_mm,
        seat_vertical_load_n=seat_load_n,
        left_arm_vertical_n=arm_load_n,
        right_arm_vertical_n=arm_load_n,
    )


class NLParser:
    @staticmethod
    def parse(prompt: str) -> tuple[EngineeringModel, list[str]]:
        """
        Parse natural language prompt into an EngineeringModel.
        Attempts smart LLM routing across Groq, OpenRouter, and Gemini first.
        If no keys are configured or remote calls fail, falls back to deterministic NLP engine.
        """
        logs = []

        from ai.llm_router import LLMRouter

        if LLMRouter.get_configured_providers():
            try:
                model, llm_logs = NLParser._parse_with_llm(prompt)
                if model:
                    logs.extend(llm_logs)
                    return model, logs
                logs.extend(llm_logs)
            except Exception as e:
                logs.append(
                    f"LLM parse notice: {str(e)}. Falling back to deterministic NLP engine."
                )

        # Deterministic regex and engineering heuristic parser
        model, nlp_logs = NLParser._parse_deterministic(prompt)
        logs.extend(nlp_logs)
        return model, logs

    @staticmethod
    def _parse_with_llm(prompt: str) -> tuple[EngineeringModel | None, list[str]]:
        """Extract structured model using cascading LLMRouter (Groq -> OpenRouter -> Gemini)."""
        from ai.llm_router import LLMRouter

        system_instruction = (
            "You are an expert mechanical engineering parser for the Machine Design Intelligence Engine (MDIE).\n"
            "Extract structured parameters from the user's natural language request into a valid JSON object.\n"
            "Accurately capture all geometry, stepped shoulders, keyways, hollow bores, and features requested.\n"
            "Return ONLY raw JSON with the following schema:\n"
            "{\n"
            '  "name": "Component Name",\n'
            '  "component_type": "shaft" or "cantilever_beam" or "simply_supported_beam",\n'
            '  "total_length": float (in meters),\n'
            '  "power_watts": float or null,\n'
            '  "speed_rpm": float or null,\n'
            '  "torque_nm": float or null,\n'
            '  "material_id": "AISI_1045_CD" or "AISI_1018_CD" or "AISI_4140_QT" or "AL_7075_T6",\n'
            '  "initial_diameter_m": float (default 0.025 if segments not given),\n'
            '  "segments": [\n'
            "    {\n"
            '      "start_pos": float (m),\n'
            '      "end_pos": float (m),\n'
            '      "outer_diameter": float (m),\n'
            '      "inner_diameter": float (m, 0 for solid),\n'
            '      "feature_type": "bearing_seat" | "gear_mount" | "pulley_seat" | "smooth",\n'
            '      "fillet_radius": float (default 0.002),\n'
            '      "keyway": {"position": float (m), "length": float (m), "width": float (m), "depth": float (m)} or null\n'
            "    }\n"
            "  ],\n"
            '  "supports": [{"name": str, "support_type": "pinned"|"roller"|"fixed"|"bearing", "position": float (m)}],\n'
            '  "point_loads": [{"name": str, "magnitude": float (N), "position": float (m)}],\n'
            '  "distributed_loads": [{"name": str, "w_start": float (N/m), "w_end": float (N/m), "start_pos": float (m), "end_pos": float (m)}],\n'
            '  "constraints": {"min_yield_safety_factor": float, "min_fatigue_safety_factor": float, "max_deflection_mm": float, "target_life_cycles": float, "max_mass_kg": float or null}\n'
            "}\n"
            "If user requests stepped segments, bearing journals, or keyways, populate the 'segments' array with exact coordinates.\n"
            "If bearing positions are not specified for a shaft, default to standard outboard bearings near the ends (e.g. 10% and 90% of length).\n"
            "Convert all dimensions and loads to standard SI (length/diameter in meters, force in Newtons, power in Watts)."
        )

        raw_text, provider, logs = LLMRouter.call_chat_completion(
            system_prompt=system_instruction, user_prompt=prompt, response_format_json=True
        )

        if not raw_text:
            return None, logs

        # Clean JSON in case model wrapped it in code blocks
        clean_json_str = raw_text.strip()
        if clean_json_str.startswith("```"):
            clean_json_str = re.sub(r"^```(?:json)?\s*", "", clean_json_str)
            clean_json_str = re.sub(r"\s*```$", "", clean_json_str)

        data = json.loads(clean_json_str)
        model = NLParser._build_model_from_json(data, provider_name=provider or "llm")
        return model, logs

    @staticmethod
    def _parse_with_gemini(prompt: str, api_key: str) -> tuple[EngineeringModel, list[str]]:
        """Backward compatibility hook delegating to _parse_with_llm."""
        os.environ["GEMINI_API_KEY"] = api_key
        model, logs = NLParser._parse_with_llm(prompt)
        if model is None:
            raise RuntimeError("Gemini parse failed.")
        return model, logs

    @staticmethod
    def _build_model_from_json(
        data: dict[str, Any], provider_name: str = "llm"
    ) -> EngineeringModel:
        """Construct validated EngineeringModel from structured JSON data."""
        L = float(data.get("total_length") or 0.400)
        d_init = float(data.get("initial_diameter_m") or 0.025)

        supports = []
        for s in data.get("supports", []):
            supports.append(
                Support(
                    name=s.get("name", "Support"),
                    support_type=s.get("support_type", "pinned"),
                    position=float(s.get("position", 0.0)),
                )
            )

        point_loads = []
        for p in data.get("point_loads", []):
            point_loads.append(
                PointLoad(
                    name=p.get("name", "Load"),
                    magnitude=float(p.get("magnitude", 0.0)),
                    position=float(p.get("position", L / 2.0)),
                )
            )

        dist_loads = []
        for d in data.get("distributed_loads", []):
            dist_loads.append(
                DistributedLoad(
                    name=d.get("name", "DistLoad"),
                    start_pos=float(d.get("start_pos", 0.0)),
                    end_pos=float(d.get("end_pos", L)),
                    w_start=float(d.get("w_start", 0.0)),
                    w_end=float(d.get("w_end", d.get("w_start", 0.0))),
                )
            )

        c_data = data.get("constraints", {})
        constraints = EngineeringConstraints(
            min_yield_safety_factor=float(c_data.get("min_yield_safety_factor", 2.0)),
            min_fatigue_safety_factor=float(c_data.get("min_fatigue_safety_factor", 1.5)),
            max_deflection_mm=float(c_data.get("max_deflection_mm", 1.0)),
            target_life_cycles=float(c_data.get("target_life_cycles", 1e7)),
            max_mass_kg=float(c_data["max_mass_kg"]) if c_data.get("max_mass_kg") else None,
        )

        segments = []
        raw_segs = data.get("segments", [])
        if raw_segs and isinstance(raw_segs, list):
            from core.models import KeywaySpec

            for seg in raw_segs:
                kw_data = seg.get("keyway")
                kw_obj = None
                if kw_data and isinstance(kw_data, dict):
                    kw_obj = KeywaySpec(
                        position=float(kw_data.get("position", seg.get("start_pos", 0.0))),
                        length=float(kw_data.get("length", 0.040)),
                        width=float(kw_data.get("width", 0.008)),
                        depth=float(kw_data.get("depth", 0.004)),
                    )
                segments.append(
                    ShaftSegment(
                        start_pos=float(seg.get("start_pos", 0.0)),
                        end_pos=float(seg.get("end_pos", L)),
                        outer_diameter=float(seg.get("outer_diameter", d_init)),
                        inner_diameter=float(seg.get("inner_diameter", 0.0)),
                        feature_type=seg.get("feature_type", "smooth"),
                        fillet_radius=float(seg.get("fillet_radius", 0.002)),
                        keyway=kw_obj,
                    )
                )

        if not segments:
            segments = [
                ShaftSegment(start_pos=0.0, end_pos=L, outer_diameter=d_init, feature_type="smooth")
            ]

        model = EngineeringModel(
            name=data.get("name", "Parsed Machine Model"),
            component_type=data.get("component_type", "shaft"),
            total_length=L,
            power_watts=data.get("power_watts"),
            speed_rpm=data.get("speed_rpm"),
            torque_nm=data.get("torque_nm"),
            material_id=data.get("material_id", "AISI_1045_CD"),
            segments=segments,
            supports=supports,
            point_loads=point_loads,
            distributed_loads=dist_loads,
            constraints=constraints,
            metadata={"source": provider_name},
        )

        model.assumptions = AssumptionManager.audit_model(model)
        return model

    @staticmethod
    def _parse_deterministic(text: str) -> tuple[EngineeringModel, list[str]]:
        """
        Robust rule-based and regex engineering NLP parser.
        Extracts power, speed, loads, dimensions, boundary conditions, and constraints.
        """
        logs = ["Using MDIE deterministic engineering NLP parser."]
        t = text.lower()

        # Component Type & Boundary conditions
        is_cantilever = "cantilever" in t
        comp_type = "cantilever_beam" if is_cantilever else "shaft"

        # Total Length
        # Match e.g. "3 m", "400 mm", "0.5 m", "500mm length"
        len_match_mm = re.search(r"(\d+(?:\.\d+)?)\s*(?:mm|millimeter)", t)
        len_match_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|meter)\b", t)

        total_length = 0.400  # Default 400 mm
        if len_match_mm:
            total_length = float(len_match_mm.group(1)) / 1000.0
            logs.append(f"Extracted length: {total_length * 1000.0:.1f} mm")
        elif len_match_m:
            total_length = float(len_match_m.group(1))
            logs.append(f"Extracted length: {total_length:.3f} m")

        # Power
        power_w = None
        kw_match = re.search(r"(\d+(?:\.\d+)?)\s*kw\b", t)
        hp_match = re.search(r"(\d+(?:\.\d+)?)\s*hp\b", t)
        w_match = re.search(r"(\d+(?:\.\d+)?)\s*w\b", t)

        if kw_match:
            power_w = float(kw_match.group(1)) * 1000.0
            logs.append(f"Extracted power: {power_w / 1000.0:.2f} kW")
        elif hp_match:
            power_w = float(hp_match.group(1)) * 745.7
            logs.append(f"Extracted power: {power_w / 745.7:.2f} hp ({power_w:.1f} W)")
        elif w_match and "10^" not in t:
            power_w = float(w_match.group(1))

        # Speed (RPM)
        speed_rpm = None
        rpm_match = re.search(r"(\d+(?:\.\d+)?)\s*rpm\b", t)
        if rpm_match:
            speed_rpm = float(rpm_match.group(1))
            logs.append(f"Extracted speed: {speed_rpm:.0f} RPM")

        # Point Loads
        point_loads = []
        # Patterns like: "2.5 kN point load at 2 m", "300 N radial load at the center", "200 N"
        kn_matches = re.finditer(
            r"(\d+(?:\.\d+)?)\s*kn\b(?:\s+(?:point\s+)?load(?:\s+at\s+(\d+(?:\.\d+)?)\s*m)?)?", t
        )
        for m in kn_matches:
            f_val = float(m.group(1)) * 1000.0
            pos = float(m.group(2)) if m.group(2) else total_length / 2.0
            point_loads.append(
                PointLoad(
                    name=f"Point Load ({f_val / 1000:.1f} kN)",
                    magnitude=f_val,
                    position=min(pos, total_length),
                )
            )
            logs.append(f"Extracted point load: {f_val} N at x={pos}m")

        n_matches = re.finditer(
            r"(\d+(?:\.\d+)?)\s*n\b(?:\s+(?:radial\s+load|point\s+load|load))?(?:\s+(?:at\s+(?:the\s+)?(?:center|middle)|at\s+(\d+(?:\.\d+)?)\s*(?:m|mm)?))?",
            t,
        )
        for m in n_matches:
            f_val = float(m.group(1))
            # Ignore if part of "N*m" or "N/m" or "10^7"
            sub_str = t[max(0, m.start() - 2) : m.end() + 4]
            if "n·m" in sub_str or "n*m" in sub_str or "nm" in sub_str or "n/m" in sub_str:
                continue

            # Position determination
            if "center" in t or "middle" in t:
                pos = total_length / 2.0
            elif m.group(2):
                pos = float(m.group(2))
                if pos > total_length:
                    pos = pos / 1000.0
            else:
                pos = total_length / 2.0

            point_loads.append(
                PointLoad(
                    name=f"Point Load ({f_val:.0f} N)",
                    magnitude=f_val,
                    position=min(pos, total_length),
                )
            )
            logs.append(f"Extracted point load: {f_val} N at x={pos:.3f}m")

        # Distributed Loads (e.g. "1 kN/m distributed load")
        dist_loads = []
        dist_kn_match = re.search(r"(\d+(?:\.\d+)?)\s*kn/m", t)
        dist_n_match = re.search(r"(\d+(?:\.\d+)?)\s*n/m", t)
        if dist_kn_match:
            w = float(dist_kn_match.group(1)) * 1000.0
            dist_loads.append(
                DistributedLoad(
                    name="Uniform Distributed Load", start_pos=0.0, end_pos=total_length, w_start=w
                )
            )
            logs.append(f"Extracted distributed load: {w} N/m across span")
        elif dist_n_match:
            w = float(dist_n_match.group(1))
            dist_loads.append(
                DistributedLoad(
                    name="Uniform Distributed Load", start_pos=0.0, end_pos=total_length, w_start=w
                )
            )
            logs.append(f"Extracted distributed load: {w} N/m across span")

        # Constraints
        # Safety Factor
        sf = 2.0
        sf_match = re.search(
            r"(?:safety\s+factor|sf)(?:\s+(?:above|at\s+least|>=|>|=|of))?\s*(\d+(?:\.\d+)?)", t
        )
        if sf_match:
            sf = float(sf_match.group(1))
            logs.append(f"Extracted required Safety Factor: {sf}")

        # Mass limit
        mass_limit = None
        mass_match = re.search(
            r"(?:weighs\s+less\s+than|mass\s+<|mass\s+below|mass\s+under|<\s*)(\d+(?:\.\d+)?)\s*kg\b",
            t,
        )
        if mass_match:
            mass_limit = float(mass_match.group(1))
            logs.append(f"Extracted mass limit: {mass_limit} kg")

        # Fatigue cycles (e.g. "10 million cycles", "10^7 cycles")
        cycles = 1e7
        if "10 million" in t or "10m cycles" in t or "10^7" in t or "1e7" in t:
            cycles = 1e7
            logs.append(
                "Extracted fatigue life constraint: 10,000,000 cycles (Infinite Life target)"
            )
        elif "1 million" in t or "10^6" in t:
            cycles = 1e6

        # Material extraction
        mat_id = "AISI_1045_CD"
        if "4140" in t:
            mat_id = "AISI_4140_QT"
        elif "4340" in t:
            mat_id = "AISI_4340_QT"
        elif "1018" in t:
            mat_id = "AISI_1018_CD"
        elif "aluminum" in t or "6061" in t:
            mat_id = "AL_6061_T6"
        elif "7075" in t:
            mat_id = "AL_7075_T6"
        elif "titanium" in t or "ti-6al" in t:
            mat_id = "TI_6AL_4V"
        elif "stainless" in t or "304" in t:
            mat_id = "AISI_304_SS"

        logs.append(f"Selected material: {mat_id}")

        # Supports Setup
        supports = []
        if is_cantilever:
            supports.append(Support(name="Fixed Base", support_type="fixed", position=0.0))
            logs.append("Boundary condition: Fixed support at x = 0.0 m (Cantilever)")
        else:
            # Standard two-bearing mounting: outboard at ~10% and ~90% of span
            sup1_pos = round(0.10 * total_length, 3)
            sup2_pos = round(0.90 * total_length, 3)
            supports.append(Support(name="Bearing A", support_type="bearing", position=sup1_pos))
            supports.append(Support(name="Bearing B", support_type="bearing", position=sup2_pos))
            logs.append(
                f"Standard shaft bearings placed at x1={sup1_pos * 1000:.0f} mm and x2={sup2_pos * 1000:.0f} mm"
            )

        # Outer Diameter extraction
        init_d = 0.025  # 25 mm default
        dia_match = re.search(
            r"(?:outer\s+)?(?:diameter|dia|od)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*(?:mm|m)?", t
        )
        dia_match2 = re.search(r"(\d+(?:\.\d+)?)\s*mm\s+(?:diameter|dia|outer\s+diameter)", t)
        if dia_match:
            val = float(dia_match.group(1))
            init_d = (val / 1000.0) if val > 0.5 else val
            logs.append(f"Extracted explicit outer diameter: {init_d * 1000:.1f} mm")
        elif dia_match2:
            val = float(dia_match2.group(1))
            init_d = val / 1000.0
            logs.append(f"Extracted explicit outer diameter: {init_d * 1000:.1f} mm")

        # Inner Bore / Hollow extraction
        inner_d = 0.0
        bore_match = re.search(
            r"(?:inner\s+diameter|inner\s+bore|bore|id)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*(?:mm|m)?",
            t,
        )
        if bore_match:
            b_val = float(bore_match.group(1))
            inner_d = (b_val / 1000.0) if b_val > 0.5 else b_val
            logs.append(f"Extracted hollow inner bore: {inner_d * 1000:.1f} mm")
        elif "hollow" in t:
            # Default thin-walled bore at 60% of outer diameter
            inner_d = round(init_d * 0.6, 4)
            logs.append(f"Hollow shaft detected: defaulted inner bore to {inner_d * 1000:.1f} mm")

        # Keyway extraction
        has_keyway = "keyway" in t or "key" in t
        keyway_spec = None
        if has_keyway:
            from core.models import KeywaySpec

            kw_len = 0.040  # 40 mm default
            kw_w = round(max(0.004, init_d * 0.25), 4)  # standard ~ d/4
            kw_d = round(max(0.002, init_d * 0.125), 4)  # standard ~ d/8
            kw_pos = max(0.05, (total_length / 2.0) - (kw_len / 2.0))

            # Check for custom keyway length
            kw_len_match = re.search(
                r"keyway\s*(?:length\s*(?:of|=|:)?|of)?\s*(\d+(?:\.\d+)?)\s*mm", t
            )
            if kw_len_match:
                kw_len = float(kw_len_match.group(1)) / 1000.0

            keyway_spec = KeywaySpec(
                position=kw_pos, length=kw_len, width=kw_w, depth=kw_d, standard="DIN 6885 Form A"
            )
            logs.append(
                f"Added standard DIN 6885 keyway ({kw_w * 1000:.0f}x{kw_d * 1000:.1f} mm, length {kw_len * 1000:.0f} mm) at x={kw_pos * 1000:.0f} mm"
            )

        # Stepped Shaft Features
        is_stepped = "stepped" in t or "shoulder" in t or "journal" in t or "bearing seat" in t
        segments = []

        if is_stepped and total_length >= 0.15:
            # Create a 3-segment stepped shaft: [Bearing Seat 1] - [Main Shoulder / Gear Mount] - [Bearing Seat 2]
            d_bearing = init_d
            d_shoulder = round(init_d * 1.25, 4)  # 25% step for bearing location shoulder
            l_bearing = round(0.15 * total_length, 3)

            logs.append(
                f"Synthesized stepped shaft with shoulders: bearing seats d={d_bearing * 1000:.1f} mm, central span d={d_shoulder * 1000:.1f} mm"
            )

            # Segment 1: Bearing Seat Left
            segments.append(
                ShaftSegment(
                    start_pos=0.0,
                    end_pos=l_bearing,
                    outer_diameter=d_bearing,
                    inner_diameter=inner_d,
                    fillet_radius=0.002,
                    feature_type="bearing_seat",
                )
            )

            # Segment 2: Center Gear Mount / Transmitting zone (holds keyway)
            segments.append(
                ShaftSegment(
                    start_pos=l_bearing,
                    end_pos=total_length - l_bearing,
                    outer_diameter=d_shoulder,
                    inner_diameter=inner_d,
                    fillet_radius=0.002,
                    feature_type="gear_mount" if has_keyway else "smooth",
                    keyway=keyway_spec,
                )
            )

            # Segment 3: Bearing Seat Right
            segments.append(
                ShaftSegment(
                    start_pos=total_length - l_bearing,
                    end_pos=total_length,
                    outer_diameter=d_bearing,
                    inner_diameter=inner_d,
                    fillet_radius=0.002,
                    feature_type="bearing_seat",
                )
            )
        else:
            # Single uniform segment
            segments = [
                ShaftSegment(
                    start_pos=0.0,
                    end_pos=total_length,
                    outer_diameter=init_d,
                    inner_diameter=inner_d,
                    feature_type="smooth",
                    keyway=keyway_spec,
                )
            ]

        model = EngineeringModel(
            name="MDIE Machine Design Model",
            component_type=comp_type,
            total_length=total_length,
            power_watts=power_w,
            speed_rpm=speed_rpm,
            material_id=mat_id,
            segments=segments,
            supports=supports,
            point_loads=point_loads,
            distributed_loads=dist_loads,
            constraints=EngineeringConstraints(
                min_yield_safety_factor=sf,
                min_fatigue_safety_factor=max(1.3, sf * 0.75),
                max_deflection_mm=1.0,
                target_life_cycles=cycles,
                max_mass_kg=mass_limit,
            ),
            metadata={"source": "deterministic_nlp"},
        )

        model.assumptions = AssumptionManager.audit_model(model)
        return model, logs


class FrameNLParser:
    """Parse natural language into FrameDesignModel for frames/furniture/structures."""

    @staticmethod
    def parse(prompt: str) -> tuple[FrameDesignModel, list[str]]:
        logs = []

        from ai.llm_router import LLMRouter

        if LLMRouter.get_configured_providers():
            try:
                model, llm_logs = FrameNLParser._parse_with_llm(prompt)
                if model:
                    logs.extend(llm_logs)
                    return model, logs
                logs.extend(llm_logs)
            except Exception as e:
                logs.append(f"LLM parse notice: {str(e)}. Falling back to deterministic NLP engine.")

        model, nlp_logs = FrameNLParser._parse_deterministic(prompt)
        logs.extend(nlp_logs)
        return model, logs

    @staticmethod
    def _parse_with_llm(prompt: str) -> tuple[FrameDesignModel | None, list[str]]:
        from ai.llm_router import LLMRouter

        system_instruction = (
            "You are an expert mechanical engineering parser for MDIE frame/furniture designs.\n"
            "Extract structured parameters from the user's natural language request into a valid JSON object.\n"
            "Return ONLY raw JSON with the following schema:\n"
            "{\n"
            '  "name": "Frame Name",\n'
            '  "topology_type": "chair" | "stool" | "table" | "bench" | "tripod",\n'
            '  "material_id": "STEEL_1018" | "AL_6061_T6" | "WHITE_OAK" | "STAINLESS_304",\n'
            '  "num_legs": 3 | 4 | 6,\n'
            '  "has_arms": true | false,\n'
            '  "has_backrest": true | false,\n'
            '  "has_seat_plate": true | false,\n'
            '  "has_stretchers": true | false,\n'
            '  "seat_height_mm": float,\n'
            '  "seat_width_mm": float,\n'
            '  "seat_depth_mm": float,\n'
            '  "seat_thickness_mm": float,\n'
            '  "leg_splay_angle_deg": float,\n'
            '  "stretcher_height_mm": float,\n'
            '  "armrest_height_above_seat_mm": float,\n'
            '  "armrest_length_mm": float,\n'
            '  "armrest_width_mm": float,\n'
            '  "armrest_overhang_front_mm": float,\n'
            '  "armrest_front_post_y_mm": float,\n'
            '  "armrest_rear_post_y_over_depth": float,\n'
            '  "armrest_has_diagonal_brace": true | false,\n'
            '  "armrest_bracket_thickness_mm": float,\n'
            '  "armrest_bracket_height_mm": float,\n'
            '  "backrest_height_above_seat_mm": float,\n'
            '  "backrest_angle_deg": float,\n'
            '  "leg_profile": {"profile_type": "round_tube", "outer_dimension_mm": float, "wall_thickness_mm": float},\n'
            '  "frame_profile": {"profile_type": "square_tube", "outer_dimension_mm": float, "wall_thickness_mm": float},\n'
            '  "arm_profile": {"profile_type": "round_tube", "outer_dimension_mm": float, "wall_thickness_mm": float},\n'
            '  "stretcher_profile": {"profile_type": "round_tube", "outer_dimension_mm": float, "wall_thickness_mm": float},\n'
            '  "seat_vertical_load_n": float,\n'
            '  "seat_load_center_x_mm": float,\n'
            '  "seat_load_center_y_mm": float,\n'
            '  "left_arm_vertical_n": float,\n'
            '  "left_arm_lateral_n": float,\n'
            '  "left_arm_foreaft_n": float,\n'
            '  "left_arm_load_y_mm": float,\n'
            '  "right_arm_vertical_n": float,\n'
            '  "right_arm_lateral_n": float,\n'
            '  "right_arm_foreaft_n": float,\n'
            '  "right_arm_load_y_mm": float,\n'
            '  "backrest_force_n": float\n'
            "}\n"
            "All dimensions in mm, forces in N. Use defaults from FrameDesignModel if not specified.\n"
            "Convert kg to N (×9.81). Infer topology from keywords: chair/armchair→chair with arms+back, stool→no arms/back, table→table height, bench→long seat."
        )

        raw_text, provider, logs = LLMRouter.call_chat_completion(
            system_prompt=system_instruction, user_prompt=prompt, response_format_json=True
        )

        if not raw_text:
            return None, logs

        import re
        clean_json_str = raw_text.strip()
        if clean_json_str.startswith("```"):
            clean_json_str = re.sub(r"^```(?:json)?\s*", "", clean_json_str)
            clean_json_str = re.sub(r"\s*```$", "", clean_json_str)

        data = json.loads(clean_json_str)
        model = FrameNLParser._build_model_from_json(data, provider_name=provider or "llm")
        return model, logs

    @staticmethod
    def _build_model_from_json(data: dict[str, Any], provider_name: str = "llm") -> FrameDesignModel:
        """Construct validated FrameDesignModel from structured JSON data."""

        # Material
        mat_id = data.get("material_id", "STEEL_1018")
        material = STRUCTURAL_MATERIALS.get(mat_id, STRUCTURAL_MATERIALS["STEEL_1018"])

        # Geometry
        geom_data = data
        geom = FrameGeometry(
            topology_type=geom_data.get("topology_type", "chair"),
            num_legs=int(geom_data.get("num_legs", 4)),
            has_arms=bool(geom_data.get("has_arms", True)),
            has_backrest=bool(geom_data.get("has_backrest", True)),
            has_seat_plate=bool(geom_data.get("has_seat_plate", True)),
            has_stretchers=bool(geom_data.get("has_stretchers", True)),
            seat_height_mm=float(geom_data.get("seat_height_mm", 450.0)),
            seat_width_mm=float(geom_data.get("seat_width_mm", 480.0)),
            seat_depth_mm=float(geom_data.get("seat_depth_mm", 460.0)),
            seat_thickness_mm=float(geom_data.get("seat_thickness_mm", 22.0)),
            leg_splay_angle_deg=float(geom_data.get("leg_splay_angle_deg", 3.5)),
            stretcher_height_mm=float(geom_data.get("stretcher_height_mm", 150.0)),
            armrest_height_above_seat_mm=float(geom_data.get("armrest_height_above_seat_mm", 210.0)),
            armrest_length_mm=float(geom_data.get("armrest_length_mm", 320.0)),
            armrest_width_mm=float(geom_data.get("armrest_width_mm", 45.0)),
            armrest_overhang_front_mm=float(geom_data.get("armrest_overhang_front_mm", 60.0)),
            armrest_front_post_y_mm=float(geom_data.get("armrest_front_post_y_mm", 110.0)),
            armrest_rear_post_y_over_depth=float(geom_data.get("armrest_rear_post_y_over_depth", -1.0 / 3.0)),
            armrest_has_diagonal_brace=bool(geom_data.get("armrest_has_diagonal_brace", True)),
            armrest_bracket_thickness_mm=float(geom_data.get("armrest_bracket_thickness_mm", 12.0)),
            armrest_bracket_height_mm=float(geom_data.get("armrest_bracket_height_mm", 11.0)),
            backrest_height_above_seat_mm=float(geom_data.get("backrest_height_above_seat_mm", 420.0)),
            backrest_angle_deg=float(geom_data.get("backrest_angle_deg", 98.0)),
            leg_profile=TubeProfile(**(geom_data.get("leg_profile", {"profile_type": "round_tube", "outer_dimension_mm": 28.0, "wall_thickness_mm": 2.0}))),
            frame_profile=TubeProfile(**(geom_data.get("frame_profile", {"profile_type": "square_tube", "outer_dimension_mm": 25.0, "wall_thickness_mm": 2.0}))),
            arm_profile=TubeProfile(**(geom_data.get("arm_profile", {"profile_type": "round_tube", "outer_dimension_mm": 22.0, "wall_thickness_mm": 1.8}))),
            stretcher_profile=TubeProfile(**(geom_data.get("stretcher_profile", {"profile_type": "round_tube", "outer_dimension_mm": 19.0, "wall_thickness_mm": 1.5}))),
        )

        # Loads
        loads = FrameLoads(
            seat_vertical_load_n=float(geom_data.get("seat_vertical_load_n", 1300.0)),
            seat_load_center_x_mm=float(geom_data.get("seat_load_center_x_mm", 0.0)),
            seat_load_center_y_mm=float(geom_data.get("seat_load_center_y_mm", -25.0)),
            left_arm_vertical_n=float(geom_data.get("left_arm_vertical_n", 450.0)),
            left_arm_lateral_n=float(geom_data.get("left_arm_lateral_n", -150.0)),
            left_arm_foreaft_n=float(geom_data.get("left_arm_foreaft_n", 0.0)),
            left_arm_load_y_mm=float(geom_data.get("left_arm_load_y_mm", 0.0)),
            right_arm_vertical_n=float(geom_data.get("right_arm_vertical_n", 450.0)),
            right_arm_lateral_n=float(geom_data.get("right_arm_lateral_n", 150.0)),
            right_arm_foreaft_n=float(geom_data.get("right_arm_foreaft_n", 0.0)),
            right_arm_load_y_mm=float(geom_data.get("right_arm_load_y_mm", 0.0)),
            backrest_force_n=float(geom_data.get("backrest_force_n", 300.0)),
        )

        model = FrameDesignModel(
            name=data.get("name", "MDIE Frame Design"),
            geometry=geom,
            loads=loads,
            material=material,
            metadata={"source": provider_name},
        )

        # FrameDesignModel doesn't use AssumptionManager.audit_model (that's for shafts)
        return model

    @staticmethod
    def _parse_deterministic(text: str) -> tuple[FrameDesignModel, list[str]]:
        """Robust rule-based regex parser for frame/furniture requests."""
        logs = ["Using MDIE deterministic frame NLP parser."]
        t = text.lower().strip()

        # Topology detection
        topology = "chair"
        num_legs = 4
        has_arms = True
        has_backrest = True
        has_seat_plate = True
        has_stretchers = True

        if any(w in t for w in ["3 leg", "three leg", "tripod"]):
            topology = "stool"
            num_legs = 3
            has_arms = False
            has_backrest = False
        elif "stool" in t:
            topology = "stool"
            has_arms = False
            has_backrest = False
        elif any(w in t for w in ["table", "desk", "workbench"]):
            topology = "table"
            has_arms = False
            has_backrest = False
            has_seat_plate = True
        elif "bench" in t:
            topology = "bench"
            has_arms = False
            has_backrest = False
        elif any(w in t for w in ["no arm", "armless", "without arm"]):
            has_arms = False
        elif any(w in t for w in ["no back", "backless", "without back"]):
            has_backrest = False

        # Dimension extraction helpers
        def extract_mm(pattern: str, default: float, label: str) -> float:
            m = re.search(pattern, t)
            if m:
                # Handle multiple capture groups - find the first non-None group
                val = None
                for g in m.groups():
                    if g is not None:
                        val = float(g)
                        break
                if val is not None:
                    logs.append(f"Extracted {label}: {val} mm")
                    return val
            return default

        def extract_kg_to_n(pattern: str, default: float, label: str) -> float:
            m = re.search(pattern, t)
            if m:
                val = float(m.group(1)) * 9.81
                logs.append(f"Extracted {label}: {m.group(1)} kg = {val:.1f} N")
                return val
            return default

        # Main dimensions
        # More flexible patterns: match "500mm height", "height 500mm", "500 mm seat height", etc.
        seat_height = extract_mm(r"(?:seat|platform|table)\s*(?:height|tall)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?|(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:seat|platform|table)\s*(?:height|tall)", 450.0, "seat height")
        seat_width = extract_mm(r"(?:seat|platform|table)\s*(?:width|wide)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?|(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:seat|platform|table)\s*(?:width|wide)", 480.0, "seat width")
        seat_depth = extract_mm(r"(?:seat|platform|table)\s*(?:depth|deep)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?|(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:seat|platform|table)\s*(?:depth|deep)", 460.0, "seat depth")
        seat_thickness = extract_mm(r"(?:seat|pan|top)\s*(?:thickness|thick)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?|(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:seat|pan|top)\s*(?:thickness|thick)", 22.0, "seat thickness")

        # Leg splay - look for degree symbol or explicit "degree" or "splay"
        splay = extract_mm(r"(\d+(?:\.\d+)?)\s*(?:deg|degree|°)\s*(?:splay|flare|angle)|splay\s*(\d+(?:\.\d+)?)\s*(?:deg|degree|°)?", 3.5, "leg splay angle")

        # Stretcher
        stretcher_h = extract_mm(r"(?:stretcher|cross)\s*(?:height|high)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?|(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:stretcher|cross)\s*(?:height|high)", 150.0, "stretcher height")

        # Armrest
        arm_height = extract_mm(r"(?:arm|armrest)\s*(?:height|tall)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?|(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:arm|armrest)\s*(?:height|tall)", 210.0, "armrest height")
        arm_length = extract_mm(r"(?:arm|armrest)\s*(?:length|long)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?|(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:arm|armrest)\s*(?:length|long)", 320.0, "armrest length")
        arm_width = extract_mm(r"(?:arm|armrest)\s*(?:width|wide)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?|(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:arm|armrest)\s*(?:width|wide)", 45.0, "armrest width")
        arm_overhang = extract_mm(r"(?:overhang|cantilever)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?|(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:overhang|cantilever)", 60.0, "armrest overhang")

        # Backrest
        back_height = extract_mm(r"(?:back|backrest)\s*(?:height|tall)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?|(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:back|backrest)\s*(?:height|tall)", 420.0, "backrest height")
        back_angle = extract_mm(r"(?:back|backrest)\s*(?:angle|recline)\s*(\d+(?:\.\d+)?)\s*(?:deg|degree|°)?|(\d+(?:\.\d+)?)\s*(?:deg|degree|°)?\s*(?:back|backrest)\s*(?:angle|recline)", 98.0, "backrest angle")

        # Loads
        seat_load = extract_kg_to_n(r"(\d+(?:\.\d+)?)\s*kg\s*(?:seat|person|user|load|weight)?", 1300.0, "seat load")
        if seat_load == 1300.0:
            seat_load = extract_mm(r"(\d+(?:\.\d+)?)\s*(?:n|newtons?)\s*(?:seat|vertical)?", 1300.0, "seat load")

        arm_load_kg = re.search(r"(\d+(?:\.\d+)?)\s*kg\s*(?:arm|armrest)", t)
        arm_load = float(arm_load_kg.group(1)) * 9.81 if arm_load_kg else 450.0
        if arm_load == 450.0:
            arm_load = extract_mm(r"(\d+(?:\.\d+)?)\s*(?:n|newtons?)\s*(?:arm|armrest)", 450.0, "arm load")

        # Material
        mat_id = "STEEL_1018"
        if "4140" in t:
            mat_id = "AISI_4140_QT"
        elif "4340" in t:
            mat_id = "AISI_4340_QT"
        elif "1018" in t:
            mat_id = "STEEL_1018"
        elif "aluminum" in t or "6061" in t:
            mat_id = "AL_6061_T6"
        elif "7075" in t:
            mat_id = "AL_7075_T6"
        elif "oak" in t or "wood" in t:
            mat_id = "WHITE_OAK"
        elif "stainless" in t or "304" in t:
            mat_id = "STAINLESS_304"
        logs.append(f"Selected material: {mat_id}")

        # Tube profiles
        leg_dia = extract_mm(r"(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:leg|tube|dia)", 28.0, "leg tube OD")
        leg_wall = extract_mm(r"(\d+(?:\.\d+)?)\s*(?:mm|millimeter)?\s*(?:wall|thick)\s*(?:leg|tube)", 2.0, "leg wall thickness")

        # Build model
        geom = FrameGeometry(
            topology_type=topology,
            num_legs=num_legs,
            has_arms=has_arms,
            has_backrest=has_backrest,
            has_seat_plate=has_seat_plate,
            has_stretchers=has_stretchers,
            seat_height_mm=seat_height,
            seat_width_mm=seat_width,
            seat_depth_mm=seat_depth,
            seat_thickness_mm=seat_thickness,
            leg_splay_angle_deg=splay,
            stretcher_height_mm=stretcher_h,
            armrest_height_above_seat_mm=arm_height,
            armrest_length_mm=arm_length,
            armrest_width_mm=arm_width,
            armrest_overhang_front_mm=arm_overhang,
            backrest_height_above_seat_mm=back_height,
            backrest_angle_deg=back_angle,
            leg_profile=TubeProfile(profile_type="round_tube", outer_dimension_mm=leg_dia, wall_thickness_mm=leg_wall),
        )

        loads = FrameLoads(
            seat_vertical_load_n=seat_load,
            left_arm_vertical_n=arm_load,
            right_arm_vertical_n=arm_load,
        )

        material = STRUCTURAL_MATERIALS.get(mat_id, STRUCTURAL_MATERIALS["STEEL_1018"])

        model = FrameDesignModel(
            name="MDIE Frame Design",
            geometry=geom,
            loads=loads,
            material=material,
            metadata={"source": "deterministic_nlp"},
        )

        # FrameDesignModel doesn't use AssumptionManager.audit_model (that's for shafts)
        return model, logs

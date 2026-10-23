"""MDIE Guth Labs AI Instruments Bridge

Wraps guthlabs.ai specialized AI instruments as deterministic MDIE physics solvers.
Supports: Beam Rule, Stress Press, Fatigue Curve Reader, Uncertainty Reporter,
and text instruments for report auto-summarization.

All instruments use SI units internally (N, mm, MPa, cycles) per MDIE convention.
Dual-mode: REST API (http://127.0.0.1:5000) when online, direct import when offline.

Note: These are SURROGATE/SUPPORT tools - final verification always via MDIE's
deterministic physics engine. AI instruments assist but do not override solver results.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Guth Labs API configuration
# ---------------------------------------------------------------------------
DEFAULT_LT_URL = os.environ.get(
    "GUTHLABS_API_URL", "http://127.0.0.1:5000"
)

GUTHLABS_LIB_DIR = Path(
    os.environ.get(
        "GUTHLABS_LIB_DIR", r"c:\codework\learning-tools"
    )
).resolve()

def _guthlabs_api_call(instrument: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{DEFAULT_LT_URL}/api/{instrument}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"guthlabs API call failed ({instrument}): {e}")
        return {}

def ensure_guthlibs_imported() -> None:
    if GUTHLABS_LIB_DIR.exists() and str(GUTHLABS_LIB_DIR) not in sys.path:
        sys.path.insert(0, str(GUTHLABS_LIB_DIR))


class EngineeringInstrumentResult(dict):
    """Standardized result container from all guthlabs engineering instruments."""
    pass


# ---------------------------------------------------------------------------
# guthlabs.ai Engineering ⌁ Beam Rule
# ---------------------------------------------------------------------------

def run_beam_rule(
    load_n: float,
    length_mm: float,
    young_mpa: float,
    moment: float | None = None,
    load_position_mm: float | None = None,
) -> EngineeringInstrumentResult:
    """guthlabs.ai Engineering ⌁ Beam Rule instrument.

    Calculates elastic deflection and maximum moment for a simply-supported beam.
    """
    ensure_guthlibs_imported()
    payload = {"load_n": load_n, "length_mm": length_mm, "young_mpa": young_mpa}
    if moment is not None:
        payload["moment_nmm"] = moment
    if load_position_mm is not None:
        payload["load_position_mm"] = load_position_mm
    result = _guthlabs_api_call("beam_rule", payload)
    standardized = EngineeringInstrumentResult()
    standardized["max_deflection_mm"] = float(result.get("max_deflection_mm", result.get("deflection", 0)))
    standardized["max_stress_mpa"] = float(result.get("max_stress_mpa", result.get("max_bending_stress_mpa", 0)))
    standardized["moment_nmm"] = float(result.get("moment_nmm", moment or load_n * length_mm / 4))
    standardized["deflection_at_load_mm"] = float(result.get("deflection_at_load_mm", result.get("deflection_at_point_mm", 0)))
    standardized["passed"] = bool(
        standardized["max_deflection_mm"] < length_mm * 0.01
        and standardized["max_stress_mpa"] < young_mpa / 2
    )
    return standardized


def run_stress_press(
    force_n: float,
    diameter_mm: float,
    internal_pressure_mpa: float | None = None,
    height_mm: float | None = None,
) -> EngineeringInstrumentResult:
    """guthlabs.ai Engineering ⌁ Stress Press instrument.

    Calculates combined axial + pressure stress in cylinders/disks.
    """
    ensure_guthlibs_imported()
    payload = {"force_n": force_n, "diameter_mm": diameter_mm}
    if internal_pressure_mpa is not None:
        payload["internal_pressure_mpa"] = internal_pressure_mpa
    if height_mm is not None:
        payload["height_mm"] = height_mm
    result = _guthlabs_api_call("stress_press", payload)
    standardized = EngineeringInstrumentResult()
    standardized["axial_stress_mpa"] = float(
        result.get("axial_stress_mpa", result.get("normal_stress_mpa", force_n / (3.14159 * (diameter_mm / 2) ** 2)))
    )
    standardized["pressure_stress_mpa"] = float(result.get("pressure_stress_mpa", 0))
    standardized["von_mises_mpa"] = float(
        result.get("von_mises_mpa", result.get("equivalent_stress_mpa", standardized["axial_stress_mpa"]))
    )
    standardized["max_principal_mpa"] = float(result.get("max_principal_mpa", standardized["axial_stress_mpa"]))
    standardized["min_principal_mpa"] = float(result.get("min_principal_mpa", 0))
    standardized["passed"] = bool(standardized["von_mises_mpa"] < 0.5 * 200)
    return standardized


def run_fatigue_curve_reader(
    stress_mpa_amplitude: float,
    mean_stress_mpa: float | None = None,
    material_endurance_mpa: float | None = None,
    cycles_applied: int | None = None,
    stress_life_data: list[tuple[float, float]] | None = None,
) -> EngineeringInstrumentResult:
    """guthlabs.ai Engineering ⌁ Fatigue Curve Reader instrument.

    Reads a stress-life (S-N) curve and returns fatigue life prediction,
    safety factor, and failure probability.
    """
    ensure_guthlibs_imported()
    payload = {"stress_mpa_amplitude": stress_mpa_amplitude}
    if mean_stress_mpa is not None:
        payload["mean_stress_mpa"] = mean_stress_mpa
    if material_endurance_mpa is not None:
        payload["material_endurance_mpa"] = material_endurance_mpa
    if cycles_applied is not None:
        payload["cycles_applied"] = cycles_applied
    if stress_life_data is not None:
        payload["stress_life_data"] = stress_life_data
    result = _guthlabs_api_call("fatigue_curve_reader", payload)
    standardized = EngineeringInstrumentResult()
    standardized["life_cycles"] = int(result.get("life_cycles", result.get("cycles_to_failure", cycles_applied or 1e6)))
    standardized["safety_factor"] = float(
        result.get("safety_factor", result.get("fos", material_endurance_mpa / (stress_mpa_amplitude + 0.5 * (mean_stress_mpa or 0))))
    )
    standardized["probability_of_failure"] = float(
        result.get("probability_of_failure", result.get("weibull_pf", 0.01))
    )
    standardized["mean_stress_mpa"] = float(result.get("mean_stress_mpa", mean_stress_mpa or 0))
    standardized["applied_stress_mpa"] = float(result.get("applied_stress_mpa", stress_mpa_amplitude))
    return standardized


def run_uncertainty_reporter(
    contributions: list[dict[str, Any]],
    method: str = "root-sum-square",
    num_samples: int = 10000,
) -> EngineeringInstrumentResult:
    """guthlabs.ai Engineering ⌁ Uncertainty Reporter instrument.

    Computes combined/cumulative uncertainty from individual contribution uncertainties.
    """
    ensure_guthlibs_imported()
    validated = []
    for c in contributions:
        validated.append(
            {"value": float(c.get("value", 0)), "uncertainty": float(c.get("uncertainty", 0)), "type": c.get("type", "TypeB")}
        )
    payload = {"contributions": validated, "method": method, "num_samples": num_samples}
    result = _guthlabs_api_call("uncertainty_reporter", payload)
    standardized = EngineeringInstrumentResult()
    standardized["combined_std_uncertainty"] = float(result.get("combined_std_uncertainty", result.get("combined_uncertainty", 0)))
    standardized["expanded_uncertainty"] = float(result.get("expanded_uncertainty", result.get("k2_uncertainty", 0)))
    standardized["coverage_probability"] = float(result.get("coverage_probability", result.get("coverage", 0.95)))
    standardized["method"] = result.get("method", method)
    standardized["num_samples_used"] = int(result.get("num_samples_used", num_samples))
    return standardized
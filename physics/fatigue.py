"""
MDIE Physics Fatigue Analysis Engine
Computes Marin endurance limit modification factors, alternating/mean stress states,
fatigue failure safety factors (Goodman, Gerber, ASME-Elliptic, Soderberg), and S-N lifecycle predictions.
"""

import math
from typing import Any

from pydantic import BaseModel, Field

from core.models import EngineeringModel, SectionStress
from materials.database import Material


class MarinFactors:
    @staticmethod
    def surface_factor(s_ut_mpa: float, surface_type: str = "machined") -> float:
        """
        Marin surface condition factor ka = a * (Sut)^b.
        Parameters from Shigley's Mechanical Engineering Design.
        """
        params = {
            "ground": (1.58, -0.085),
            "machined": (4.51, -0.265),
            "cold_drawn": (4.51, -0.265),
            "hot_rolled": (57.7, -0.718),
            "as_forged": (272.0, -0.995),
        }
        surf = surface_type.lower().replace(" ", "_")
        a, b = params.get(surf, (4.51, -0.265))
        ka = a * (s_ut_mpa**b)
        return float(max(0.2, min(1.0, ka)))

    @staticmethod
    def size_factor(diameter_m: float) -> float:
        """
        Marin size factor kb for rotating round shafts.
        kb = 1.24 * d^(-0.107) for 2.79 <= d <= 51 mm
        kb = 1.51 * d^(-0.157) for 51 < d <= 254 mm
        """
        d_mm = diameter_m * 1000.0
        if d_mm <= 2.79:
            return 1.0
        elif d_mm <= 51.0:
            kb = 1.24 * (d_mm**-0.107)
        elif d_mm <= 254.0:
            kb = 1.51 * (d_mm**-0.157)
        else:
            kb = 0.6
        return float(max(0.5, min(1.0, kb)))

    @staticmethod
    def load_factor(load_type: str = "bending") -> float:
        """Marin load factor kc: bending=1.0, axial=0.85, torsion=0.59."""
        return {"bending": 1.0, "axial": 0.85, "torsion": 0.59}.get(load_type, 1.0)

    @staticmethod
    def reliability_factor(reliability: float = 0.99) -> float:
        """Marin reliability factor ke."""
        table = {
            0.50: 1.000,
            0.90: 0.897,
            0.95: 0.868,
            0.99: 0.814,
            0.999: 0.753,
            0.9999: 0.702,
        }
        for rel_level, factor in sorted(table.items()):
            if reliability <= rel_level:
                return factor
        return 0.753


class RepeatedLoadResult(BaseModel):
    """Non-rotating repeated (pulsating) loading check via mean/alternating stress.

    A chair arm under a seated occupant is *not* a rotating shaft: the stress
    cycles between zero and its peak as the user sits and stands, rather than
    fully reversing every revolution. Judging it with the bare fully-reversed
    ``S_e`` ignores the large mean stress that is actually present and so
    over-penalises the member.

    Stress ratio ``R = sigma_min / sigma_max``. ``R = 0`` is the seated
    sit/stand cycle; ``R = -1`` is the fully reversed bound.
    """

    stress_ratio_r: float = Field(..., description="R = sigma_min / sigma_max (dimensionless)")
    sigma_max_mpa: float = Field(..., description="Peak stress magnitude (MPa)")
    sigma_min_mpa: float = Field(..., description="Minimum stress magnitude (MPa)")
    sigma_a_mpa: float = Field(..., description="Alternating stress (sigma_max - sigma_min)/2 (MPa)")
    sigma_m_mpa: float = Field(..., description="Mean stress (sigma_max + sigma_min)/2 (MPa)")
    endurance_limit_mpa: float = Field(..., description="Fully corrected endurance limit Se (MPa)")
    nf_goodman: float = Field(..., description="Modified Goodman n (sigma_a/Se + sigma_m/Sut)")
    nf_gerber: float = Field(..., description="Gerber parabola n")
    nf_soderberg: float = Field(..., description="Soderberg n (most conservative of the three)")
    governing_nf: float = Field(..., description="Lowest of the three criteria (MPa)")
    governing_criterion: str = Field(..., description="Name of the criterion producing governing_nf")
    predicted_cycles: float = Field(..., description="Basquin S-N life at the Goodman-equivalent reversed stress")
    is_infinite_life: bool = Field(..., description="True when the equivalent reversed stress is at or below Se")


class FatigueSolver:
    @staticmethod
    def repeated_load_fatigue(
        sigma_max_mpa: float,
        s_ut_mpa: float,
        s_y_mpa: float,
        s_e_mpa: float,
        stress_ratio_r: float = 0.0,
    ) -> RepeatedLoadResult:
        """Fatigue check for repeated, non-reversing loading.

        The governing criterion is always the minimum of Goodman, Gerber and
        Soderberg so the result cannot be improved by choosing a friendlier
        line; ``criterion_used`` records which one is actually reported.
        """
        if not -1.0 <= stress_ratio_r <= 1.0:
            raise ValueError(f"stress_ratio_r must be within [-1, 1], got {stress_ratio_r}")
        if s_e_mpa <= 0.0 or s_ut_mpa <= 0.0 or s_y_mpa <= 0.0:
            raise ValueError("strengths and endurance limit must be positive")

        sigma_min = stress_ratio_r * sigma_max_mpa
        sigma_a = (sigma_max_mpa - sigma_min) / 2.0
        sigma_m = (sigma_max_mpa + sigma_min) / 2.0

        # 1. Modified Goodman
        d_goodman = (sigma_a / s_e_mpa) + (sigma_m / s_ut_mpa)
        nf_goodman = 1.0 / d_goodman if d_goodman > 1e-9 else 999.0

        # 2. Gerber parabola
        a_term = (sigma_m / s_ut_mpa) ** 2
        b_term = sigma_a / s_e_mpa
        root_term = 1.0 + (2.0 * sigma_m * s_e_mpa / (s_ut_mpa * sigma_a)) ** 2 if sigma_a > 1e-6 else 1.0
        nf_gerber = (1.0 / (2.0 * a_term * b_term)) * (-1.0 + math.sqrt(root_term)) if b_term > 1e-9 else 999.0

        # 3. Soderberg (most conservative)
        d_soderberg = (sigma_a / s_e_mpa) + (sigma_m / s_y_mpa)
        nf_soderberg = 1.0 / d_soderberg if d_soderberg > 1e-9 else 999.0

        candidates = {
            "goodman": nf_goodman,
            "gerber": nf_gerber,
            "soderberg": nf_soderberg,
        }
        governing_criterion = min(candidates, key=lambda k: candidates[k])

        # Basquin life at the Goodman-equivalent fully reversed stress.
        denom_rev = 1.0 - (sigma_m / s_ut_mpa)
        sigma_rev = (sigma_max_mpa / denom_rev) if denom_rev > 0.05 else sigma_max_mpa
        f_factor = 0.9
        s_1000 = f_factor * s_ut_mpa
        if sigma_rev <= s_e_mpa:
            is_infinite = True
            predicted_cycles = 1e8
        elif s_1000 > s_e_mpa:
            is_infinite = False
            b_exp = -(1.0 / 3.0) * math.log10(s_1000 / s_e_mpa)
            a_coeff = (s_1000**2) / s_e_mpa
            if sigma_rev < s_1000:
                predicted_cycles = float((sigma_rev / a_coeff) ** (1.0 / b_exp))
            else:
                predicted_cycles = float(max(100.0, 1000.0 * (s_1000 / sigma_rev) ** 3))
        else:
            is_infinite = False
            predicted_cycles = 1e4

        return RepeatedLoadResult(
            stress_ratio_r=stress_ratio_r,
            sigma_max_mpa=float(sigma_max_mpa),
            sigma_min_mpa=float(sigma_min),
            sigma_a_mpa=float(sigma_a),
            sigma_m_mpa=float(sigma_m),
            endurance_limit_mpa=float(s_e_mpa),
            nf_goodman=float(nf_goodman),
            nf_gerber=float(nf_gerber),
            nf_soderberg=float(nf_soderberg),
            governing_nf=float(candidates[governing_criterion]),
            governing_criterion=governing_criterion,
            predicted_cycles=float(predicted_cycles),
            is_infinite_life=is_infinite,
        )

    @staticmethod
    def evaluate_fatigue(
        critical_sec: SectionStress,
        material: Material,
        model: EngineeringModel,
        reliability: float = 0.99,
    ) -> dict[str, Any]:
        """
        Calculates endurance limit Se, fatigue safety factors (Goodman, Gerber, ASME-Elliptic),
        and predicts cycles to failure Nf.
        """
        s_ut = material.ultimate_strength_mpa
        s_y = material.yield_strength_mpa
        s_e_prime = material.endurance_limit_base_mpa
        diameter = critical_sec.outer_diameter

        # Compute Marin factors
        ka = MarinFactors.surface_factor(s_ut, "machined")
        kb = MarinFactors.size_factor(diameter)
        kc = MarinFactors.load_factor("bending")
        kd = 1.0  # Temperature factor (room temp)
        ke = MarinFactors.reliability_factor(reliability)
        kf_other = 1.0

        # Fully corrected endurance limit Se (MPa)
        s_e = ka * kb * kc * kd * ke * kf_other * s_e_prime

        # In rotating shafts:
        # Bending stress is completely reversed: sigma_a = Kf * sigma_b, sigma_m = 0
        sigma_a = critical_sec.kt_bending * critical_sec.bending_stress
        sigma_m = critical_sec.axial_stress

        # Torsion is typically steady: tau_m = Kts * tau, tau_a = 0
        tau_m = critical_sec.kt_torsion * critical_sec.torsional_stress
        tau_a = 0.0

        # Equivalent multiaxial alternating and mean Von Mises stresses
        sigma_a_prime = math.sqrt(sigma_a**2 + 3.0 * (tau_a**2))
        sigma_m_prime = math.sqrt(sigma_m**2 + 3.0 * (tau_m**2))

        # 1. Modified Goodman criterion: sigma_a'/Se + sigma_m'/Sut = 1 / nf
        denom_goodman = (sigma_a_prime / s_e) + (sigma_m_prime / s_ut)
        nf_goodman = 1.0 / denom_goodman if denom_goodman > 1e-9 else 999.0

        # 2. Gerber criterion
        if sigma_m_prime > 1e-6 and sigma_a_prime > 1e-6:
            a_term = (sigma_m_prime / s_ut) ** 2
            b_term = sigma_a_prime / s_e
            root_term = 1.0 + (2.0 * sigma_m_prime * s_e / (s_ut * sigma_a_prime)) ** 2
            nf_gerber = (1.0 / (2.0 * a_term * b_term)) * (-1.0 + math.sqrt(root_term))
        else:
            nf_gerber = s_e / sigma_a_prime if sigma_a_prime > 1e-9 else 999.0

        # 3. ASME-Elliptic criterion: (sigma_a'/Se)^2 + (sigma_m'/Sy)^2 = 1 / nf^2
        denom_asme = (sigma_a_prime / s_e) ** 2 + (sigma_m_prime / s_y) ** 2
        nf_asme = 1.0 / math.sqrt(denom_asme) if denom_asme > 1e-9 else 999.0

        # 4. Soderberg criterion: sigma_a'/Se + sigma_m'/Sy = 1 / nf
        denom_soderberg = (sigma_a_prime / s_e) + (sigma_m_prime / s_y)
        nf_soderberg = 1.0 / denom_soderberg if denom_soderberg > 1e-9 else 999.0

        # Life Prediction using Basquin S-N equation
        # Completely reversed equivalent stress sigma_rev = sigma_a_prime / (1 - sigma_m_prime / Sut)
        denom_rev = 1.0 - (sigma_m_prime / s_ut)
        sigma_rev = (sigma_a_prime / denom_rev) if denom_rev > 0.05 else sigma_a_prime

        f_factor = 0.9  # 0.9 for steels with Sut <= 1400 MPa
        s_1000 = f_factor * s_ut

        if sigma_rev <= s_e:
            is_infinite = True
            predicted_cycles = 1e8  # Infinite life (>10^6 - 10^7)
            life_description = "Infinite Life (N > 10^7 cycles)"
        else:
            is_infinite = False
            # Basquin parameters: S_f = a * N^b
            # b = -1/3 * log10(S_1000 / S_e)
            # a = (S_1000)^2 / S_e
            if s_1000 > s_e:
                b_exp = -(1.0 / 3.0) * math.log10(s_1000 / s_e)
                a_coeff = (s_1000**2) / s_e
                if sigma_rev < s_1000:
                    predicted_cycles = float((sigma_rev / a_coeff) ** (1.0 / b_exp))
                else:
                    # Low-cycle fatigue (<1000 cycles)
                    predicted_cycles = float(max(100.0, 1000.0 * (s_1000 / sigma_rev) ** 3))
            else:
                predicted_cycles = 1e4
            life_description = f"Finite Life (~{predicted_cycles:,.0f} cycles)"

        return {
            "endurance_limit_mpa": float(s_e),
            "ka_surface": float(ka),
            "kb_size": float(kb),
            "kc_load": float(kc),
            "ke_reliability": float(ke),
            "sigma_a_prime_mpa": float(sigma_a_prime),
            "sigma_m_prime_mpa": float(sigma_m_prime),
            "nf_goodman": float(nf_goodman),
            "nf_gerber": float(nf_gerber),
            "nf_asme": float(nf_asme),
            "nf_soderberg": float(nf_soderberg),
            "is_infinite_life": is_infinite,
            "predicted_cycles": float(predicted_cycles),
            "life_description": life_description,
        }

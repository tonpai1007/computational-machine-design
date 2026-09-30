"""
MDIE Physics Fatigue Analysis Engine
Computes Marin endurance limit modification factors, alternating/mean stress states,
fatigue failure safety factors (Goodman, Gerber, ASME-Elliptic, Soderberg), and S-N lifecycle predictions.
"""

import math
from typing import Dict, Any, Tuple
from mdie.core.models import EngineeringModel, SectionStress
from mdie.materials.database import Material

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
        ka = a * (s_ut_mpa ** b)
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
            kb = 1.24 * (d_mm ** -0.107)
        elif d_mm <= 254.0:
            kb = 1.51 * (d_mm ** -0.157)
        else:
            kb = 0.6
        return float(max(0.5, min(1.0, kb)))

    @staticmethod
    def load_factor(load_type: str = "bending") -> float:
        """Marin load factor kc: bending=1.0, axial=0.85, torsion=0.59."""
        if load_type == "bending":
            return 1.0
        elif load_type == "axial":
            return 0.85
        elif load_type == "torsion":
            return 0.59
        return 1.0

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


class FatigueSolver:
    @staticmethod
    def evaluate_fatigue(
        critical_sec: SectionStress,
        material: Material,
        model: EngineeringModel,
        reliability: float = 0.99
    ) -> Dict[str, Any]:
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
        denom_asme = (sigma_a_prime / s_e)**2 + (sigma_m_prime / s_y)**2
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
                a_coeff = (s_1000 ** 2) / s_e
                if sigma_rev < s_1000:
                    predicted_cycles = float((sigma_rev / a_coeff) ** (1.0 / b_exp))
                else:
                    # Low-cycle fatigue (<1000 cycles)
                    predicted_cycles = float(max(100.0, 1000.0 * (s_1000 / sigma_rev)**3))
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

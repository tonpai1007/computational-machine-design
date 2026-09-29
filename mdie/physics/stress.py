"""
MDIE Physics Stress Solver
Calculates bending, torsional, axial, and multiaxial Von Mises stresses,
along with geometric (Kt) and fatigue (Kf) stress concentration factors.
"""

import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from mdie.core.models import EngineeringModel, ShaftSegment, SectionStress
from mdie.materials.database import Material

class StressConcentration:
    @staticmethod
    def shoulder_fillet_kt(d_small: float, d_large: float, r_fillet: float) -> Tuple[float, float]:
        """
        Computes geometric stress concentration factors Kt (bending) and Kts (torsion)
        for a stepped circular shaft with a shoulder fillet.
        Based on Peterson's Stress Concentration Factors / Shigley formulations.
        """
        if d_small <= 0 or d_large <= 0:
            return 1.0, 1.0
        if d_large <= d_small or r_fillet <= 0:
            return 1.0, 1.0

        ratio_d = d_large / d_small
        ratio_r = r_fillet / d_small

        # Clamp to realistic mechanical design range
        ratio_r = max(0.01, min(0.3, ratio_r))
        ratio_d = max(1.01, min(3.0, ratio_d))

        # Peterson approximation for circular shaft shoulder with fillet in bending
        # Kt_b ~ 1 + 0.355 * (r/d)^(-0.37) * (D/d - 1)^0.22
        kt_bending = 1.0 + 0.355 * (ratio_r ** -0.37) * ((ratio_d - 1.0) ** 0.22)

        # Kts in torsion
        # Kts ~ 1 + 0.262 * (r/d)^(-0.35) * (D/d - 1)^0.20
        kt_torsion = 1.0 + 0.262 * (ratio_r ** -0.35) * ((ratio_d - 1.0) ** 0.20)

        return float(kt_bending), float(kt_torsion)

    @staticmethod
    def notch_sensitivity(s_ut_mpa: float, r_fillet_m: float) -> float:
        """
        Computes notch sensitivity q using Neuber's constant for steel.
        q = 1 / (1 + sqrt(a) / sqrt(r))
        """
        r_mm = r_fillet_m * 1000.0
        if r_mm <= 0:
            return 1.0

        # Empirical Neuber constant sqrt(a) in mm^0.5 for bending of steels
        s_ut = max(300.0, min(1500.0, s_ut_mpa))
        # Curve fit from Shigley Eq:
        # sqrt(a) = 0.246 - 3.08e-3 * Sut + 1.51e-5 * Sut^2 - 2.67e-9 * Sut^3
        # with Sut in kpsi. In MPa, let's use direct polynomial:
        s_ut_kpsi = s_ut * 0.145038
        sqrt_a_inch = 0.246 - 3.08e-3 * s_ut_kpsi + 1.51e-5 * (s_ut_kpsi**2) - 2.67e-9 * (s_ut_kpsi**3)
        sqrt_a_mm = sqrt_a_inch * math.sqrt(25.4)

        q = 1.0 / (1.0 + (sqrt_a_mm / math.sqrt(r_mm)))
        return float(max(0.1, min(1.0, q)))

    @staticmethod
    def fatigue_stress_concentration(kt: float, q: float) -> float:
        """Fatigue stress concentration factor Kf = 1 + q*(Kt - 1)."""
        return 1.0 + q * (kt - 1.0)


class StressSolver:
    @staticmethod
    def get_diameter_and_segment_at(model: EngineeringModel, x: float) -> Tuple[float, float, Optional[ShaftSegment]]:
        """Return (outer_diameter, inner_diameter, segment) at axial coordinate x."""
        for seg in model.segments:
            if seg.start_pos <= x <= seg.end_pos:
                return seg.outer_diameter, seg.inner_diameter, seg
        
        # Fallback if no explicit segments defined
        return 0.030, 0.0, None  # default 30mm

    @staticmethod
    def calculate_stresses(
        model: EngineeringModel,
        internal_dist: Dict[str, Any],
        material: Material
    ) -> Dict[str, Any]:
        """
        Compute bending, torsional, and Von Mises stresses across all stations.
        Applies stress concentrations at shoulder fillets and keyways.
        """
        x_arr = np.array(internal_dist["x"])
        m_arr = np.array(internal_dist["bending_moment"])
        t_arr = np.array(internal_dist["torque"])
        v_arr = np.array(internal_dist["shear_force"])
        n_pts = len(x_arr)

        sigma_bending = np.zeros(n_pts)
        tau_torsion = np.zeros(n_pts)
        von_mises = np.zeros(n_pts)
        effective_von_mises = np.zeros(n_pts)
        diameters = np.zeros(n_pts)
        kt_bending_arr = np.ones(n_pts)
        kt_torsion_arr = np.ones(n_pts)
        kf_bending_arr = np.ones(n_pts)

        # Detect shoulder transitions
        segments = sorted(model.segments, key=lambda s: s.start_pos)
        shoulder_stations = {}
        for i in range(len(segments) - 1):
            s1 = segments[i]
            s2 = segments[i + 1]
            x_trans = s1.end_pos
            d_smaller = min(s1.outer_diameter, s2.outer_diameter)
            d_larger = max(s1.outer_diameter, s2.outer_diameter)
            r_fillet = min(s1.fillet_radius, s2.fillet_radius)
            kt_b, kt_t = StressConcentration.shoulder_fillet_kt(d_smaller, d_larger, r_fillet)
            q = StressConcentration.notch_sensitivity(material.ultimate_strength_mpa, r_fillet)
            kf_b = StressConcentration.fatigue_stress_concentration(kt_b, q)
            shoulder_stations[round(x_trans, 5)] = (kt_b, kt_t, kf_b)

        # Keyway stations
        keyway_zones = []
        for seg in model.segments:
            if seg.keyway:
                kw = seg.keyway
                keyway_zones.append((kw.position, kw.position + kw.length, 2.14, 3.0))

        critical_sec: Optional[SectionStress] = None
        max_vm_eff = -1.0
        critical_idx = 0

        for i, x in enumerate(x_arr):
            do, di, seg = StressSolver.get_diameter_and_segment_at(model, x)
            diameters[i] = do * 1000.0  # in mm for display
            
            c = do / 2.0
            I = (math.pi / 64.0) * (do**4 - di**4) if do > 0 else 1e-12
            J = (math.pi / 32.0) * (do**4 - di**4) if do > 0 else 1e-12

            # Nominal stresses (Pa)
            m_abs = abs(m_arr[i])
            t_abs = abs(t_arr[i])
            sigma_b = (m_abs * c) / I
            tau_t = (t_abs * c) / J

            # Check for stress concentration
            kt_b = 1.0
            kt_t = 1.0
            kf_b = 1.0

            # Check shoulder proximity (within 1mm)
            for x_sh, (k_b, k_t, kf) in shoulder_stations.items():
                if abs(x - x_sh) < 0.002:
                    kt_b = max(kt_b, k_b)
                    kt_t = max(kt_t, k_t)
                    kf_b = max(kf_b, kf)

            # Check keyways
            for kw_start, kw_end, kw_kt_b, kw_kt_t in keyway_zones:
                if kw_start <= x <= kw_end:
                    kt_b = max(kt_b, kw_kt_b)
                    kt_t = max(kt_t, kw_kt_t)
                    q_kw = StressConcentration.notch_sensitivity(material.ultimate_strength_mpa, 0.0005)
                    kf_b = max(kf_b, StressConcentration.fatigue_stress_concentration(kw_kt_b, q_kw))

            kt_bending_arr[i] = kt_b
            kt_torsion_arr[i] = kt_t
            kf_bending_arr[i] = kf_b

            # Unnotched Von Mises (MPa)
            vm = math.sqrt(sigma_b**2 + 3.0 * (tau_t**2)) / 1e6
            # Effective concentrated Von Mises (for peak yield evaluation)
            vm_eff = math.sqrt((kt_b * sigma_b)**2 + 3.0 * ((kt_t * tau_t)**2)) / 1e6

            sigma_bending[i] = sigma_b / 1e6
            tau_torsion[i] = tau_t / 1e6
            von_mises[i] = vm
            effective_von_mises[i] = vm_eff

            if vm_eff > max_vm_eff:
                max_vm_eff = vm_eff
                critical_idx = i

        # Critical section details
        c_x = float(x_arr[critical_idx])
        c_do, _, _ = StressSolver.get_diameter_and_segment_at(model, c_x)
        c_mb = float(m_arr[critical_idx])
        c_sb = float(sigma_bending[critical_idx])
        c_t = float(t_arr[critical_idx])
        c_tau = float(tau_torsion[critical_idx])
        c_vm = float(von_mises[critical_idx])
        c_vm_eff = float(effective_von_mises[critical_idx])
        c_kt_b = float(kt_bending_arr[critical_idx])
        c_kt_t = float(kt_torsion_arr[critical_idx])

        # Principal stresses at critical section
        sig_x = c_kt_b * c_sb
        tau_xy = c_kt_t * c_tau
        r_mohr = math.sqrt((sig_x / 2.0)**2 + tau_xy**2)
        p1 = (sig_x / 2.0) + r_mohr
        p2 = (sig_x / 2.0) - r_mohr

        sf_yield = material.yield_strength_mpa / c_vm_eff if c_vm_eff > 0 else 999.0

        critical_sec = SectionStress(
            x=c_x,
            outer_diameter=c_do,
            bending_moment=c_mb,
            bending_stress=c_sb,
            torque=c_t,
            torsional_stress=c_tau,
            axial_force=0.0,
            axial_stress=0.0,
            von_mises_stress=c_vm,
            principal_stress_1=p1,
            principal_stress_2=p2,
            kt_bending=c_kt_b,
            kt_torsion=c_kt_t,
            effective_von_mises=c_vm_eff,
            yield_safety_factor=sf_yield,
            fatigue_safety_factor=1.0,  # Will be updated by fatigue solver
            predicted_cycles=1e9
        )

        return {
            "x": x_arr.tolist(),
            "diameters_mm": diameters.tolist(),
            "bending_stress_mpa": sigma_bending.tolist(),
            "torsional_stress_mpa": tau_torsion.tolist(),
            "von_mises_mpa": von_mises.tolist(),
            "effective_von_mises_mpa": effective_von_mises.tolist(),
            "kt_bending": kt_bending_arr.tolist(),
            "kt_torsion": kt_torsion_arr.tolist(),
            "kf_bending": kf_bending_arr.tolist(),
            "max_von_mises_mpa": float(np.max(effective_von_mises)),
            "max_von_mises_x": float(x_arr[np.argmax(effective_von_mises)]),
            "critical_section": critical_sec,
            "min_yield_safety_factor": float(sf_yield),
        }

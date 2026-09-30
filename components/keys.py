"""
MDIE Standard Key & Keyway Verification Engine
Sizes standard parallel keys per DIN 6885-1 / ISO 2491,
and checks shear stress (tau_key) and contact crushing pressure (sigma_crush).
"""

from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

class KeyCheckResult(BaseModel):
    standard: str = "DIN 6885-1 Form A"
    shaft_diameter_mm: float
    key_width_mm: float
    key_height_mm: float
    key_length_mm: float
    effective_length_mm: float
    torque_nm: float
    tangential_force_n: float
    shear_stress_mpa: float
    crushing_stress_mpa: float
    shear_safety_factor: float
    crushing_safety_factor: float
    passed: bool
    status_note: str


# DIN 6885-1 Standard parallel key dimensions: (d_min, d_max) -> (width, height, shaft_depth_t1)
DIN_6885_TABLE = [
    (10.0, 12.0, 4.0, 4.0, 2.5),
    (12.0, 17.0, 5.0, 5.0, 3.0),
    (17.0, 22.0, 6.0, 6.0, 3.5),
    (22.0, 30.0, 8.0, 7.0, 4.0),
    (30.0, 38.0, 10.0, 8.0, 5.0),
    (38.0, 44.0, 12.0, 8.0, 5.0),
    (44.0, 50.0, 14.0, 9.0, 5.5),
    (50.0, 58.0, 16.0, 10.0, 6.0),
    (58.0, 65.0, 18.0, 11.0, 7.0),
    (65.0, 75.0, 20.0, 12.0, 7.5),
    (75.0, 85.0, 22.0, 14.0, 9.0),
    (85.0, 95.0, 25.0, 14.0, 9.0),
    (95.0, 110.0, 28.0, 16.0, 10.0),
]

class KeyEngine:
    @staticmethod
    def get_standard_key_size(shaft_diameter_mm: float) -> Tuple[float, float, float]:
        """Lookup DIN 6885 standard (width_mm, height_mm, depth_t1_mm) for shaft diameter."""
        d = float(shaft_diameter_mm)
        for d_min, d_max, w, h, t1 in DIN_6885_TABLE:
            if d_min < d <= d_max:
                return w, h, t1
        # Fallback for very small or large
        if d <= 10.0:
            return 3.0, 3.0, 1.8
        return 32.0, 18.0, 11.0

    @classmethod
    def verify_key(
        cls,
        shaft_diameter_m: float,
        torque_nm: float,
        key_length_m: Optional[float] = None,
        key_yield_strength_mpa: float = 370.0,  # Standard C45 / AISI 1045 key stock (Sy ~ 370-530 MPa)
        allowable_crush_sf: float = 1.5,
        allowable_shear_sf: float = 2.0
    ) -> KeyCheckResult:
        """
        Calculates key shear stress tau and contact crushing pressure sigma_c.
        Tangential force: Ft = 2*T / d
        Shear stress: tau = Ft / (w * L_eff)
        Crushing stress: sigma_c = Ft / (t2 * L_eff)  where t2 = h - t1
        """
        d_mm = shaft_diameter_m * 1000.0
        d_m = shaft_diameter_m
        t_nm = max(0.1, abs(torque_nm))

        w_mm, h_mm, t1_mm = cls.get_standard_key_size(d_mm)
        t2_mm = h_mm - t1_mm  # Hub engagement depth

        # Default standard length: typically 1.5 * shaft diameter, clamped to standard lengths
        if key_length_m is None or key_length_m <= 0:
            l_mm = min(100.0, max(20.0, round(d_mm * 1.5 / 5.0) * 5.0))
        else:
            l_mm = key_length_m * 1000.0

        # Effective length for Form A rounded key: L_eff = L - width
        l_eff_mm = max(5.0, l_mm - w_mm)
        l_eff_m = l_eff_mm / 1000.0
        w_m = w_mm / 1000.0
        t2_m = t2_mm / 1000.0

        # Transmitted tangential force at shaft surface
        f_t = (2.0 * t_nm) / d_m  # Newtons

        # 1. Direct Shear Stress
        tau_key_pa = f_t / (w_m * l_eff_m)
        tau_key_mpa = tau_key_pa / 1e6

        # 2. Hub Surface Crushing Stress
        sigma_c_pa = f_t / (t2_m * l_eff_m)
        sigma_c_mpa = sigma_c_pa / 1e6

        # Allowable stresses based on key stock yield strength
        # Maximum shear stress theory (Tresca): S_sy = 0.5 * S_y, or Von Mises: S_sy = 0.577 * S_y
        s_sy = 0.577 * key_yield_strength_mpa
        s_cy = key_yield_strength_mpa

        sf_shear = s_sy / tau_key_mpa if tau_key_mpa > 0 else 999.0
        sf_crush = s_cy / sigma_c_mpa if sigma_c_mpa > 0 else 999.0

        passed = bool(sf_shear >= allowable_shear_sf and sf_crush >= allowable_crush_sf)
        
        if passed:
            note = f"Standard key {w_mm:.0f}x{h_mm:.0f}x{l_mm:.0f} mm verified. Shear SF = {sf_shear:.2f}, Crushing SF = {sf_crush:.2f}."
        else:
            note = f"Key stress warning! Increase key length L from {l_mm:.0f} mm to reduce shear/crushing stress."

        return KeyCheckResult(
            standard=f"DIN 6885-1 ({w_mm:.0f}x{h_mm:.0f}x{l_mm:.0f} mm)",
            shaft_diameter_mm=round(d_mm, 1),
            key_width_mm=round(w_mm, 1),
            key_height_mm=round(h_mm, 1),
            key_length_mm=round(l_mm, 1),
            effective_length_mm=round(l_eff_mm, 1),
            torque_nm=round(t_nm, 2),
            tangential_force_n=round(f_t, 1),
            shear_stress_mpa=round(tau_key_mpa, 2),
            crushing_stress_mpa=round(sigma_c_mpa, 2),
            shear_safety_factor=round(sf_shear, 2),
            crushing_safety_factor=round(sf_crush, 2),
            passed=passed,
            status_note=note
        )

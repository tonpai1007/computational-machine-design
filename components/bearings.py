"""
MDIE Standard Bearing Catalog & Life Calculation Engine
Matches reaction forces to standard SKF/ISO deep groove ball bearings and computes L10/L10h rating life.
Standards: ISO 281 / ISO 76.
"""

from __future__ import annotations

from pydantic import BaseModel


class BearingSpecification(BaseModel):
    designation: str
    series: str
    bore_diameter_mm: float
    outer_diameter_mm: float
    width_mm: float
    dynamic_load_c_kn: float
    static_load_c0_kn: float
    limiting_speed_rpm: float

    @property
    def dynamic_load_c_n(self) -> float:
        return self.dynamic_load_c_kn * 1000.0

    @property
    def static_load_c0_n(self) -> float:
        return self.static_load_c0_kn * 1000.0


class BearingLifeResult(BaseModel):
    bearing: BearingSpecification
    radial_load_n: float
    speed_rpm: float
    c_over_p: float
    l10_millions_rev: float
    l10h_hours: float
    status: str
    recommendation_note: str


# Curated catalog of standard SKF metric deep groove ball bearings (ISO 15)
SKF_BALL_BEARINGS: list[BearingSpecification] = [
    # 6000 Series (Extra Light)
    BearingSpecification(
        designation="SKF 6003",
        series="6000",
        bore_diameter_mm=17,
        outer_diameter_mm=35,
        width_mm=10,
        dynamic_load_c_kn=6.37,
        static_load_c0_kn=3.25,
        limiting_speed_rpm=28000,
    ),
    BearingSpecification(
        designation="SKF 6004",
        series="6000",
        bore_diameter_mm=20,
        outer_diameter_mm=42,
        width_mm=12,
        dynamic_load_c_kn=9.95,
        static_load_c0_kn=5.00,
        limiting_speed_rpm=24000,
    ),
    BearingSpecification(
        designation="SKF 6005",
        series="6000",
        bore_diameter_mm=25,
        outer_diameter_mm=47,
        width_mm=12,
        dynamic_load_c_kn=11.9,
        static_load_c0_kn=6.55,
        limiting_speed_rpm=20000,
    ),
    BearingSpecification(
        designation="SKF 6006",
        series="6000",
        bore_diameter_mm=30,
        outer_diameter_mm=55,
        width_mm=13,
        dynamic_load_c_kn=13.8,
        static_load_c0_kn=8.30,
        limiting_speed_rpm=17000,
    ),
    BearingSpecification(
        designation="SKF 6007",
        series="6000",
        bore_diameter_mm=35,
        outer_diameter_mm=62,
        width_mm=14,
        dynamic_load_c_kn=16.8,
        static_load_c0_kn=10.2,
        limiting_speed_rpm=15000,
    ),
    BearingSpecification(
        designation="SKF 6008",
        series="6000",
        bore_diameter_mm=40,
        outer_diameter_mm=68,
        width_mm=15,
        dynamic_load_c_kn=17.8,
        static_load_c0_kn=11.6,
        limiting_speed_rpm=13000,
    ),
    BearingSpecification(
        designation="SKF 6010",
        series="6000",
        bore_diameter_mm=50,
        outer_diameter_mm=80,
        width_mm=16,
        dynamic_load_c_kn=22.9,
        static_load_c0_kn=16.6,
        limiting_speed_rpm=11000,
    ),
    # 6200 Series (Light - Most Common Machinery Standard)
    BearingSpecification(
        designation="SKF 6203",
        series="6200",
        bore_diameter_mm=17,
        outer_diameter_mm=40,
        width_mm=12,
        dynamic_load_c_kn=9.95,
        static_load_c0_kn=4.75,
        limiting_speed_rpm=24000,
    ),
    BearingSpecification(
        designation="SKF 6204",
        series="6200",
        bore_diameter_mm=20,
        outer_diameter_mm=47,
        width_mm=14,
        dynamic_load_c_kn=13.5,
        static_load_c0_kn=6.55,
        limiting_speed_rpm=20000,
    ),
    BearingSpecification(
        designation="SKF 6205",
        series="6200",
        bore_diameter_mm=25,
        outer_diameter_mm=52,
        width_mm=15,
        dynamic_load_c_kn=14.8,
        static_load_c0_kn=7.80,
        limiting_speed_rpm=18000,
    ),
    BearingSpecification(
        designation="SKF 6206",
        series="6200",
        bore_diameter_mm=30,
        outer_diameter_mm=62,
        width_mm=16,
        dynamic_load_c_kn=20.3,
        static_load_c0_kn=11.2,
        limiting_speed_rpm=15000,
    ),
    BearingSpecification(
        designation="SKF 6207",
        series="6200",
        bore_diameter_mm=35,
        outer_diameter_mm=72,
        width_mm=17,
        dynamic_load_c_kn=27.0,
        static_load_c0_kn=15.3,
        limiting_speed_rpm=13000,
    ),
    BearingSpecification(
        designation="SKF 6208",
        series="6200",
        bore_diameter_mm=40,
        outer_diameter_mm=80,
        width_mm=18,
        dynamic_load_c_kn=32.5,
        static_load_c0_kn=19.0,
        limiting_speed_rpm=11000,
    ),
    BearingSpecification(
        designation="SKF 6209",
        series="6200",
        bore_diameter_mm=45,
        outer_diameter_mm=85,
        width_mm=19,
        dynamic_load_c_kn=35.1,
        static_load_c0_kn=21.6,
        limiting_speed_rpm=10000,
    ),
    BearingSpecification(
        designation="SKF 6210",
        series="6200",
        bore_diameter_mm=50,
        outer_diameter_mm=90,
        width_mm=20,
        dynamic_load_c_kn=37.1,
        static_load_c0_kn=23.2,
        limiting_speed_rpm=9500,
    ),
    # 6300 Series (Medium - Heavy Duty Radial Capacity)
    BearingSpecification(
        designation="SKF 6303",
        series="6300",
        bore_diameter_mm=17,
        outer_diameter_mm=47,
        width_mm=14,
        dynamic_load_c_kn=14.3,
        static_load_c0_kn=6.55,
        limiting_speed_rpm=20000,
    ),
    BearingSpecification(
        designation="SKF 6304",
        series="6300",
        bore_diameter_mm=20,
        outer_diameter_mm=52,
        width_mm=15,
        dynamic_load_c_kn=16.8,
        static_load_c0_kn=7.80,
        limiting_speed_rpm=18000,
    ),
    BearingSpecification(
        designation="SKF 6305",
        series="6300",
        bore_diameter_mm=25,
        outer_diameter_mm=62,
        width_mm=17,
        dynamic_load_c_kn=23.4,
        static_load_c0_kn=11.6,
        limiting_speed_rpm=15000,
    ),
    BearingSpecification(
        designation="SKF 6306",
        series="6300",
        bore_diameter_mm=30,
        outer_diameter_mm=72,
        width_mm=19,
        dynamic_load_c_kn=29.6,
        static_load_c0_kn=16.0,
        limiting_speed_rpm=13000,
    ),
    BearingSpecification(
        designation="SKF 6307",
        series="6300",
        bore_diameter_mm=35,
        outer_diameter_mm=80,
        width_mm=21,
        dynamic_load_c_kn=35.1,
        static_load_c0_kn=19.0,
        limiting_speed_rpm=11000,
    ),
    BearingSpecification(
        designation="SKF 6308",
        series="6300",
        bore_diameter_mm=40,
        outer_diameter_mm=90,
        width_mm=23,
        dynamic_load_c_kn=42.3,
        static_load_c0_kn=24.0,
        limiting_speed_rpm=10000,
    ),
    BearingSpecification(
        designation="SKF 6310",
        series="6300",
        bore_diameter_mm=50,
        outer_diameter_mm=110,
        width_mm=27,
        dynamic_load_c_kn=65.0,
        static_load_c0_kn=38.0,
        limiting_speed_rpm=8000,
    ),
]


class BearingCatalog:
    @classmethod
    def select_bearing(
        cls,
        shaft_diameter_m: float,
        radial_load_n: float,
        speed_rpm: float = 1500.0,
        preferred_series: str = "6200",
    ) -> BearingLifeResult:
        """
        Select standard SKF bearing for shaft journal and compute ISO 281 L10h rating life.
        L10 = (C / P)^3  [millions of revs]
        L10h = 10^6 / (60 * n) * L10  [hours]
        """
        dia_mm = shaft_diameter_m * 1000.0
        p_load = max(10.0, abs(radial_load_n))
        rpm = max(1.0, speed_rpm)

        # Find candidates matching bore
        exact_matches = [b for b in SKF_BALL_BEARINGS if abs(b.bore_diameter_mm - dia_mm) < 1.0]
        if not exact_matches:
            # Find closest standard bore size
            sorted_by_bore = sorted(
                SKF_BALL_BEARINGS, key=lambda b: abs(b.bore_diameter_mm - dia_mm)
            )
            target_bore = sorted_by_bore[0].bore_diameter_mm
            exact_matches = [b for b in SKF_BALL_BEARINGS if b.bore_diameter_mm == target_bore]

        # Prioritize preferred series (e.g. 6200 series)
        series_match = [b for b in exact_matches if b.series == preferred_series]
        chosen = series_match[0] if series_match else exact_matches[0]

        # If chosen bearing's static capacity is dangerously low, upgrade to 6300 series
        if p_load > chosen.static_load_c0_n * 0.5:
            heavy_match = [b for b in exact_matches if b.series == "6300"]
            if heavy_match:
                chosen = heavy_match[0]

        # Life calculation
        c_val = chosen.dynamic_load_c_n
        c_over_p = c_val / p_load
        l10_rev = c_over_p**3.0
        l10h = (1e6 / (60.0 * rpm)) * l10_rev

        # Operational status assessment
        if l10h >= 30000.0:
            status = "EXCELLENT"
            note = "L10h > 30,000 hrs. Well suited for continuous 24/7 industrial duty."
        elif l10h >= 10000.0:
            status = "GOOD"
            note = f"L10h = {l10h:,.0f} hrs. Satisfies 8-hr/day intermittent industrial duty (>10,000 hrs)."
        elif l10h >= 2500.0:
            status = "ACCEPTABLE"
            note = f"L10h = {l10h:,.0f} hrs. Adequate for consumer/automotive service with scheduled maintenance."
        else:
            status = "WARNING"
            note = f"L10h = {l10h:,.0f} hrs is marginal under load. Consider upgrading to series 6300 or larger bore."

        return BearingLifeResult(
            bearing=chosen,
            radial_load_n=p_load,
            speed_rpm=rpm,
            c_over_p=round(c_over_p, 2),
            l10_millions_rev=round(l10_rev, 2),
            l10h_hours=round(l10h, 0),
            status=status,
            recommendation_note=note,
        )

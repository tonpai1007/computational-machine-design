"""
MDIE Core Units Module
Handles engineering unit conversions between SI, metric engineering, and Imperial units.
"""


class Units:
    # Length conversions to meters (m)
    LENGTH_TO_M: dict[str, float] = {
        "m": 1.0,
        "mm": 1e-3,
        "cm": 1e-2,
        "in": 0.0254,
        "ft": 0.3048,
    }

    # Force conversions to Newtons (N)
    FORCE_TO_N: dict[str, float] = {
        "N": 1.0,
        "kN": 1e3,
        "MN": 1e6,
        "lbf": 4.4482216152605,
        "kgf": 9.80665,
    }

    # Stress / Pressure conversions to Pascals (Pa)
    STRESS_TO_PA: dict[str, float] = {
        "Pa": 1.0,
        "kPa": 1e3,
        "MPa": 1e6,
        "GPa": 1e9,
        "psi": 6894.757293168,
        "ksi": 6.894757293168e6,
        "bar": 1e5,
        "N/mm2": 1e6,
    }

    # Torque / Moment conversions to Newton-meters (N*m)
    TORQUE_TO_NM: dict[str, float] = {
        "N*m": 1.0,
        "Nm": 1.0,
        "N*mm": 1e-3,
        "Nmm": 1e-3,
        "kN*m": 1e3,
        "lbf*in": 0.1129848290276167,
        "lbf*ft": 1.3558179483314,
    }

    # Power conversions to Watts (W)
    POWER_TO_W: dict[str, float] = {
        "W": 1.0,
        "kW": 1e3,
        "MW": 1e6,
        "hp": 745.69987158227022,  # mechanical hp
        "metric_hp": 735.49875,
    }

    @classmethod
    def to_si(cls, value: float, unit_type: str, from_unit: str) -> float:
        """Convert a value to standard SI base unit (m, N, Pa, N*m, W)."""
        table_map = {
            "length": cls.LENGTH_TO_M,
            "force": cls.FORCE_TO_N,
            "stress": cls.STRESS_TO_PA,
            "torque": cls.TORQUE_TO_NM,
            "moment": cls.TORQUE_TO_NM,
            "power": cls.POWER_TO_W,
        }
        if unit_type not in table_map:
            raise ValueError(f"Unknown unit type '{unit_type}'. Valid: {list(table_map.keys())}")

        table = table_map[unit_type]
        if from_unit not in table:
            raise ValueError(
                f"Unknown unit '{from_unit}' for {unit_type}. Valid: {list(table.keys())}"
            )

        return value * table[from_unit]

    @classmethod
    def from_si(cls, value: float, unit_type: str, to_unit: str) -> float:
        """Convert a value from standard SI base unit to specified unit."""
        table_map = {
            "length": cls.LENGTH_TO_M,
            "force": cls.FORCE_TO_N,
            "stress": cls.STRESS_TO_PA,
            "torque": cls.TORQUE_TO_NM,
            "moment": cls.TORQUE_TO_NM,
            "power": cls.POWER_TO_W,
        }
        if unit_type not in table_map:
            raise ValueError(f"Unknown unit type '{unit_type}'")

        table = table_map[unit_type]
        if to_unit not in table:
            raise ValueError(f"Unknown unit '{to_unit}' for {unit_type}")

        return value / table[to_unit]

    @classmethod
    def rpm_to_rad_per_sec(cls, rpm: float) -> float:
        """Convert rotational speed in RPM to angular velocity in rad/s."""
        import math

        return rpm * (2.0 * math.pi / 60.0)

    @classmethod
    def rad_per_sec_to_rpm(cls, rad_s: float) -> float:
        """Convert angular velocity in rad/s to RPM."""
        import math

        return rad_s * (60.0 / (2.0 * math.pi))

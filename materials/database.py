"""
MDIE Materials Database
Curated mechanical properties for engineering alloys, steels, aluminums, titanium, and bronzes.
Data sourced from standard engineering references (Shigley's Mechanical Engineering Design, ASM Handbooks).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Material(BaseModel):
    id: str
    name: str
    category: str = Field(
        ...,
        description="'carbon_steel', 'alloy_steel', 'stainless_steel', 'aluminum', 'titanium', 'cast_iron', 'copper_alloy'",
    )
    yield_strength_mpa: float = Field(..., description="Yield tensile strength Sy in MPa")
    ultimate_strength_mpa: float = Field(..., description="Ultimate tensile strength Sut in MPa")
    elastic_modulus_gpa: float = Field(..., description="Young's modulus E in GPa")
    shear_modulus_gpa: float = Field(..., description="Shear modulus G in GPa")
    poissons_ratio: float = Field(0.29, description="Poisson's ratio nu")
    density_kg_m3: float = Field(..., description="Mass density rho in kg/m3")
    endurance_limit_base_mpa: float = Field(
        ..., description="Uncorrected rotary beam endurance limit Se' in MPa"
    )
    machinability_rating: float = Field(
        100.0, description="Machinability index relative to AISI 1212 = 100%"
    )
    cost_index_per_kg: float = Field(
        1.0, description="Normalized relative material cost index per kg (AISI 1018 ~ 1.0)"
    )
    description: str = ""

    @property
    def elastic_modulus_pa(self) -> float:
        return self.elastic_modulus_gpa * 1e9

    @property
    def shear_modulus_pa(self) -> float:
        return self.shear_modulus_gpa * 1e9

    @property
    def yield_strength_pa(self) -> float:
        return self.yield_strength_mpa * 1e6

    @property
    def ultimate_strength_pa(self) -> float:
        return self.ultimate_strength_mpa * 1e6

    @property
    def endurance_limit_base_pa(self) -> float:
        return self.endurance_limit_base_mpa * 1e6


MATERIALS_DB: dict[str, Material] = {
    # Carbon Steels
    "AISI_1018_CD": Material(
        id="AISI_1018_CD",
        name="AISI 1018 Cold Drawn Steel",
        category="carbon_steel",
        yield_strength_mpa=370.0,
        ultimate_strength_mpa=440.0,
        elastic_modulus_gpa=205.0,
        shear_modulus_gpa=79.3,
        poissons_ratio=0.29,
        density_kg_m3=7850.0,
        endurance_limit_base_mpa=220.0,
        machinability_rating=78.0,
        cost_index_per_kg=1.0,
        description="General purpose low-carbon mild steel shafting, easily welded and machined.",
    ),
    "AISI_1045_CD": Material(
        id="AISI_1045_CD",
        name="AISI 1045 Cold Drawn Steel",
        category="carbon_steel",
        yield_strength_mpa=530.0,
        ultimate_strength_mpa=625.0,
        elastic_modulus_gpa=206.0,
        shear_modulus_gpa=80.0,
        poissons_ratio=0.29,
        density_kg_m3=7850.0,
        endurance_limit_base_mpa=312.5,
        machinability_rating=57.0,
        cost_index_per_kg=1.2,
        description="Workhorse medium-carbon machinery steel for transmission shafts, axles, and studs.",
    ),
    "AISI_1045_QT": Material(
        id="AISI_1045_QT",
        name="AISI 1045 Quenched & Tempered (540°C)",
        category="carbon_steel",
        yield_strength_mpa=620.0,
        ultimate_strength_mpa=770.0,
        elastic_modulus_gpa=206.0,
        shear_modulus_gpa=80.0,
        poissons_ratio=0.29,
        density_kg_m3=7850.0,
        endurance_limit_base_mpa=385.0,
        machinability_rating=50.0,
        cost_index_per_kg=1.5,
        description="Heat-treated carbon steel offering enhanced fatigue resistance and strength.",
    ),
    # Alloy Steels
    "AISI_4140_QT": Material(
        id="AISI_4140_QT",
        name="AISI 4140 Chromoly Steel (Q&T 540°C)",
        category="alloy_steel",
        yield_strength_mpa=850.0,
        ultimate_strength_mpa=1020.0,
        elastic_modulus_gpa=210.0,
        shear_modulus_gpa=80.0,
        poissons_ratio=0.30,
        density_kg_m3=7850.0,
        endurance_limit_base_mpa=510.0,
        machinability_rating=55.0,
        cost_index_per_kg=2.3,
        description="High-strength chrome-moly alloy steel for heavy duty power transmission, severe fatigue.",
    ),
    "AISI_4340_QT": Material(
        id="AISI_4340_QT",
        name="AISI 4340 Nickel-Chromium-Moly Steel (Q&T)",
        category="alloy_steel",
        yield_strength_mpa=1100.0,
        ultimate_strength_mpa=1280.0,
        elastic_modulus_gpa=210.0,
        shear_modulus_gpa=80.0,
        poissons_ratio=0.30,
        density_kg_m3=7850.0,
        endurance_limit_base_mpa=640.0,
        machinability_rating=40.0,
        cost_index_per_kg=3.8,
        description="Ultra-high strength aerospace and high-stress automotive transmission shaft alloy.",
    ),
    # Stainless Steels
    "AISI_304_SS": Material(
        id="AISI_304_SS",
        name="AISI 304 Stainless Steel (Annealed)",
        category="stainless_steel",
        yield_strength_mpa=215.0,
        ultimate_strength_mpa=505.0,
        elastic_modulus_gpa=193.0,
        shear_modulus_gpa=74.0,
        poissons_ratio=0.29,
        density_kg_m3=8000.0,
        endurance_limit_base_mpa=240.0,
        machinability_rating=45.0,
        cost_index_per_kg=3.5,
        description="Austenitic stainless steel with excellent corrosion resistance in chemical & food machinery.",
    ),
    "AISI_316_SS": Material(
        id="AISI_316_SS",
        name="AISI 316 Stainless Steel (Annealed)",
        category="stainless_steel",
        yield_strength_mpa=290.0,
        ultimate_strength_mpa=580.0,
        elastic_modulus_gpa=193.0,
        shear_modulus_gpa=74.0,
        poissons_ratio=0.30,
        density_kg_m3=8000.0,
        endurance_limit_base_mpa=275.0,
        machinability_rating=36.0,
        cost_index_per_kg=4.8,
        description="Molybdenum-bearing marine grade stainless steel, resistant to pitting and chlorides.",
    ),
    # Aluminum Alloys
    "AL_6061_T6": Material(
        id="AL_6061_T6",
        name="Aluminum 6061-T6",
        category="aluminum",
        yield_strength_mpa=276.0,
        ultimate_strength_mpa=310.0,
        elastic_modulus_gpa=68.9,
        shear_modulus_gpa=26.0,
        poissons_ratio=0.33,
        density_kg_m3=2700.0,
        endurance_limit_base_mpa=96.5,
        machinability_rating=90.0,
        cost_index_per_kg=2.8,
        description="Lightweight structural aluminum with balanced strength, weldability, and corrosion resistance.",
    ),
    "AL_7075_T6": Material(
        id="AL_7075_T6",
        name="Aluminum 7075-T6",
        category="aluminum",
        yield_strength_mpa=503.0,
        ultimate_strength_mpa=572.0,
        elastic_modulus_gpa=71.7,
        shear_modulus_gpa=26.9,
        poissons_ratio=0.33,
        density_kg_m3=2810.0,
        endurance_limit_base_mpa=159.0,
        machinability_rating=70.0,
        cost_index_per_kg=5.2,
        description="Aircraft-grade high-strength zinc alloy aluminum for weight-critical aerospace and robotics.",
    ),
    # Titanium
    "TI_6AL_4V": Material(
        id="TI_6AL_4V",
        name="Titanium Ti-6Al-4V (Grade 5)",
        category="titanium",
        yield_strength_mpa=880.0,
        ultimate_strength_mpa=950.0,
        elastic_modulus_gpa=113.8,
        shear_modulus_gpa=44.0,
        poissons_ratio=0.342,
        density_kg_m3=4430.0,
        endurance_limit_base_mpa=510.0,
        machinability_rating=22.0,
        cost_index_per_kg=18.0,
        description="Extreme specific strength, corrosion-proof, exceptional fatigue endurance at lightweight.",
    ),
    # Bronze
    "BRONZE_C93200": Material(
        id="BRONZE_C93200",
        name="SAE 660 Bearing Bronze (C93200)",
        category="copper_alloy",
        yield_strength_mpa=140.0,
        ultimate_strength_mpa=240.0,
        elastic_modulus_gpa=100.0,
        shear_modulus_gpa=38.0,
        poissons_ratio=0.34,
        density_kg_m3=8930.0,
        endurance_limit_base_mpa=110.0,
        machinability_rating=70.0,
        cost_index_per_kg=4.2,
        description="Standard sleeve bearing and bushing bronze with superior antifriction and wear resistance.",
    ),
}


class MaterialDatabase:
    @classmethod
    def get(cls, material_id: str) -> Material:
        """Fetch material by ID or raise informative error with available materials."""
        # Try exact match
        if material_id in MATERIALS_DB:
            return MATERIALS_DB[material_id]

        # Try case-insensitive and normalized match
        norm = material_id.upper().replace("-", "_").replace(" ", "_")
        for k, v in MATERIALS_DB.items():
            if norm == k or norm in k:
                return v

        # Keyword search
        for k, v in MATERIALS_DB.items():
            if norm in v.name.upper().replace("-", "_").replace(" ", "_"):
                return v

        available = list(MATERIALS_DB.keys())
        raise KeyError(
            f"Material '{material_id}' not found in database. Available options: {available}"
        )

    @classmethod
    def list_all(cls) -> list[Material]:
        """Return all materials in the database."""
        return list(MATERIALS_DB.values())

    @classmethod
    def find_candidates_for_safety_factor(
        cls, max_stress_mpa: float, target_sf: float = 2.0
    ) -> list[Material]:
        """Find all materials where Sy >= max_stress * target_sf."""
        req_yield = max_stress_mpa * target_sf
        candidates = [m for m in MATERIALS_DB.values() if m.yield_strength_mpa >= req_yield]
        # Sort by cost index ascending
        candidates.sort(key=lambda m: m.cost_index_per_kg)
        return candidates

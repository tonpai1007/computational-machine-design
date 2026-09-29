"""
MDIE Domain Intent Classifier & Semantic Router
Accurately categorizes user engineering prompts into specific machine design domains:
- 'shaft': Rotating shafts, power transmission, stepped shafts, beams.
- 'frame': Chairs, stools, tables, desks, benches, multi-column chassis.
- 'space_frame': 3D space trusses, transmission towers, cantilever box girders.
- 'bracket': Motor mounting brackets, flange plates, L-brackets with bolt hole patterns.
- 'unsupported': Recognizes out-of-scope concepts explicitly rather than falling back silently.
"""

import re
from typing import Tuple, Dict, Any, Optional


class DomainClassifier:
    """Classifies natural language mechanical requests into supported MDIE domains."""

    BRACKET_KEYWORDS = [
        "bracket", "mount", "mounting", "motor mount", "l-bracket", "l bracket",
        "flange plate", "faceplate", "adapter plate", "motor plate", "bolt hole",
        "bolt pattern", "stiffener plate"
    ]

    SPACE_FRAME_KEYWORDS = [
        "tower", "truss", "space frame", "girder", "spatial frame", "lattice",
        "cantilever truss", "transmission tower", "mast"
    ]

    FRAME_KEYWORDS = [
        "chair", "armchair", "furniture", "stool", "table", "desk", "bench",
        "workbench", "tripod", "3 leg", "three leg", "4 leg", "four leg",
        "armrest", "seating", "stand"
    ]

    SHAFT_KEYWORDS = [
        "shaft", "axle", "stepped shaft", "spindle", "rotor", "bearing journal",
        "keyway", "torque", "rpm", "transmission shaft", "drive shaft"
    ]

    UNSUPPORTED_DOMAINS = {
        "gear": "Gears & Transmission (Spur / Helical / Planetary)",
        "spring": "Springs (Helical Compression / Extension / Torsion)",
        "bearing": "Bearings (Deep Groove / Roller Bearing Selection)",
        "screw": "Power Screws & Lead Screws",
        "pressure vessel": "Pressure Vessels & Cylinders (ASME Boiler & Pressure Code)",
        "clutch": "Clutches & Brakes",
        "belt": "V-Belt & Timing Belt Drives",
        "chain": "Roller Chain Drives",
        "fastener": "Threaded Fasteners & Bolted Joint Analysis",
        "weld": "Welded Structural Joints (AWS Standards)"
    }

    @classmethod
    def classify(cls, prompt: str) -> Tuple[str, Dict[str, Any]]:
        """
        Classify prompt into domain.
        Returns (domain_key, metadata).
        """
        p_lower = prompt.lower().strip()

        # 1. Check for Mounting Brackets & Plates
        if any(w in p_lower for w in cls.BRACKET_KEYWORDS):
            return "bracket", {"confidence": 0.95, "matched": "bracket"}

        # 2. Check for 3D Space Frames & Towers
        if any(w in p_lower for w in cls.SPACE_FRAME_KEYWORDS):
            return "space_frame", {"confidence": 0.95, "matched": "space_frame"}

        # 3. Check for Furniture / Column Frames (tables, chairs, stools)
        if any(w in p_lower for w in cls.FRAME_KEYWORDS):
            return "frame", {"confidence": 0.95, "matched": "frame"}

        # 4. Check for Shafts / Power Transmission
        if any(w in p_lower for w in cls.SHAFT_KEYWORDS):
            return "shaft", {"confidence": 0.95, "matched": "shaft"}

        # 5. Check if it's explicitly an unsupported engineering domain
        for kw, domain_name in cls.UNSUPPORTED_DOMAINS.items():
            if kw in p_lower:
                return "unsupported", {
                    "unsupported_domain": domain_name,
                    "keyword": kw,
                    "message": f"MDIE currently supports: 1) Rotating Shafts, 2) Frames/Furniture, 3) 3D Space Trusses, and 4) Mounting Brackets."
                }

        # 6. Fallback based on physics cues
        if any(w in p_lower for w in ["kw", "rpm", "torque", "n*m", "nm", "deflection"]):
            return "shaft", {"confidence": 0.70, "matched": "shaft_physics_cues"}

        # Default domain: shaft with low confidence notice
        return "shaft", {"confidence": 0.50, "matched": "default"}

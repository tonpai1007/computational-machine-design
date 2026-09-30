"""MDIE - Mechanical Design Intelligence Engine.

Describe a part in plain language; MDIE builds the geometry, runs the
structural analysis and emits CAD, drawings and engineering reports.

Subpackages
-----------
``core``          geometry primitives, units and the design data model
``cad``           solid modelling, STEP/STL export, OpenSCAD emission
``components``    standard component sizing (bearings, gears, fasteners)
``physics``       stress, deflection, fatigue, buckling, FEA, frame solver
``materials``     material property database
``optimizer``     parameter search
``ai``            LLM routing, parser, critic, narrative synthesis
``drafting``      dimensioned drawing sheets, FBD plots, Mermaid diagrams
``reporting``     HTML/DOCX/Markdown engineering report generators
``convert``       the file converter (documents, CAD, drawing sheets)
``cli``           command line interface
``web``           FastAPI application
``integrations``  external bridges (learning-tools)
"""

__version__ = "0.2.0"

__all__ = ["__version__"]
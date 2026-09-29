"""
MDIE Web Application and API Server
FastAPI backend providing REST endpoints for AI parsing, physics verification,
OpenSCAD CAD generation, design optimization, interactive copilot, and report generation.
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from pydantic import BaseModel

from mdie.core.models import EngineeringModel, SolverResult, ShaftSegment, Support, PointLoad
from mdie.physics.solver import PhysicsSolver
from mdie.materials.database import MaterialDatabase
from mdie.cad.openscad import OpenSCADGenerator
from mdie.optimizer.design_search import DesignOptimizer
from mdie.ai.parser import NLParser
from mdie.ai.copilot import EngineeringCopilot
from mdie.reports.generator import ReportGenerator

app = FastAPI(
    title="Machine Design Intelligence Engine (MDIE)",
    description="AI-assisted computational engineering platform for machine design and verification",
    version="1.0.0"
)

# Current active model state in memory for interactive session
STATIC_DIR = Path(__file__).parent / "static"

class ParseRequest(BaseModel):
    prompt: str

class SolveRequest(BaseModel):
    model: EngineeringModel

class OptimizeRequest(BaseModel):
    model: EngineeringModel
    target_yield_sf: float = 2.0
    target_fatigue_sf: float = 1.5
    max_deflection_mm: float = 1.0

class CopilotRequest(BaseModel):
    query: str
    model: EngineeringModel
    result: Optional[SolverResult] = None

class ExploreRequest(BaseModel):
    model: EngineeringModel
    materials: Optional[List[str]] = None

class ChairSolveRequest(BaseModel):
    seat_load_n: float = 1300.0
    arm_load_n: float = 550.0
    leg_dia_mm: float = 28.0
    splay_deg: float = 3.5
    material_id: str = "STEEL_1018"

class FEANodeInput(BaseModel):
    x: float
    y: float
    z: float
    name: Optional[str] = ""
    restraints: List[bool] = [False, False, False, False, False, False]
    loads: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

class FEAMemberInput(BaseModel):
    name: str
    node_start_idx: int
    node_end_idx: int
    E: float = 205e9
    G: float = 79e9
    A: float = 0.001963
    Iy: float = 3.068e-7
    Iz: float = 3.068e-7
    J: float = 6.136e-7
    outer_dim: float = 0.050
    yield_strength: float = 250e6

class FEA3DSolveRequest(BaseModel):
    name: str = "3D Frame Structure"
    nodes: List[FEANodeInput]
    members: List[FEAMemberInput]

class DocxExportRequest(BaseModel):
    html_path: str
    output_docx_path: Optional[str] = None
    enable_ai: bool = False
    custom_ai_instructions: Optional[str] = None

class ConsolidateRequest(BaseModel):
    report_path: str
    output_dir: Optional[str] = None
    convert_docx: bool = True
    generate_summaries: bool = True
    generate_notebooklm: bool = True
    enable_ai: bool = False


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "MDIE Physics, FEA & CAD Engine"}

@app.get("/api/materials")
def get_materials():
    return [m.model_dump() for m in MaterialDatabase.list_all()]

@app.post("/api/parse")
def parse_natural_language(req: ParseRequest):
    try:
        p_lower = req.prompt.lower()

        # 1. 3D Spatial Frame / Truss Domain
        if any(w in p_lower for w in ["tower", "truss", "space frame", "girder", "spatial frame", "3d frame"]):
            from mdie.physics.fea_3d import build_space_truss_tower_model, build_cantilever_space_frame_model
            if "cantilever" in p_lower or "girder" in p_lower or "box" in p_lower:
                solver = build_cantilever_space_frame_model()
            else:
                solver = build_space_truss_tower_model()
            fea_res = solver.solve()
            return {
                "domain": "fea3d",
                "fea": fea_res,
                "logs": [f"Parsed 3D space frame request. Generated 6-DOF Direct Stiffness FEA model: '{solver.name}' ({fea_res['num_nodes']} nodes, {fea_res['num_members']} members)."]
            }

        # 2. Chair & Furniture Multi-Body Domain
        chair_keywords = ["chair", "armchair", "furniture", "stool", "4 leg", "four leg", "armrest", "seating"]
        is_chair = any(w in p_lower for w in chair_keywords) or ("seat" in p_lower and "bearing" not in p_lower and "shaft" not in p_lower)
        if is_chair:
            from mdie.core.frame_model import FrameDesignModel as ChairDesignModel, STRUCTURAL_MATERIALS as CHAIR_MATERIALS
            from mdie.physics.frame_physics import FramePhysicsSolver as ChairPhysicsSolver
            from mdie.cad.assembly import FrameCADEngine as ChairCADEngine
            from mdie.physics.fea_3d import build_chair_3d_fea_model

            chair_model = ChairDesignModel(name="MDIE Ergonomic Armchair")
            
            if "aluminum" in p_lower:
                chair_model.material = CHAIR_MATERIALS["AL_6061_T6"]
            elif "oak" in p_lower or "wood" in p_lower:
                chair_model.material = CHAIR_MATERIALS["WHITE_OAK"]
            elif "stainless" in p_lower:
                chair_model.material = CHAIR_MATERIALS["STAINLESS_304"]

            chair_result = ChairPhysicsSolver.solve(chair_model)
            fea_solver = build_chair_3d_fea_model(chair_model)
            fea_res = fea_solver.solve()
            mesh_data = ChairCADEngine.generate_3d_preview_mesh(chair_model)

            return {
                "domain": "chair",
                "chair_model": chair_model.model_dump(),
                "chair_result": chair_result.model_dump(),
                "chair_fea": fea_res,
                "mesh": mesh_data,
                "logs": [f"Parsed chair request. Configured 4 splayed legs, 2 armrests with {chair_model.material.name}."]
            }

        # 3. Rotating Shaft & Beam Domain
        model, logs = NLParser.parse(req.prompt)
        result = PhysicsSolver.solve(model)
        mesh_data = OpenSCADGenerator.generate_3d_preview_mesh(model)
        return {
            "domain": "shaft",
            "model": model.model_dump(),
            "result": result.model_dump(),
            "mesh": mesh_data,
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/solve")
def solve_model(req: SolveRequest):
    try:
        result = PhysicsSolver.solve(req.model)
        mesh_data = OpenSCADGenerator.generate_3d_preview_mesh(req.model)
        return {
            "result": result.model_dump(),
            "mesh": mesh_data,
            "scad_code": result.openscad_code
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/optimize")
def optimize_model(req: OptimizeRequest):
    try:
        cand, logs = DesignOptimizer.optimize_diameter_for_minimum_mass(
            req.model,
            req.target_yield_sf,
            req.target_fatigue_sf,
            req.max_deflection_mm
        )
        if not cand:
            return {"success": False, "logs": logs, "message": "No feasible standardized diameter found"}
        
        mesh_data = OpenSCADGenerator.generate_3d_preview_mesh(cand.model)
        return {
            "success": True,
            "candidate": cand.to_dict(),
            "optimized_model": cand.model.model_dump(),
            "result": cand.result.model_dump(),
            "mesh": mesh_data,
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/explore")
def explore_designs(req: ExploreRequest):
    try:
        candidates = DesignOptimizer.explore_candidates(req.model, req.materials)
        return {
            "candidates": [c.to_dict() for c in candidates]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/copilot")
def copilot_chat(req: CopilotRequest):
    try:
        res = req.result
        if not res or not res.success:
            res = PhysicsSolver.solve(req.model)
        
        reply = EngineeringCopilot.answer_query(req.query, req.model, res)
        
        new_mesh = None
        if reply.get("modified_model"):
            new_mesh = OpenSCADGenerator.generate_3d_preview_mesh(reply["modified_model"])
        
        return {
            "response": reply["response"],
            "modified_model": reply["modified_model"].model_dump() if reply.get("modified_model") else None,
            "new_result": reply["new_result"].model_dump() if reply.get("new_result") else None,
            "mesh": new_mesh,
            "review": reply["design_review"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/report/html")
def generate_report_html(req: SolveRequest):
    try:
        res = PhysicsSolver.solve(req.model)
        html_content = ReportGenerator.generate_html_report(req.model, res)
        return HTMLResponse(content=html_content, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/report/scad")
def download_scad(req: SolveRequest):
    try:
        res = PhysicsSolver.solve(req.model)
        return PlainTextResponse(
            content=res.openscad_code,
            headers={"Content-Disposition": f"attachment; filename={req.model.name.replace(' ', '_')}.scad"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/export/stl")
def export_stl(req: SolveRequest):
    from fastapi.responses import Response
    from mdie.cad.stl_exporter import STLExporter
    try:
        stl_bytes = STLExporter.export_binary_stl(req.model, n_slices=64)
        filename = (req.model.name or "machine_part").replace(" ", "_") + ".stl"
        return Response(
            content=stl_bytes,
            media_type="model/stl",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/export/step")
def export_step(req: SolveRequest):
    from fastapi.responses import Response
    from mdie.cad.step_exporter import STEPExporter
    try:
        step_text = STEPExporter.export_step(req.model, n_slices=48)
        filename = (req.model.name or "machine_part").replace(" ", "_") + ".step"
        return Response(
            content=step_text.encode('utf-8'),
            media_type="application/step",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==============================================================================
# CHAIR & MULTI-BODY COMPONENT ENDPOINTS
# ==============================================================================

def _build_chair_from_request(req: ChairSolveRequest):
    from mdie.core.frame_model import FrameDesignModel, STRUCTURAL_MATERIALS
    mat = STRUCTURAL_MATERIALS.get(req.material_id, STRUCTURAL_MATERIALS["STEEL_1018"])
    chair = FrameDesignModel(name="MDIE Ergonomic Armchair", material=mat)
    chair.loads.seat_vertical_load_n = req.seat_load_n
    chair.loads.left_arm_vertical_n = req.arm_load_n
    chair.loads.right_arm_vertical_n = req.arm_load_n
    chair.geometry.leg_profile.outer_dimension_mm = req.leg_dia_mm
    chair.geometry.leg_splay_angle_deg = req.splay_deg
    return chair

@app.post("/api/chair/solve")
def solve_chair(req: ChairSolveRequest):
    try:
        from mdie.physics.frame_physics import FramePhysicsSolver as ChairPhysicsSolver
        from mdie.cad.assembly import FrameCADEngine as ChairCADEngine
        from mdie.physics.fea_3d import build_chair_3d_fea_model

        chair = _build_chair_from_request(req)
        result = ChairPhysicsSolver.solve(chair)
        fea_solver = build_chair_3d_fea_model(chair)
        fea_res = fea_solver.solve()
        mesh = ChairCADEngine.generate_3d_preview_mesh(chair)
        scad = ChairCADEngine.generate_openscad(chair)

        return {
            "model": chair.model_dump(),
            "result": result.model_dump(),
            "fea": fea_res,
            "mesh": mesh,
            "scad_code": scad
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/chair/export/step")
def export_chair_step(req: ChairSolveRequest):
    from fastapi.responses import Response
    from mdie.cad.assembly import FrameCADEngine as ChairCADEngine
    try:
        chair = _build_chair_from_request(req)
        step_text = ChairCADEngine.export_step_solid(chair)
        return Response(
            content=step_text.encode('utf-8'),
            media_type="application/step",
            headers={"Content-Disposition": "attachment; filename=chair.step"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/chair/export/stl")
def export_chair_stl(req: ChairSolveRequest):
    from fastapi.responses import Response
    from mdie.cad.assembly import FrameCADEngine as ChairCADEngine
    try:
        chair = _build_chair_from_request(req)
        stl_bytes = ChairCADEngine.export_stl(chair)
        return Response(
            content=stl_bytes,
            media_type="model/stl",
            headers={"Content-Disposition": "attachment; filename=chair.stl"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/chair/export/scad")
def export_chair_scad(req: ChairSolveRequest):
    from mdie.cad.assembly import FrameCADEngine as ChairCADEngine
    try:
        chair = _build_chair_from_request(req)
        scad_text = ChairCADEngine.generate_openscad(chair)
        return PlainTextResponse(
            content=scad_text,
            headers={"Content-Disposition": "attachment; filename=chair.scad"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/chair/report/html")
def export_chair_report(req: ChairSolveRequest):
    from mdie.physics.frame_physics import FramePhysicsSolver as ChairPhysicsSolver
    from mdie.reports.frame_report import FrameReportGenerator as ChairReportGenerator
    try:
        chair = _build_chair_from_request(req)
        res = ChairPhysicsSolver.solve(chair)
        html_code = ChairReportGenerator.generate_html_report(chair, res)
        return HTMLResponse(content=html_code, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==============================================================================
# 3D SPATIAL FRAME & TRUSS FEA ENDPOINTS
# ==============================================================================

@app.get("/api/fea3d/presets")
def list_fea_presets():
    return [
        {"id": "tower", "name": "3D Space Truss Tower (6m tall, wind + vertical load)"},
        {"id": "girder", "name": "3D Cantilever Space Truss Girder (4m box beam, tip shear)"},
        {"id": "chair", "name": "3D Armchair Space Frame (4 splayed legs, seat & arm loads)"}
    ]

@app.get("/api/fea3d/preset/{preset_id}")
def get_fea_preset(preset_id: str):
    try:
        from mdie.physics.fea_3d import (
            build_space_truss_tower_model,
            build_cantilever_space_frame_model,
            build_chair_3d_fea_model
        )
        if preset_id == "tower":
            solver = build_space_truss_tower_model()
        elif preset_id == "girder":
            solver = build_cantilever_space_frame_model()
        elif preset_id == "chair":
            from mdie.core.frame_model import FrameDesignModel
            solver = build_chair_3d_fea_model(FrameDesignModel())
        else:
            raise HTTPException(status_code=404, detail="Preset not found")

        return solver.solve()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/fea3d/solve")
def solve_custom_fea_3d(req: FEA3DSolveRequest):
    try:
        from mdie.physics.fea_3d import FEA3DSolver
        solver = FEA3DSolver(name=req.name)
        nodes = []
        for n in req.nodes:
            node = solver.add_node(n.x, n.y, n.z, n.name or "")
            solver.set_support(node, *n.restraints)
            solver.add_nodal_load(node, *n.loads)
            nodes.append(node)

        for m in req.members:
            n1 = nodes[m.node_start_idx]
            n2 = nodes[m.node_end_idx]
            solver.add_member(
                name=m.name,
                node_start=n1,
                node_end=n2,
                E=m.E,
                G=m.G,
                A=m.A,
                Iy=m.Iy,
                Iz=m.Iz,
                J=m.J,
                outer_dim=m.outer_dim,
                yield_strength=m.yield_strength
            )

        return solver.solve()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------
# Learning Tools & DOCX Export Endpoints
# ---------------------------------------------------------

@app.post("/api/export/docx")
def export_docx(req: DocxExportRequest):
    """Export an HTML report to DOCX using the learning-tools converter."""
    try:
        from mdie.integrations.learning_tools import LearningToolsBridge
        bridge = LearningToolsBridge()
        docx_path = bridge.convert_docx(
            html_path=req.html_path,
            output_docx_path=req.output_docx_path,
            enable_ai=req.enable_ai,
            custom_ai_instructions=req.custom_ai_instructions
        )
        return {
            "status": "ok",
            "docx_path": str(docx_path),
            "filename": Path(docx_path).name,
            "exists": Path(docx_path).exists()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/learning/consolidate")
def consolidate_report(req: ConsolidateRequest):
    """Consolidate an MDIE engineering report into summaries and study guides using learning-tools."""
    try:
        from mdie.integrations.learning_tools import LearningToolsBridge
        bridge = LearningToolsBridge()
        result = bridge.consolidate_report(
            report_path=req.report_path,
            output_dir=req.output_dir,
            convert_docx=req.convert_docx,
            generate_summaries=req.generate_summaries,
            generate_notebooklm=req.generate_notebooklm,
            enable_ai=req.enable_ai
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/learning-tools/status")
def learning_tools_status():
    """Check connectivity to learning-tools microservice (port 5000)."""
    from mdie.integrations.learning_tools import LearningToolsBridge
    bridge = LearningToolsBridge()
    return {
        "learning_tools_url": bridge.base_url,
        "is_online": bridge.is_online(),
        "bridge_mode": "api" if bridge.is_online() else "direct_library_fallback"
    }


# Mount static web directory
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

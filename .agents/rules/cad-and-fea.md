---
description: "3D Parametric CAD and Direct Stiffness FEA Modeling Standards: Governs coordinate systems, STEP/STL/OpenSCAD pipeline, and 3D frame element formulations."
globs: ["cad/**", "physics/fea_3d.py", "Project/**"]
---

# 3D CAD & Finite Element Analysis (FEA) Modeling Standards

This rule specifies the spatial coordinate conventions, multi-format CAD solid generation pipeline, and 3D Direct Stiffness FEA formulations used throughout MDIE.

---

## 1. Spatial Coordinate System Conventions

To ensure flawless interoperability between mathematical solvers, OpenSCAD scripts, and ISO-10303 STEP solid models, adhere to the following coordinate frames:

### 1.1 Rotating Shafts & Power Transmissions
- **$+X$-axis:** Longitudinal centerline of the shaft (axial length).
- **$Y$-$Z$ plane:** Transverse cross-section plane (radial dimensions, gear pitch circles, keyway cuts).
- **Origin $(0, 0, 0)$:** Shaft left driving face or datum shoulder.

### 1.2 Structural Frames, Furniture, Towers & Chassis
- **Datum Plane ($Z = 0$):** Ground floor plane.
- **$+Z$-axis:** Vertical height (positive upward).
- **$X$-axis:** Lateral width (left-to-right).
- **$Y$-axis:** Longitudinal depth (front-to-back).
- **Origin $(0, 0, 0)$:** Geometric center of the structure on the floor plane.

---

## 2. Multi-Format CAD Generation Pipeline

Every MDIE run generates production deliverables in standardized engineering formats:

```
                            Design Model
                                 │
         ┌───────────────┬───────┴───────┬───────────────┐
         ▼               ▼               ▼               ▼
     OpenSCAD        ISO STEP        Binary STL       2D Vector
     (.scad)         (.step)          (.stl)         Blueprint
  Parametric CSG  Solid Assembly  Watertight Mesh  ISO 128 Drawings
```

### 2.1 Parametric OpenSCAD (`.scad`)
- Parametric variables must be defined cleanly at the top of the script.
- Enforce smooth cylindrical rendering: `$fn = 32` (or `$fn = 64` for bearing fits and gear teeth).
- Modules: [`cad.assembly`](file:///c:/codework/computational-machine-design/cad/assembly.py), [`cad.bracket_cad`](file:///c:/codework/computational-machine-design/cad/bracket_cad.py), [`cad.openscad_runner`](file:///c:/codework/computational-machine-design/cad/openscad_runner.py).
- Headless CLI rendering: Use `openscad.com` on Windows to avoid GUI detachment.

### 2.2 ISO-10303 STEP Solid Interchange (`.step`)
- Must output valid ISO-10303-21 manifold solid syntax (`MANIFOLD_SOLID_BREP`).
- Suitable for professional CAD packages (SolidWorks, Autodesk Fusion 360, FreeCAD, Siemens NX).
- Modules: [`cad.step_exporter`](file:///c:/codework/computational-machine-design/cad/step_exporter.py).

### 2.3 Watertight Binary STL (`.stl`)
- Must output standard binary format with accurate normal vectors.
- Ensure watertight non-self-intersecting topology suitable for slicers (PrusaSlicer, Cura, Bambu Studio).
- Modules: [`cad.stl_exporter`](file:///c:/codework/computational-machine-design/cad/stl_exporter.py).

### 2.4 Vector 2D Blueprints (`.svg` / `.html`)
- Must conform to ISO 128 / ANSI Y14.5 drafting standards.
- Include standard title block, third-angle projection symbol, dimension callouts, and manufacturing notes.
- Modules: [`drafting.blueprint_2d`](file:///c:/codework/computational-machine-design/drafting/blueprint_2d.py).

---

## 3. 3D Direct Stiffness Finite Element Analysis (FEA)

For spatial machine frames, trusses, and chassis, apply the Direct Stiffness Method:

### 3.1 Nodal Degrees of Freedom
- Each node possesses **6 DOFs**:
  $$\mathbf{u} = \begin{bmatrix} u_x & u_y & u_z & \theta_x & \theta_y & \theta_z \end{bmatrix}^T$$

### 3.2 12x12 Space Frame Element Stiffness Matrix
- Formulate the standard $12 \times 12$ local element stiffness matrix $[\mathbf{k}_e]$ capturing:
  - Axial deformation: $\frac{E A}{L}$
  - Torsional twist: $\frac{G J}{L}$
  - Dual-axis bending: $\frac{12 E I_z}{L^3}, \frac{6 E I_z}{L^2}, \frac{4 E I_z}{L}$ and $\frac{12 E I_y}{L^3}, \frac{6 E I_y}{L^2}, \frac{4 E I_y}{L}$
- Transform to global coordinates using direction cosines:
  $$[\mathbf{K}_e] = [\mathbf{T}]^T [\mathbf{k}_e] [\mathbf{T}]$$

### 3.3 Boundary Conditions & Stress Extraction
- Enforce rigid foundation constraints ($u_x = u_y = u_z = 0$) at datum floor nodes.
- Compute local internal forces and evaluate combined Von Mises stress at each member section:
  $$\sigma_{vm} = \sqrt{\left(\sigma_{axial} + \sigma_{bend}\right)^2 + 3\tau_{torsion}^2}$$
- Solver: [`physics.fea_3d`](file:///c:/codework/computational-machine-design/physics/fea_3d.py).

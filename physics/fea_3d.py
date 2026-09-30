"""
3D Frame & Truss Finite Element Analysis (FEA) Engine
Implements the Direct Stiffness Method for 3D space frames with 6 DOFs per node
(Translation in X, Y, Z and Rotation about X, Y, Z).
Authority: Physics verifies.
"""

import math
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from pydantic import BaseModel, Field

class FEANode:
    """A node in 3D space with 6 Degrees of Freedom."""
    def __init__(self, node_id: int, x: float, y: float, z: float, name: str = ""):
        self.id = node_id
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.name = name or f"Node_{node_id}"
        # Restraints: (Tx, Ty, Tz, Rx, Ry, Rz) - True means fixed/supported
        self.restraints = [False, False, False, False, False, False]
        # Applied loads: [Fx, Fy, Fz, Mx, My, Mz] (N and N*m)
        self.loads = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        # Solution results
        self.displacements = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.reactions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


class FEAMember:
    """A 3D beam-column frame element connecting two nodes."""
    def __init__(
        self,
        member_id: str,
        node_start: FEANode,
        node_end: FEANode,
        E: float,          # Young's modulus (Pa)
        G: float,          # Shear modulus (Pa)
        A: float,          # Cross-sectional area (m^2)
        Iy: float,         # Second moment of area about local y (m^4)
        Iz: float,         # Second moment of area about local z (m^4)
        J: float,          # Polar/torsional moment (m^4)
        outer_dim: float,  # Outer dimension for stress calculation (m)
        yield_strength: float = 250e6
    ):
        self.id = member_id
        self.n1 = node_start
        self.n2 = node_end
        self.E = float(E)
        self.G = float(G)
        self.A = float(A)
        self.Iy = float(Iy)
        self.Iz = float(Iz)
        self.J = float(J)
        self.outer_dim = float(outer_dim)
        self.yield_strength = float(yield_strength)

        # Output results
        self.axial_force_n: float = 0.0
        self.max_shear_n: float = 0.0
        self.torsion_nm: float = 0.0
        self.max_moment_nm: float = 0.0
        self.axial_stress_mpa: float = 0.0
        self.bending_stress_mpa: float = 0.0
        self.von_mises_stress_mpa: float = 0.0
        self.safety_factor: float = 99.0

    @property
    def length(self) -> float:
        dx = self.n2.x - self.n1.x
        dy = self.n2.y - self.n1.y
        dz = self.n2.z - self.n1.z
        return math.sqrt(dx**2 + dy**2 + dz**2)

    def get_local_stiffness_matrix(self) -> np.ndarray:
        """Standard 12x12 3D space frame element stiffness matrix."""
        L = self.length
        if L < 1e-7:
            raise ValueError(f"Member {self.id} has zero length.")

        E, G, A, Iy, Iz, J = self.E, self.G, self.A, self.Iy, self.Iz, self.J
        k = np.zeros((12, 12), dtype=float)

        # Axial: 1, 7
        k[0, 0] = k[6, 6] = E * A / L
        k[0, 6] = k[6, 0] = -E * A / L

        # Torsion: 4, 10
        k[3, 3] = k[9, 9] = G * J / L
        k[3, 9] = k[9, 3] = -G * J / L

        # Bending in local xy plane (Iz, shears 2, 8 and moments 6, 12)
        k[1, 1] = k[7, 7] = 12.0 * E * Iz / (L**3)
        k[1, 7] = k[7, 1] = -12.0 * E * Iz / (L**3)
        k[1, 5] = k[5, 1] = 6.0 * E * Iz / (L**2)
        k[1, 11] = k[11, 1] = 6.0 * E * Iz / (L**2)
        k[7, 5] = k[5, 7] = -6.0 * E * Iz / (L**2)
        k[7, 11] = k[11, 7] = -6.0 * E * Iz / (L**2)
        k[5, 5] = k[11, 11] = 4.0 * E * Iz / L
        k[5, 11] = k[11, 5] = 2.0 * E * Iz / L

        # Bending in local xz plane (Iy, shears 3, 9 and moments 5, 11)
        k[2, 2] = k[8, 8] = 12.0 * E * Iy / (L**3)
        k[2, 8] = k[8, 2] = -12.0 * E * Iy / (L**3)
        k[2, 4] = k[4, 2] = -6.0 * E * Iy / (L**2)
        k[2, 10] = k[10, 2] = -6.0 * E * Iy / (L**2)
        k[8, 4] = k[4, 8] = 6.0 * E * Iy / (L**2)
        k[8, 10] = k[10, 8] = 6.0 * E * Iy / (L**2)
        k[4, 4] = k[10, 10] = 4.0 * E * Iy / L
        k[4, 10] = k[10, 4] = 2.0 * E * Iy / L

        return k

    def get_transformation_matrix(self) -> np.ndarray:
        """Calculates 12x12 coordinate transformation matrix T from local to global."""
        L = self.length
        dx = (self.n2.x - self.n1.x) / L
        dy = (self.n2.y - self.n1.y) / L
        dz = (self.n2.z - self.n1.z) / L

        # Local x-axis unit vector along member
        ux = np.array([dx, dy, dz], dtype=float)

        # Choose reference up vector to construct orthogonal local y and z
        ref = np.array([0.0, 0.0, 1.0], dtype=float)
        if abs(np.dot(ux, ref)) > 0.999:
            # If member is almost vertical along Z, use Y as reference
            ref = np.array([0.0, 1.0, 0.0], dtype=float)

        uz = np.cross(ux, ref)
        uz /= np.linalg.norm(uz)
        uy = np.cross(uz, ux)
        uy /= np.linalg.norm(uy)

        # 3x3 direction cosine rotation matrix
        R = np.array([ux, uy, uz], dtype=float)

        # Build 12x12 block diagonal transformation matrix
        T = np.zeros((12, 12), dtype=float)
        for i in range(4):
            T[i*3:(i+1)*3, i*3:(i+1)*3] = R

        return T


class FEA3DSolver:
    """Direct Stiffness Method Solver for 3D Space Frames and Trusses."""

    def __init__(self, name: str = "3D Frame FEA Model"):
        self.name = name
        self.nodes: List[FEANode] = []
        self.members: List[FEAMember] = []

    def add_node(self, x: float, y: float, z: float, name: str = "") -> FEANode:
        node_id = len(self.nodes)
        node = FEANode(node_id, x, y, z, name)
        self.nodes.append(node)
        return node

    def add_member(
        self,
        name: str,
        node_start: FEANode,
        node_end: FEANode,
        E: float,
        G: float,
        A: float,
        Iy: float,
        Iz: float,
        J: float,
        outer_dim: float,
        yield_strength: float = 250e6
    ) -> FEAMember:
        m = FEAMember(name, node_start, node_end, E, G, A, Iy, Iz, J, outer_dim, yield_strength)
        self.members.append(m)
        return m

    def set_support(self, node: FEANode, tx=True, ty=True, tz=True, rx=False, ry=False, rz=False):
        """Sets support boundary conditions for a node."""
        node.restraints = [tx, ty, tz, rx, ry, rz]

    def add_nodal_load(self, node: FEANode, fx=0.0, fy=0.0, fz=0.0, mx=0.0, my=0.0, mz=0.0):
        """Applies external point loads and moments to a node."""
        node.loads[0] += fx
        node.loads[1] += fy
        node.loads[2] += fz
        node.loads[3] += mx
        node.loads[4] += my
        node.loads[5] += mz

    def solve(self) -> Dict[str, Any]:
        """
        Executes Direct Stiffness Method:
        1. Assembles global stiffness matrix K_global
        2. Applies boundary conditions
        3. Solves K * U = F
        4. Calculates reactions and internal member stresses
        """
        n_nodes = len(self.nodes)
        total_dof = n_nodes * 6
        K_global = np.zeros((total_dof, total_dof), dtype=float)
        F_global = np.zeros(total_dof, dtype=float)

        # Assemble global load vector
        for node in self.nodes:
            idx = node.id * 6
            for d in range(6):
                F_global[idx + d] = node.loads[d]

        # Assemble global stiffness matrix
        for mem in self.members:
            k_loc = mem.get_local_stiffness_matrix()
            T = mem.get_transformation_matrix()
            k_glob = T.T @ k_loc @ T

            # Map member DOFs to global DOFs
            dofs = []
            for n in (mem.n1, mem.n2):
                base = n.id * 6
                dofs.extend(range(base, base + 6))

            for i in range(12):
                for j in range(12):
                    K_global[dofs[i], dofs[j]] += k_glob[i, j]

        # Partition Free and Restrained DOFs
        free_dofs = []
        restrained_dofs = []
        for node in self.nodes:
            base = node.id * 6
            for d in range(6):
                if node.restraints[d]:
                    restrained_dofs.append(base + d)
                else:
                    free_dofs.append(base + d)

        if not free_dofs:
            raise ValueError("All degrees of freedom are restrained; cannot solve.")

        # Solve system: K_free * U_free = F_free
        K_ff = K_global[np.ix_(free_dofs, free_dofs)]
        F_f = F_global[free_dofs]

        # Solve linear system
        try:
            U_f = np.linalg.solve(K_ff, F_f)
        except np.linalg.LinAlgError:
            # Add tiny regularization if singular (e.g. unconstrained torsional mechanism)
            K_ff_reg = K_ff + np.eye(len(free_dofs)) * 1e-6
            U_f = np.linalg.solve(K_ff_reg, F_f)

        # Assemble complete displacement vector U
        U_total = np.zeros(total_dof, dtype=float)
        for i, dof in enumerate(free_dofs):
            U_total[dof] = U_f[i]

        # Compute reactions: R = K_global * U - F_global
        R_total = K_global @ U_total - F_global

        # Store results in nodes
        for node in self.nodes:
            base = node.id * 6
            node.displacements = U_total[base:base+6].tolist()
            node.reactions = R_total[base:base+6].tolist()

        # Compute element end forces and internal stresses
        max_stress_overall = 0.0
        min_sf_overall = 999.0
        member_results = []

        for mem in self.members:
            T = mem.get_transformation_matrix()
            k_loc = mem.get_local_stiffness_matrix()

            dofs = []
            for n in (mem.n1, mem.n2):
                base = n.id * 6
                dofs.extend(range(base, base + 6))

            u_elem_glob = U_total[dofs]
            u_elem_loc = T @ u_elem_glob
            f_elem_loc = k_loc @ u_elem_loc

            # Internal forces (axial, shear, torsion, bending)
            # f_elem_loc: [N1, Vy1, Vz1, T1, My1, Mz1, N2, Vy2, Vz2, T2, My2, Mz2]
            axial_force = abs(f_elem_loc[6])
            shear_force = max(math.sqrt(f_elem_loc[1]**2 + f_elem_loc[2]**2), math.sqrt(f_elem_loc[7]**2 + f_elem_loc[8]**2))
            torsion = max(abs(f_elem_loc[3]), abs(f_elem_loc[9]))
            moment = max(math.sqrt(f_elem_loc[4]**2 + f_elem_loc[5]**2), math.sqrt(f_elem_loc[10]**2 + f_elem_loc[11]**2))

            sigma_axial = axial_force / mem.A
            c = mem.outer_dim / 2.0
            z_mod = min(mem.Iy, mem.Iz) / max(c, 1e-6)
            sigma_bend = moment / max(z_mod, 1e-9)

            # Combined Von Mises stress (MPa)
            sigma_axial_mpa = sigma_axial / 1e6
            sigma_bend_mpa = sigma_bend / 1e6
            tau_mpa = (shear_force / mem.A) / 1e6
            sigma_vm_mpa = math.sqrt((sigma_axial_mpa + sigma_bend_mpa)**2 + 3.0 * (tau_mpa**2))

            sf = (mem.yield_strength / 1e6) / max(sigma_vm_mpa, 0.01)

            mem.axial_force_n = axial_force
            mem.max_shear_n = shear_force
            mem.torsion_nm = torsion
            mem.max_moment_nm = moment
            mem.axial_stress_mpa = sigma_axial_mpa
            mem.bending_stress_mpa = sigma_bend_mpa
            mem.von_mises_stress_mpa = sigma_vm_mpa
            mem.safety_factor = sf

            if sigma_vm_mpa > max_stress_overall:
                max_stress_overall = sigma_vm_mpa
            if sf < min_sf_overall:
                min_sf_overall = sf

            member_results.append({
                "member_id": mem.id,
                "node_start_id": mem.n1.id,
                "node_end_id": mem.n2.id,
                "p1": [mem.n1.x, mem.n1.y, mem.n1.z],
                "p2": [mem.n2.x, mem.n2.y, mem.n2.z],
                "outer_dim_m": mem.outer_dim,
                "length_m": mem.length,
                "axial_force_n": axial_force,
                "max_moment_nm": moment,
                "axial_stress_mpa": sigma_axial_mpa,
                "bending_stress_mpa": sigma_bend_mpa,
                "von_mises_mpa": sigma_vm_mpa,
                "safety_factor": sf,
                "passed": (sf >= 2.0)
            })

        max_disp_m = max(math.sqrt(n.displacements[0]**2 + n.displacements[1]**2 + n.displacements[2]**2) for n in self.nodes) if self.nodes else 0.0

        nodes_data = [
            {
                "id": n.id,
                "name": n.name,
                "coords": [n.x, n.y, n.z],
                "displacements": n.displacements,
                "reactions": n.reactions,
                "restraints": n.restraints
            }
            for n in self.nodes
        ]

        return {
            "model_name": self.name,
            "num_nodes": n_nodes,
            "total_dof": total_dof,
            "active_free_dof": len(free_dofs),
            "num_members": len(self.members),
            "max_displacement_mm": max_disp_m * 1000.0,
            "max_von_mises_mpa": max_stress_overall,
            "min_safety_factor": min_sf_overall,
            "nodes": nodes_data,
            "members": member_results,
            "passed": (min_sf_overall >= 2.0)
        }


def build_chair_3d_fea_model(chair_model: Any) -> FEA3DSolver:
    """
    Constructs a complete 3D space frame FEA model for the 4-leg armchair.
    """
    from mdie.core.frame_model import FrameDesignModel
    g = chair_model.geometry
    l = chair_model.loads
    m = chair_model.material

    solver = FEA3DSolver(name="Chair 3D Space Frame FEA")

    h = g.seat_height_mm / 1000.0
    w = g.seat_width_mm / 1000.0
    d = g.seat_depth_mm / 1000.0
    splay = math.radians(g.leg_splay_angle_deg)
    delta = h * math.tan(splay)

    E = m.elastic_modulus_gpa * 1e9
    G = E / (2.0 * (1.0 + m.poissons_ratio))
    Sy = m.yield_strength_mpa * 1e6

    # 1. Floor Foot Nodes & Seat Corner Nodes
    n_legs = max(3, g.num_legs)
    bot_nodes = []
    top_nodes = []

    if n_legs == 3:
        r_top = min(w, d) / 2.0
        r_bot = r_top + delta
        angles = [math.pi / 2.0, 7.0 * math.pi / 6.0, 11.0 * math.pi / 6.0]
        for i, ang in enumerate(angles):
            bx = r_bot * math.cos(ang); by = r_bot * math.sin(ang)
            tx = r_top * math.cos(ang); ty = r_top * math.sin(ang)
            bn = solver.add_node(bx, by, 0.0, f"Foot_Leg{i+1}")
            tn = solver.add_node(tx, ty, h, f"SeatCorner_Leg{i+1}")
            solver.set_support(bn, tx=True, ty=True, tz=True, rx=True, ry=True, rz=True)
            bot_nodes.append(bn)
            top_nodes.append(tn)
    else:
        # Standard 4 Splayed Legs
        corners = [
            ("FL", -w/2,  d/2, -w/2 - delta,  d/2 + delta),
            ("FR",  w/2,  d/2,  w/2 + delta,  d/2 + delta),
            ("RR",  w/2, -d/2,  w/2 + delta, -d/2 - delta),
            ("RL", -w/2, -d/2, -w/2 - delta, -d/2 - delta),
        ]
        for name, tx, ty, bx, by in corners:
            bn = solver.add_node(bx, by, 0.0, f"Foot_{name}")
            tn = solver.add_node(tx, ty, h, f"SeatCorner_{name}")
            solver.set_support(bn, tx=True, ty=True, tz=True, rx=True, ry=True, rz=True)
            bot_nodes.append(bn)
            top_nodes.append(tn)

    # 2. Leg Members
    lp = g.leg_profile
    for i in range(len(bot_nodes)):
        solver.add_member(f"Leg_{i+1}", bot_nodes[i], top_nodes[i], E, G, lp.area_m2, lp.moment_of_inertia_m4, lp.moment_of_inertia_m4, lp.moment_of_inertia_m4*2, lp.outer_dim_m, Sy)

    # 3. Seat Frame Rails (Perimeter ring connecting top nodes)
    fp = g.frame_profile
    for i in range(len(top_nodes)):
        next_i = (i + 1) % len(top_nodes)
        solver.add_member(f"Rail_{i+1}_{next_i+1}", top_nodes[i], top_nodes[next_i], E, G, fp.area_m2, fp.moment_of_inertia_m4, fp.moment_of_inertia_m4, fp.moment_of_inertia_m4*2, fp.outer_dim_m, Sy)

    # 4. Lower Stretchers (if enabled)
    if g.has_stretchers:
        sh = g.stretcher_height_mm / 1000.0
        sp = g.stretcher_profile
        s_delta = (h - sh) * math.tan(splay)
        stretcher_nodes = []
        if n_legs == 3:
            r_stretcher = (min(w, d) / 2.0) + s_delta
            angles = [math.pi / 2.0, 7.0 * math.pi / 6.0, 11.0 * math.pi / 6.0]
            for i, ang in enumerate(angles):
                sx = r_stretcher * math.cos(ang); sy = r_stretcher * math.sin(ang)
                sn = solver.add_node(sx, sy, sh, f"Stretcher_Node_{i+1}")
                stretcher_nodes.append(sn)
        else:
            s_corners = [
                ("FL", -w/2 - s_delta,  d/2 + s_delta),
                ("FR",  w/2 + s_delta,  d/2 + s_delta),
                ("RR",  w/2 + s_delta, -d/2 - s_delta),
                ("RL", -w/2 - s_delta, -d/2 - s_delta),
            ]
            for name, sx, sy in s_corners:
                sn = solver.add_node(sx, sy, sh, f"Stretcher_{name}")
                stretcher_nodes.append(sn)

        for i in range(len(stretcher_nodes)):
            next_i = (i + 1) % len(stretcher_nodes)
            solver.add_member(f"Stretcher_{i+1}_{next_i+1}", stretcher_nodes[i], stretcher_nodes[next_i], E, G, sp.area_m2, sp.moment_of_inertia_m4, sp.moment_of_inertia_m4, sp.moment_of_inertia_m4*2, sp.outer_dim_m, Sy)

    # 5. Armrests (if enabled)
    if g.has_arms:
        arm_h = g.armrest_height_above_seat_mm / 1000.0
        arm_x_l = -(w/2 + 0.025)
        arm_x_r = +(w/2 + 0.025)
        # Match OpenSCAD: front arm post at y=+40mm, rear at y=-seat_d/3=-160mm
        arm_y_front = 40 / 1000.0    # +40 mm (front)
        arm_y_rear  = -d / 3.0       # -160 mm (rear, matches seat_d/3)

        # Left side arm posts (front + rear)
        n_arm_l_front_top = solver.add_node(arm_x_l, arm_y_front, h + arm_h, "Arm_Left_Front_Top")
        n_arm_l_front_base = solver.add_node(arm_x_l, arm_y_front, h, "Arm_Left_Front_Base")
        n_arm_l_rear_top = solver.add_node(arm_x_l, arm_y_rear, h + arm_h, "Arm_Left_Rear_Top")
        n_arm_l_rear_base = solver.add_node(arm_x_l, arm_y_rear, h, "Arm_Left_Rear_Base")

        # Right side arm posts (front + rear)
        n_arm_r_front_top = solver.add_node(arm_x_r, arm_y_front, h + arm_h, "Arm_Right_Front_Top")
        n_arm_r_front_base = solver.add_node(arm_x_r, arm_y_front, h, "Arm_Right_Front_Base")
        n_arm_r_rear_top = solver.add_node(arm_x_r, arm_y_rear, h + arm_h, "Arm_Right_Rear_Top")
        n_arm_r_rear_base = solver.add_node(arm_x_r, arm_y_rear, h, "Arm_Right_Rear_Base")

        ap = g.arm_profile
        # Vertical arm posts (front and rear, per side)
        solver.add_member("Arm_Post_L_Front", n_arm_l_front_base, n_arm_l_front_top, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)
        solver.add_member("Arm_Post_L_Rear", n_arm_l_rear_base, n_arm_l_rear_top, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)
        solver.add_member("Arm_Post_R_Front", n_arm_r_front_base, n_arm_r_front_top, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)
        solver.add_member("Arm_Post_R_Rear", n_arm_r_rear_base, n_arm_r_rear_top, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)

        # Short connecting members from arm posts to nearest seat frame corners
        # Left side: FL connects to front arm base, RL connects to rear arm base
        solver.add_member("Arm_Post_L_Front_FLT", top_nodes[0], n_arm_l_front_base, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)
        solver.add_member("Arm_Post_L_Rear_RLT", top_nodes[3], n_arm_l_rear_base, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)
        solver.add_member("Arm_Post_R_Front_FRT", top_nodes[1], n_arm_r_front_base, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)
        solver.add_member("Arm_Post_R_Rear_RRT", top_nodes[2], n_arm_r_rear_base, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)

        # Cross-connectors between front and rear arm posts (top and base)
        solver.add_member("Arm_Post_L_Top_X", n_arm_l_front_top, n_arm_l_rear_top, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)
        solver.add_member("Arm_Post_R_Top_X", n_arm_r_front_top, n_arm_r_rear_top, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)
        solver.add_member("Arm_Post_L_Base_X", n_arm_l_front_base, n_arm_l_rear_base, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)
        solver.add_member("Arm_Post_R_Base_X", n_arm_r_front_base, n_arm_r_rear_base, E, G, ap.area_m2, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4, ap.moment_of_inertia_m4*2, ap.outer_dim_m, Sy)

        # Split arm loads between front and rear posts (50/50 split)
        left_force = l.left_arm_vertical_n / 2.0
        solver.add_nodal_load(n_arm_l_front_top, fz=-left_force, fy=l.left_arm_lateral_n)
        solver.add_nodal_load(n_arm_l_rear_top, fz=-left_force, fy=l.left_arm_lateral_n)
        right_force = l.right_arm_vertical_n / 2.0
        solver.add_nodal_load(n_arm_r_front_top, fz=-right_force, fy=l.right_arm_lateral_n)
        solver.add_nodal_load(n_arm_r_rear_top, fz=-right_force, fy=l.right_arm_lateral_n)

    # 6. Backrest (if enabled)
    if g.has_backrest:
        back_h_m = g.backrest_height_above_seat_mm / 1000.0
        back_rad = math.radians(g.backrest_angle_deg - 90.0)
        dy_back = back_h_m * math.sin(back_rad)
        dz_back = back_h_m * math.cos(back_rad)
        # Use leg profile for backrest legs (same tube as main columns)
        bp = g.leg_profile
        back_attach_y = -d / 2 + bp.outer_dim_m  # Attach at rear of seat frame
        # Backrest attachment nodes on seat frame (at rear corners)
        back_base_fl = solver.add_node(-w/2 + bp.outer_dim_m, back_attach_y, h, "Back_Base_FL")
        back_base_fr = solver.add_node(w/2 - bp.outer_dim_m, back_attach_y, h, "Back_Base_FR")
        # Backrest top nodes (splayed at backrest angle)
        back_top_fl = solver.add_node(-w/2 + bp.outer_dim_m, back_attach_y - dy_back, h + dz_back, "Back_Top_FL")
        back_top_fr = solver.add_node(w/2 - bp.outer_dim_m, back_attach_y - dy_back, h + dz_back, "Back_Top_FR")
        # Backrest leg members
        solver.add_member("Backrest_Leg_FL", back_base_fl, back_top_fl, E, G, bp.area_m2, bp.moment_of_inertia_m4, bp.moment_of_inertia_m4, bp.moment_of_inertia_m4*2, bp.outer_dim_m, Sy)
        solver.add_member("Backrest_Leg_FR", back_base_fr, back_top_fr, E, G, bp.area_m2, bp.moment_of_inertia_m4, bp.moment_of_inertia_m4, bp.moment_of_inertia_m4*2, bp.outer_dim_m, Sy)
        # Connect backrest base to seat frame corners
        solver.add_member("Back_Base_FL_Connect_FL", top_nodes[0], back_base_fl, E, G, bp.area_m2, bp.moment_of_inertia_m4, bp.moment_of_inertia_m4, bp.moment_of_inertia_m4*2, bp.outer_dim_m, Sy)
        solver.add_member("Back_Base_FR_Connect_FR", top_nodes[1], back_base_fr, E, G, bp.area_m2, bp.moment_of_inertia_m4, bp.moment_of_inertia_m4, bp.moment_of_inertia_m4*2, bp.outer_dim_m, Sy)
        # Apply backrest horizontal thrust (backward in -Y direction)
        f_back = l.backrest_force_n / 2.0
        solver.add_nodal_load(back_top_fl, fy=-f_back)
        solver.add_nodal_load(back_top_fr, fy=-f_back)

    # 7. Apply External Seat Load distributed on corner nodes
    f_seat_per_corner = -l.seat_vertical_load_n / float(len(top_nodes))
    for tn in top_nodes:
        solver.add_nodal_load(tn, fz=f_seat_per_corner)

    return solver


def build_space_truss_tower_model(
    height_m: float = 6.0,
    base_w: float = 2.0,
    top_w: float = 1.0,
    wind_load_n: float = 3000.0,
    vertical_load_n: float = 8000.0
) -> FEA3DSolver:
    """
    Constructs a 3D transmission / telecommunication tower space truss with 3 vertical bays,
    corner chords, horizontal ties, and cross-braces.
    """
    solver = FEA3DSolver("3D Space Truss Tower")
    E = 205e9    # Structural Steel (Pa)
    G = 79e9
    Sy = 250e6   # 250 MPa yield
    
    # Outer dimension 60 mm x 4 mm tube for main chords
    d_chord = 0.060
    t_chord = 0.004
    A_chord = math.pi * (d_chord**2 - (d_chord - 2*t_chord)**2) / 4.0
    I_chord = math.pi * (d_chord**4 - (d_chord - 2*t_chord)**4) / 64.0
    J_chord = 2.0 * I_chord

    # Outer dimension 40 mm x 3 mm tube for braces
    d_brace = 0.040
    t_brace = 0.003
    A_brace = math.pi * (d_brace**2 - (d_brace - 2*t_brace)**2) / 4.0
    I_brace = math.pi * (d_brace**4 - (d_brace - 2*t_brace)**4) / 64.0
    J_brace = 2.0 * I_brace

    n_bays = 3
    levels_z = [height_m * (i / n_bays) for i in range(n_bays + 1)]
    # Linear taper from base_w to top_w
    widths = [base_w + (top_w - base_w) * (i / n_bays) for i in range(n_bays + 1)]

    # Store nodes level by level: [ [FL, FR, RR, RL] for each level ]
    level_nodes = []
    for lvl_idx, (z, w) in enumerate(zip(levels_z, widths)):
        hw = w / 2.0
        n_fl = solver.add_node(-hw,  hw, z, f"Node_L{lvl_idx}_FL")
        n_fr = solver.add_node( hw,  hw, z, f"Node_L{lvl_idx}_FR")
        n_rr = solver.add_node( hw, -hw, z, f"Node_L{lvl_idx}_RR")
        n_rl = solver.add_node(-hw, -hw, z, f"Node_L{lvl_idx}_RL")
        level_nodes.append([n_fl, n_fr, n_rr, n_rl])

    # Restrain base level nodes (fully fixed foundations)
    for n in level_nodes[0]:
        solver.set_support(n, tx=True, ty=True, tz=True, rx=True, ry=True, rz=True)

    # Add members for each bay
    for b in range(n_bays):
        bot = level_nodes[b]
        top = level_nodes[b + 1]

        # 4 Main Chords (vertical / sloping columns)
        for i, name in enumerate(["FL", "FR", "RR", "RL"]):
            solver.add_member(f"Chord_Bay{b}_{name}", bot[i], top[i], E, G, A_chord, I_chord, I_chord, J_chord, d_chord, Sy)

        # 4 Top Horizontal Ties
        solver.add_member(f"Tie_Bay{b}_F", top[0], top[1], E, G, A_brace, I_brace, I_brace, J_brace, d_brace, Sy)
        solver.add_member(f"Tie_Bay{b}_R", top[1], top[2], E, G, A_brace, I_brace, I_brace, J_brace, d_brace, Sy)
        solver.add_member(f"Tie_Bay{b}_B", top[2], top[3], E, G, A_brace, I_brace, I_brace, J_brace, d_brace, Sy)
        solver.add_member(f"Tie_Bay{b}_L", top[3], top[0], E, G, A_brace, I_brace, I_brace, J_brace, d_brace, Sy)

        # Diagonal X-Braces on all 4 faces
        faces = [(0, 1), (1, 2), (2, 3), (3, 0)]
        for f_idx, (i1, i2) in enumerate(faces):
            solver.add_member(f"XBrace1_Bay{b}_F{f_idx}", bot[i1], top[i2], E, G, A_brace, I_brace, I_brace, J_brace, d_brace, Sy)
            solver.add_member(f"XBrace2_Bay{b}_F{f_idx}", bot[i2], top[i1], E, G, A_brace, I_brace, I_brace, J_brace, d_brace, Sy)

    # Apply tip lateral wind load + vertical dead/cable load at top nodes
    top_nodes = level_nodes[-1]
    f_wind_each = wind_load_n / 4.0
    f_vert_each = -vertical_load_n / 4.0
    for tn in top_nodes:
        solver.add_nodal_load(tn, fx=f_wind_each, fz=f_vert_each)

    return solver


def build_cantilever_space_frame_model(
    length_m: float = 4.0,
    width_m: float = 1.0,
    height_m: float = 1.0,
    tip_load_n: float = 5000.0
) -> FEA3DSolver:
    """
    Constructs a 3D cantilever space truss box girder with root fixed support and tip downward shear load.
    """
    solver = FEA3DSolver("3D Cantilever Space Truss Girder")
    E = 205e9
    G = 79e9
    Sy = 250e6

    d_elem = 0.050
    t_elem = 0.003
    A_elem = math.pi * (d_elem**2 - (d_elem - 2*t_elem)**2) / 4.0
    I_elem = math.pi * (d_elem**4 - (d_elem - 2*t_elem)**4) / 64.0
    J_elem = 2.0 * I_elem

    n_bays = 4
    dx = length_m / n_bays
    hw = width_m / 2.0
    hh = height_m / 2.0

    bay_nodes = []
    for b in range(n_bays + 1):
        x = b * dx
        n_top_l = solver.add_node(x, -hw,  hh, f"Node_X{b}_TL")
        n_top_r = solver.add_node(x,  hw,  hh, f"Node_X{b}_TR")
        n_bot_r = solver.add_node(x,  hw, -hh, f"Node_X{b}_BR")
        n_bot_l = solver.add_node(x, -hw, -hh, f"Node_X{b}_BL")
        bay_nodes.append([n_top_l, n_top_r, n_bot_r, n_bot_l])

    # Root fixity (bay 0)
    for n in bay_nodes[0]:
        solver.set_support(n, tx=True, ty=True, tz=True, rx=True, ry=True, rz=True)

    # Longitudinal chords & transverse rings & diagonals
    for b in range(n_bays):
        b0 = bay_nodes[b]
        b1 = bay_nodes[b + 1]

        # 4 Longitudinal Chords
        for i, name in enumerate(["TL", "TR", "BR", "BL"]):
            solver.add_member(f"Chord_{name}_Bay{b}", b0[i], b1[i], E, G, A_elem, I_elem, I_elem, J_elem, d_elem, Sy)

        # Transverse perimeter at b1
        solver.add_member(f"Ring_Top_B{b}", b1[0], b1[1], E, G, A_elem, I_elem, I_elem, J_elem, d_elem, Sy)
        solver.add_member(f"Ring_Right_B{b}", b1[1], b1[2], E, G, A_elem, I_elem, I_elem, J_elem, d_elem, Sy)
        solver.add_member(f"Ring_Bot_B{b}", b1[2], b1[3], E, G, A_elem, I_elem, I_elem, J_elem, d_elem, Sy)
        solver.add_member(f"Ring_Left_B{b}", b1[3], b1[0], E, G, A_elem, I_elem, I_elem, J_elem, d_elem, Sy)

        # Side diagonals (vertical shear carry)
        solver.add_member(f"Diag_L_B{b}", b0[3], b1[0], E, G, A_elem, I_elem, I_elem, J_elem, d_elem, Sy)
        solver.add_member(f"Diag_R_B{b}", b0[2], b1[1], E, G, A_elem, I_elem, I_elem, J_elem, d_elem, Sy)
        # Top and bottom diagonals
        solver.add_member(f"Diag_Top_B{b}", b0[0], b1[1], E, G, A_elem, I_elem, I_elem, J_elem, d_elem, Sy)
        solver.add_member(f"Diag_Bot_B{b}", b0[3], b1[2], E, G, A_elem, I_elem, I_elem, J_elem, d_elem, Sy)

    # Tip downward load at bay_nodes[-1]
    tip_nodes = bay_nodes[-1]
    f_down_each = -tip_load_n / 4.0
    for tn in tip_nodes:
        solver.add_nodal_load(tn, fz=f_down_each)

    return solver


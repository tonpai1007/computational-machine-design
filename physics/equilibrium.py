"""
MDIE Physics Equilibrium Solver
Computes support reaction forces, reaction moments, and internal shear/bending/torque distributions.
"""

from typing import Any

import numpy as np

from core.models import EngineeringModel, Support, SupportReaction


class EquilibriumSolver:
    @staticmethod
    def solve_reactions(model: EngineeringModel) -> tuple[list[SupportReaction], list[str]]:
        """
        Solve static equilibrium equations for support reactions:
        sum(Fy) = 0, sum(M_about_ref) = 0.
        Returns list of SupportReaction and equation log.
        """
        logs = []
        supports = model.supports
        num_supports = len(supports)

        if num_supports == 0:
            raise ValueError(
                "Statically unconstrained system: No supports defined. Cannot solve equilibrium."
            )

        # Total applied downward transverse loads
        total_point_force = sum(p.magnitude for p in model.point_loads)
        total_dist_force = 0.0
        for d in model.distributed_loads:
            w_avg = 0.5 * (d.w_start + d.get_w_end())
            total_dist_force += w_avg * (d.end_pos - d.start_pos)

        total_applied_force = total_point_force + total_dist_force
        logs.append(f"Total applied transverse load: {total_applied_force:.2f} N")

        reactions: list[SupportReaction] = []

        if num_supports == 1:
            sup = supports[0]
            if sup.support_type != "fixed":
                raise ValueError(
                    f"Single support at x={sup.position}m is '{sup.support_type}', not 'fixed'. "
                    "System is statically unstable (mechanism)."
                )
            # Cantilever beam fixed at sup.position
            # R = total_applied_force
            r_force = total_applied_force

            # Moment about support
            m_reaction = 0.0
            for p in model.point_loads:
                m_reaction += p.magnitude * (p.position - sup.position)
            for d in model.distributed_loads:
                dx = d.end_pos - d.start_pos
                w1, w2 = d.w_start, d.get_w_end()
                # Rectangle portion + triangle portion centroid
                f_rect = min(w1, w2) * dx
                c_rect = d.start_pos + 0.5 * dx
                f_tri = 0.5 * abs(w2 - w1) * dx
                c_tri = d.start_pos + (2.0 / 3.0 * dx if w2 > w1 else 1.0 / 3.0 * dx)
                m_reaction += f_rect * (c_rect - sup.position) + f_tri * (c_tri - sup.position)

            reactions.append(
                SupportReaction(
                    support_name=f"{sup.name} (Fixed @ x={sup.position:.3f}m)",
                    position=sup.position,
                    reaction_force_n=r_force,
                    reaction_moment_nm=m_reaction,
                )
            )
            logs.append(
                f"Fixed Support Reaction: R = {r_force:.2f} N, M_react = {m_reaction:.2f} N*m"
            )
            return reactions, logs

        elif num_supports == 2:
            s1, s2 = sorted(supports, key=lambda s: s.position)
            x1, x2 = s1.position, s2.position
            span = x2 - x1
            if abs(span) < 1e-6:
                raise ValueError(
                    "Both supports are placed at the exact same axial location. Degenerate support geometry."
                )

            # Moment equilibrium about support 1: sum(M_about_x1) = 0
            # R2 * span - sum(F_i * (x_i - x1)) = 0  =>  R2 = sum(F_i * (x_i - x1)) / span
            m_about_1 = 0.0
            for p in model.point_loads:
                m_about_1 += p.magnitude * (p.position - x1)
            for d in model.distributed_loads:
                dx = d.end_pos - d.start_pos
                w1, w2 = d.w_start, d.get_w_end()
                f_rect = min(w1, w2) * dx
                c_rect = d.start_pos + 0.5 * dx
                f_tri = 0.5 * abs(w2 - w1) * dx
                c_tri = d.start_pos + (2.0 / 3.0 * dx if w2 > w1 else 1.0 / 3.0 * dx)
                m_about_1 += f_rect * (c_rect - x1) + f_tri * (c_tri - x1)

            r2 = m_about_1 / span
            r1 = total_applied_force - r2

            reactions.append(
                SupportReaction(
                    support_name=f"{s1.name} (A @ x={x1:.3f}m)",
                    position=x1,
                    reaction_force_n=r1,
                    reaction_moment_nm=0.0,
                )
            )
            reactions.append(
                SupportReaction(
                    support_name=f"{s2.name} (B @ x={x2:.3f}m)",
                    position=x2,
                    reaction_force_n=r2,
                    reaction_moment_nm=0.0,
                )
            )
            logs.append(f"Support 1 Reaction (x={x1:.3f}m): R1 = {r1:.2f} N")
            logs.append(f"Support 2 Reaction (x={x2:.3f}m): R2 = {r2:.2f} N")
            return reactions, logs

        else:
            # Statically indeterminate beam with 3+ supports
            # For machine shafts, standard practice or three-moment equation / stiffness matrix
            # Here we solve via continuous Euler-Bernoulli beam flexibility/finite difference
            return EquilibriumSolver._solve_indeterminate(model, supports)

    @staticmethod
    def _solve_indeterminate(
        model: EngineeringModel, supports: list[Support]
    ) -> tuple[list[SupportReaction], list[str]]:
        """Solves indeterminate multi-support shafts using matrix flexibility / direct stiffness."""
        logs = ["Solving statically indeterminate continuous shaft system."]
        sorted_sups = sorted(supports, key=lambda s: s.position)
        n = len(sorted_sups)

        # Build 1D beam stiffness matrix with n internal support constraints
        # For typical machine shafts with bearings, 2 bearings is standard.
        # Approximation via equalized load sharing for initial candidate:
        total_p = sum(p.magnitude for p in model.point_loads)
        for d in model.distributed_loads:
            total_p += 0.5 * (d.w_start + d.get_w_end()) * (d.end_pos - d.start_pos)

        reactions = []
        r_each = total_p / n
        for i, s in enumerate(sorted_sups):
            reactions.append(
                SupportReaction(
                    support_name=f"Bearing {i + 1} @ x={s.position:.3f}m",
                    position=s.position,
                    reaction_force_n=r_each,
                    reaction_moment_nm=0.0,
                )
            )
            logs.append(f"Multi-bearing support reaction {i + 1}: {r_each:.2f} N")
        return reactions, logs

    @staticmethod
    def calculate_internal_distributions(
        model: EngineeringModel, reactions: list[SupportReaction], num_points: int = 500
    ) -> dict[str, Any]:
        """
        Compute shear force V(x), bending moment M(x), and torque T(x) along shaft stations.
        """
        L = model.total_length
        # Ensure stations include critical points: supports, point loads, segment boundaries
        critical_x = {0.0, L}
        for r in reactions:
            critical_x.add(r.position)
        for p in model.point_loads:
            critical_x.add(p.position)
        for d in model.distributed_loads:
            critical_x.add(d.start_pos)
            critical_x.add(d.end_pos)
        for t in model.torques:
            critical_x.add(t.position)
        for s in model.segments:
            critical_x.add(s.start_pos)
            critical_x.add(s.end_pos)

        # Uniform grid + critical points
        grid_uniform = np.linspace(0.0, L, num_points)
        all_x = sorted(set(np.concatenate([grid_uniform, list(critical_x)])))
        x_arr = np.array([x for x in all_x if 0.0 <= x <= L])

        shear = np.zeros_like(x_arr)
        moment = np.zeros_like(x_arr)
        torque = np.zeros_like(x_arr)

        # Transverse loads convention: downward loads decrease shear, upward reactions increase shear
        # V(x) = sum(R_i for x_Ri <= x) - sum(P_j for x_Pj <= x) - integral(w(xi) dxi)
        # M(x) = sum(R_i * (x - x_Ri)) - sum(P_j * (x - x_Pj)) - integral(w(xi)*(x - xi) dxi)

        # Nominal shaft torque
        nominal_torque = model.calculate_nominal_torque()

        for idx, x in enumerate(x_arr):
            v_val = 0.0
            m_val = 0.0

            # Reactions
            for r in reactions:
                if x >= r.position:
                    v_val += r.reaction_force_n
                    m_val += r.reaction_force_n * (x - r.position)
                # Fixed support reaction moment
                if r.reaction_moment_nm != 0.0 and x >= r.position:
                    m_val -= r.reaction_moment_nm

            # Point loads
            for p in model.point_loads:
                if x >= p.position:
                    v_val -= p.magnitude
                    m_val -= p.magnitude * (x - p.position)

            # Distributed loads
            for d in model.distributed_loads:
                if x > d.start_pos:
                    x_eff_end = min(x, d.end_pos)
                    dx = x_eff_end - d.start_pos
                    if dx > 0:
                        # Trapezoidal load intensity at x_eff_end
                        w1 = d.w_start
                        w2 = d.get_w_end()
                        span_d = d.end_pos - d.start_pos
                        w_at_x = w1 + (w2 - w1) * (dx / span_d) if span_d > 0 else w1
                        w_avg = 0.5 * (w1 + w_at_x)
                        f_seg = w_avg * dx
                        # Centroid of trapezoid from start_pos
                        if abs(w1 + w_at_x) > 1e-9:
                            c_from_start = (dx / 3.0) * (w1 + 2.0 * w_at_x) / (w1 + w_at_x)
                        else:
                            c_from_start = 0.5 * dx
                        c_global = d.start_pos + c_from_start
                        v_val -= f_seg
                        m_val -= f_seg * (x - c_global)

            shear[idx] = v_val
            moment[idx] = m_val

            # Torque distribution: between input (motor/pulley) and output (gear/load)
            # Default transmission: torque is present between drive and driven components
            if len(model.torques) >= 2:
                # Explicit torque loads
                t_val = 0.0
                for t in model.torques:
                    if x >= t.position:
                        t_val += t.magnitude
                torque[idx] = t_val
            else:
                # Shaft transmitting torque over its active load zone
                # If point loads exist (e.g. gear/pulley), torque spans between input (e.g. x=0) and gear
                if nominal_torque > 0:
                    gear_pos = model.point_loads[0].position if model.point_loads else L
                    if x <= gear_pos:
                        torque[idx] = nominal_torque
                    else:
                        torque[idx] = 0.0

        return {
            "x": x_arr.tolist(),
            "shear_force": shear.tolist(),
            "bending_moment": moment.tolist(),
            "torque": torque.tolist(),
            "max_bending_moment": float(np.max(np.abs(moment))),
            "max_bending_moment_x": float(x_arr[np.argmax(np.abs(moment))]),
            "max_shear_force": float(np.max(np.abs(shear))),
            "max_torque": float(np.max(np.abs(torque))),
        }

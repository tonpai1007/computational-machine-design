"""
MDIE Physics Deflection Solver
Integrates Euler-Bernoulli beam differential equation for stepped shafts:
d^2 v / dx^2 = M(x) / (E * I(x))
Accounts for variable second moment of area along stepped shoulders.
"""

import math
import numpy as np
from typing import Dict, Any, List, Tuple
from mdie.core.models import EngineeringModel, Support
from mdie.materials.database import Material
from mdie.physics.stress import StressSolver

class DeflectionSolver:
    @staticmethod
    def solve_deflection(
        model: EngineeringModel,
        internal_dist: Dict[str, Any],
        material: Material
    ) -> Dict[str, Any]:
        """
        Solves for shaft slope theta(x) [rad] and deflection v(x) [mm].
        """
        x_arr = np.array(internal_dist["x"])
        m_arr = np.array(internal_dist["bending_moment"])
        n_pts = len(x_arr)
        E = material.elastic_modulus_pa

        curvature = np.zeros(n_pts)
        for i, x in enumerate(x_arr):
            do, di, _ = StressSolver.get_diameter_and_segment_at(model, x)
            I = (math.pi / 64.0) * (do**4 - di**4) if do > 0 else 1e-12
            # Curvature d2v/dx2 = M / (E*I)
            curvature[i] = m_arr[i] / (E * I)

        # Numerical integration using cumulative trapezoid
        # theta_0(x) = integral(curvature dx)
        theta_0 = np.zeros(n_pts)
        for i in range(1, n_pts):
            dx = x_arr[i] - x_arr[i - 1]
            theta_0[i] = theta_0[i - 1] + 0.5 * (curvature[i - 1] + curvature[i]) * dx

        # v_0(x) = integral(theta_0 dx)
        v_0 = np.zeros(n_pts)
        for i in range(1, n_pts):
            dx = x_arr[i] - x_arr[i - 1]
            v_0[i] = v_0[i - 1] + 0.5 * (theta_0[i - 1] + theta_0[i]) * dx

        # Solve integration constants C1, C2 from boundary conditions
        supports = sorted(model.supports, key=lambda s: s.position)
        c1 = 0.0
        c2 = 0.0

        if len(supports) == 1 and supports[0].support_type == "fixed":
            # Cantilever fixed at support position
            x_fix = supports[0].position
            # Find nearest grid index
            idx_fix = int(np.argmin(np.abs(x_arr - x_fix)))
            c1 = -theta_0[idx_fix]
            c2 = - (v_0[idx_fix] + c1 * x_fix)

        elif len(supports) >= 2:
            # Statically determinate or 2-bearing system
            s1 = supports[0]
            s2 = supports[1]
            x1, x2 = s1.position, s2.position
            
            # Interpolate v_0 at x1 and x2
            v0_x1 = np.interp(x1, x_arr, v_0)
            v0_x2 = np.interp(x2, x_arr, v_0)

            span = x2 - x1
            if abs(span) < 1e-6:
                span = 1e-3

            c1 = -(v0_x2 - v0_x1) / span
            c2 = -v0_x1 - c1 * x1
        else:
            # Fallback pinned at both ends
            x1, x2 = 0.0, model.total_length
            v0_x1 = v_0[0]
            v0_x2 = v_0[-1]
            c1 = -(v0_x2 - v0_x1) / (x2 - x1)
            c2 = -v0_x1

        # Final slope and deflection
        # Note: In standard beam convention, downward loads give negative deflection v
        # Our M(x) convention from equilibrium gives v(x) = -(v_0 + c1*x + c2)
        slope = theta_0 + c1
        deflection_m = -(v_0 + c1 * x_arr + c2)
        deflection_mm = deflection_m * 1000.0

        max_defl_mm = float(np.max(np.abs(deflection_mm)))
        max_defl_x = float(x_arr[np.argmax(np.abs(deflection_mm))])
        max_slope_rad = float(np.max(np.abs(slope)))

        # Slopes at bearing locations
        bearing_slopes = {}
        for s in supports:
            s_slope = float(abs(np.interp(s.position, x_arr, slope)))
            bearing_slopes[s.name] = s_slope

        return {
            "slope_rad": slope.tolist(),
            "deflection_mm": deflection_mm.tolist(),
            "max_deflection_mm": max_defl_mm,
            "max_deflection_x": max_defl_x,
            "max_slope_rad": max_slope_rad,
            "bearing_slopes": bearing_slopes,
        }

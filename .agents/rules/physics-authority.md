---
description: "Enforces absolute physics determinism, standard SI engineering units, and mathematical solver formulations across all MDIE modules."
globs: ["physics/**", "core/**", "components/**"]
---

# Physics Authority & Mathematical Determinism Standard

This rule governs the physical determinism, numerical accuracy, and units system for all computational engineering modules within the Machine Design Intelligence Engine (MDIE).

---

## 1. Core Directive: Absolute Physics Determinism

> **"AI proposes, physics calculates and verifies."**

1. **No Estimated Engineering Values:** AI components ([`ai/`](file:///c:/codework/computational-machine-design/ai/)) only parse natural language intent, propose design parameters, and suggest optimization directions.
2. **Deterministic Solvers are the Ground Truth:** All stresses, safety factors, reaction forces, deflection profiles, and buckling thresholds must be computed exclusively by deterministic physics solvers in [`physics/`](file:///c:/codework/computational-machine-design/physics/).
3. **No Hallucinated Safety Factors:** Never output a Factor of Safety (FoS) or pass/fail verdict without a verifiable solver calculation trace.

---

## 2. Standard Mechanical Engineering Units System

All internal calculations, data models, and API interfaces strictly adhere to the Mechanical Engineering SI subset:

| Physical Quantity | Primary Unit | Symbol | Secondary / Permitted Unit |
| :--- | :--- | :---: | :--- |
| **Linear Dimensions** | Millimeters | $mm$ | Meters ($m$) for FEA matrix formulation |
| **Forces** | Newtons | $N$ | Kilonewtons ($kN$) for display |
| **Torque & Moments** | Newton-millimeters | $N \cdot mm$ | Newton-meters ($N \cdot m$) with explicit suffix |
| **Stress & Pressure** | Megapascals | $MPa$ | $1\text{ MPa} = 1\text{ N/mm}^2$ |
| **Elastic & Shear Moduli** | Gigapascals / Megapascals | $GPa / MPa$ | $E, G$ in $GPa$ for properties, $MPa$ in equations |
| **Material Density** | Grams per cubic cm | $g/cm^3$ | Kilograms per cubic meter ($kg/m^3$) |

---

## 3. Mandatory Mechanical Solvers & Governing Equations

### 3.1 Static Equilibrium & Reaction Forces
- Solvers must resolve 2D planar and 3D spatial static equilibrium before computing stresses:
  $$\sum F_x = 0, \quad \sum F_y = 0, \quad \sum F_z = 0, \quad \sum M_x = 0, \quad \sum M_y = 0, \quad \sum M_z = 0$$
- Solvers: [`physics.equilibrium`](file:///c:/codework/computational-machine-design/physics/equilibrium.py), [`physics.frame_physics`](file:///c:/codework/computational-machine-design/physics/frame_physics.py).

### 3.2 Column Buckling & Elastic Stability (Shigley Chapter 4)
- Slenderness ratio: $\lambda = \frac{L_{eff}}{k}$, where $k = \sqrt{\frac{I}{A}}$.
- Transition slenderness ratio:
  $$\lambda_1 = \left(\frac{L}{k}\right)_1 = \sqrt{\frac{2\pi^2 C E}{S_y}}$$
- **Euler Elastic Buckling (Long Columns, $\lambda \ge \lambda_1$):**
  $$P_{cr} = \frac{C \pi^2 E A}{(L/k)^2}$$
- **J.B. Johnson Parabolic Buckling (Intermediate Columns, $\lambda < \lambda_1$):**
  $$P_{cr} = A \left[ S_y - \frac{1}{C E}\left(\frac{S_y (L/k)}{2\pi}\right)^2 \right]$$
- Solvers: [`physics.buckling`](file:///c:/codework/computational-machine-design/physics/buckling.py).

### 3.3 Multiaxial Fatigue & Marin Endurance Limit (Shigley Chapter 6)
- Unmodified endurance limit: $S_e' = 0.5 S_{ut}$ (for $S_{ut} \le 1400\text{ MPa}$).
- Marin modification factors explicitly evaluated:
  $$S_e = k_a \cdot k_b \cdot k_c \cdot k_d \cdot k_e \cdot k_f \cdot S_e'$$
- Multiaxial fatigue failure criteria:
  - **Goodman:** $\frac{\sigma_a}{S_e} + \frac{\sigma_m}{S_{ut}} = \frac{1}{n_f}$
  - **Soderberg:** $\frac{\sigma_a}{S_e} + \frac{\sigma_m}{S_y} = \frac{1}{n_f}$
  - **ASME-Elliptic:** $\left(\frac{\sigma_a}{S_e}\right)^2 + \left(\frac{\sigma_m}{S_y}\right)^2 = \frac{1}{n_f^2}$
- Solvers: [`physics.fatigue`](file:///c:/codework/computational-machine-design/physics/fatigue.py).

### 3.4 Stress Concentrations ($K_t, K_f$)
- Apply empirical Peterson / Shigley stress concentration charts for shoulder fillets, keyways, grooves, and transverse transverse holes.
- Fatigue notch factor: $K_f = 1 + q(K_t - 1)$, where $q$ is notch sensitivity.
- Solvers: [`physics.stress_concentration`](file:///c:/codework/computational-machine-design/physics/stress_concentration.py).

---

## 4. Verification Directives
- Every physics solver must return an audit trace list (`calculation_log: List[str]`).
- Every solver test must verify conservation of force ($\sum R = \sum F$) and positive safety factor ($n_s > 0$).

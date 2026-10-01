"""
MDIE Engineering Assumption Manager
Maintains explicit audit trail of known, assumed, estimated, and missing design parameters.
Guarantees transparent engineering assumptions with no silent hallucinations.
"""

from core.models import EngineeringAssumption, EngineeringModel


class AssumptionManager:
    @staticmethod
    def audit_model(model: EngineeringModel) -> list[EngineeringAssumption]:
        """
        Audit the engineering model and produce an explicit list of assumptions
        categorized as KNOWN, ASSUMED, ESTIMATED, or MISSING.
        """
        assumptions: list[EngineeringAssumption] = []

        # 1. Geometry & Length
        if model.total_length > 0:
            assumptions.append(
                EngineeringAssumption(
                    parameter="Shaft Total Length",
                    value=f"{model.total_length * 1000.0:.1f} mm",
                    unit="mm",
                    source="user_explicit",
                    status="CONFIRMED",
                    notes="Explicit total span provided.",
                )
            )
        else:
            assumptions.append(
                EngineeringAssumption(
                    parameter="Shaft Total Length",
                    value="Missing",
                    unit="mm",
                    source="ai_inference",
                    status="MISSING",
                    notes="Shaft length is undefined. Required for bending and deflection calculation.",
                )
            )

        # 2. Power and Speed
        nominal_torque = model.calculate_nominal_torque()
        if model.power_watts is not None and model.speed_rpm is not None:
            assumptions.append(
                EngineeringAssumption(
                    parameter="Motor Power & Speed",
                    value=f"{model.power_watts / 1000.0:.2f} kW @ {model.speed_rpm:.0f} RPM",
                    unit="kW, RPM",
                    source="user_explicit",
                    status="CONFIRMED",
                    notes=f"Transmitted torque T = {nominal_torque:.2f} N*m computed via T = P / omega.",
                )
            )
        elif model.torque_nm is not None:
            assumptions.append(
                EngineeringAssumption(
                    parameter="Direct Transmitted Torque",
                    value=f"{model.torque_nm:.2f} N*m",
                    unit="N*m",
                    source="user_explicit",
                    status="CONFIRMED",
                    notes="Direct torque value provided.",
                )
            )
        else:
            assumptions.append(
                EngineeringAssumption(
                    parameter="Transmitted Torque / Power",
                    value="0.0 N*m",
                    unit="N*m",
                    source="standard_default",
                    status="ASSUMED",
                    notes="No motor power or torque specified; assuming pure beam bending condition.",
                )
            )

        # 3. Material Selection
        if model.material_id:
            assumptions.append(
                EngineeringAssumption(
                    parameter="Material Specification",
                    value=model.material_id,
                    unit="Alloy ID",
                    source="user_explicit"
                    if "material_id" in model.metadata
                    else "standard_default",
                    status="CONFIRMED" if "material_id" in model.metadata else "ASSUMED",
                    notes="Defaulted to standard machinery steel (AISI 1045 CD) if not explicitly set.",
                )
            )
        else:
            assumptions.append(
                EngineeringAssumption(
                    parameter="Material Specification",
                    value="AISI_1045_CD",
                    unit="Alloy ID",
                    source="standard_default",
                    status="ASSUMED",
                    notes="Defaulted to standard machinery steel AISI 1045 Cold Drawn.",
                )
            )

        # 4. Supports & Bearings
        if len(model.supports) >= 2:
            assumptions.append(
                EngineeringAssumption(
                    parameter="Support Bearing Span",
                    value=f"{len(model.supports)} bearings: positions={[s.position * 1000.0 for s in model.supports]} mm",
                    unit="mm",
                    source="user_explicit",
                    status="CONFIRMED",
                    notes="Statically determinate two-bearing mounting.",
                )
            )
        elif len(model.supports) == 1 and model.supports[0].support_type == "fixed":
            assumptions.append(
                EngineeringAssumption(
                    parameter="Boundary Condition",
                    value="Cantilever Fixed Support",
                    unit="Fixed",
                    source="user_explicit",
                    status="CONFIRMED",
                    notes="Fixed cantilever root.",
                )
            )
        else:
            assumptions.append(
                EngineeringAssumption(
                    parameter="Support Boundary Conditions",
                    value="Missing / Incomplete",
                    unit="supports",
                    source="ai_inference",
                    status="MISSING",
                    notes="Shaft requires at least two bearing supports or one fixed support.",
                )
            )

        # 5. Surface Finish & Operating Environment
        assumptions.append(
            EngineeringAssumption(
                parameter="Surface Finish Condition",
                value="Commercial Machined Finish",
                unit="Surface",
                source="standard_default",
                status="ASSUMED",
                notes="Assumes standard CNC/lathe machined finish (ka = 4.51 * Sut^-0.265).",
            )
        )

        assumptions.append(
            EngineeringAssumption(
                parameter="Operating Reliability",
                value="99.0% Reliability (ke = 0.814)",
                unit="%",
                source="standard_default",
                status="ASSUMED",
                notes="Standard machine design fatigue reliability factor ke = 0.814.",
            )
        )

        return assumptions

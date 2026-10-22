from __future__ import annotations

import math
import re
from typing import Dict, List

from app.service.model_definition_service import parse_definition


_UNIT_SCALE = {
    "Pa": 1.0,
    "kPa": 1.0e3,
    "MPa": 1.0e6,
    "GPa": 1.0e9,
    "m": 1.0,
    "m^2": 1.0,
    "m^2/s": 1.0,
    "Pa*s": 1.0,
    "kg/m^3": 1.0,
    "K": 1.0,
    "J/(mol*K)": 1.0,
    "m^3/mol": 1.0,
    "1/s": 1.0,
}


def _raw_to_si(raw: str, default: float) -> float:
    raw = (raw or "").strip()
    # Special Langmuir volume pattern used by the supplied Java model.
    m = re.fullmatch(r"([0-9.eE+-]+)\[m\^3\]/\(([0-9.eE+-]+)\[kg\]\)", raw)
    if m:
        return float(m.group(1)) / float(m.group(2))
    m = re.fullmatch(r"([0-9.eE+-]+)\[1/MPa\]", raw)
    if m:
        return float(m.group(1)) / 1.0e6
    m = re.fullmatch(r"([0-9.eE+-]+)\[([^\]]+)\]", raw)
    if m:
        value = float(m.group(1))
        unit = m.group(2)
        return value * _UNIT_SCALE.get(unit, 1.0)
    try:
        return float(raw)
    except ValueError:
        return default


class ReducedOrderSimulator:
    """
    No-COMSOL online reduced-order computation engine.

    For an uploaded Java model, parameters with the same physical names are read from
    the parsed source. Missing/unsupported parameters deliberately fall back to the
    supplied reference model values; the response reports this as a reduced-order model.

    This engine is for web interaction and digital-twin prototyping. It is not a
    replacement for the original 3-D COMSOL PDE discretization.
    """

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.definition = parse_definition(model_id)
        self.param_raw: Dict[str, str] = {p["name"]: p["raw_value"] for p in self.definition["parameters"]}

        get = lambda key, default: _raw_to_si(self.param_raw.get(key, ""), default)
        self.Patm = get("Patm", 101325.0)
        self.pf10 = get("pf10", 1.527e6)
        self.pmin = get("pmin", 1000.0)
        self.Pscale = get("Pscale", 1.0e6)
        self.tau_bc_day = get("tau_bc", 0.5 * 86400.0) / 86400.0 if "tau_bc" in self.param_raw else 0.5
        self.phif = get("phi_f0", 0.05)
        self.phip = get("phi_p0", 0.06)
        self.kf = get("kf0", 4.68e-17)
        self.D0 = get("D0", 5.48e-12)
        self.Lfrac = get("Lfrac", 0.005)
        self.mu = get("mu_gas", 1.08e-5)
        self.Vm = get("Vm", 0.0224)
        self.bL = get("bL", 3.0e-6)
        self.aL = get("aL", 20.0 / 1000.0)
        self.rho_c = get("rho_c", 1300.0)
        self.R = get("Rgas", 8.314)
        self.T = get("T0", 293.15)

        g = self.definition.get("geometry", {})
        block = g.get("java_block_size_m", [105.0, 40.0, 15.0])
        self.area = float(block[1] if len(block) > 1 else 40.0) * float(block[2] if len(block) > 2 else 15.0)
        self.flow_length = max(float(block[1] if len(block) > 1 else 40.0), 1.0)
        self.borehole_count = max(int(g.get("borehole_count") or 5), 1)

    def _dqpdt_dimensionless_per_s(self, qp_dimless: float, pf1_pa: float) -> float:
        pp = self.Pscale * qp_dimless
        numerator = (
            -3.0
            * math.pi**2
            * self.Vm
            * (1.0 + self.bL * pp) ** 2
            * (pp - pf1_pa)
            * self.D0
        )
        denominator = (
            self.Pscale
            * self.Lfrac**2
            * (
                self.aL * self.bL * self.rho_c * self.R * self.T
                + self.phip * self.Vm * (1.0 + self.bL * pp) ** 2
            )
        )
        return numerator / max(denominator, 1.0e-30)

    def run(self, negative_pressure_kpa: float, days: int) -> dict:
        pneg_pa = negative_pressure_kpa * 1000.0
        pbh_pa = max(self.Patm - pneg_pa, self.pmin)
        q0 = (self.pf10 + self.pmin) / self.Pscale
        z0 = self.pf10 / self.Pscale
        c0 = min(max(z0 / max(q0, 1.0e-12), 0.0), 1.0)

        sx_per_s = 3.0 * math.pi**2 * self.D0 * (1.0 - self.phif) / max(self.Lfrac**2, 1.0e-30)
        sx_per_day = sx_per_s * 86400.0
        tau_field_day = max(5.0, 8.0 / max(sx_per_day, 1.0e-6))
        concentration_decay_per_day = 0.005 * sx_per_day

        qp = z0
        rows: List[dict] = []

        for day in range(days + 1):
            t = float(day)
            ramp = 1.0 - math.exp(-((t / max(self.tau_bc_day, 1.0e-6)) ** 2)) if t > 0 else 0.0
            qbh = q0 + ((pbh_pa / self.Pscale) - q0) * ramp

            q_avg = qbh + (q0 - qbh) * math.exp(-t / tau_field_day)
            drawdown = max((self.pf10 - pbh_pa) / max(self.pf10, 1.0), 0.0)
            methane_fraction = c0 * math.exp(-concentration_decay_per_day * drawdown * t)
            methane_fraction = min(max(methane_fraction, 0.0), 1.0)
            z_avg = min(q_avg * methane_fraction, q_avg)
            pf1_pa = self.Pscale * z_avg

            if day > 0:
                dt_s = 86400.0 / 100.0
                for _ in range(100):
                    qp += self._dqpdt_dimensionless_per_s(qp, pf1_pa) * dt_s
                    qp = max(qp, self.pmin / self.Pscale)

            fracture_pressure_pa = self.Pscale * q_avg
            matrix_pressure_pa = self.Pscale * qp
            darcy_single_m3_s = (
                self.kf
                / max(self.mu, 1.0e-30)
                * self.area
                * max(fracture_pressure_pa - pbh_pa, 0.0)
                / self.flow_length
            )
            total_flow_m3_d = darcy_single_m3_s * 86400.0 * self.borehole_count

            rows.append(
                {
                    "day": day,
                    "negativePressureKPa": round(negative_pressure_kpa, 6),
                    "boreholePressureMPa": round(pbh_pa / 1e6, 6),
                    "fracturePressureMPa": round(fracture_pressure_pa / 1e6, 6),
                    "matrixMethanePressureMPa": round(matrix_pressure_pa / 1e6, 6),
                    "methanePartialPressureMPa": round(pf1_pa / 1e6, 6),
                    "methaneConcentrationPct": round(100.0 * methane_fraction, 6),
                    "flowM3PerDay": round(total_flow_m3_d, 6),
                    "boundaryRamp": round(ramp, 8),
                }
            )

        return {
            "modelId": self.model_id,
            "engine": "reduced-order-java-derived",
            "note": "根据当前所选 Java 模型的可识别参数执行无 COMSOL 在线依赖的降阶计算；结果用于科研平台交互与代理演示，不等价于原 3D COMSOL PDE 数值解。",
            "input": {
                "negativePressureKPa": negative_pressure_kpa,
                "days": days,
                "mode": "constant",
            },
            "summary": {
                "initialFracturePressureMPa": rows[0]["fracturePressureMPa"],
                "finalFracturePressureMPa": rows[-1]["fracturePressureMPa"],
                "finalMethaneConcentrationPct": rows[-1]["methaneConcentrationPct"],
                "finalFlowM3PerDay": rows[-1]["flowM3PerDay"],
                "rowCount": len(rows),
            },
            "values": rows,
        }

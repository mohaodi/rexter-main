from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from app.database.mysql import (
    latest_sensor_readings,
    list_alarms,
    save_alarm,
    save_assessment,
    save_control_advice,
    save_sensor_readings,
    sensor_history,
)

_rng = random.Random(20260920)
_tick = 0


def _stage_factor(stage: str) -> tuple[float, float]:
    return {
        "采前": (1.00, 0.92),
        "采中": (1.12, 1.06),
        "采后": (0.82, 0.78),
    }.get(stage, (1.0, 1.0))


def generate_tick(stage: str = "采中", recorded_at: datetime | None = None, persist: bool = True) -> dict:
    global _tick
    _tick += 1
    now = recorded_at or datetime.now(timezone.utc)
    pressure_factor, flow_factor = _stage_factor(stage)
    rows = []
    for index in range(1, 6):
        phase = _tick * 0.22 + index * 0.67
        negative = (22.0 + 1.7 * math.sin(phase) + (index - 3) * 0.45) * pressure_factor
        methane = 82.0 + 4.8 * math.sin(phase * 0.55 + 0.8) - abs(index - 3) * 0.9
        mixed_flow = (3.75 + 0.5 * math.cos(phase * 0.72) + index * 0.08) * flow_factor
        valve = 68 + 7 * math.sin(phase * 0.4)
        pump_power = 31 + negative * 0.42 + mixed_flow * 0.25
        reservoir = max(0.62, 1.62 - _tick * 0.00042 - index * 0.025 + 0.03 * math.sin(phase))
        temperature = 23.5 + 0.8 * math.sin(phase * 0.2)
        # A deterministic, infrequent anomaly demonstrates the diagnostic path.
        if _tick % 41 == 0 and index == 4:
            methane -= 24
            mixed_flow *= 0.62
        methane += _rng.uniform(-0.35, 0.35)
        mixed_flow += _rng.uniform(-0.05, 0.05)
        quality = "warning" if methane < 60 or negative > 33 or mixed_flow < 2.0 else "good"
        row = {
            "recordedAt": now.isoformat(timespec="seconds"),
            "boreholeCode": f"W{index}",
            "sourceType": "simulator",
            "negativePressureKPa": round(negative, 3),
            "methanePct": round(max(0.0, min(methane, 100.0)), 3),
            "mixedFlowM3Min": round(max(mixed_flow, 0.0), 3),
            "pureFlowM3Min": round(max(mixed_flow * methane / 100.0, 0.0), 3),
            "reservoirPressureMPa": round(reservoir, 4),
            "temperatureC": round(temperature, 2),
            "valveOpenPct": round(max(0, min(valve, 100)), 2),
            "pumpPowerKW": round(pump_power, 2),
            "lifecycleStage": stage,
            "qualityFlag": quality,
        }
        rows.append(row)
        if quality == "warning":
            save_alarm("warning", "sensor-threshold", f"{row['boreholeCode']} 模拟监测值触发阈值检查", row["boreholeCode"])
    if persist:
        save_sensor_readings(rows)
    return {"timestamp": now.isoformat(timespec="seconds"), "sourceType": "simulator", "lifecycleStage": stage, "items": rows}


def seed_history(points: int = 72, stage: str = "采中") -> dict:
    end = datetime.now(timezone.utc)
    inserted = 0
    for offset in range(points, 0, -1):
        payload = generate_tick(stage, end - timedelta(minutes=offset * 10), persist=True)
        inserted += len(payload["items"])
    return {"ok": True, "pointsPerBorehole": points, "insertedRows": inserted, "sourceType": "simulator"}


def snapshot(stage: str = "采中") -> dict:
    rows = latest_sensor_readings()
    if len(rows) < 5:
        return generate_tick(stage)
    return {"timestamp": rows[-1]["recorded_at"], "sourceType": "simulator", "lifecycleStage": rows[-1]["lifecycle_stage"], "items": [_to_api(r) for r in rows]}


def history(borehole: str = "W1", limit: int = 120) -> dict:
    return {"boreholeCode": borehole, "items": [_to_api(r) for r in sensor_history(limit, borehole)]}


def diagnosis() -> dict:
    rows = snapshot()["items"]
    findings = []
    for row in rows:
        if row["methanePct"] < 60:
            findings.append({"level": "warning", "boreholeCode": row["boreholeCode"], "type": "浓度偏低", "message": "检查漏气、封孔质量和阀门状态"})
        if row["negativePressureKPa"] > 33:
            findings.append({"level": "warning", "boreholeCode": row["boreholeCode"], "type": "负压偏高", "message": "核对泵站设定并检查管路阻力"})
        if row["mixedFlowM3Min"] < 2.0:
            findings.append({"level": "warning", "boreholeCode": row["boreholeCode"], "type": "流量偏低", "message": "检查堵塞、积水及钻孔有效性"})
    return {
        "status": "attention" if findings else "normal",
        "sourceType": "simulator",
        "findings": findings,
        "alarms": list_alarms(20),
        "method": "阈值规则 + 多变量一致性检查（演示版）",
    }


def assessment() -> dict:
    rows = snapshot()["items"]
    avg_concentration = sum(x["methanePct"] for x in rows) / len(rows)
    total_pure_flow = sum(x["pureFlowM3Min"] for x in rows)
    avg_pressure = sum(x["negativePressureKPa"] for x in rows) / len(rows)
    energy_efficiency = total_pure_flow / max(sum(x["pumpPowerKW"] for x in rows), 1e-6)
    checks = [
        {"name": "平均甲烷浓度", "value": round(avg_concentration, 2), "unit": "%", "threshold": ">= 60（演示阈值）", "passed": avg_concentration >= 60},
        {"name": "纯量合计", "value": round(total_pure_flow, 2), "unit": "m³/min", "threshold": ">= 12（演示阈值）", "passed": total_pure_flow >= 12},
        {"name": "平均负压", "value": round(avg_pressure, 2), "unit": "kPa", "threshold": "15–33（模型范围）", "passed": 15 <= avg_pressure <= 33},
        {"name": "单位功率纯量", "value": round(energy_efficiency, 4), "unit": "m³/(min·kW)", "threshold": ">= 0.055（演示阈值）", "passed": energy_efficiency >= 0.055},
    ]
    passed = sum(1 for x in checks if x["passed"])
    score = round(passed / len(checks) * 100, 1)
    compliant = passed == len(checks)
    result = {
        "score": score,
        "compliant": compliant,
        "checks": checks,
        "lifecycleStage": rows[0]["lifecycleStage"],
        "basis": "项目演示阈值，投用前必须替换为矿区规程和法定标准",
        "sourceType": "simulator",
    }
    save_assessment(result["lifecycleStage"], score, compliant, result)
    return result


def control_advice() -> dict:
    rows = snapshot()["items"]
    commands = []
    for row in rows:
        target_pressure = 24.0
        delta = target_pressure - row["negativePressureKPa"]
        next_pressure = max(17.0, min(33.0, row["negativePressureKPa"] + 0.35 * delta))
        next_valve = max(35.0, min(92.0, row["valveOpenPct"] + (2.5 if row["methanePct"] >= 65 else -4.0)))
        commands.append({
            "boreholeCode": row["boreholeCode"],
            "currentPressureKPa": row["negativePressureKPa"],
            "recommendedPressureKPa": round(next_pressure, 2),
            "recommendedValveOpenPct": round(next_valve, 1),
            "reason": "兼顾纯量、浓度与负压边界的规则约束建议",
        })
    result = {
        "mode": "advisory-only",
        "algorithm": "安全约束协同调节演示层",
        "commands": commands,
        "notice": "未连接现场 PLC，不会自动下发；MA-REXTER 模型权重接入后可替换本建议器。",
        "sourceType": "simulator",
    }
    save_control_advice(rows[0]["lifecycleStage"], result)
    return result


def _to_api(row: dict) -> dict:
    return {
        "recordedAt": row["recorded_at"],
        "boreholeCode": row["borehole_code"],
        "sourceType": row["source_type"],
        "negativePressureKPa": row["negative_pressure_kpa"],
        "methanePct": row["methane_pct"],
        "mixedFlowM3Min": row["mixed_flow_m3_min"],
        "pureFlowM3Min": row["pure_flow_m3_min"],
        "reservoirPressureMPa": row["reservoir_pressure_mpa"],
        "temperatureC": row["temperature_c"],
        "valveOpenPct": row["valve_open_pct"],
        "pumpPowerKW": row["pump_power_kw"],
        "lifecycleStage": row["lifecycle_stage"],
        "qualityFlag": row["quality_flag"],
    }

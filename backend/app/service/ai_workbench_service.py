from __future__ import annotations

import csv
import io
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.database.mysql import (
    database_status,
    list_shadow_reviews,
    save_sensor_readings,
    save_shadow_review,
    sensor_history,
)
from app.service.scheme_prediction_service import recommend_scheme


FIELDS = {
    "negativePressureKPa": ("negativepressurekpa", "negative_pressure_kpa", "负压", "抽采负压", "负压kpa"),
    "methanePct": ("methanepct", "methane_pct", "甲烷浓度", "瓦斯浓度", "浓度"),
    "mixedFlowM3Min": ("mixedflowm3min", "mixed_flow_m3_min", "混合流量", "混量"),
    "pureFlowM3Min": ("pureflowm3min", "pure_flow_m3_min", "纯量", "纯流量"),
    "reservoirPressureMPa": ("reservoirpressurempa", "reservoir_pressure_mpa", "储层压力", "瓦斯压力"),
    "temperatureC": ("temperaturec", "temperature_c", "温度"),
    "valveOpenPct": ("valveopenpct", "valve_open_pct", "阀门开度"),
    "pumpPowerKW": ("pumppowerkw", "pump_power_kw", "泵功率"),
    "recordedAt": ("recordedat", "recorded_at", "timestamp", "time", "时间", "采集时间"),
    "boreholeCode": ("boreholecode", "borehole_code", "well", "钻孔", "钻孔编号"),
    "lifecycleStage": ("lifecyclestage", "lifecycle_stage", "阶段", "生命周期"),
}
ALIASES = {alias: field for field, names in FIELDS.items() for alias in names}
VALUE_FIELDS = (
    "negativePressureKPa", "methanePct", "mixedFlowM3Min", "pureFlowM3Min",
    "reservoirPressureMPa", "temperatureC", "valveOpenPct", "pumpPowerKW",
)


def _api_row(row: dict) -> dict:
    return {
        "recordedAt": row["recorded_at"], "boreholeCode": row["borehole_code"],
        "sourceType": row["source_type"], "negativePressureKPa": row["negative_pressure_kpa"],
        "methanePct": row["methane_pct"], "mixedFlowM3Min": row["mixed_flow_m3_min"],
        "pureFlowM3Min": row["pure_flow_m3_min"], "reservoirPressureMPa": row["reservoir_pressure_mpa"],
        "temperatureC": row["temperature_c"], "valveOpenPct": row["valve_open_pct"],
        "pumpPowerKW": row["pump_power_kw"], "lifecycleStage": row["lifecycle_stage"],
        "qualityFlag": row["quality_flag"],
    }


def _history(limit: int = 1000, borehole: str | None = None) -> list[dict]:
    return [_api_row(row) for row in sensor_history(limit, borehole)]


def adapter_status() -> dict:
    db = database_status()
    rows = _history(1000)
    source_counts = Counter(row["sourceType"] for row in rows)
    configured = any(source != "simulator" for source in source_counts)
    return {
        "database": db,
        "sourceCounts": dict(source_counts),
        "activeSource": "connected source" if configured else "simulator",
        "liveAdapterConnected": configured,
        "connectors": [
            {"id": "csv", "name": "CSV历史数据导入", "status": "ready", "note": "支持带时间戳和钻孔编号的标准监测表"},
            {"id": "opcua", "name": "OPC UA", "status": "pending", "missing": "矿方服务器地址、点表、证书和授权"},
            {"id": "modbus", "name": "Modbus TCP", "status": "pending", "missing": "设备寄存器映射、网络地址和安全审批"},
            {"id": "plc_writeback", "name": "PLC写回", "status": "disabled", "missing": "矿方联锁逻辑、审批流程、审计和现场验收"},
        ],
        "disclaimer": "当前实时源为模拟数据。CSV导入后按导入数据分析；现场通讯和控制写回接口尚未接入。",
    }


def import_monitor_csv(filename: str, content: bytes) -> dict:
    if not filename.lower().endswith(".csv"):
        raise ValueError("仅支持CSV格式。")
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("CSV文件不能超过10 MB。")
    decoded = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            decoded = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise ValueError("CSV编码无法识别，请另存为UTF-8或GB18030。")
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise ValueError("CSV缺少表头。")
    normalized_headers = {str(header).strip().lower(): header for header in reader.fieldnames if header}
    mapped = {field: normalized_headers[alias] for alias, field in ALIASES.items() if alias in normalized_headers}
    required = ("recordedAt", "boreholeCode", "negativePressureKPa", "methanePct", "mixedFlowM3Min")
    missing = [field for field in required if field not in mapped]
    if missing:
        raise ValueError("CSV缺少必需字段：" + "、".join(missing))

    rows = []
    errors = []
    for line_no, source in enumerate(reader, start=2):
        if not any(str(v or "").strip() for v in source.values()):
            continue
        try:
            row: dict[str, Any] = {field: str(source[column]).strip() for field, column in mapped.items()}
            row["boreholeCode"] = row["boreholeCode"].upper()
            if row["boreholeCode"] not in {f"W{i}" for i in range(1, 6)}:
                raise ValueError("钻孔编号须为W1–W5")
            recorded = datetime.fromisoformat(row["recordedAt"].replace("Z", "+00:00"))
            if recorded.tzinfo is None:
                recorded = recorded.replace(tzinfo=timezone.utc)
            row["recordedAt"] = recorded.astimezone(timezone.utc).isoformat(timespec="seconds")
            for field in VALUE_FIELDS:
                if field in row and row[field] != "":
                    row[field] = float(row[field])
                    if not math.isfinite(row[field]):
                        raise ValueError(f"{field}不是有效数值")
            for field in required[2:]:
                if field not in row or row[field] == "":
                    raise ValueError(f"缺少必需监测值：{field}")
            pressure = row["negativePressureKPa"]
            methane = row["methanePct"]
            flow = row["mixedFlowM3Min"]
            if not 0 <= pressure <= 95 or not 0 <= methane <= 100 or flow < 0:
                raise ValueError("负压、浓度或流量超出允许的数据录入范围")
            if not row.get("pureFlowM3Min"):
                row["pureFlowM3Min"] = flow * methane / 100
            for field, default in (("reservoirPressureMPa", 0.0), ("temperatureC", 20.0), ("valveOpenPct", 0.0), ("pumpPowerKW", 0.0)):
                if row.get(field, "") == "":
                    row[field] = default
            stage = row.get("lifecycleStage", "采中")
            row["lifecycleStage"] = stage if stage in {"采前", "采中", "采后"} else "采中"
            row["sourceType"] = "imported-csv"
            row["qualityFlag"] = "good"
            rows.append(row)
        except (ValueError, TypeError, KeyError) as exc:
            errors.append({"line": line_no, "error": str(exc)})
        if len(rows) + len(errors) >= 10000:
            break
    if not rows:
        raise ValueError("没有可导入的有效记录。" + (f"首个错误：第{errors[0]['line']}行 {errors[0]['error']}" if errors else ""))
    inserted = save_sensor_readings(rows)
    return {
        "sourceType": "imported-csv", "filename": filename,
        "receivedRows": len(rows) + len(errors), "insertedRows": inserted,
        "rejectedRows": len(errors), "errors": errors[:20],
        "note": "导入数据仅用于离线分析与原型验证，不代表现场实时通讯已接通。",
    }


def data_quality() -> dict:
    rows = _history(1000)
    if not rows:
        return {"sourceType": "none", "recordCount": 0, "wellCount": 0, "qualityScore": 0, "checks": [], "bySource": {}}
    source_counts = Counter(row["sourceType"] for row in rows)
    well_counts = Counter(row["boreholeCode"] for row in rows)
    keys = [(row["recordedAt"], row["boreholeCode"]) for row in rows]
    duplicate_count = len(keys) - len(set(keys))
    invalid = sum(
        1 for row in rows
        if any(not math.isfinite(float(row[field])) for field in VALUE_FIELDS)
        or not (0 <= row["methanePct"] <= 100)
        or row["negativePressureKPa"] < 0
        or row["mixedFlowM3Min"] < 0
    )
    by_well = defaultdict(list)
    for row in rows:
        by_well[row["boreholeCode"]].append(row)
    gap_counts = {}
    for well, records in by_well.items():
        times = []
        for row in records:
            try:
                times.append(datetime.fromisoformat(row["recordedAt"].replace("Z", "+00:00")).timestamp())
            except (ValueError, TypeError):
                continue
        gaps = [b - a for a, b in zip(times, times[1:]) if b >= a]
        if len(gaps) > 2:
            typical = statistics.median(gaps)
            gap_counts[well] = sum(1 for gap in gaps if gap > max(typical * 3, 60))
        else:
            gap_counts[well] = 0
    gaps = sum(gap_counts.values())
    warnings = sum(1 for row in rows if row["qualityFlag"] != "good")
    score = max(0, round(100 - invalid / len(rows) * 100 - duplicate_count / len(rows) * 100 - warnings / len(rows) * 15 - gaps / len(rows) * 10, 1))
    return {
        "recordCount": len(rows), "wellCount": len(well_counts),
        "byWell": dict(well_counts), "bySource": dict(source_counts),
        "warningRecords": warnings, "duplicateKeys": duplicate_count,
        "invalidRecords": invalid, "largeGaps": gaps,
        "gapsByWell": dict(gap_counts), "qualityScore": score,
        "latestAt": max(row["recordedAt"] for row in rows),
        "sourceType": "mixed" if len(source_counts) > 1 else next(iter(source_counts)),
        "checks": [
            {"name": "必需监测量及取值范围", "passed": invalid == 0, "detail": f"{invalid}条无效记录"},
            {"name": "时间戳与钻孔键唯一性", "passed": duplicate_count == 0, "detail": f"{duplicate_count}个重复键"},
            {"name": "采集连续性", "passed": gaps == 0, "detail": f"{gaps}处大间隔，按每孔历史中位间隔×3筛查"},
            {"name": "数据质量标记", "passed": warnings == 0, "detail": f"{warnings}条告警标记"},
        ],
        "scoreNote": "原型质量指数，仅按完整性、重复、间隔与质量标记计算，不等同于矿方验收指标。",
    }


def _median(values: list[float]) -> float:
    return float(statistics.median(values))


def _trend_forecast(values: list[float], horizon: int) -> tuple[list[float], float]:
    arr = np.asarray(values, dtype=float)
    if len(arr) < 12:
        raise ValueError("每个钻孔至少需要12条历史记录才能运行趋势基线。")
    diffs = np.diff(arr[-min(len(arr), 40):])
    center = float(np.median(diffs)) if len(diffs) else 0.0
    mad = float(np.median(np.abs(diffs - center))) if len(diffs) else 0.0
    cap = max(3.5 * 1.4826 * mad, abs(center) * 2, 1e-9)
    slope = float(np.clip(center, -cap, cap))
    anchor = _median(list(arr[-5:]))
    residuals = []
    start = max(10, len(arr) - 30)
    for i in range(start, len(arr)):
        prior = arr[max(0, i - 12):i]
        if len(prior) >= 8:
            local = float(np.median(np.diff(prior[-min(12, len(prior)):])) if len(prior) >= 3 else 0.0)
            estimate = float(np.median(prior[-3:])) + local * 0.65
            residuals.append(float(arr[i] - estimate))
    error = float(np.sqrt(np.mean(np.square(residuals)))) if residuals else float(np.std(np.diff(arr)) or 0.0)
    forecast = [anchor + slope * 0.65 * sum(0.82 ** step for step in range(k)) for k in range(1, horizon + 1)]
    return forecast, max(error, 1e-6)


def forecast_well(borehole: str = "W1", horizon: int = 6, samples: int = 120) -> dict:
    if borehole not in {f"W{i}" for i in range(1, 6)}:
        raise ValueError("钻孔编号必须为W1–W5。")
    horizon = int(np.clip(horizon, 1, 12))
    rows = _history(int(np.clip(samples, 12, 500)), borehole)
    if len(rows) < 12:
        return {"ok": False, "boreholeCode": borehole, "historyCount": len(rows), "requiredCount": 12, "message": "历史数据不足，请先导入或积累至少12条记录。"}
    time_values = []
    for row in rows:
        try:
            time_values.append(datetime.fromisoformat(row["recordedAt"].replace("Z", "+00:00")).timestamp())
        except (ValueError, TypeError):
            continue
    intervals = [b - a for a, b in zip(time_values, time_values[1:]) if b > a]
    sample_seconds = float(statistics.median(intervals)) if intervals else 3.0
    specifications = {
        "negativePressureKPa": {"label": "负压", "unit": "kPa", "minimum": 0, "maximum": 95, "demoThresholds": [15, 33]},
        "methanePct": {"label": "甲烷浓度", "unit": "%", "minimum": 0, "maximum": 100, "demoThresholds": [60, 100]},
        "mixedFlowM3Min": {"label": "混合流量", "unit": "m³/min", "minimum": 0, "maximum": None, "demoThresholds": [2, None]},
        "pureFlowM3Min": {"label": "纯流量", "unit": "m³/min", "minimum": 0, "maximum": None, "demoThresholds": [None, None]},
    }
    variables = {}
    for field, meta in specifications.items():
        values = [float(row[field]) for row in rows]
        prediction, error = _trend_forecast(values, horizon)
        lower, upper = [], []
        for step, value in enumerate(prediction, start=1):
            spread = 1.96 * error * math.sqrt(step)
            v = min(max(value, meta["minimum"]), meta["maximum"] if meta["maximum"] is not None else max(value + spread, 1.0))
            prediction[step - 1] = v
            lower.append(max(meta["minimum"], v - spread))
            upper.append(min(meta["maximum"], v + spread) if meta["maximum"] is not None else v + spread)
        variables[field] = {
            **meta, "current": values[-1], "forecast": prediction,
            "lowerBand": lower, "upperBand": upper, "rollingRmse": error,
        }
    return {
        "ok": True, "boreholeCode": borehole, "historyCount": len(rows),
        "horizon": horizon, "sampleIntervalSeconds": sample_seconds,
        "forecastTimes": [round(sample_seconds * step, 1) for step in range(1, horizon + 1)],
        "variables": variables,
        "model": "稳健中位数趋势基线 + 滚动留出误差区间",
        "validation": "以最近历史点逐点滚动留出估计误差；非独立矿井验证集。",
        "sourceType": rows[-1]["sourceType"],
        "disclaimer": "用于原型短期趋势提示，不是经现场验证的瓦斯风险预警模型。阈值为演示参考。",
    }


def detect_anomalies(samples: int = 120) -> dict:
    rows = _history(int(np.clip(samples, 12, 500)))
    by_well: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_well[row["boreholeCode"]].append(row)
    checks = {
        "negativePressureKPa": ("负压", "kPa", 0.0, 95.0, (15.0, 33.0)),
        "methanePct": ("甲烷浓度", "%", 0.0, 100.0, (60.0, 100.0)),
        "mixedFlowM3Min": ("混合流量", "m³/min", 0.0, None, (2.0, None)),
        "pureFlowM3Min": ("纯流量", "m³/min", 0.0, None, (None, None)),
    }
    findings = []
    monitored = 0
    for well, series in by_well.items():
        if not series:
            continue
        row = series[-1]
        baseline = series[-min(len(series), 60):-1]
        for field, (label, unit, low, high, display_range) in checks.items():
            value = float(row[field])
            monitored += 1
            reason = None
            severity = "warning"
            if value < low or (high is not None and value > high):
                reason, severity = "传感器物理取值范围检查", "critical"
            elif display_range[0] is not None and value < display_range[0]:
                reason = "低于演示筛查阈值，需人工复核"
            elif display_range[1] is not None and value > display_range[1]:
                reason = "高于演示筛查阈值，需人工复核"
            elif len(baseline) >= 10:
                history_values = [float(x[field]) for x in baseline]
                med = _median(history_values)
                mad = _median([abs(x - med) for x in history_values])
                scale = max(1.4826 * mad, float(np.std(history_values)) * 0.25, 1e-6)
                robust_z = abs(value - med) / scale
                if robust_z >= 4.5:
                    reason = f"相对最近{len(baseline)}条滚动基线偏离，稳健Z={robust_z:.1f}"
            if reason:
                findings.append({
                    "id": f"{well}:{row['recordedAt']}:{field}", "boreholeCode": well,
                    "recordedAt": row["recordedAt"], "field": field, "label": label,
                    "value": value, "unit": unit, "severity": severity, "reason": reason,
                    "sourceType": row["sourceType"],
                })
        expected_pure = float(row["mixedFlowM3Min"]) * float(row["methanePct"]) / 100.0
        error = abs(expected_pure - float(row["pureFlowM3Min"]))
        if expected_pure > 0.05 and error / expected_pure > 0.35:
            findings.append({
                "id": f"{well}:{row['recordedAt']}:flow_consistency", "boreholeCode": well,
                "recordedAt": row["recordedAt"], "field": "pureFlowM3Min", "label": "流量一致性",
                "value": round(error / expected_pure, 3), "unit": "相对偏差", "severity": "warning",
                "reason": "纯流量与混合流量×甲烷浓度估算值偏差较大，检查传感器与标定。",
                "sourceType": row["sourceType"],
            })
    severity_rank = {"critical": 0, "warning": 1}
    findings.sort(key=lambda item: (severity_rank.get(item["severity"], 2), item["recordedAt"]), reverse=False)
    return {
        "sourceType": "mixed" if any(row["sourceType"] != "simulator" for row in rows) else "simulator",
        "windowRecords": len(rows), "monitoredPoints": monitored,
        "anomalyCount": len(findings), "findings": findings[:100],
        "method": "演示物理边界 + 滚动中位数/MAD稳健偏离 + 流量一致性规则",
        "disclaimer": "规则与统计基线结果仅供人工复核；报警阈值尚未按矿区规程标定，不构成正式安全预警。",
    }


def generate_safe_candidates(
    pressures_pa: list[float], lifecycle_stage: str, borehole_count: int,
    inclination_deg: float, spacing_m: float, length_m: float,
    pressure_min: float, pressure_max: float, methane_min: float,
    flow_min: float, min_fit_pct: float,
) -> dict:
    if len(pressures_pa) != 5 or any(not math.isfinite(float(v)) or float(v) <= 0 for v in pressures_pa):
        raise ValueError("请提供5个大于0的目标压力。")
    if pressure_min < 0 or pressure_max > 95 or pressure_min >= pressure_max:
        raise ValueError("负压演示边界需满足0≤下限<上限≤95 kPa。")
    if not 0 <= methane_min <= 100 or flow_min < 0:
        raise ValueError("浓度或流量边界无效。")

    site_rows = _history(20)
    latest = {}
    for row in site_rows:
        latest[row["boreholeCode"]] = row
    site_ok = bool(latest) and all(
        float(row["methanePct"]) >= methane_min and float(row["mixedFlowM3Min"]) >= flow_min
        for row in latest.values()
    )
    variants = [
        {"name": "紧凑布置", "boreholeCount": max(1, int(borehole_count)), "inclinationDeg": max(10.0, float(inclination_deg) - 5), "spacingM": max(15.0, float(spacing_m) - 5), "lengthM": max(60.0, float(length_m) - 20)},
        {"name": "基准布置", "boreholeCount": int(borehole_count), "inclinationDeg": float(inclination_deg), "spacingM": float(spacing_m), "lengthM": float(length_m)},
        {"name": "扩展布置", "boreholeCount": min(9, int(borehole_count) + 2), "inclinationDeg": min(35.0, float(inclination_deg) + 5), "spacingM": min(40.0, float(spacing_m) + 5), "lengthM": min(200.0, float(length_m) + 20)},
    ]
    candidates = []
    for index, variant in enumerate(variants):
        scheme = recommend_scheme(
            [float(v) for v in pressures_pa], swarm_size=12, max_iter=6,
            seed=20261015 + index, lifecycle_stage=lifecycle_stage,
            borehole_count=variant["boreholeCount"], inclination_deg=variant["inclinationDeg"],
            spacing_m=variant["spacingM"], length_m=variant["lengthM"],
        )
        checks = [
            {"name": "候选孔负压范围", "passed": all(pressure_min <= b["extractionPressureKPa"] <= pressure_max for b in scheme["boreholes"]), "detail": f"{pressure_min:g}–{pressure_max:g} kPa"},
            {"name": "钻孔倾角边界", "passed": 10 <= variant["inclinationDeg"] <= 35, "detail": f"{variant['inclinationDeg']:g}°；演示边界10–35°"},
            {"name": "孔间距边界", "passed": 15 <= variant["spacingM"] <= 40, "detail": f"{variant['spacingM']:g} m；演示边界15–40 m"},
            {"name": "钻孔长度边界", "passed": 60 <= variant["lengthM"] <= 200, "detail": f"{variant['lengthM']:g} m；演示边界60–200 m"},
            {"name": "压力拟合门槛", "passed": scheme["metrics"]["fitScorePct"] >= min_fit_pct, "detail": f"{scheme['metrics']['fitScorePct']:.2f}%；演示门槛≥{min_fit_pct:g}%"},
            {"name": "当前抽采状态门槛", "passed": site_ok, "detail": "基于最新监测的浓度/流量演示边界" if latest else "无可用监测状态"},
        ]
        scheme["candidateName"] = variant["name"]
        scheme["safetyChecks"] = checks
        scheme["feasible"] = all(check["passed"] for check in checks)
        scheme["safetyStatus"] = "满足演示筛查" if scheme["feasible"] else "未通过演示筛查"
        candidates.append(scheme)
    candidates.sort(key=lambda item: (not item["feasible"], item["metrics"]["rmsePa"]))
    return {
        "candidates": candidates,
        "feasibleCount": sum(1 for item in candidates if item["feasible"]),
        "constraints": {"negativePressureKPa": [pressure_min, pressure_max], "methanePctMinimum": methane_min, "mixedFlowM3MinMinimum": flow_min, "minFitScorePct": min_fit_pct},
        "constraintSource": "界面输入的演示边界；上线前需用矿区规程、设计资料和审批版本替换。",
        "modelBoundary": "Attention-LSTM/PSO仅反演压力模型参数；倾角、孔数、间距和长度作为工程候选条件分别展示，并未输入现有LSTM模型预测压力。",
        "siteStatusSource": "simulator" if all(row["sourceType"] == "simulator" for row in latest.values()) else "imported-or-mixed",
    }


def record_review(item_type: str, item_id: str, decision: str, comment: str, item: dict) -> dict:
    if item_type not in {"forecast", "anomaly", "plan"}:
        raise ValueError("复核对象类型无效。")
    if decision not in {"accepted", "rejected", "adjusted"}:
        raise ValueError("复核结论须为采纳、驳回或调整后采纳。")
    return save_shadow_review(item_type, item_id[:128], decision, comment[:1000], item)


def review_history(limit: int = 50) -> dict:
    rows = list_shadow_reviews(int(np.clip(limit, 1, 200)))
    return {"items": rows, "count": len(rows), "mode": "shadow-review-only", "note": "记录人工意见用于后续校准，不触发PLC写回。"}

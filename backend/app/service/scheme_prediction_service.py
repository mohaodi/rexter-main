from __future__ import annotations

import io
import math
import zipfile
import warnings
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

import h5py
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.database.mysql import save_scheme

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)


ASSET_DIR = Path(__file__).resolve().parents[1] / "model_assets" / "scheme_prediction"
KERAS_MODEL_PATH = ASSET_DIR / "optimized_attention_lstm_model.keras"
PLATFORM_CSV_PATH = ASSET_DIR / "platform.csv"

# 标准化器来自用户提供的 scaler_X / scaler_y。
# 将统计量显式保存，避免部署端因 sklearn pickle 版本差异导致反序列化失败。
X_MEAN = np.array([0.78058824, 1.37058824, 25.29411765, 6.16176471, 100.0], dtype=np.float64)
X_SCALE = np.array([0.11274493, 0.73705671, 7.37056711, 3.25276034, 60.55300708], dtype=np.float64)
Y_MEAN = np.array([103517.87378770, 62248.57759731, 45264.76599459, 47044.55116193, 64468.63695972], dtype=np.float64)
Y_SCALE = np.array([6480.22261564, 7438.47828735, 12714.15899693, 17928.78896312, 21512.21650040], dtype=np.float64)

PARAM_NAMES = ["修正系数", "储层瓦斯压力_MPa", "抽采压力_kPa", "渗透率_mD", "开挖距离_m"]
PARAM_RANGES = {
    "修正系数": (0.63, 0.95),
    "储层瓦斯压力_MPa": (0.4, 2.4),
    "抽采压力_kPa": (15.0, 35.0),
    "渗透率_mD": (1.0, 10.0),
    "开挖距离_m": (0.0, 200.0),
}

# 双指数 + BP 残差修正模型参数（来自用户提供的“第五章双指数模型.py / predictor.py”）
Y0 = 3455.54995
A1 = 2202.95501
T1 = 73.74008
A2 = 4113.27628
T2 = 641.08170
FUTURE_DECAY_LENGTH = 220.0
LATE_STAGE_GAIN_MAX = 1.18
LATE_STAGE_GAIN_SCALE = 120.0
RANDOM_SEED = 42


def _sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-x))


def _softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    z = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(z)
    return e / np.sum(e, axis=axis, keepdims=True)


def _lstm_forward_sequence(
    x_seq: np.ndarray,
    kernel: np.ndarray,
    recurrent_kernel: np.ndarray,
    bias: np.ndarray,
    return_sequences: bool,
) -> np.ndarray:
    """Keras LSTM 的推理等价实现。门顺序为 [i, f, c, o]。"""
    x_seq = np.asarray(x_seq, dtype=np.float64)
    units = recurrent_kernel.shape[0]
    h = np.zeros(units, dtype=np.float64)
    c = np.zeros(units, dtype=np.float64)
    outputs = []

    for x_t in x_seq:
        z = x_t @ kernel + h @ recurrent_kernel + bias
        i, f, g, o = np.split(z, 4)
        i = _sigmoid(i)
        f = _sigmoid(f)
        g = np.tanh(g)
        o = _sigmoid(o)
        c = f * c + i * g
        h = o * np.tanh(c)
        outputs.append(h.copy())

    if return_sequences:
        return np.stack(outputs, axis=0)
    return outputs[-1]


def _batch_norm(x: np.ndarray, gamma: np.ndarray, beta: np.ndarray, mean: np.ndarray, var: np.ndarray, epsilon=1e-3):
    return gamma * (x - mean) / np.sqrt(var + epsilon) + beta


class AttentionLSTMForwardModel:
    """
    使用 NumPy 复现用户上传的 Attention-LSTM .keras 模型推理。
    这样部署时不需要 TensorFlow，但使用的仍是原模型权重。
    """

    def __init__(self, model_path: Path = KERAS_MODEL_PATH):
        self.model_path = Path(model_path)
        self.weights = self._load_weights()

    def _load_weights(self) -> Dict[str, np.ndarray]:
        if not self.model_path.exists():
            raise FileNotFoundError(f"方案预测模型不存在: {self.model_path}")

        with zipfile.ZipFile(self.model_path, "r") as zf:
            raw = zf.read("model.weights.h5")

        with h5py.File(io.BytesIO(raw), "r") as h5:
            def arr(path):
                return np.asarray(h5[path], dtype=np.float64)

            return {
                "lstm1_k": arr(r"_layer_checkpoint_dependencies\lstm\cell/vars/0"),
                "lstm1_r": arr(r"_layer_checkpoint_dependencies\lstm\cell/vars/1"),
                "lstm1_b": arr(r"_layer_checkpoint_dependencies\lstm\cell/vars/2"),
                "bn1_g": arr(r"_layer_checkpoint_dependencies\batch_normalization/vars/0"),
                "bn1_b": arr(r"_layer_checkpoint_dependencies\batch_normalization/vars/1"),
                "bn1_m": arr(r"_layer_checkpoint_dependencies\batch_normalization/vars/2"),
                "bn1_v": arr(r"_layer_checkpoint_dependencies\batch_normalization/vars/3"),
                "lstm2_k": arr(r"_layer_checkpoint_dependencies\lstm_2\cell/vars/0"),
                "lstm2_r": arr(r"_layer_checkpoint_dependencies\lstm_2\cell/vars/1"),
                "lstm2_b": arr(r"_layer_checkpoint_dependencies\lstm_2\cell/vars/2"),
                "bn2_g": arr(r"_layer_checkpoint_dependencies\batch_normalization_2/vars/0"),
                "bn2_b": arr(r"_layer_checkpoint_dependencies\batch_normalization_2/vars/1"),
                "bn2_m": arr(r"_layer_checkpoint_dependencies\batch_normalization_2/vars/2"),
                "bn2_v": arr(r"_layer_checkpoint_dependencies\batch_normalization_2/vars/3"),
                "att_k": arr(r"_layer_checkpoint_dependencies\dense/vars/0"),
                "att_b": arr(r"_layer_checkpoint_dependencies\dense/vars/1"),
                "lstm3_k": arr(r"_layer_checkpoint_dependencies\lstm_4\cell/vars/0"),
                "lstm3_r": arr(r"_layer_checkpoint_dependencies\lstm_4\cell/vars/1"),
                "lstm3_b": arr(r"_layer_checkpoint_dependencies\lstm_4\cell/vars/2"),
                "out_k": arr(r"_layer_checkpoint_dependencies\dense_2/vars/0"),
                "out_b": arr(r"_layer_checkpoint_dependencies\dense_2/vars/1"),
            }

    def predict_raw(self, raw_params: List[float]) -> np.ndarray:
        x = np.asarray(raw_params, dtype=np.float64)
        if x.shape != (5,):
            raise ValueError("方案参数必须为5维。")
        x_scaled = (x - X_MEAN) / X_SCALE
        # 原模型 timesteps=3，反演代码将同一组工况复制到3个时间步。
        seq = np.repeat(x_scaled.reshape(1, 5), 3, axis=0)
        w = self.weights

        lstm1 = _lstm_forward_sequence(seq, w["lstm1_k"], w["lstm1_r"], w["lstm1_b"], True)
        bn1 = _batch_norm(lstm1, w["bn1_g"], w["bn1_b"], w["bn1_m"], w["bn1_v"])

        lstm2 = _lstm_forward_sequence(bn1, w["lstm2_k"], w["lstm2_r"], w["lstm2_b"], True)
        bn2 = _batch_norm(lstm2, w["bn2_g"], w["bn2_b"], w["bn2_m"], w["bn2_v"])

        # 注意力分支：Dense(tanh) -> softmax(time) -> 加权和
        att_logits = np.tanh(bn2 @ w["att_k"] + w["att_b"]).reshape(-1)
        att_weights = _softmax(att_logits)
        attention_output = np.sum(bn2 * att_weights.reshape(-1, 1), axis=0)

        # 残差分支使用第一层 BN 的序列作为输入，与原 Keras 图一致。
        lstm_final = _lstm_forward_sequence(bn1, w["lstm3_k"], w["lstm3_r"], w["lstm3_b"], False)
        combined = attention_output + lstm_final
        y_scaled = combined @ w["out_k"] + w["out_b"]
        return y_scaled * Y_SCALE + Y_MEAN


@lru_cache(maxsize=1)
def get_forward_model() -> AttentionLSTMForwardModel:
    return AttentionLSTMForwardModel()


def _parameter_bounds() -> Tuple[np.ndarray, np.ndarray]:
    lb = np.array([0.63, 0.4, 15.0, 1.0, 0.0], dtype=np.float64)
    ub = np.array([0.95, 2.4, 35.0, 10.0, 200.0], dtype=np.float64)
    return lb, ub


def recommend_scheme(
    target_pressures_pa: List[float],
    swarm_size=48,
    max_iter=45,
    seed=42,
    lifecycle_stage: str = "采前",
    borehole_count: int = 3,
    inclination_deg: float = 20.0,
    spacing_m: float = 30.0,
    length_m: float = 120.0,
) -> Dict:
    if len(target_pressures_pa) != 5:
        raise ValueError("必须输入5个钻孔目标压力（Pa）。")
    target = np.asarray(target_pressures_pa, dtype=np.float64)
    if np.any(~np.isfinite(target)) or np.any(target <= 0):
        raise ValueError("五个钻孔压力必须为正数。")

    model = get_forward_model()
    lb, ub = _parameter_bounds()
    rng = np.random.default_rng(seed)
    n = int(np.clip(swarm_size, 12, 120))
    iters = int(np.clip(max_iter, 5, 150))
    dim = 5

    pos = rng.uniform(lb, ub, size=(n, dim))
    vel = rng.uniform(-(ub - lb) * 0.08, (ub - lb) * 0.08, size=(n, dim))

    def score(x):
        pred = model.predict_raw(x)
        # 在输出标准差尺度上计算误差，避免某个钻孔量级主导优化。
        return float(np.mean(((pred - target) / Y_SCALE) ** 2))

    values = np.array([score(x) for x in pos])
    pbest = pos.copy()
    pbest_val = values.copy()
    gidx = int(np.argmin(values))
    gbest = pos[gidx].copy()
    gbest_val = float(values[gidx])

    history = [gbest_val]
    for _ in range(iters):
        r1 = rng.random((n, dim))
        r2 = rng.random((n, dim))
        vel = 0.70 * vel + 1.45 * r1 * (pbest - pos) + 1.55 * r2 * (gbest - pos)
        vel = np.clip(vel, -(ub - lb) * 0.18, (ub - lb) * 0.18)
        pos = np.clip(pos + vel, lb, ub)
        values = np.array([score(x) for x in pos])
        improved = values < pbest_val
        pbest[improved] = pos[improved]
        pbest_val[improved] = values[improved]
        idx = int(np.argmin(pbest_val))
        if float(pbest_val[idx]) < gbest_val:
            gbest_val = float(pbest_val[idx])
            gbest = pbest[idx].copy()
        history.append(gbest_val)

    pred = model.predict_raw(gbest)
    residual = pred - target
    mae = float(np.mean(np.abs(residual)))
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    rel = mae / max(float(np.mean(np.abs(target))), 1.0)
    fit_score = float(np.clip((1.0 - rel) * 100.0, 0.0, 100.0))

    lifecycle_stage = lifecycle_stage if lifecycle_stage in {"采前", "采中", "采后"} else "采前"
    borehole_count = int(np.clip(borehole_count, 1, 9))
    inclination_deg = float(np.clip(inclination_deg, 5.0, 45.0))
    spacing_m = float(np.clip(spacing_m, 10.0, 50.0))
    length_m = float(np.clip(length_m, 40.0, 260.0))
    stage_pressure_factor = {"采前": 1.0, "采中": 1.06, "采后": 0.88}[lifecycle_stage]
    mean_target = float(np.mean(target))
    boreholes = []
    center = (borehole_count - 1) / 2.0
    for index in range(borehole_count):
        lateral = (index - center) * spacing_m
        azimuth = (index - center) * min(10.0, 32.0 / max(borehole_count - 1, 1))
        angle = math.radians(inclination_deg)
        az = math.radians(azimuth)
        horizontal = length_m * math.cos(angle)
        start = {"x": 0.0, "y": round(lateral, 3), "z": 0.0}
        end = {
            "x": round(horizontal * math.cos(az), 3),
            "y": round(lateral + horizontal * math.sin(az), 3),
            "z": round(length_m * math.sin(angle), 3),
        }
        pressure_adjust = 1.0 + 0.035 * abs(index - center)
        boreholes.append({
            "code": f"W{index + 1}",
            "inclinationDeg": round(inclination_deg, 2),
            "azimuthDeg": round(azimuth, 2),
            "spacingM": round(spacing_m, 2),
            "lengthM": round(length_m, 2),
            "extractionPressureKPa": round(float(gbest[2]) * stage_pressure_factor * pressure_adjust, 3),
            "targetPressurePa": round(mean_target * (1.0 + (index - center) * 0.025), 2),
            "start": start,
            "end": end,
        })

    scheme_code = f"S{int(round(inclination_deg))}-{borehole_count}-{int(round(spacing_m))}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    result = {
        "ok": True,
        "model": "EA-LSTM forward surrogate + PSO inverse search + engineering constraint layer",
        "schemeCode": scheme_code,
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lifecycleStage": lifecycle_stage,
        "sourceModel": "增强型 Attention-LSTM（Transformer 仅为对比基线）",
        "status": "candidate",
        "scheme": {
            "correctionCoefficient": float(gbest[0]),
            "reservoirGasPressureMPa": float(gbest[1]),
            "extractionPressureKPa": float(gbest[2]),
            "permeabilityMd": float(gbest[3]),
            "excavationDistanceM": float(gbest[4]),
        },
        "targetPressuresPa": [float(v) for v in target],
        "predictedPressuresPa": [float(v) for v in pred],
        "residualPressuresPa": [float(v) for v in residual],
        "metrics": {
            "maePa": mae,
            "rmsePa": rmse,
            "normalizedObjective": gbest_val,
            "fitScorePct": fit_score,
        },
        "optimizer": {
            "swarmSize": n,
            "maxIter": iters,
            "seed": seed,
            "objectiveHistory": [float(v) for v in history],
        },
        "engineeringConstraints": {
            "inclinationRangeDeg": [5, 45],
            "spacingRangeM": [10, 50],
            "extractionPressureRangeKPa": [15, 35],
            "fractureZoneReferenceM": [10.3, 38.5],
            "recommendedRoofHeightM": 18,
            "safetyCheck": all(15 <= b["extractionPressureKPa"] <= 35 for b in boreholes),
            "note": "倾角、间距和轨迹由工程约束层生成；需用正式 COMSOL 工况与矿区规程复核。",
        },
        "boreholes": boreholes,
    }
    save_scheme(result)
    return result


def forward_scheme(params: List[float]) -> Dict:
    if len(params) != 5:
        raise ValueError("方案参数必须为5维。")
    pred = get_forward_model().predict_raw(params)
    return {
        "ok": True,
        "params": [float(v) for v in params],
        "predictedPressuresPa": [float(v) for v in pred],
    }


def physics_model_exp2(x):
    x = np.asarray(x, dtype=float)
    return A1 * np.exp(-x / T1) + A2 * np.exp(-x / T2) + Y0


def _read_platform_csv() -> pd.DataFrame:
    last = None
    for enc in ["utf-8", "utf-8-sig", "gbk", "gb18030"]:
        try:
            df = pd.read_csv(PLATFORM_CSV_PATH, encoding=enc)
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except Exception as exc:
            last = exc
    raise last


def _features(day_array, physics_pred):
    t = np.asarray(day_array, dtype=float)
    q = np.asarray(physics_pred, dtype=float)
    return np.column_stack([t, t ** 2, np.log(np.maximum(t, 1.0)), q, t / 1500.0, 1.0 / np.sqrt(np.maximum(t, 1.0))])


def _late_gain(days):
    days = np.asarray(days, dtype=float)
    gain = 1.0 + (LATE_STAGE_GAIN_MAX - 1.0) * (1.0 - np.exp(-(days - 1300.0) / LATE_STAGE_GAIN_SCALE))
    gain[days <= 1300] = 1.0
    return gain


@lru_cache(maxsize=1)
def _train_residual_model():
    df = _read_platform_csv()[["天数", "日产气量"]].copy()
    df["天数"] = pd.to_numeric(df["天数"], errors="coerce")
    df["日产气量"] = pd.to_numeric(df["日产气量"], errors="coerce")
    df = df.dropna().sort_values("天数")
    train = df[(df["天数"] >= 100) & (df["天数"] <= 1150)].copy()
    val = df[(df["天数"] >= 1151) & (df["天数"] <= 1300)].copy()
    if len(train) < 50 or len(val) < 20:
        raise ValueError("产能预测训练/验证数据不足。")

    for part in (train, val):
        part["physics"] = physics_model_exp2(part["天数"].values)
        part["residual"] = part["日产气量"] - part["physics"]

    x_train = _features(train["天数"].values, train["physics"].values)
    y_train = train["residual"].values
    x_val = _features(val["天数"].values, val["physics"].values)
    y_val_real = val["日产气量"].values

    candidates = [
        ((8,), 1e-2, 1e-3, 6000),
        ((10,), 8e-3, 1e-3, 6000),
        ((12,), 5e-3, 1e-3, 6000),
        ((12, 6), 3e-3, 8e-4, 6000),
        ((16, 8), 1e-3, 8e-4, 6000),
        ((20, 10), 1e-3, 6e-4, 7000),
    ]
    best = None
    for idx, (hidden, alpha, lr, max_iter) in enumerate(candidates, start=1):
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("mlp", MLPRegressor(
                hidden_layer_sizes=hidden,
                activation="relu",
                solver="adam",
                alpha=alpha,
                learning_rate_init=lr,
                max_iter=max_iter,
                random_state=RANDOM_SEED,
                early_stopping=True,
                validation_fraction=0.15,
                n_iter_no_change=60,
            )),
        ])
        model.fit(x_train, y_train)
        res = model.predict(x_val)
        for mix in np.linspace(0, 1.3, 131):
            pred = val["physics"].values + mix * res
            rmse = float(np.sqrt(mean_squared_error(y_val_real, pred)))
            if best is None or rmse < best[0]:
                best = (rmse, model, float(mix), f"候选BP模型{idx}")
    return best


def predict_productivity(start_day: int, end_day: int, model_type: str = "hybrid") -> Dict:
    start_day = int(start_day)
    end_day = int(end_day)
    model_type = str(model_type).lower()
    if start_day <= 100:
        raise ValueError("预测起始天数必须大于100。")
    if end_day <= start_day:
        raise ValueError("预测终止天数必须大于起始天数。")
    if end_day - start_day > 1200:
        raise ValueError("单次预测区间请控制在1200天以内。")
    if model_type not in {"physical", "hybrid", "compare"}:
        model_type = "hybrid"

    best_rmse, model, best_alpha, best_name = _train_residual_model()
    days = np.arange(start_day, end_day + 1)
    physics = physics_model_exp2(days)
    residual = model.predict(_features(days, physics))
    decay = np.exp(-(days - 1500) / FUTURE_DECAY_LENGTH)
    decay = np.where(days <= 1500, 1.0, decay)
    hybrid = physics + best_alpha * _late_gain(days) * decay * residual
    physics = np.maximum(physics, 0.0)
    hybrid = np.maximum(hybrid, 0.0)
    final_curve = physics if model_type == "physical" else hybrid

    sample_idx = sorted(set([0, len(days) // 4, len(days) // 2, 3 * len(days) // 4, len(days) - 1]))
    table = [{
        "day": int(days[i]),
        "physical": float(physics[i]),
        "hybrid": float(hybrid[i]),
        "final": float(final_curve[i]),
    } for i in sample_idx]

    return {
        "ok": True,
        "modelType": model_type,
        "days": [int(v) for v in days],
        "physicalCurve": [float(v) for v in physics],
        "hybridCurve": [float(v) for v in hybrid],
        "finalCurve": [float(v) for v in final_curve],
        "finalDailyOutput": float(final_curve[-1]),
        "cumulativeOutput": float(np.sum(final_curve)),
        "tableData": table,
        "meta": {
            "physicsModel": "double exponential decline",
            "residualModel": best_name,
            "validationRmse": float(best_rmse),
            "bestAlpha": float(best_alpha),
            "parameters": {"Y0": Y0, "A1": A1, "T1": T1, "A2": A2, "T2": T2},
        },
    }


def model_status() -> Dict:
    return {
        "ok": True,
        "moduleName": "煤系气抽采方案预测与优选",
        "forwardModel": "Attention-LSTM (NumPy inference from uploaded Keras weights)",
        "optimizer": "Particle Swarm Optimization (PSO)",
        "productivityModel": "Double-exponential physical decline + BP residual correction",
        "inputParameters": [
            {"name": "修正系数", "range": [0.63, 0.95], "unit": "-"},
            {"name": "储层瓦斯压力", "range": [0.4, 2.4], "unit": "MPa"},
            {"name": "抽采压力", "range": [15, 35], "unit": "kPa"},
            {"name": "渗透率", "range": [1, 10], "unit": "mD"},
            {"name": "开挖距离", "range": [0, 200], "unit": "m"},
        ],
        "outputs": ["W1压力", "W2压力", "W3压力", "W4压力", "W5压力"],
        "sourceAssets": [
            "optimized_attention_lstm_model.keras",
            "500组数据集.xlsx",
            "平台.csv",
            "用户提供的反演/产能预测脚本",
        ],
    }

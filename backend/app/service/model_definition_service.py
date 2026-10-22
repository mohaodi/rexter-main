from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.service.formula_formatter import (
    expression_to_latex,
    formula_category,
    formula_title,
    parameter_category,
    parameter_title,
    parameter_value_to_latex,
    symbol_latex,
)


BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_SOURCE_DIR = BASE_DIR / "model_source"
MODEL_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_MODEL_ID = "BigDataFixed_120d_AutoInit"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


FORMULA_DESCRIPTIONS: Dict[str, str] = {
    "q0": "由初始甲烷分压与初始空气分压构造的归一化裂隙总压力。",
    "z0": "初始归一化裂隙甲烷分压。",
    "qsafe": "对裂隙总压力采用光滑正值正则，避免 Newton 迭代中出现非物理负压。",
    "zpos": "对甲烷分压采用光滑正值正则。",
    "zsafe": "光滑实现 min(z,q)，用于保证后处理与源项中的甲烷分压不超过总压力。",
    "pf": "由归一化变量 q 重构裂隙总压力。",
    "pf1": "由 zsafe 重构裂隙甲烷分压。",
    "pf2": "裂隙总压力与甲烷分压之差，对应空气分压。",
    "pp": "由归一化基质变量 qp 重构基质甲烷压力。",
    "alpha_f": "裂隙压力—应力耦合系数。",
    "alpha_p": "基质压力—应力耦合系数。",
    "peff": "裂隙压力、基质压力与附加应力组成的有效压力项。",
    "Dt": "考虑时间衰减的扩散系数。",
    "Sx": "由扩散系数和特征裂隙长度确定的基质—裂隙交换系数。",
    "dqpdt": "基质甲烷压力 ODE 的时间演化源项。",
    "ramp_bc": "零初始斜率的边界平滑加载函数。",
    "qbh": "钻孔边界归一化总压力，随抽采负压平滑加载。",
    "qroad": "巷道边界归一化总压力。",
    "zroad": "巷道边界归一化甲烷分压。",
    "Cch4": "裂隙甲烷体积分数。",
    "Cch4_pct": "裂隙甲烷体积分数百分比。",
}


PDE_NAME_MAP = {
    "q": ("裂隙总压力守恒方程", "fracture_total_pressure"),
    "zch4": ("裂隙甲烷分压守恒方程", "fracture_methane_partial_pressure"),
    "qp": ("基质甲烷压力演化方程", "matrix_methane_pressure"),
}


def _source_path(model_id: str) -> Path:
    safe_id = Path(model_id).stem
    candidate = MODEL_SOURCE_DIR / f"{safe_id}.java"
    if not candidate.exists():
        raise FileNotFoundError(f"Unknown model: {model_id}")
    return candidate


def _decode_java(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Java 文件编码无法识别，请保存为 UTF-8 或 GB18030 后重新上传。")


def _safe_stem(filename: str) -> str:
    stem = Path(filename).stem
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", stem).strip("_")
    return safe or "uploaded_model"


def save_uploaded_java(filename: str, data: bytes) -> dict:
    if not filename or not filename.lower().endswith(".java"):
        raise ValueError("仅支持上传 .java 建模文件。")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Java 文件不能超过 5 MB。")

    text = _decode_java(data)
    # We parse source only. Uploaded code is never compiled or executed on the server.
    if "model.param()" not in text and "ModelUtil" not in text and "com.comsol.model" not in text:
        raise ValueError("未检测到 COMSOL Java 建模特征（model.param / ModelUtil / com.comsol.model）。")

    base = _safe_stem(filename)
    digest = hashlib.sha256(data).hexdigest()[:8]
    model_id = base
    target = MODEL_SOURCE_DIR / f"{model_id}.java"

    if target.exists() and target.read_bytes() != data:
        model_id = f"{base}_{digest}"
        target = MODEL_SOURCE_DIR / f"{model_id}.java"

    target.write_text(text, encoding="utf-8")
    definition = parse_definition(model_id)
    return {
        "id": model_id,
        "file_name": target.name,
        "original_file_name": filename,
        "parameter_count": len(definition["parameters"]),
        "formula_count": len(definition["formulas"]),
        "pde_count": len(definition["pde_formulas"]),
        "warnings": definition.get("warnings", []),
    }


def delete_uploaded_model(model_id: str) -> None:
    if model_id == DEFAULT_MODEL_ID:
        raise ValueError("默认模型不能删除。")
    path = _source_path(model_id)
    path.unlink()


def list_models() -> List[dict]:
    models = []
    for path in sorted(MODEL_SOURCE_DIR.glob("*.java"), key=lambda p: (p.stem != DEFAULT_MODEL_ID, p.name.lower())):
        text = path.read_text(encoding="utf-8", errors="ignore")
        label_match = re.search(r'model\.label\("([^"]+)"\)', text)
        class_match = re.search(r"public\s+class\s+([A-Za-z0-9_]+)", text)
        models.append(
            {
                "id": path.stem,
                "name": (label_match.group(1) if label_match else (class_match.group(1) if class_match else path.stem)),
                "file_name": path.name,
                "default": path.stem == DEFAULT_MODEL_ID,
                "uploaded": path.stem != DEFAULT_MODEL_ID,
            }
        )
    return models


def _parse_java_strings(expr: str) -> str:
    literals = re.findall(r'"((?:\\.|[^"\\])*)"', expr)
    if literals:
        return "".join(literals).replace(r'\"', '"')
    return expr.strip()


def _simple_number_with_unit(raw: str) -> Tuple[Optional[float], Optional[str]]:
    m = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\[([^\]]+)\]\s*", raw)
    if m:
        return float(m.group(1)), m.group(2)
    m = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*", raw)
    if m:
        return float(m.group(1)), None
    return None, None


def _parameter_rows(text: str) -> List[dict]:
    rows = []
    for idx, m in enumerate(re.finditer(r'model\.param\(\)\.set\("([^"]+)",\s*"([^"]+)"\);', text)):
        name, raw_value = m.group(1), m.group(2)
        numeric, unit = _simple_number_with_unit(raw_value)
        rows.append(
            {
                "name": name,
                "symbol_latex": symbol_latex(name),
                "title": parameter_title(name),
                "raw_value": raw_value,
                "value_latex": parameter_value_to_latex(raw_value),
                "numeric_value": numeric,
                "unit": unit,
                "category": parameter_category(name),
                "source_order": idx,
            }
        )
    return rows


def _variable_formula_rows(text: str) -> List[dict]:
    rows = []
    pattern = re.compile(
        r'model\.component\("[^"]+"\)\.variable\("[^"]+"\)\.set\(\s*"([^"]+)"\s*,\s*(.*?)\);',
        re.S,
    )
    for idx, m in enumerate(pattern.finditer(text)):
        name = m.group(1)
        raw = _parse_java_strings(m.group(2))
        rows.append(
            {
                "name": name,
                "symbol_latex": symbol_latex(name),
                "title": formula_title(name),
                "raw": raw,
                "latex": rf"{symbol_latex(name)} = {expression_to_latex(raw)}",
                "description": FORMULA_DESCRIPTIONS.get(name, "从上传 Java 模型自动读取的派生变量或后处理关系。"),
                "category": formula_category(name),
                "source_order": idx,
                "conversion": "automatic",
            }
        )
    return rows


def _extract_field_component(text: str, tag: str) -> Optional[str]:
    m = re.search(
        rf'physics\("{re.escape(tag)}"\)\.field\("[^"]+"\)\s*\.component\(new String\[\]\{{"([^"]+)"\}}\)',
        text,
        re.S,
    )
    return m.group(1) if m else None


def _extract_set_string(text: str, tag: str, key: str) -> Optional[str]:
    pattern = re.compile(
        rf'physics\("{re.escape(tag)}"\).*?feature\("gfeq1"\)\.set\(\s*"{re.escape(key)}"\s*,\s*(.*?)\);',
        re.S,
    )
    m = pattern.search(text)
    return _parse_java_strings(m.group(1)) if m else None


def _extract_flux(text: str, tag: str) -> List[str]:
    # Scope the search around the GeneralFormPDE block and its gfeq1 Ga assignment.
    m = re.search(
        rf'physics\("{re.escape(tag)}"\).*?feature\("gfeq1"\)\.set\(\s*"Ga"\s*,\s*new String\[\]\[\]\s*\{{\{{(.*?)\}}\}}\s*\);',
        text,
        re.S,
    )
    if not m:
        return []
    return re.findall(r'"((?:\\.|[^"\\])*)"', m.group(1))


def _semantic_default_pde(variable: str) -> Optional[str]:
    if variable == "q":
        return (
            r"\phi_f\frac{\partial q}{\partial t}"
            r"-\nabla\!\cdot\!\left(\frac{k_f P_{\mathrm{scale}} q_{\mathrm{safe}}}{\mu_g}\nabla q\right)"
            r"=S_x\left(q_p-z_{\mathrm{safe}}\right)"
        )
    if variable == "zch4":
        return (
            r"\phi_f\frac{\partial z_{\mathrm{CH_4}}}{\partial t}"
            r"-\nabla\!\cdot\!\left(\frac{k_f P_{\mathrm{scale}} z_{\mathrm{safe}}}{\mu_g}\nabla q"
            r"+D_{\mathrm{art}}\nabla z_{\mathrm{CH_4}}\right)"
            r"=S_x\left(q_p-z_{\mathrm{safe}}\right)"
        )
    if variable == "qp":
        return r"\frac{\partial q_p}{\partial t}=\dot q_p,\qquad \boldsymbol{\Gamma}=\mathbf{0}"
    return None


def _pde_rows(text: str, model_id: str) -> List[dict]:
    tags = re.findall(r'physics\(\)\.create\("([^"]+)",\s*"GeneralFormPDE"', text)
    rows = []
    for idx, tag in enumerate(tags):
        variable = _extract_field_component(text, tag) or tag
        source = _extract_set_string(text, tag, "f") or "0"
        da = _extract_set_string(text, tag, "da") or "1"
        flux = _extract_flux(text, tag)

        semantic = _semantic_default_pde(variable) if model_id == DEFAULT_MODEL_ID else None
        generic = rf"{expression_to_latex(da)}\frac{{\partial {symbol_latex(variable)}}}{{\partial t}}+\nabla\cdot\boldsymbol{{\Gamma}}={expression_to_latex(source)}"
        title, semantic_name = PDE_NAME_MAP.get(variable, (f"General Form PDE：{variable}", f"general_pde_{tag}"))
        rows.append(
            {
                "name": semantic_name,
                "tag": tag,
                "variable": variable,
                "title": title,
                "latex": semantic or generic,
                "source_raw": source,
                "source_latex": expression_to_latex(source),
                "da_raw": da,
                "da_latex": expression_to_latex(da),
                "flux_raw": flux,
                "flux_latex": [expression_to_latex(v) for v in flux],
                "description": f"从 Java 中 GeneralFormPDE '{tag}' 自动识别；未知模型采用通用守恒形式展示。",
                "category": "控制方程",
                "source_order": idx,
                "conversion": "semantic" if semantic else "automatic-general-pde",
            }
        )
    return rows


def _param_map(params: List[dict]) -> Dict[str, str]:
    return {p["name"]: p["raw_value"] for p in params}


def _raw_float(params: Dict[str, str], key: str, default: float) -> float:
    raw = params.get(key)
    if raw is None:
        return default
    number, _ = _simple_number_with_unit(raw)
    return number if number is not None else default


def _geometry(text: str, params: List[dict]) -> dict:
    pmap = _param_map(params)
    block_match = re.search(r'\.set\("size",\s*new (?:int|double)\[\]\{([^}]+)\}\)', text)
    java_block = [105.0, 40.0, 15.0]
    if block_match:
        try:
            vals = [float(x.strip()) for x in block_match.group(1).split(",")]
            if len(vals) == 3:
                java_block = vals
        except ValueError:
            pass

    rbh = _raw_float(pmap, "rbh", 0.048)
    dbh = _raw_float(pmap, "dbh", 2.0 * rbh)
    spacing = _raw_float(pmap, "Sbh", 5.0)

    loop_match = re.search(r'for\s*\(int\s+i\s*=\s*1;\s*i\s*<=\s*(\d+);', text)
    count = int(loop_match.group(1)) if loop_match else len(re.findall(r'\.create\("cyl[^\"]*",\s*"Cylinder"\)', text))
    count = count or 0

    h_match = re.search(r'feature\(tag\)\.set\("h",\s*([0-9.eE+-]+)\)', text)
    if not h_match:
        h_match = re.search(r'feature\("cyl[^\"]*"\)\.set\("h",\s*([0-9.eE+-]+)\)', text)
    length = float(h_match.group(1)) if h_match else 80.0

    # Default COMSOL code places five cylinders at y=10,15,20,25,30 and z=7.5.
    java_positions = []
    if count:
        center_y = 20.0
        z0 = 7.5
        for i in range(1, count + 1):
            java_positions.append({"index": i, "x": 0.0, "y": center_y + spacing * (i - (count + 1) / 2.0), "z": z0})

    # For web visualization we map COMSOL: X(length)->Three Z, Y(spacing)->Three X, Z(height)->Three Y.
    display_width = java_block[1] if len(java_block) >= 2 else 40.0
    display_height = java_block[2] if len(java_block) >= 3 else 15.0
    display_length = length
    three_positions = [
        {"index": p["index"], "x": (p["index"] - (count + 1) / 2.0) * spacing, "y": 0.0, "z": 0.0}
        for p in java_positions
    ]

    return {
        "java_block_size_m": java_block,
        "display_mapping": {
            "three_x": "钻孔间距/煤层宽度方向",
            "three_y": "煤层高度方向",
            "three_z": "钻孔长度方向（COMSOL X → Three.js Z）",
        },
        "display_box_m": {"x": display_width, "y": display_height, "z": display_length},
        "borehole_count": count,
        "borehole_radius_m": rbh,
        "borehole_diameter_m": dbh,
        "borehole_length_m": length,
        "borehole_spacing_m": spacing,
        "java_positions": java_positions,
        "three_positions": three_positions,
    }


def _solver(text: str) -> dict:
    gas_times = re.search(r'final String\s+gasTimes\s*=\s*"([^"]+)"', text)
    max_step = re.search(r'setTimeControls\([^,]+,\s*"[^"]+",\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*([0-9.eE+-]+)\)', text)
    linear = re.search(r'\.set\("linsolver",\s*"([^"]+)"\)', text)
    damp = re.search(r'\.set\("damp",\s*([0-9.eE+-]+)\)', text)
    maxiter = re.search(r'\.set\("maxiter",\s*(\d+)\)', text)
    return {
        "time_range": gas_times.group(1) if gas_times else "未自动识别",
        "time_unit": "d" if 'set("tunit", "d")' in text else "未自动识别",
        "max_days": 120 if "120" in (gas_times.group(1) if gas_times else "") else None,
        "time_method": "BDF" if 'set("timemethod", "bdf")' in text else "未自动识别",
        "max_step": max_step.group(1) if max_step else "未自动识别",
        "initial_step": max_step.group(2) if max_step else "未自动识别",
        "max_order": int(max_step.group(3)) if max_step else None,
        "relative_tolerance": float(max_step.group(4)) if max_step else None,
        "linear_solver": (linear.group(1).upper() if linear else "未自动识别"),
        "fully_coupled_damping": float(damp.group(1)) if damp else None,
        "fully_coupled_maxiter": int(maxiter.group(1)) if maxiter else None,
    }


def parse_definition(model_id: str = DEFAULT_MODEL_ID) -> dict:
    path = _source_path(model_id)
    text = path.read_text(encoding="utf-8")

    params = _parameter_rows(text)
    formulas = _variable_formula_rows(text)
    pdes = _pde_rows(text, model_id)
    warnings = []
    if not params:
        warnings.append("未识别到 model.param().set(...) 参数。")
    if not formulas:
        warnings.append("未识别到 component(...).variable(...).set(...) 派生公式。")
    if not pdes:
        warnings.append("未识别到 GeneralFormPDE 控制方程；仍可展示已解析参数和变量公式。")

    label_match = re.search(r'model\.label\("([^"]+)"\)', text)
    class_match = re.search(r"public\s+class\s+([A-Za-z0-9_]+)", text)

    return {
        "model": {
            "id": model_id,
            "name": label_match.group(1) if label_match else (class_match.group(1) if class_match else model_id),
            "source_file": path.name,
            "default": model_id == DEFAULT_MODEL_ID,
            "description": "由上传的 COMSOL Java 建模文件静态解析；服务器不会编译或执行上传代码。",
        },
        "parameters": params,
        "formulas": formulas,
        "pde_formulas": pdes,
        "geometry": _geometry(text, params),
        "solver": _solver(text),
        "warnings": warnings,
        "statistics": {
            "parameter_count": len(params),
            "formula_count": len(formulas),
            "pde_count": len(pdes),
            "source_lines": len(text.splitlines()),
        },
    }

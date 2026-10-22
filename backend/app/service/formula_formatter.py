from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


# Human-readable symbol map for the default CBM model and similar uploaded models.
SYMBOL_LATEX = {
    "q": r"q",
    "q0": r"q_0",
    "qp": r"q_p",
    "z0": r"z_0",
    "zch4": r"z_{\mathrm{CH_4}}",
    "qsafe": r"q_{\mathrm{safe}}",
    "zpos": r"z_{+}",
    "zsafe": r"z_{\mathrm{safe}}",
    "pf": r"p_f",
    "pf1": r"p_{f,\mathrm{CH_4}}",
    "pf2": r"p_{f,\mathrm{air}}",
    "pp": r"p_p",
    "pf10": r"p_{f1,0}",
    "pf2_init": r"p_{f2,\mathrm{init}}",
    "Pscale": r"P_{\mathrm{scale}}",
    "Pneg": r"P_{\mathrm{neg}}",
    "Pbh": r"P_{\mathrm{bh}}",
    "Patm": r"P_{\mathrm{atm}}",
    "pmin": r"p_{\min}",
    "qfloor": r"q_{\mathrm{floor}}",
    "epsZ": r"\varepsilon_z",
    "phif": r"\phi_f",
    "phip": r"\phi_p",
    "phi_f0": r"\phi_{f0}",
    "phi_p0": r"\phi_{p0}",
    "kf": r"k_f",
    "kf0": r"k_{f0}",
    "mu_gas": r"\mu_g",
    "Dt": r"D(t)",
    "D0": r"D_0",
    "Dart": r"D_{\mathrm{art}}",
    "lambdaD": r"\lambda_D",
    "Sx": r"S_x",
    "Lfrac": r"L_f",
    "aL": r"a_L",
    "bL": r"b_L",
    "rho_c": r"\rho_c",
    "Rgas": r"R",
    "T0": r"T_0",
    "Vm": r"V_m",
    "alpha_f": r"\alpha_f",
    "alpha_p": r"\alpha_p",
    "Ecoal": r"E_c",
    "Ep": r"E_p",
    "nu1": r"\nu",
    "sigma_a": r"\sigma_a",
    "sigma_top": r"\sigma_{\mathrm{top}}",
    "peff": r"p_{\mathrm{eff}}",
    "epsv": r"\varepsilon_v",
    "tau_bc": r"\tau_{\mathrm{bc}}",
    "ramp_bc": r"R_{\mathrm{bc}}(t)",
    "qbh": r"q_{\mathrm{bh}}",
    "qroad": r"q_{\mathrm{road}}",
    "zroad": r"z_{\mathrm{road}}",
    "Cch4": r"C_{\mathrm{CH_4}}",
    "Cch4_pct": r"C_{\mathrm{CH_4}}^{(\%)}",
    "dqpdt": r"\dot q_p",
    "KY": r"K_Y",
    "Mch4": r"M_{\mathrm{CH_4}}",
    "Mair": r"M_{\mathrm{air}}",
    "Lx": r"L_x",
    "Ly": r"L_y",
    "Lz": r"L_z",
    "road_w": r"w_{\mathrm{road}}",
    "rbh": r"r_{\mathrm{bh}}",
    "dbh": r"d_{\mathrm{bh}}",
    "Sbh": r"S_{\mathrm{bh}}",
}

FORMULA_TITLES = {
    "q0": "初始归一化裂隙总压力",
    "z0": "初始归一化裂隙甲烷分压",
    "qsafe": "裂隙总压力平滑正则",
    "zpos": "甲烷分压正值平滑正则",
    "zsafe": "受限甲烷分压平滑表达式",
    "pf": "裂隙总压力重构",
    "pf1": "裂隙甲烷分压重构",
    "pf2": "裂隙空气分压重构",
    "pp": "基质甲烷压力重构",
    "alpha_f": "裂隙耦合系数",
    "alpha_p": "基质耦合系数",
    "peff": "有效压力",
    "Dt": "时变扩散系数",
    "Sx": "基质—裂隙质量交换系数",
    "dqpdt": "基质甲烷压力演化率",
    "ramp_bc": "边界条件平滑加载函数",
    "qbh": "钻孔归一化总压力边界",
    "qroad": "巷道归一化总压力边界",
    "zroad": "巷道归一化甲烷分压边界",
    "Cch4": "甲烷体积分数",
    "Cch4_pct": "甲烷体积分数百分比",
}

PARAM_TITLES = {
    "Lx": "煤层 X 向尺度参数",
    "Ly": "煤层 Y 向尺度参数",
    "Lz": "煤层厚度",
    "road_w": "巷道宽度",
    "rbh": "钻孔半径",
    "dbh": "钻孔直径",
    "Sbh": "钻孔间距",
    "Ecoal": "煤体杨氏模量",
    "Ep": "颗粒/骨架杨氏模量",
    "nu1": "泊松比",
    "rho_c": "煤体密度",
    "sigma_top": "顶部载荷",
    "aL": "Langmuir 体积常数",
    "bL": "Langmuir 压力常数",
    "phi_f0": "初始裂隙孔隙率",
    "phi_p0": "初始基质孔隙率",
    "kf0": "初始裂隙渗透率",
    "D0": "初始扩散系数",
    "Lfrac": "特征裂隙长度",
    "lambdaD": "扩散衰减系数",
    "mu_gas": "气体动力黏度",
    "Mch4": "甲烷摩尔质量",
    "Mair": "空气摩尔质量",
    "Rgas": "通用气体常数",
    "T0": "温度",
    "Vm": "标准摩尔体积",
    "Patm": "大气压力",
    "pf10": "初始甲烷压力",
    "Pneg": "默认抽采负压",
    "Pbh": "钻孔边界绝对压力",
    "Pscale": "压力归一化尺度",
    "pmin": "最小压力正则项",
    "pf2_init": "初始空气压力",
    "qfloor": "归一化压力下限",
    "epsZ": "甲烷分压平滑正则项",
    "KY": "体积应变相关系数",
    "tau_bc": "边界平滑加载时间",
    "Dart": "甲烷分压方程人工数值扩散",
}

PARAM_CATEGORY = {
    **{k: "几何与钻孔" for k in ["Lx", "Ly", "Lz", "road_w", "rbh", "dbh", "Sbh"]},
    **{k: "力学参数" for k in ["Ecoal", "Ep", "nu1", "rho_c", "sigma_top", "KY"]},
    **{k: "吸附—扩散参数" for k in ["aL", "bL", "phi_f0", "phi_p0", "kf0", "D0", "Lfrac", "lambdaD", "Dart"]},
    **{k: "气体热物性" for k in ["mu_gas", "Mch4", "Mair", "Rgas", "T0", "Vm"]},
    **{k: "压力与边界" for k in ["Patm", "pf10", "Pneg", "Pbh", "Pscale", "pmin", "pf2_init", "qfloor", "epsZ", "tau_bc"]},
}

FORMULA_CATEGORY = {
    **{k: "初始条件与正则化" for k in ["q0", "z0", "qsafe", "zpos", "zsafe"]},
    **{k: "物理量重构" for k in ["pf", "pf1", "pf2", "pp", "Cch4", "Cch4_pct"]},
    **{k: "耦合与传质" for k in ["alpha_f", "alpha_p", "sigma_a", "peff", "Dt", "phif", "phip", "kf", "Sx", "dqpdt"]},
    **{k: "边界条件" for k in ["ramp_bc", "qbh", "qroad", "zroad"]},
}


@dataclass
class Token:
    kind: str
    value: str


TOKEN_RE = re.compile(
    r"\s*(?:(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)|"
    r"(?P<ident>[A-Za-z_][A-Za-z0-9_]*)|"
    r"(?P<op>\^|\+|-|\*|/|\(|\)|,))"
)


def _symbol(name: str) -> str:
    if name in SYMBOL_LATEX:
        return SYMBOL_LATEX[name]
    if "_" in name:
        head, *tail = name.split("_")
        sub = ",".join(tail)
        return rf"{head}_{{\mathrm{{{sub}}}}}"
    # A conservative fallback: retain the source variable name rather than invent semantics.
    return rf"\mathrm{{{name}}}"


def _tokenize(expr: str) -> Optional[List[Token]]:
    tokens: List[Token] = []
    pos = 0
    while pos < len(expr):
        m = TOKEN_RE.match(expr, pos)
        if not m:
            return None
        if m.lastgroup == "number":
            tokens.append(Token("number", m.group("number")))
        elif m.lastgroup == "ident":
            tokens.append(Token("ident", m.group("ident")))
        else:
            tokens.append(Token(m.group("op"), m.group("op")))
        pos = m.end()
    tokens.append(Token("EOF", ""))
    return tokens


class _Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.i = 0

    @property
    def cur(self) -> Token:
        return self.tokens[self.i]

    def eat(self, kind: str) -> Token:
        if self.cur.kind != kind:
            raise ValueError(f"expected {kind}, got {self.cur.kind}")
        tok = self.cur
        self.i += 1
        return tok

    def parse(self) -> str:
        out = self.expr()
        if self.cur.kind != "EOF":
            raise ValueError("trailing token")
        return out

    def expr(self) -> str:
        left = self.term()
        while self.cur.kind in {"+", "-"}:
            op = self.cur.kind
            self.i += 1
            right = self.term()
            left = rf"{left} {op} {right}"
        return left

    def term(self) -> str:
        left = self.power()
        while self.cur.kind in {"*", "/"}:
            op = self.cur.kind
            self.i += 1
            right = self.power()
            if op == "*":
                left = rf"{left}\,{right}"
            else:
                left = rf"\frac{{{left}}}{{{right}}}"
        return left

    def power(self) -> str:
        left = self.unary()
        if self.cur.kind == "^":
            self.i += 1
            right = self.power()
            return rf"{{{left}}}^{{{right}}}"
        return left

    def unary(self) -> str:
        if self.cur.kind in {"+", "-"}:
            op = self.cur.kind
            self.i += 1
            return rf"{op}{self.unary()}"
        return self.primary()

    def primary(self) -> str:
        if self.cur.kind == "number":
            return self.eat("number").value
        if self.cur.kind == "ident":
            name = self.eat("ident").value
            if self.cur.kind == "(":
                self.eat("(")
                args = []
                if self.cur.kind != ")":
                    args.append(self.expr())
                    while self.cur.kind == ",":
                        self.eat(",")
                        args.append(self.expr())
                self.eat(")")
                return self.func(name, args)
            if name == "pi":
                return r"\pi"
            return _symbol(name)
        if self.cur.kind == "(":
            self.eat("(")
            inside = self.expr()
            self.eat(")")
            return rf"\left({inside}\right)"
        raise ValueError(f"unexpected token {self.cur.kind}")

    @staticmethod
    def func(name: str, args: List[str]) -> str:
        if name == "sqrt" and len(args) == 1:
            return rf"\sqrt{{{args[0]}}}"
        if name == "exp" and len(args) == 1:
            return rf"\exp\!\left({args[0]}\right)"
        if name in {"sin", "cos", "tan", "log", "ln"} and len(args) == 1:
            return rf"\{name}\!\left({args[0]}\right)"
        if name == "abs" and len(args) == 1:
            return rf"\left|{args[0]}\right|"
        if name == "d" and len(args) == 2:
            return rf"\frac{{\partial {args[0]}}}{{\partial {args[1]}}}"
        joined = ", ".join(args)
        return rf"\operatorname{{{name}}}\!\left({joined}\right)"


def expression_to_latex(expr: str) -> str:
    """Convert common COMSOL/Java arithmetic expressions to display LaTeX.

    If an uploaded model contains unsupported syntax, the function deliberately falls
    back to a readable monospace-safe representation instead of changing semantics.
    """
    if expr is None:
        return ""
    value = str(expr).strip()
    # COMSOL unit literals such as 0[Pa] are valid in Java strings but not algebraic syntax.
    value = re.sub(r"(?<=\d)\[([^\]]+)\]", "", value)
    tokens = _tokenize(value)
    if not tokens:
        return raw_to_readable(value)
    try:
        return _Parser(tokens).parse()
    except Exception:
        return raw_to_readable(value)


def raw_to_readable(expr: str) -> str:
    out = str(expr)
    # Replace known variables first, longest first, without attempting to reinterpret unknown code.
    for name in sorted(SYMBOL_LATEX, key=len, reverse=True):
        out = re.sub(rf"\b{re.escape(name)}\b", lambda _m, n=name: SYMBOL_LATEX[n], out)
    out = out.replace("*", r"\,")
    out = out.replace("pi", r"\pi")
    return out


def parameter_value_to_latex(raw_value: str) -> str:
    """Make COMSOL parameter strings readable while preserving the original value."""
    text = str(raw_value).strip()
    # e.g. 2.63[GPa] -> 2.63\,\mathrm{GPa}; expressions keep their algebraic delimiters.
    text = re.sub(
        r"([0-9.]+(?:e[+-]?\d+)?)\[([^\]]+)\]",
        lambda m: rf"{m.group(1)}\,\mathrm{{{_unit_latex(m.group(2))}}}",
        text,
        flags=re.I,
    )
    text = text.replace("*", r"\,")
    for name in sorted(SYMBOL_LATEX, key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(name)}\b", lambda _m, n=name: SYMBOL_LATEX[n], text)
    return text


def _unit_latex(unit: str) -> str:
    # Keep unit text faithful; only make common powers typographically nicer.
    unit = unit.replace("^2", "^{2}").replace("^3", "^{3}")
    unit = unit.replace("*", r"\,")
    return unit


def formula_title(name: str) -> str:
    return FORMULA_TITLES.get(name, f"派生变量 {name}")


def parameter_title(name: str) -> str:
    return PARAM_TITLES.get(name, f"模型参数 {name}")


def formula_category(name: str) -> str:
    return FORMULA_CATEGORY.get(name, "其他派生关系")


def parameter_category(name: str) -> str:
    return PARAM_CATEGORY.get(name, "其他模型参数")


def symbol_latex(name: str) -> str:
    return _symbol(name)

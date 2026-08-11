"""Module ① 数据模型与齿厚反算 — 设计书 §4.1.

不依赖 OCCT。提供:
  - GearParams: 工件齿轮参数 (与前端 gearParams 对齐)
  - WorkpieceResult: 计算结果
  - normal_to_transverse (K-1.2): 法向→端面参数转换
  - K-1.11 齿厚: compute_tooth_thickness / back_solve_x_w_from_W_k / back_solve_x_w_from_M

ADR-012 (2026-08-07): K-1.1 渐开线数学已迁至 profile.py (单一权威源);
本模块保留重导出以兼容旧导入路径。
"""

import math
from dataclasses import dataclass, field


# ── K-1.2 端面/法向换算 ────────────────────────────────────────────

def normal_to_transverse(
    m_n: float,
    alpha_n_deg: float,
    beta_deg: float,
) -> tuple[float, float]:
    """K-1.2 法向参数 → 端面参数.

    m_t = m_n / cos(β)
    tan(α_t) = tan(α_n) / cos(β)

    Args:
        m_n: 法向模数 [mm]
        alpha_n_deg: 法向压力角 [°]
        beta_deg: 螺旋角 [°], β≥0 (U7)

    Returns:
        (m_t [mm], alpha_t [°])
    """
    beta = math.radians(beta_deg)
    cos_beta = math.cos(beta)

    if abs(cos_beta) < 1e-15:
        raise ValueError(f"螺旋角 β={beta_deg}° 使 cos(β)≈0，无法计算端面参数")

    m_t = m_n / cos_beta
    tan_alpha_t = math.tan(math.radians(alpha_n_deg)) / cos_beta
    alpha_t_deg = math.degrees(math.atan(tan_alpha_t))

    return (m_t, alpha_t_deg)


# ── K-1.1 渐开线廓形 (端面) — 已迁至 profile.py ─────────────────────
# ADR-012: 权威实现位于 core.workpiece.profile;
# 本模块不再重导出以避免循环导入 (profile 依赖 models 的 GearParams)

# ── K-1.11 齿厚与反算 (纯数学) ───────────────────────────────────────

def compute_tooth_thickness(p: "GearParams") -> float:
    """K-1.11: 计算端面节圆齿厚 s_t.

    支持三种齿厚指定方式:
      - x_w: s_t = π·m_t/2 + 2·x_w·m_n·tan(α_t)
      - W_k: 通过 back_solve_x_w_from_W_k 反推 x_w
      - M: 通过 back_solve_x_w_from_M 反推 x_w

    Args:
        p: 工件齿轮参数

    Returns:
        端面节圆齿厚 s_t [mm]
    """
    m_t, alpha_t_deg = p.to_transverse()
    alpha_t = math.radians(alpha_t_deg)

    if p.tooth_method == "x_w":
        x_w = p.x_w
    elif p.tooth_method == "W_k":
        if p.W_k is None or p.k_teeth is None:
            raise ValueError("tooth_method='W_k' 需要提供 W_k 和 k_teeth")
        x_w = back_solve_x_w_from_W_k(p, p.W_k, p.k_teeth)
    elif p.tooth_method == "M":
        if p.M is None or p.d_p is None:
            raise ValueError("tooth_method='M' 需要提供 M 和 d_p")
        x_w = back_solve_x_w_from_M(p, p.M, p.d_p)
    else:
        raise ValueError(f"未知的齿厚方式: {p.tooth_method}")

    # s_t = π·m_t/2 + 2·x_w·m_n·tan(α_t)
    s_t = math.pi * m_t / 2.0 + 2.0 * x_w * p.m_n * math.tan(alpha_t)
    return s_t


def back_solve_x_w_from_W_k(p: "GearParams", W_k: float, k: int) -> float:
    """K-1.11: 从公法线长度 W_k 反推变位系数 x_w.

    公法线长度:
      W_k = m_n·cos(α_n)·[(k−0.5)·π + z_w·inv(α_t) + 2·x_w·tan(α_n)]

    其中 inv(α) = tan(α) − α.

    Args:
        p: 工件齿轮参数 (不含 x_w)
        W_k: 公法线长度 [mm]
        k: 跨齿数

    Returns:
        变位系数 x_w
    """
    _, alpha_t_deg = p.to_transverse()
    alpha_t = math.radians(alpha_t_deg)
    alpha_n = math.radians(p.alpha_n_deg)

    inv_at = math.tan(alpha_t) - alpha_t

    # W_k = m_n·cos(α_n)·[(k−0.5)·π + z_w·inv(α_t) + 2·x_w·tan(α_n)]
    # ⇒ x_w = (W_k / (m_n·cos(α_n)) − (k−0.5)·π − z_w·inv(α_t)) / (2·tan(α_n))
    base = p.m_n * math.cos(alpha_n)
    term1 = (k - 0.5) * math.pi
    term2 = p.z_w * inv_at
    x_w = (W_k / base - term1 - term2) / (2.0 * math.tan(alpha_n))

    return x_w


def back_solve_x_w_from_M(p: "GearParams", M: float, d_p: float) -> float:
    """K-1.11: 从跨棒距 M 反推变位系数 x_w (端面近似).

    对于直齿轮 (β=0):
      cos(α_M) = d_b / (M − d_p)  (外齿轮, k_io=+1)
      inv(α_M) = inv(α_t) + d_p/(m_n·z_w·cos(α_n)) − π/(2·z_w) + 2·x_w·tan(α_n)/z_w

    Args:
        p: 工件齿轮参数 (不含 x_w)
        M: 跨棒距 [mm]
        d_p: 量棒直径 [mm]

    Returns:
        变位系数 x_w
    """
    m_t, alpha_t_deg = p.to_transverse()
    alpha_t = math.radians(alpha_t_deg)
    alpha_n = math.radians(p.alpha_n_deg)
    d_b = 2.0 * p.base_radius()

    if p.k_io == 1:
        # 外齿轮: M = d_b / cos(α_M) + d_p
        cos_alpha_M = d_b / (M - d_p)
    else:
        # 内齿轮: M = d_b / cos(α_M) − d_p
        cos_alpha_M = d_b / (M + d_p)

    if abs(cos_alpha_M) > 1.0:
        raise ValueError(f"量棒参数不合理: cos(α_M)={cos_alpha_M} 超出 [−1,1]")

    alpha_M = math.acos(cos_alpha_M)
    inv_alpha_M = math.tan(alpha_M) - alpha_M
    inv_alpha_t = math.tan(alpha_t) - alpha_t

    # inv(α_M) = inv(α_t) + d_p/(m_n·z_w·cos(α_n)) − π/(2·z_w) + 2·x_w·tan(α_n)/z_w
    # ⇒ x_w = z_w/(2·tan(α_n)) · [inv(α_M) − inv(α_t) − d_p/(m_n·z_w·cos(α_n)) + π/(2·z_w)]
    term = (
        inv_alpha_M
        - inv_alpha_t
        - d_p / (p.m_n * p.z_w * math.cos(alpha_n))
        + math.pi / (2.0 * p.z_w)
    )
    x_w = p.z_w / (2.0 * math.tan(alpha_n)) * term
    return x_w


# ── 数据模型 ────────────────────────────────────────────────────────

@dataclass
class GearParams:
    """工件齿轮参数 — 与前端 MainPanel.vue gearParams 字段对齐.

    设计书 §3.1 组A 工件参数。
    接口使用 ° (U12)，内核计算时内部转 rad。
    """

    # 必填
    m_n: float          # 法向模数 [mm]
    z_w: int            # 工件齿数
    b_w: float          # 齿宽 [mm]

    # 可默认
    profile_type: str = "involute"  # 齿廓类型
    k_io: int = 1       # 内/外齿轮: +1 外齿, −1 内齿
    beta_w_deg: float = 0.0   # 螺旋角 [°], β≥0 (U7)
    j_w: int = 1        # 旋向: +1 右旋, −1 左旋 (U7)
    alpha_n_deg: float = 20.0  # 法向压力角 [°]
    h_an: float = 1.0   # 齿顶高系数
    c_n: float = 0.25   # 顶隙系数
    rho_f: float = 0.38 # 齿根圆角半径系数 (ρ_f = ρ*_f·m_n)
    rho_tip: float = 0.0  # 齿顶倒圆系数 ρ*_tip (默认 0 = 锐角齿顶; >0 为预留能力, ADR-013 缺口)
    root_fillet: bool = True  # 齿根圆角开关 (默认开; False = 锐齿根, 无圆角段, 走径向回退)

    # 齿厚指定 (三选一, E1)
    tooth_method: str = "x_w"  # "x_w" | "W_k" | "M"

    # 齿厚指定 (三选一, E1)
    tooth_method: str = "x_w"  # "x_w" | "W_k" | "M"
    x_w: float = 0.0    # 变位系数
    W_k: float | None = None   # 公法线长度 [mm]
    k_teeth: int | None = None # 跨齿数
    M: float | None = None     # 跨棒距 [mm]
    d_p: float | None = None   # 量棒直径 [mm]

    def __post_init__(self):
        """校核基本参数合法性."""
        if self.m_n <= 0:
            raise ValueError(f"模数 m_n={self.m_n} 必须 > 0")
        if self.z_w < 1:
            raise ValueError(f"齿数 z_w={self.z_w} 必须 ≥ 1")
        if self.b_w <= 0:
            raise ValueError(f"齿宽 b_w={self.b_w} 必须 > 0")
        if self.k_io not in (1, -1):
            raise ValueError(f"k_io={self.k_io} 必须为 +1(外齿) 或 −1(内齿)")
        if self.j_w not in (1, -1):
            raise ValueError(f"j_w={self.j_w} 必须为 +1(右旋) 或 −1(左旋)")
        if self.beta_w_deg < 0:
            raise ValueError(f"螺旋角 β_w={self.beta_w_deg} 必须 ≥ 0 (U7)")
        if self.tooth_method not in ("x_w", "W_k", "M"):
            raise ValueError(f"齿厚方式 tooth_method='{self.tooth_method}' 无效")
        if self.rho_tip < 0:
            raise ValueError(f"齿顶倒圆系数 ρ*_tip={self.rho_tip} 必须 ≥ 0 (ADR-013 缺口)")

    def to_transverse(self) -> tuple[float, float]:
        """K-1.2 法向→端面参数转换.

        Returns:
            (m_t [mm], alpha_t [°])
        """
        return normal_to_transverse(self.m_n, self.alpha_n_deg, self.beta_w_deg)

    def pitch_radius(self) -> float:
        """分度圆半径 r_pw [mm]."""
        m_t, _ = self.to_transverse()
        return m_t * self.z_w / 2.0

    def base_radius(self) -> float:
        """基圆半径 r_b = r_pw·cos(α_t) [mm]."""
        r_pw = self.pitch_radius()
        _, alpha_t_deg = self.to_transverse()
        return r_pw * math.cos(math.radians(alpha_t_deg))

    def tip_radius(self) -> float:
        """齿顶圆半径 r_a [mm] (标准齿)."""
        r_pw = self.pitch_radius()
        # d_a = m_t*z + 2*h_an*m_n → r_a = r_pw + h_an*m_n
        return r_pw / (self.m_n * self.z_w / 2.0) * self.pitch_radius() + self.h_an * self.m_n
        # 简化: r_a = m_t*z_w/2 + h_an*m_n

    def tip_diameter(self) -> float:
        """齿顶圆直径 d_a [mm]."""
        m_t, _ = self.to_transverse()
        return m_t * self.z_w + 2.0 * self.h_an * self.m_n

    def root_radius(self) -> float:
        """齿根圆半径 r_f [mm] (标准齿)."""
        m_t, _ = self.to_transverse()
        return (m_t * self.z_w - 2.0 * (self.h_an + self.c_n) * self.m_n) / 2.0

    def root_diameter(self) -> float:
        """齿根圆直径 d_f [mm]."""
        m_t, _ = self.to_transverse()
        return m_t * self.z_w - 2.0 * (self.h_an + self.c_n) * self.m_n

    def tip_fillet_radius(self) -> float:
        """齿顶倒圆半径 ρ_tip = ρ*_tip·m_n [mm].

        默认 ρ*_tip=0 → 锐角齿顶 (与现 3D 网格一致)。
        >0 为预留能力 (ADR-013 齿顶倒圆缺口)，未销项不得当已验证公式使用。
        """
        return self.rho_tip * self.m_n


@dataclass
class WorkpieceResult:
    """模块① 工件齿轮计算结果.

    API 响应 (POST /api/workpiece/generate) 的 result 字段。
    """

    d_a: float          # 齿顶圆直径 [mm]
    d_f: float          # 齿根圆直径 [mm]
    r_b: float          # 基圆半径 [mm]
    r_pw: float         # 工件节圆半径 [mm]
    m_t: float          # 端面模数 [mm]
    alpha_t_deg: float  # 端面压力角 [°]
    z_w: int            # 工件齿数

    def to_dict(self) -> dict:
        """序列化为 JSON 字典."""
        return {
            "d_a": self.d_a,
            "d_f": self.d_f,
            "r_b": self.r_b,
            "r_pw": self.r_pw,
            "m_t": self.m_t,
            "alpha_t_deg": self.alpha_t_deg,
            "z_w": self.z_w,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorkpieceResult":
        """从 JSON 字典反序列化."""
        return cls(
            d_a=d["d_a"],
            d_f=d["d_f"],
            r_b=d["r_b"],
            r_pw=d["r_pw"],
            m_t=d["m_t"],
            alpha_t_deg=d["alpha_t_deg"],
            z_w=d["z_w"],
        )

    @classmethod
    def from_gear_params(cls, p: GearParams) -> "WorkpieceResult":
        """从 GearParams 直接计算 (不含齿厚反算).

        Args:
            p: 工件齿轮参数

        Returns:
            WorkpieceResult 含 d_a, d_f, r_b, r_pw, m_t, α_t, z_w
        """
        m_t, alpha_t_deg = p.to_transverse()
        return cls(
            d_a=p.tip_diameter(),
            d_f=p.root_diameter(),
            r_b=p.base_radius(),
            r_pw=p.pitch_radius(),
            m_t=m_t,
            alpha_t_deg=alpha_t_deg,
            z_w=p.z_w,
        )

"""Module ① 数据模型与纯数学齿廓计算 — 设计书 §4.1.

不依赖 OCCT。提供:
  - GearParams: 工件齿轮参数 (与前端 gearParams 对齐)
  - WorkpieceResult: 计算结果
  - normal_to_transverse (K-1.2): 法向→端面参数转换
  - involute_point (K-1.1): 渐开线单点
  - generate_involute_points: 渐开线点集
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


# ── K-1.1 渐开线廓形 (端面) ────────────────────────────────────────

def involute_point(r_b: float, xi: float) -> tuple[float, float]:
    """K-1.1 渐开线单点 (端面).

    x = r_b·(cos ξ + ξ·sin ξ)
    y = r_b·(sin ξ − ξ·cos ξ)

    起点 ξ=0 在基圆上: (r_b, 0).

    Args:
        r_b: 基圆半径 [mm]
        xi: 展角参数 (roll angle) [rad]

    Returns:
        (x, y) 渐开线上点坐标 [mm]
    """
    cos_xi = math.cos(xi)
    sin_xi = math.sin(xi)

    x = r_b * (cos_xi + xi * sin_xi)
    y = r_b * (sin_xi - xi * cos_xi)

    return (x, y)


def involute_radius(r_b: float, xi: float) -> float:
    """渐开线上点的径向距离: r(ξ) = r_b·√(1+ξ²).

    Args:
        r_b: 基圆半径 [mm]
        xi: 展角参数 [rad]

    Returns:
        径向距离 [mm]
    """
    return r_b * math.sqrt(1.0 + xi * xi)


def xi_at_radius(r_b: float, r: float) -> float:
    """已知径向距离 r 反求展角 ξ.

    ξ = √((r/r_b)² − 1)

    Args:
        r_b: 基圆半径 [mm]
        r: 目标径向距离 [mm], r ≥ r_b

    Returns:
        展角 ξ [rad]

    Raises:
        ValueError: r < r_b (点在基圆内，无渐开线)
    """
    if r < r_b - 1e-12:
        raise ValueError(f"r={r} < r_b={r_b}: 基圆内无渐开线")
    if abs(r - r_b) < 1e-12:
        return 0.0
    return math.sqrt((r / r_b) ** 2 - 1.0)


def generate_involute_points(
    r_b: float,
    r_a: float,
    n_points: int,
    r_f: float | None = None,
) -> list[tuple[float, float]]:
    """K-1.1 + K-1.12 生成渐开线齿面点集 (端面).

    从基圆 (或齿根圆，取大者) 到齿顶圆，等间距采样。

    Args:
        r_b: 基圆半径 [mm]
        r_a: 齿顶圆半径 [mm]
        n_points: 采样点数
        r_f: 齿根圆半径 [mm], 可选。若 r_b > r_f 则从 r_b 开始；
              否则从 max(r_f, r_b) 开始 (K-1.12 圆角段不由本函数处理)

    Returns:
        [(x, y), ...] 渐开线点集 (从齿根到齿顶)
    """
    if n_points < 2:
        raise ValueError(f"n_points={n_points} 必须 ≥ 2")

    r_start = max(r_b, r_f) if r_f is not None else r_b

    if r_a <= r_start:
        raise ValueError(f"齿顶圆 r_a={r_a} ≤ 起始半径 r_start={r_start}")

    xi_start = xi_at_radius(r_b, r_start)
    xi_end = xi_at_radius(r_b, r_a)

    points: list[tuple[float, float]] = []
    for i in range(n_points):
        t = i / (n_points - 1)
        xi = xi_start + t * (xi_end - xi_start)
        points.append(involute_point(r_b, xi))

    return points


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

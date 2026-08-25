"""模块② 工艺方案 ProcessPlan — 设计书 K-1.4~K-1.8 纯数学.

由工件参数 + 刀具参数导出安装与运动方案（Σ/a/r_pw/r_pt/传动比 i/同步比），
是离散包络（K-2.9~K-2.13）的输入。不依赖 OCCT。

符号约定：内部 rad / 接口 °（U12）；变量名与设计书一致（w/t，禁 1/2）。
斜齿工件（β_w≠0）产形面（K-2.6 纯滚动共轭）已支持；同步比 ω_t/ω_w = z_w/z_t
恒为滚动项（与螺旋角无关）。轴向进给差动项 s_d（K-1.7，T2 判定表未销项）只影响
模块④ 正向仿真（含进给），不影响产形面/刃形（纯滚动），留待模块④。
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessPlan:
    """安装与运动方案（坐标无关标量）.

    注意区分两个「比」：
      - ``i``           传动比 = −k_io·z_w/z_t（含内外啮合方向，[25] 式(3)；
                        外齿轮为负、内齿轮为正）
      - ``omega_ratio`` 同步比 ω_t/ω_w = z_w/z_t（恒正，滚动啮合 K-1.7）
    """

    sigma_deg: float   # Σ 轴交角 [°]（有符号，U8）
    a: float           # 中心距 [mm]（U9，内齿轮 a = r_pw − r_pt）
    r_pw: float        # 工件节圆半径 [mm]
    r_pt: float        # 刀具节圆半径 [mm]
    i: float           # 传动比（含方向，[25] 式(3)）
    omega_ratio: float  # 同步比 ω_t/ω_w（恒正，K-1.7）
    beta_w_deg: float  # 工件螺旋角 [°]（U7，供 K-0.6 螺旋面构造）
    j_w: int           # 工件旋向系数（+1 右旋 / −1 左旋，U7）


def compute_process_plan(
    *,
    z_w: int,
    z_t: int,
    m_n: float,
    beta_w_deg: float,
    beta_t_deg: float,
    j_w: int,
    j_t: int,
    k_io: int,
) -> ProcessPlan:
    """K-1.4~K-1.8 安装与运动方案.

    Args:
        z_w: 工件齿数
        z_t: 刀具齿数
        m_n: 法向模数 [mm]
        beta_w_deg: 工件螺旋角 [°], β≥0 (U7)
        beta_t_deg: 刀具螺旋角 [°], β≥0 (U7)
        j_w: 工件旋向 (+1 右旋 / −1 左旋；β_w=0 时占位 +1)
        j_t: 刀具旋向 (+1 / −1)
        k_io: 内/外齿轮系数 (+1 外齿 / −1 内齿)

    Returns:
        ProcessPlan

    Raises:
        ValueError: Σ=0、中心距非正、参数非法
    """
    if k_io not in (1, -1):
        raise ValueError(f"k_io={k_io} 必须为 +1(外齿) 或 −1(内齿)")
    if z_w < 1 or z_t < 1:
        raise ValueError("齿数 z_w/z_t 必须 ≥ 1")
    if m_n <= 0:
        raise ValueError(f"模数 m_n={m_n} 必须 > 0")
    if beta_w_deg < 0 or beta_t_deg < 0:
        raise ValueError("螺旋角 β_w/β_t 必须 ≥ 0 (U7)")
    if j_w not in (1, -1) or j_t not in (1, -1):
        raise ValueError("旋向 j_w/j_t 必须为 +1 或 −1")

    beta_w = math.radians(beta_w_deg)
    beta_t = math.radians(beta_t_deg)

    # K-1.4 Σ = j_w·β_w − j_t·β_t（有符号，U8）
    sigma = j_w * beta_w - j_t * beta_t
    if abs(sigma) < 1e-12:
        raise ValueError("Σ=0：刮齿需轴交角提供切削速度分量")

    # 工件节圆半径 r_pw = m_t·z_w/2，m_t = m_n/cosβ_w（β_w=0 → m_t=m_n）
    m_t = m_n / math.cos(beta_w)
    r_pw = m_t * z_w / 2.0

    # K-1.6 刀具节圆半径 r_pt = r_pw·z_t·cosβ_w/(z_w·cosβ_t)（法向模数相等）
    r_pt = r_pw * z_t * math.cos(beta_w) / (z_w * math.cos(beta_t))

    # K-1.5 中心距 a = r_pw + k_io·r_pt（内齿轮 k_io=−1 → 相减）
    a = r_pw + k_io * r_pt
    if a <= 0:
        raise ValueError(f"中心距非正 a={a:.3f}，请调整 z_t/β_t")

    # 传动比 [25] 式(3) i = −k_io·z_w/z_t（含内外啮合方向）
    i = -k_io * z_w / z_t
    # 同步比 K-1.7 ω_t/ω_w = z_w/z_t（滚动项，与 β_w 无关；轴向进给差动项 s_d 仅模块④ 用）
    omega_ratio = z_w / z_t

    return ProcessPlan(
        sigma_deg=math.degrees(sigma),
        a=a,
        r_pw=r_pw,
        r_pt=r_pt,
        i=i,
        omega_ratio=omega_ratio,
        beta_w_deg=beta_w_deg,
        j_w=j_w,
    )

"""模块③ K-3.1 单齿预览 — 闭合实体（B 方案 v2，2026-08-21）.

单齿 = 闭合流形实体（前刀面闭合轮廓扇形前帽 + 闭环 ribbon 后刀面族 + 后帽，截面恒定
螺旋扫掠）。B 方案 v2（用户方案）：开放轮廓（1/2齿根-齿侧-齿顶-齿侧-1/2齿根，
含齿顶弧段共轭）+ 齿距线径向偏置 1/20 分度圆直径 + 谷底圆弧闭合；齿根延伸贴
理论极限圆 r_limit = r_a − a（见 tooth_solid.py）。三件套非实体已被闭合实体替代；
刃形线可视化由独立 /edge 图层承担。不依赖 OCCT。
"""

from core.common.gltf_export import GeometrySpec
from core.envelope.rake import build_plane_rake
from core.envelope.tooth_solid import ROOT_OFFSET_RATIO_DEFAULT, build_single_tooth_solid


def _tooth_meta(solid) -> dict:
    """实体元数据（router 响应 meta 字段，前端规格窗口/调试用）."""
    return {
        "r_limit_mm": solid.loop.r_limit,
        "root_radius_mm": solid.loop.root_radius,
        "root_offset_mm": solid.loop.offset_mm,
        "arch_spread_deg": solid.loop.arch_spread_deg,
        "pitch_z_mm": solid.loop.pitch_z_mm,
        "loop_points": solid.n_loop,
        "n_sections": solid.n_sections,
        "volume_mm3": solid.volume_mm3,
    }


def build_single_tooth(
    profile_pts,
    plan,
    *,
    r_a: float,
    r_f: float | None,
    gamma_0_deg: float,
    beta_t_deg: float,
    z_t: int,
    m_n: float,
    L: float,
    n_L: int,
    k_io: int,
    root_offset_ratio: float = ROOT_OFFSET_RATIO_DEFAULT,
    n_arc: int = 17,
    n_ext: int = 4,
    n_off: int = 4,
    m: int = 181,
    theta_range_deg: float = 40.0,
    normals=None,
    b_w: float = 0.0,
    n_z: int = 21,
) -> tuple[list[GeometrySpec], dict]:
    """单齿闭合实体（坐标 T，layer_id='singleTooth'）.

    斜齿（β_w≠0，2026-08-25 第二批）同构适用（b_w>0 必传，数值求交刃形链；
    闭合环 precut + 螺旋扫掠管线与直齿同构）。

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]（含齿顶弧段）
        plan: ProcessPlan
        r_a: 工件齿顶圆半径 [mm]（理论极限 = r_a − a）
        r_f: 工件齿根圆半径 [mm]（齿顶伪点判据 r_f−a；None 跳过）
        gamma_0_deg: 前角 γ₀ [°]（前刀面）
        beta_t_deg: 刀具螺旋角 β_t [°]（导程 Ltp）
        z_t / m_n: 刀具齿数 / 法向模数 [mm]
        L / n_L: 总重磨量 / 等分数（实体轴向厚度）
        k_io: 内/外齿轮系数（外齿轮 T14 未销项，build_single_tooth_solid 内部 raise）
        root_offset_ratio: 齿根径向偏置 / 分度圆直径（默认 1/20，用户选定）
        n_arc / n_ext / n_off: 谷底圆弧 / 延伸弦直线 / 偏置直线采样
        m / theta_range_deg: 运动离散
        normals: 廓形法矢
        b_w / n_z: 工件齿宽 / 轴向层数（斜齿数值求交链必需；直齿忽略）

    Returns:
        (geos, meta)：geos = [闭合实体 mesh]，meta 见 _tooth_meta
    """
    rake = build_plane_rake(gamma_0_deg, beta_t_deg, plan.r_pt)
    solid = build_single_tooth_solid(
        profile_pts, plan, rake,
        r_a=r_a, beta_t_deg=beta_t_deg, z_t=z_t, m_n=m_n,
        L=L, n_L=n_L, root_offset_ratio=root_offset_ratio,
        n_arc=n_arc, n_ext=n_ext, n_off=n_off,
        m=m, theta_range_deg=theta_range_deg, normals=normals, r_f=r_f,
        b_w=b_w, n_z=n_z,
    )
    geo = GeometrySpec(
        kind="mesh",
        positions=solid.mesh_positions,
        indices=solid.mesh_indices,
        normals=solid.mesh_normals,
        layer_id="singleTooth",
    )
    return [geo], _tooth_meta(solid)

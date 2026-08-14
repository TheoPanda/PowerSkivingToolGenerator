"""模块②c 单齿预览 — 前刀面 + 后刀面 + 刃形三件套非实体（K-3.1 预览级）.

单齿 = 前刀面片 + 后刀面片 + 刃形线三件套叠加（**非闭合流形**，闭合流形实体留模块③）。
三件套均标 layer_id='singleTooth'，前端以硬质合金材质着色。不依赖 OCCT。
"""

from core.common.gltf_export import GeometrySpec
from core.envelope.edge import extract_edge
from core.envelope.flank import generate_flank
from core.envelope.rake import build_plane_rake, plane_patch


def build_single_tooth(
    profile_pts,
    plan,
    *,
    gamma_0_deg: float,
    beta_t_deg: float,
    alpha_0_deg: float,
    L: float,
    n_L: int,
    k_io: int,
    m: int = 181,
    theta_range_deg: float = 20.0,
) -> list[GeometrySpec]:
    """三件套非实体（前刀面片 + 后刀面片 + 刃形线），均标 singleTooth.

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]
        plan: ProcessPlan
        gamma_0_deg: 前角 γ₀ [°]（前刀面）
        beta_t_deg: 刀具螺旋角 β_t [°]（前刀面）
        alpha_0_deg: 后角 α₀ [°]（后刀面重磨方向）
        L / n_L: 总重磨量 / 等分数
        k_io: 内/外齿轮系数

    Returns:
        [GeometrySpec]（前刀面片 + 后刀面片 + 刃形线…，全部 layer_id='singleTooth'）
    """
    # 前刀面片
    rake = build_plane_rake(gamma_0_deg, beta_t_deg, plan.r_pt)
    rake_patch = plane_patch(rake)

    # 刃形（a_0 = a，前刀面刃形 = 前刀面 ∩ 生成面，K-2.8 离散）
    edge = extract_edge(
        profile_pts, plan, rake, m=m, theta_range_deg=theta_range_deg, k_io=k_io
    )
    if not edge.segments:
        raise ValueError("刃形为空（外齿轮前刀面符号 T14 未销项）：请使用内齿轮（k_io=−1）")
    edge_geos = [
        GeometrySpec(kind="line", positions=[c for pt in seg.pts for c in pt])
        for seg in edge.segments
    ]

    # 后刀面片
    flank = generate_flank(
        profile_pts, plan, rake, L=L, n_L=n_L, alpha_0_deg=alpha_0_deg, k_io=k_io,
        m=m, theta_range_deg=theta_range_deg,
    )
    flank_geo = GeometrySpec(
        kind="mesh",
        positions=flank.mesh_positions,
        indices=flank.mesh_indices,
        normals=flank.mesh_normals,
    )

    geos = [rake_patch, flank_geo, *edge_geos]
    for g in geos:
        g.layer_id = "singleTooth"
    return geos

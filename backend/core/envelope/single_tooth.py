"""模块②c 单齿预览 — 前刀面 + 后刀面 + 刃形三件套非实体（K-3.1 预览级）.

单齿 = 前刀面片 + 后刀面片 + 刃形线三件套叠加（**非闭合流形**，闭合流形实体留模块③）。
前刀面片 = 刃形环（前刀面 ∩ 生成面）在前刀面平面上围成的区域（扇形三角剖分），
非全尺寸 plane_patch；后刀面片 = 重磨刃形族三角网；刃形线 = 左右两段。不依赖 OCCT。
"""

from core.common.gltf_export import GeometrySpec
from core.envelope.edge import compute_discrete_edge, split_flank_segments
from core.envelope.flank import generate_flank
from core.envelope.rake import RakeSurface, build_plane_rake


def _rake_face_from_edge(edge_pts, rake: RakeSurface) -> GeometrySpec:
    """前刀面片 = 刃形环围成的平面区域（扇形三角剖分：形心 + 相邻刃形点）.

    刃形点均落在前刀面平面上（F=0），形心亦在其上；扇形三角剖分把闭合刃形环
    铺成前刀面片。法向统一取前刀面法矢 n_rake（doubleSide，绕向无关）。
    """
    n = len(edge_pts)
    if n < 3:
        return GeometrySpec(kind="mesh", positions=[], indices=[], normals=[])
    cx = sum(p[0] for p in edge_pts) / n
    cy = sum(p[1] for p in edge_pts) / n
    cz = sum(p[2] for p in edge_pts) / n
    positions = [cx, cy, cz]
    positions += [v for p in edge_pts for v in p]  # p_0..p_{n-1}
    indices: list[int] = []
    for i in range(n):
        j = (i + 1) % n
        indices += [0, i + 1, j + 1]  # 形心(0) + 相邻刃形点
    normals = list(rake.n_rake) * (n + 1)
    return GeometrySpec(
        kind="mesh", positions=positions, indices=indices, normals=normals,
        layer_id="singleTooth",
    )


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
    rake = build_plane_rake(gamma_0_deg, beta_t_deg, plan.r_pt)

    # 完整刃形环（a_0 = a，前刀面 ∩ 生成面，K-2.8 离散；不拆段）
    edge_pts, _roots, _found = compute_discrete_edge(
        profile_pts, plan, rake, m=m, theta_range_deg=theta_range_deg
    )
    if not edge_pts:
        raise ValueError("刃形为空（外齿轮前刀面符号 T14 未销项）：请使用内齿轮（k_io=−1）")

    # 前刀面片 = 刃形环围成的平面区域
    rake_patch = _rake_face_from_edge(edge_pts, rake)

    # 刃形线（左右两段）
    edge_geos = [
        GeometrySpec(kind="line", positions=[c for pt in seg for c in pt])
        for seg in split_flank_segments(edge_pts, closed=(k_io == -1))
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

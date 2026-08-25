"""模块②b 符号距离工具 — 产形面顶点 → 工件齿槽廓形的符号距离（纯 Python）.

符号语义（2026-08-20 修正）：
  齿槽廓形（tooth_gap_segments）围的是工件齿槽**空隙**，不是材料——
  - 刀齿顶点落入齿槽空隙（多边形内）→ 正常啮合 → d > 0（间隙/安全）
  - 刀齿顶点落入工件材料（多边形外）→ 碰撞 → d < 0（干涉）
  旧实现的符号恰好相反（把齿槽当材料），已修复；测试同步以新语义断言。

静态安装位（φ_t=0）快照的局限：产形面是桶形包络，正确设计在静态位也有大片
区域落在最终材料内（那是「待切削」的名义余量，不是碰撞）。判别真实干涉须沿
啮合周期扫掠取**最深侵入**（worst-case）——见 swept_interference_colors：
每顶点以自身接触角 φ_t* 为中心扫掠 ±60°，且只在「点进入工件齿宽范围」的
相位计入（W 系 |z| ≤ b_w/2），物理上不接触的桶形悬伸段归为参考灰。

距离计算用点到线段投影（非到顶点），精度高。为何不逐点 OCCT：BRepClass3d +
BRepExtrema 每点 ~0.5s，2625 顶点要 ~20 分钟。
"""

import math

import numpy as np


def _point_in_polygon(poly: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """2D 射线法 point-in-polygon（向量化），返回 bool 数组（pts 是否在 poly 内）."""
    x, y = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), dtype=bool)
    n = len(poly)
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[(i + 1) % n]
        cross = (yi > y) != (yj > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (xj - xi) * (y - yi) / (yj - yi) + xi
        inside ^= cross & (x < xint)
    return inside


def _nearest_distance(pts: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """点到多边形各**边**的最近欧氏距离（2D），用于有符号距离的绝对值部分.

    逐边投影求点到线段距离（不是到顶点），精度远优于旧顶点距离。
    """
    n = len(poly)
    d = np.full(len(pts), np.inf)
    for j in range(n):
        a = poly[j]
        b = poly[(j + 1) % n]
        ab = b - a
        ab_sq = ab[0] ** 2 + ab[1] ** 2
        if ab_sq < 1e-24:
            continue
        # 点 p 到线段 ab 的投影参数 t ∈ [0,1]
        ap = pts - a  # (N, 2)
        t = (ap[:, 0] * ab[0] + ap[:, 1] * ab[1]) / ab_sq
        t = np.clip(t, 0.0, 1.0)
        # 线段上最近点
        qx = a[0] + t * ab[0]
        qy = a[1] + t * ab[1]
        dd = (pts[:, 0] - qx) ** 2 + (pts[:, 1] - qy) ** 2
        d = np.minimum(d, dd)
    return np.sqrt(d)


def signed_distance_full_ring(pts_w: np.ndarray, poly: np.ndarray, z_w: int) -> np.ndarray:
    """全周向符号距离：点 vs 完整内齿轮（z_w 齿 + z_w 槽），内齿轮几何语义.

    工件是完整内齿轮（齿从环坯内缘切入）：材料 = 齿带 r∈[r_a,r_f] 内的齿体
    角窗 + r≥r_f 的实心环坯；r<r_a 为通孔自由区（刀具合法通过）。

    实现要点（2026-08-20 推导）：
    ① 角向：点旋转 k·齿距角不改变「角度残差 mod 齿距」，故对每个点只需把其
       角度解析折叠到基准齿距胞（θ ← θ − round((θ−θ_c)/pitch)·pitch）后做一次
       单槽判定——在带内与「对全部 z_w 个槽求最大」完全等价，且快 z_w 倍。
    ② 径向：r < r_a（多边形顶点最小半径）为通孔自由区 → 符号翻正（间隙）；
       r > r_f 单槽判定天然为负（实心环坯 = 真干涉）✓。

    Returns:
        符号距离 (N,)：≥0 = 间隙量（自由区/齿槽内），<0 = 侵入材料深度
    """
    theta = np.arctan2(pts_w[:, 1], pts_w[:, 0])
    poly_r = np.hypot(poly[:, 0], poly[:, 1])
    r_lo = float(poly_r.min())
    theta_c = float(np.arctan2(poly[:, 1].sum(), poly[:, 0].sum()))  # 基准槽方位
    pitch = 2.0 * math.pi / z_w

    # 解析折叠：把点转到基准齿距胞（残差不变，仅重定位）
    k = np.round((theta - theta_c) / pitch)
    fold = -k * pitch
    c, s = np.cos(fold), np.sin(fold)
    x = pts_w[:, 0] * c - pts_w[:, 1] * s
    y = pts_w[:, 0] * s + pts_w[:, 1] * c
    folded = np.stack([x, y], axis=1)

    d_abs = _nearest_distance(folded, poly)
    inside = _point_in_polygon(poly, folded)
    d = np.where(inside, d_abs, -d_abs)
    # 通孔自由区（r < r_a）：内齿轮内孔，刀具合法空间 → 间隙
    r = np.hypot(pts_w[:, 0], pts_w[:, 1])
    d = np.where(r < r_lo, d_abs, d)
    return d


def interference_color(d: np.ndarray, clamp: float) -> np.ndarray:
    """符号距离 → 工程干涉色阶 RGB (N,3) ∈ [0,1].

    与旧「红白蓝」发散色阶的差异（2026-08-20 改良动机）：
    - 白色接触带在受光表面不可辨识 → 改为**绿**（工程「通过/GO」色，与红对立）
    - 红↔蓝非自然对立色对 → 红（干涉）/绿（贴合）/蓝（远离）三段语义明确
    - 过渡区窄（|t|≤0.2 橙黄临界带），大部分区域快速到纯色——一眼分辨
      「有没有干涉」，而不是「渐变到哪了」

    分段（t = d/clamp 截断 [-1,1]）：
      t ≤ −1        深红 (0.86, 0.08, 0.08)   干涉饱和
      −1 < t < −0.2 红→橙过渡                  干涉深度
      |t| ≤ 0.2     橙黄 (1.0, 0.75, 0.0)↔绿   临界/接触带
      0.2 < t < 1   黄→绿→蓝过渡               间隙渐远
      t ≥ 1         蓝 (0.12, 0.25, 0.75)      大间隙
    """
    t = np.clip(d / clamp, -1.0, 1.0)
    r = np.empty_like(t)
    g = np.empty_like(t)
    b = np.empty_like(t)

    # 干涉侧（t<0）：t=−0.2 橙 (1.0,0.55,0.0) → t=−1 深红 (0.86,0.08,0.08)
    interfer = t < 0
    k = np.clip(-t[interfer] / 1.0, 0.0, 1.0) * 0.8  # 0(轻)→0.8(重)
    r[interfer] = 1.0 - 0.14 * k
    g[interfer] = 0.55 - 0.47 * k
    b[interfer] = 0.0 + 0.08 * k

    # 临界带（0 ≤ t ≤ 0.2）：t=0 绿 (0.10,0.80,0.15) → t=0.2 橙黄 (1.0,0.75,0.0)
    band = ~interfer & (t <= 0.2)
    k2 = np.clip(t[band] / 0.2, 0.0, 1.0)
    r[band] = 0.10 + 0.90 * k2
    g[band] = 0.80 - 0.05 * k2
    b[band] = 0.15 - 0.15 * k2

    # 间隙侧（t>0.2）：t=0.2 橙黄 → t≈0.5 绿 (0.15,0.75,0.20) → t=1 蓝 (0.12,0.25,0.75)
    clear = t > 0.2
    k3 = np.clip((t[clear] - 0.2) / 0.8, 0.0, 1.0)
    first = k3 < 0.375
    r[clear] = np.where(first, 1.0 - 0.85 * (k3 / 0.375), 0.15 - 0.03 * ((k3 - 0.375) / 0.625))
    g[clear] = np.where(first, 0.75, 0.75 - 0.50 * ((k3 - 0.375) / 0.625))
    b[clear] = np.where(first, 0.20 * (k3 / 0.375), 0.20 + 0.55 * ((k3 - 0.375) / 0.625))

    return np.stack([r, g, b], axis=1)


def neutral_gray_color(n: int) -> np.ndarray:
    """中性灰 RGB (n,3)——齿宽外参考段（不参与干涉判读，仅保持齿轮外形完整）."""
    col = np.empty((n, 3), dtype=np.float64)
    col[:, 0] = 0.62
    col[:, 1] = 0.62
    col[:, 2] = 0.66
    return col


def swept_interference_colors(
    positions: list[float],
    contact_phi: list[float],
    plan,
    poly: np.ndarray,
    *,
    b_w: float,
    z_w: int,
    clamp_mm: float = 0.5,
    n_sweep: int = 25,
) -> tuple[list[float], dict]:
    """扫掠最坏位干涉着色：每顶点沿自身接触窗取最深侵入 → 工程色阶.

    对每个顶点：以该点接触角 φ_t* 为中心扫掠 ±60°（覆盖接触窗 + 余量；实测
    接触位 ∈ ±26°）。每相位经 tool_to_workpiece_chain 变换到 W 系——链分解为
    逐元素旋转（Rot_z(φ_t) → 静态安装 → Rot_z(−φ_w) → 螺旋回扭 θ(z)），全部
    numpy 向量化，无 4×4 matmul（遵循 transforms.py 崩溃规避纪律）。

    符号距离用**全周向**判定（signed_distance_full_ring）：工件是 z_w 齿/槽
    完整内齿轮，点在某相位落入任一齿槽为间隙、落入任一齿体为干涉。

    只在「点进入工件齿宽范围」（W 系 |z| ≤ b_w/2）的相位计入符号距离——轴向
    在工件外的桶形悬伸段物理上不可能干涉，从不啮合的顶点归为参考灰。

    Args:
        positions: 顶点扁平坐标 [x,y,z,...]（T 系；建议单齿槽基准几何，阵列份复制色）
        contact_phi: 各顶点接触角 φ_t [rad]（无接触信息的补面点可传 0）
        plan: ProcessPlan（a/sigma/omega_ratio/beta_w/j_w/r_pw）
        poly: 工件齿槽廓形 (n,2)（W 系端面，单齿槽）
        b_w: 工件齿宽 [mm]（轴向啮合区判据）
        z_w: 工件齿数（全周向齿槽折叠判定）
        clamp_mm: 色阶饱和距离 [mm]
        n_sweep: 每顶点扫掠相位数（强制奇数，含中心相位）

    Returns:
        (colors_flat, stats)——colors 为 RGB 扁平数组 [r,g,b,...]；
        stats = {n_interference, n_contact_band, n_clearance, n_reference, min_d_mm}
    """
    from core.common.transforms import apply_transform_batch, install_transform

    n_vert = len(positions) // 3
    if n_sweep % 2 == 0:
        n_sweep += 1
    sigma = math.radians(plan.sigma_deg)
    beta_w = math.radians(plan.beta_w_deg)
    tan_bw = math.tan(beta_w)

    # 静态安装矩阵（F_t → F_w，常量，每相位共用）
    M_fw_ft = install_transform(plan.a, sigma, 0.0)

    pts = np.array(positions, dtype=np.float64).reshape(n_vert, 3)
    phis_star = np.asarray(
        contact_phi[:n_vert] if len(contact_phi) >= n_vert else np.zeros(n_vert),
        dtype=np.float64,
    )

    # 扫掠相位偏移：±60°（接触窗实测 ±26°，留余量）
    sweep_half = math.pi / 3.0
    offsets = np.linspace(-sweep_half, sweep_half, n_sweep)

    d_worst = np.full(n_vert, np.inf)   # 最深侵入（最负符号距离）
    engaged_any = np.zeros(n_vert, dtype=bool)  # 是否有相位进入工件齿宽

    for off in offsets:
        ph_t = phis_star + off
        ph_w = ph_t / plan.omega_ratio
        c_t, s_t = np.cos(ph_t), np.sin(ph_t)
        # ① Rot_z(φ_t)（逐元素）
        x1 = pts[:, 0] * c_t - pts[:, 1] * s_t
        y1 = pts[:, 0] * s_t + pts[:, 1] * c_t
        z1 = pts[:, 2]
        # ② 静态安装（批量 4×4）
        q = apply_transform_batch(M_fw_ft, np.vstack([x1, y1, z1, np.ones(n_vert)]))
        # ③ Rot_z(−φ_w)（逐元素）
        c_w, s_w = np.cos(ph_w), np.sin(ph_w)
        x3 = q[0] * c_w + q[1] * s_w
        y3 = -q[0] * s_w + q[1] * c_w
        z3 = q[2]
        # ④ 螺旋回扭 θ(z) = j_w·z·tanβ_w/r_pw（β_w=0 时恒 0）
        if abs(beta_w) > 1e-15:
            th = plan.j_w * z3 * tan_bw / plan.r_pw
            c_r, s_r = np.cos(th), np.sin(th)
            xw = x3 * c_r + y3 * s_r
            yw = -x3 * s_r + y3 * c_r
        else:
            xw, yw = x3, y3
        # ⑤ 轴向啮合区判据：W 系 |z| ≤ b_w/2 才计入
        engaged = np.abs(z3) <= b_w / 2.0
        engaged_any |= engaged
        d = signed_distance_full_ring(np.stack([xw, yw], axis=1), poly, z_w)
        d_masked = np.where(engaged, d, np.inf)
        d_worst = np.minimum(d_worst, d_masked)

    # 从未进入工件齿宽 → 参考灰；其余按最坏位着色
    in_band = engaged_any & np.isfinite(d_worst)
    d_plot = np.where(in_band, d_worst, 0.0)
    colors = interference_color(d_plot, clamp_mm)
    colors[~in_band] = neutral_gray_color(int((~in_band).sum()))

    band_lo, band_hi = -0.2 * clamp_mm, 0.2 * clamp_mm
    stats = {
        "n_interference": int((in_band & (d_worst < band_lo)).sum()),
        "n_contact_band": int((in_band & (d_worst >= band_lo) & (d_worst <= band_hi)).sum()),
        "n_clearance": int((in_band & (d_worst > band_hi)).sum()),
        "n_reference": int((~in_band).sum()),
        "min_d_mm": float(d_worst[in_band].min()) if in_band.any() else 0.0,
        # 图例权威数据（前端渐变条按 stops 直出，避免复制色阶公式）：
        # stops 采样 t = d/clamp ∈ {−1,−0.5,−0.2,0,+0.2,+0.5,+1}；ticks 为关键刻度 [mm]；
        # reference_color = 齿宽外参考灰。
        "legend": {
            "stops": _legend_stops(clamp_mm),
            "ticks_mm": [
                round(-clamp_mm, 4), round(-0.2 * clamp_mm, 4), 0.0,
                round(0.2 * clamp_mm, 4), round(clamp_mm, 4),
            ],
            "reference_color": [0.62, 0.62, 0.66],
        },
    }
    return [float(c) for c in colors.ravel()], stats


def _legend_stops(clamp_mm: float) -> list[dict]:
    """图例渐变采样点：t 归一位置 [0,1]（−clamp→+clamp）+ interference_color 采样色."""
    ts = np.array([-1.0, -0.5, -0.2, 0.0, 0.2, 0.5, 1.0])
    cols = interference_color(ts * clamp_mm, clamp_mm)
    return [
        {
            "t": (float(tv) + 1.0) / 2.0,  # −1..1 → 0..1（渐变条位置）
            "color": [round(float(c), 4) for c in cols[i]],
        }
        for i, tv in enumerate(ts)
    ]

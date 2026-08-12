"""内齿轮齿廓修正目视验证 — 渲染 2D 轮廓 PNG (全貌 + 单齿放大)."""
import math
import sys

sys.path.insert(0, "E:/Works/Claude_Code/PowerSkivingToolGenerator/backend")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.workpiece.models import GearParams
from core.workpiece.profile import sample_profile_points

p = GearParams(m_n=3.0, z_w=40, b_w=20.0, k_io=-1)
pts = sample_profile_points(p)
xs = [q[0] for q in pts] + [pts[0][0]]
ys = [q[1] for q in pts] + [pts[0][1]]
r_a, r_f = p.tip_radius(), p.root_radius()
r_rim = p.effective_rim_diameter() / 2

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
t = [i / 200 * 2 * math.pi for i in range(201)]
for ax in (ax1, ax2):
    ax.plot(xs, ys, "b-", lw=1.0)
    for r, c, lbl in ((r_a, "g", "d_a(tip)"), (r_f, "r", "d_f(root)"), (r_rim, "0.5", "d_rim")):
        ax.plot([r * math.cos(a) for a in t], [r * math.sin(a) for a in t], "--", color=c, lw=0.6, label=lbl)
    ax.set_aspect("equal")
    ax.legend(fontsize=7)
ax1.set_title("internal gear k_io=-1 (m=3, z=40) full")
ax2.set_xlim(r_a - 2, r_f + 3)
ax2.set_ylim(-12, 12)
ax2.set_title("teeth zoom")
out = "E:/Works/Claude_Code/PowerSkivingToolGenerator/.scratch/internal-gear/fixed_inner_gears.png"
fig.savefig(out, dpi=110)
print("saved", out)

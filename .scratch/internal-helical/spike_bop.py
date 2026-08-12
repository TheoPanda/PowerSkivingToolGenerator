"""Internal HELICAL gear: Boolean Cut construction strategy spike probe.

Read-only OCCT experiment. Tests two ways of building an internal ring gear via BOP
Cut, focusing on the coincident-face risk (gap-solid tip arc EXACTLY on preform bore).

Construction A (direct): Cut(preform_annulus, compound_of_gap_solids)
Construction B (fallback): Cut(full_cyl_rim, [bore_cyl + gap_solids])

Reference gear: GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, x_w=0.0)
  r_a = 80, r_f = 84.5, r_rim = 86.5
"""
import math
import sys
import time

sys.path.insert(0, "E:/Works/Claude_Code/PowerSkivingToolGenerator/backend")

from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_Transform,
)
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.GC import GC_MakeCircle, GC_MakeArcOfCircle
from OCP.gp import gp_Circ, gp_Ax2, gp_Pnt, gp_Dir, gp_Vec, gp_Trsf, gp_Ax1
from OCP.TopAbs import TopAbs_REVERSED, TopAbs_SOLID, TopAbs_FACE, TopAbs_VERTEX, TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.BRep import BRep_Tool
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Builder

# ---------------------------------------------------------------------------
# gear params
# ---------------------------------------------------------------------------
m_n = 2.0
z_w = 82
b_w = 20.0
r_a = 80.0
r_f = 84.5
r_rim = 86.5
beta_deg = 15.0


def volume(s):
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(s, props)
    return props.Mass()


def check_valid(shape, tag):
    ana = BRepCheck_Analyzer(shape)
    ok = ana.IsValid()
    avg = 0.0
    try:
        avg = volume(shape)
    except Exception:
        avg = None
    if not ok:
        print(f"    [{tag}] INVALID (BRepCheck)" )
    return ok, avg


def count_solids(shape):
    n = 0
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    while exp.More():
        n += 1
        exp.Next()
    return n


def vertex_radius_range(shape):
    mn, mx = 1e18, -1e18
    exp = TopExp_Explorer(shape, TopAbs_VERTEX)
    while exp.More():
        v = TopoDS.Vertex_s(exp.Current())
        p = BRep_Tool.Pnt_s(v)
        r = math.hypot(p.X(), p.Y())
        if r < mn:
            mn = r
        if r > mx:
            mx = r
        exp.Next()
    return mn, mx


def circle_arc_wire(cx, cy, radius, a0, a1):
    """Arc wire centered (cx,cy) radius from angle a0 to a1 (rad)."""
    circ = gp_Circ(gp_Ax2(gp_Pnt(cx, cy, 0.0), gp_Dir(0.0, 0.0, 1.0)), radius)
    arc = GC_MakeArcOfCircle(circ, a0, a1, True)
    return BRepBuilderAPI_MakeEdge(arc.Value()).Edge()


def radial_line(cx, cy, radius, ang):
    # segment from bore r_a to `radius` at angle `ang` (outward)
    return BRepBuilderAPI_MakeEdge(
        gp_Pnt(cx + r_a * math.cos(ang), cy + r_a * math.sin(ang), 0.0),
        gp_Pnt(cx + radius * math.cos(ang), cy + radius * math.sin(ang), 0.0),
    ).Edge()


def build_wedge_wire(gap_half_angle_rad, center_ang):
    """Wedge spanning [center-hal, center+hal] in [r_a, r_f]. One gap solid proxy."""
    a0 = center_ang - gap_half_angle_rad
    a1 = center_ang + gap_half_angle_rad
    w = BRepBuilderAPI_MakeWire()
    # outer arc at r_f from a0->a1 (CCW thin arc)
    w.Add(circle_arc_wire(0.0, 0.0, r_f, a0, a1))
    # radial line at a1 from r_a up to r_f
    w.Add(radial_line(0.0, 0.0, r_f, a1))
    # inner arc at r_a: thin CCW arc a0->a1, reversed so wire loops back
    inv = circle_arc_wire(0.0, 0.0, r_a, a0, a1)
    w.Add(TopoDS.Edge_s(inv.Reversed()))
    # radial line at a0 from r_f back down to r_a
    w.Add(radial_line(0.0, 0.0, r_f, a0))
    return w.Wire()


def build_wedge_solid(gap_half_angle_rad, center_ang):
    wire = build_wedge_wire(gap_half_angle_rad, center_ang)
    f = BRepBuilderAPI_MakeFace(wire)
    if not f.IsDone():
        raise RuntimeError("wedge face not done")
    face = f.Face()
    if face.Orientation() == TopAbs_REVERSED:
        face = face.Reversed()
    prism = BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 0.0, b_w))
    if not prism.IsDone():
        raise RuntimeError("wedge prism not done")
    return prism.Shape()


def rotate_z(shape, ang):
    trsf = gp_Trsf()
    trsf.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), ang)
    return BRepBuilderAPI_Transform(shape, trsf, False).Shape()


def make_compound(shapes):
    comp = TopoDS_Compound()
    bd = TopoDS_Builder()
    bd.MakeCompound(comp)
    for s in shapes:
        bd.Add(comp, s)
    return comp


def print_result(tag, shape, expected_vol, timing):
    if shape.IsNull():
        print(f"  [{tag}] NULL SHAPE t={timing:.1f}s")
        return False, 0.0, 0
    ok, vol = check_valid(shape, tag)
    n = count_solids(shape)
    if vol is not None:
        d = vol - expected_vol
        rel = d / expected_vol * 100
        vstr = f"vol={vol:.4f} exp={expected_vol:.4f} d={d:+.5f} ({rel:+.4f}%)"
    else:
        vstr = "vol=ERR"
    print(f"  [{tag}] valid={ok} #solids={n} {vstr} t={timing:.1f}s")
    return ok, (vol if vol is not None else 0.0), n


def run_cut(base, tools, tag):
    t0 = time.time()
    cut = BRepAlgoAPI_Cut(base, tools)
    cut.Build()
    shape = cut.Shape()
    dt = time.time() - t0
    # collect BOP warning / error messages
    msgs = []
    try:
        from OCP.Standard import Standard_SStream
    except Exception:
        msgs = []
    return shape, dt


# ---------------------------------------------------------------------------
# (1) preform annulus
# ---------------------------------------------------------------------------
print("=" * 70)
print("(1) PREFORM ANNULUS")
outer = BRepBuilderAPI_MakeWire()
outer.Add(BRepBuilderAPI_MakeEdge(GC_MakeCircle(gp_Circ(
    gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_rim)).Value()).Edge())
inner = BRepBuilderAPI_MakeWire()
inner.Add(BRepBuilderAPI_MakeEdge(GC_MakeCircle(gp_Circ(
    gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_a)).Value()).Edge())

pf_face = BRepBuilderAPI_MakeFace(outer.Wire())
inner_w = inner.Wire().Reversed()
pf_face.Add(TopoDS.Wire_s(inner_w))
if not pf_face.IsDone():
    print("  preform face failed")
else:
    pf_face_shape = pf_face.Face()
    preform = BRepPrimAPI_MakePrism(pf_face_shape, gp_Vec(0, 0, b_w)).Shape()
    exp_vol_preform = math.pi * (r_rim ** 2 - r_a ** 2) * b_w
    ok, vol = check_valid(preform, "preform")
    print(f"  preform valid={ok} vol={vol:.4f} exp={exp_vol_preform:.4f} "
          f"(d={vol-exp_vol_preform:+.4f})")

# ---------------------------------------------------------------------------
# (2) single straight wedge proxy
# ---------------------------------------------------------------------------
print("=" * 70)
print("(2) SINGLE STRAIGHT WEDGE PROXY")
# gap width representative: real tooth-space angular half-width at r_f for z=82
# space width ~ p/2 = (π·m_t)/2 ; half-angle in [r_a,r_f] region
gap_half = 0.5 * (math.pi * m_n) / (2.0 * r_f)  # half space width (approx) in rad
print(f"  gap_half_angle={gap_half:.6f} rad")
wedge = build_wedge_solid(gap_half, 0.0)
exp_wedge_vol = volume(wedge)
ok, v = check_valid(wedge, "wedge")
print(f"  wedge valid={ok} vol={exp_wedge_vol:.4f} (analytic~{0.5*(r_f**2-r_a**2)*gap_half*2*b_w:.4f})")

# ---------------------------------------------------------------------------
# (3) Cut A direct single
# ---------------------------------------------------------------------------
print("=" * 70)
print("(3) CUT A DIRECT (annulus - single wedge)")
t0 = time.time()
shapeA1, dt = run_cut(preform, wedge, "A1")
print_result("A-direct-single", shapeA1, exp_vol_preform - exp_wedge_vol, dt)
cut_a1_null = shapeA1.IsNull()
print(f"  A1 IsNull={cut_a1_null}")

# ---------------------------------------------------------------------------
# (4) Cut A full compound 82 wedges
# ---------------------------------------------------------------------------
print("=" * 70)
print("(4) CUT A FULL COMPOUND (82 wedges)")
t0 = time.time()
wedges = []
for i in range(z_w):
    wedges.append(rotate_z(wedge, i * 2 * math.pi / z_w))
compound_A = make_compound(wedges)
print(f"  compound built in {time.time()-t0:.1f}s, #elems={len(wedges)}")
shapeA2, dt = run_cut(preform, compound_A, "A2")
exp_A2 = exp_vol_preform - 82 * exp_wedge_vol
print_result("A-compound-82", shapeA2, exp_A2, dt)

# ---------------------------------------------------------------------------
# (5) twisted wedge via ThruSections, then Cut A with twist
# ---------------------------------------------------------------------------
print("=" * 70)
print("(5) TWIST (ThruSections) BETA=15 deg")
r_pw = 164.0 / 2.0  # since beta=0 m_t=m_n ; for twist use r_pw
theta_z = lambda z: z * math.tan(math.radians(beta_deg)) / r_pw
n_slices = 6
ts = BRepOffsetAPI_ThruSections(True, True, 0.001)  # Solid=True, ruled=False
for iz in range(n_slices + 1):
    z = iz * b_w / n_slices
    rot = theta_z(z)
    wire_plane = build_wedge_wire(gap_half, 0.0)
    if rot != 0.0:
        # rotate about Z and translate to z
        trsf = gp_Trsf()
        trsf.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), rot)
        trsf2 = gp_Trsf()
        trsf2.SetTranslation(gp_Vec(0, 0, z))
        tmp = BRepBuilderAPI_Transform(wire_plane, trsf, True).Shape()
        tmp = BRepBuilderAPI_Transform(tmp, trsf2, True).Shape()
        ts.AddWire(TopoDS.Wire_s(tmp))
    else:
        ts.AddWire(wire_plane)
ts.Build()
print(f"  ThruSections IsDone={ts.IsDone()}")
if ts.IsDone():
    tw_shape = ts.Shape()
    ok_tw, v_tw = check_valid(tw_shape, "twisted-wedge")
    print(f"  twisted wedge valid={ok_tw} vol={v_tw and f'{v_tw:.4f}'} "
          f"(straight={exp_wedge_vol:.4f})")
    shapeA3, dt = run_cut(preform, tw_shape, "A3")
    print_result("A-direct-twisted-1", shapeA3, exp_vol_preform - v_tw, dt)

    # helical mechanism: rotate the SAME twisted wedge about Z into n tool slots
    n_tw = 4
    tw_wedges = [rotate_z(tw_shape, i * 2 * math.pi / z_w) for i in range(n_tw)]
    comp_tw = make_compound(tw_wedges)
    ts_b = time.time()
    shapeA4, dt4 = run_cut(preform, comp_tw, "A4")
    print_result(f"A-direct-twisted-{n_tw}", shapeA4,
                 exp_vol_preform - n_tw * v_tw, dt4)
else:
    print("  ThruSections FAILED; skipping twist cut")

# ---------------------------------------------------------------------------
# (6) Cut B fallback: full cylinder - (bore cyl + wedges)
# ---------------------------------------------------------------------------
print("=" * 70)
print("(6) CUT B FALLBACK (full cyl - bore_cyl - wedges)")
full_cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_rim, b_w).Shape()
bore_cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_a, b_w).Shape()

tools_B_comp = [bore_cyl] + wedges
tools_B = make_compound(tools_B_comp)

exp_full_cyl = math.pi * r_rim ** 2 * b_w
exp_B = exp_full_cyl - math.pi * r_a ** 2 * b_w - 82 * exp_wedge_vol

shapeB1, dt = run_cut(full_cyl, wedge, "B-single")
print_result("B-single-wedge", shapeB1, exp_full_cyl - exp_wedge_vol, dt)

shapeB2, dt = run_cut(full_cyl, tools_B, "B-compound-82")
print_result("B-compound-82", shapeB2, exp_B, dt)

# ---------------------------------------------------------------------------
# (7) vertex radius range of best result
# ---------------------------------------------------------------------------
print("=" * 70)
print("(7) VERTEX RADIUS RANGE")
for name, shape in (("A-compound-82", shapeA2), ("B-compound-82", shapeB2)):
    mn, mx = vertex_radius_range(shape)
    print(f"  {name}: min_r={mn:.4f} max_r={mx:.4f}  (expect min<=80, max~86.5)")
print("DONE")

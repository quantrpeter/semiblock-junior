"""SemiBlock Junior - stage-1 mechanical part library.

Every builder returns a PartDef (one or more coloured bodies) in the part's own
frame. Conventions: hole axes along Z, beams along +X starting at hole 0,
pins along Z, TwistLock parts have the knob side at z = 0 (the beam face) and
go down -Z. Electronics housings live in modules.py.
"""
import math

from params import *  # noqa: F401,F403
from sbcad import (Body, PartDef, V, box, cone_between, cross_prism, cyl_between, edges_at_z,
                   engrave, frame, prism_xy, revolve_rz, ring, rotated,
                   rounded_box, rounded_rect_prism, sector, stadium_xy, try_fillet, zcyl)
import Part


# =============================================================== helpers
def _hole_cutters(x, y, z0, z1, counterbore=True):
    t = [zcyl(HOLE_D / 2, z0 - 1, z1 + 1, x, y)]
    if counterbore:
        t += [zcyl(CB_D / 2, z1 - CB_DEPTH, z1 + 1, x, y), zcyl(CB_D / 2, z0 - 1, z0 + CB_DEPTH, x, y)]
    return t


def _axle_hole(x, y, z0, z1):
    return cross_prism(AXLE_HOLE_D, AXLE_HOLE_SPLINE, z0 - 1, z1 + 1, x, y)


def _soften(body, z0, z1, r=0.35):
    return try_fillet(body, r, edges_at_z(body, z0) + edges_at_z(body, z1))


def _bar(p0, p1, z0, z1, r=BEAM_W / 2):
    """Stadium bar between two XY points."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    s = stadium_xy(length, r, z0, z1)
    return frame(s, (dx / length, dy / length, 0), (-dy / length, dx / length, 0), (p0[0], p0[1], 0))


def _union(shapes):
    s = shapes[0]
    if len(shapes) > 1:
        s = s.fuse(shapes[1:])
    return s.removeSplitter()


def _pin_half(z_root, z_tip, lip=True, bore=True, slit=True):
    """One half of a Technic-style pin from z_root to z_tip (either direction)."""
    sgn = 1 if z_tip > z_root else -1
    r, rl = QP_D / 2, QP_LIP_D / 2
    L = abs(z_tip - z_root)

    def z(d):
        return z_root + sgn * d
    if lip:
        prof = [(0, z(0)), (r, z(0)), (r, z(L - QP_LIP_T - 0.2)), (rl, z(L - QP_LIP_T)),
                (rl, z(L - 0.25)), (r - 0.2, z(L)), (0, z(L))]
    else:
        prof = [(0, z(0)), (r, z(0)), (r, z(L - 0.3)), (r - 0.3, z(L)), (0, z(L))]
    if sgn < 0:
        prof = list(reversed(prof))
    p = revolve_rz(prof)
    tools = []
    if bore:
        tools.append(zcyl(QP_ID / 2, min(z(0.6), z(L + 1)), max(z(0.6), z(L + 1))))
    if slit:
        za, zb = sorted((z(L - QP_SLIT_L), z(L + 1)))
        tools.append(box(-3, -QP_SLIT_W / 2, za, 3, QP_SLIT_W / 2, zb))
    return p.cut(tools) if tools else p


def _collar(z=0.0):
    return zcyl(QP_COLLAR_D / 2, z - QP_COLLAR_T / 2, z + QP_COLLAR_T / 2)


def _axle_end(z_root, z_tip):
    """Cross axle stub with a chamfered tip."""
    R, ch = AXLE_D / 2, 0.3
    a, b = sorted((z_root, z_tip))
    c = cross_prism(AXLE_D, AXLE_SPLINE, a, b)
    if z_tip > z_root:
        env = revolve_rz([(0, a), (R, a), (R, b - ch), (R - ch, b), (0, b)])
    else:
        env = revolve_rz([(0, a), (R - ch, a), (R, a + ch), (R, b), (0, b)])
    return c.common(env)


# =============================================================== structure
def beam_shape(n, thickness=BEAM_T, axle_holes=(), counterbore=True, ticks=True, label=True, label_size=4.2):
    """Straight 1 x n beam. Extras vs. Technic: hole ticks on both edges
    (long tick every 5th hole) and the length engraved near hole 1."""
    r = BEAM_W / 2
    z0, z1 = -thickness / 2, thickness / 2
    body = _soften(stadium_xy((n - 1) * PITCH, r, z0, z1), z0, z1)
    tools = []
    for i in range(n):
        x = i * PITCH
        if i in axle_holes or (i - n) in axle_holes:
            tools.append(_axle_hole(x, 0, z0, z1))
        else:
            tools += _hole_cutters(x, 0, z0, z1, counterbore)
        if ticks:
            h = min(4.4 if (i + 1) % 5 == 0 else 1.6, thickness - 1.4)
            tools.append(box(x - 0.3, r - 0.28, -h / 2, x + 0.3, r + 0.5, h / 2))
            tools.append(box(x - 0.3, -r - 0.5, -h / 2, x + 0.3, -r + 0.28, h / 2))
    if label and n >= 2:
        tools.append(engrave(str(n), label_size, 0.25, (PITCH / 2, r, 0), (-1, 0, 0), (0, 0, 1)))
        tools.append(engrave(str(n), label_size, 0.25, (PITCH / 2, -r, 0), (1, 0, 0), (0, 0, 1)))
    return body.cut(tools)


def beam(n, mat="sb_blue"):
    return PartDef("SB-B%02d" % n, "Beam 1x%d" % n, [Body("beam", beam_shape(n), mat)], {"family": "Beams"})


def crank_beam(mat="sb_lgrey"):
    return PartDef("SB-B02X", "Beam 1x2 (pin + axle hole)",
                   [Body("beam", beam_shape(2, axle_holes=(1,), label=False), mat)], {"family": "Beams"})


def thin_beam(n, mat="sb_yellow"):
    t = PITCH / 2 - GAP
    body = beam_shape(n, thickness=t, axle_holes=(0, -1), counterbore=False, label=True, label_size=2.8)
    return PartDef("SB-H%02d" % n, "Thin beam 1x%d (half thickness)" % n, [Body("beam", body, mat)],
                   {"family": "Beams"})


def lbeam(na=5, nb=3, mat="sb_yellow"):
    z0, z1 = -BEAM_T / 2, BEAM_T / 2
    body = _soften(_union([_bar((0, 0), ((na - 1) * PITCH, 0), z0, z1), _bar((0, 0), (0, (nb - 1) * PITCH), z0, z1)]), z0, z1)
    tools = []
    for i in range(na):
        tools += _hole_cutters(i * PITCH, 0, z0, z1)
    for j in range(1, nb):
        tools += _hole_cutters(0, j * PITCH, z0, z1)
    return PartDef("SB-L%d%d" % (nb, na), "L-beam %dx%d" % (nb, na), [Body("lbeam", body.cut(tools), mat)],
                   {"family": "Beams"})


def bent_beam(na=4, nb=6, angle=53.13, mat="sb_white"):
    """1 x 9 bent beam. 53.13 deg (3-4-5 triangle) keeps the far end on the grid."""
    z0, z1 = -BEAM_T / 2, BEAM_T / 2
    a = math.radians(angle)
    pb = ((na - 1) * PITCH, 0.0)
    pc = (pb[0] + (nb - 1) * PITCH * math.cos(a), (nb - 1) * PITCH * math.sin(a))
    body = _soften(_union([_bar((0, 0), pb, z0, z1), _bar(pb, pc, z0, z1)]), z0, z1)
    tools = []
    for i in range(na):
        tools += _hole_cutters(i * PITCH, 0, z0, z1)
    for j in range(1, nb):
        tools += _hole_cutters(pb[0] + j * PITCH * math.cos(a), j * PITCH * math.sin(a), z0, z1)
    return PartDef("SB-K%d%d" % (na, nb), "Bent beam 1x%d (53 deg)" % (na + nb - 1),
                   [Body("beam", body.cut(tools), mat)], {"family": "Beams"})


def t_beam(mat="sb_lgrey"):
    z0, z1 = -BEAM_T / 2, BEAM_T / 2
    body = _soften(_union([_bar((0, 0), (16, 0), z0, z1), _bar((8, 0), (8, -16), z0, z1)]), z0, z1)
    tools = []
    for p in ((0, 0), (8, 0), (16, 0), (8, -8), (8, -16)):
        tools += _hole_cutters(p[0], p[1], z0, z1)
    return PartDef("SB-T33", "T-beam 3x3", [Body("beam", body.cut(tools), mat)], {"family": "Beams"})


def frame_beam(nx=5, ny=7, mat="sb_white"):
    z0, z1 = -BEAM_T / 2, BEAM_T / 2
    X, Y = (nx - 1) * PITCH, (ny - 1) * PITCH
    body = _soften(_union([_bar((0, 0), (X, 0), z0, z1), _bar((0, Y), (X, Y), z0, z1),
                           _bar((0, 0), (0, Y), z0, z1), _bar((X, 0), (X, Y), z0, z1)]), z0, z1)
    pts = {(i * PITCH, 0) for i in range(nx)} | {(i * PITCH, Y) for i in range(nx)}
    pts |= {(0, j * PITCH) for j in range(ny)} | {(X, j * PITCH) for j in range(ny)}
    tools = []
    for p in pts:
        tools += _hole_cutters(p[0], p[1], z0, z1)
    return PartDef("SB-F%d%d" % (nx, ny), "Frame %dx%d" % (nx, ny), [Body("frame", body.cut(tools), mat)],
                   {"family": "Beams"})


def semicube(mat="sb_white"):
    """1x1x1 cube: pin holes along Y and Z, axle hole along X (6-way node)."""
    h = BEAM_T / 2
    body = rounded_box(-h, -h, -h, h, h, h, 0.7)
    tools = _hole_cutters(0, 0, -h, h)
    tools += [frame(t, (1, 0, 0), (0, 0, 1)) for t in _hole_cutters(0, 0, -h, h)]
    tools.append(frame(_axle_hole(0, 0, -h, h), (0, 1, 0), (0, 0, 1)))
    return PartDef("SB-C111", "SemiCube 1x1x1 (6-way)", [Body("cube", body.cut(tools), mat)], {"family": "Connectors"})


def block_1x2(mat="sb_white"):
    h = BEAM_T / 2
    body = rounded_box(-h, -h, -h, PITCH + h, h, h, 0.7)
    tools = []
    for x in (0.0, PITCH):
        tools += _hole_cutters(x, 0, -h, h)
        tools += [frame(t, (1, 0, 0), (0, 0, 1), (x, 0, 0)) for t in _hole_cutters(0, 0, -h, h)]
    tools.append(frame(_axle_hole(0, 0, -h, PITCH + h), (0, 1, 0), (0, 0, 1)))
    return PartDef("SB-C121", "Block 1x2x1 (pin holes on 4 faces)", [Body("block", body.cut(tools), mat)],
                   {"family": "Connectors"})


def name_plate(mat="sb_blue"):
    t = PITCH / 2 - GAP
    body = rounded_box(-3.9, -3.9, -t / 2, 5 * PITCH + 3.9, PITCH + 3.9, t / 2, 0.8)
    tools = []
    for x in (0.0, 5 * PITCH):
        for y in (0.0, PITCH):
            tools += _hole_cutters(x, y, -t / 2, t / 2, counterbore=False)
    tools.append(rounded_rect_prism(2.5 * PITCH, PITCH / 2, 26.0, 13.0, 1.5, t / 2 - 0.4, t / 2 + 1))
    card = rounded_rect_prism(2.5 * PITCH, PITCH / 2, 25.8, 12.8, 1.4, t / 2 - 0.4, t / 2 - 0.05)
    return PartDef("SB-N26", "Name plate 2x6 (write-on)", [Body("plate", body.cut(tools), mat),
                                                          Body("card", card, "sb_white", False)],
                   {"family": "Accessories"})


# ================================================================ axles
def axle_shape(n, stop=False, notches=True):
    """Cross axle. New: a shallow notch at every module so kids can count length."""
    length = n * PITCH - GAP
    R = AXLE_D / 2
    ch = 0.3
    a = cross_prism(AXLE_D, AXLE_SPLINE, 0, length)
    a = a.common(revolve_rz([(0, 0), (R - ch, 0), (R, ch), (R, length - ch), (R - ch, length), (0, length)]))
    if notches and n > 1:
        a = a.cut([ring(R - 0.2, R + 1, k * PITCH - GAP / 2 - 0.25, k * PITCH - GAP / 2 + 0.25)
                   for k in range(1, n)])
    if stop:
        a = a.fuse(zcyl(2.95, 0, 0.7)).removeSplitter()
    return a


def axle(n, stop=False):
    mat = "sb_black" if n % 2 == 0 else "sb_lgrey"
    pid = "SB-A%02d%s" % (n, "S" if stop else "")
    return PartDef(pid, "Axle %d%s" % (n, " with stop" if stop else ""),
                   [Body("axle", axle_shape(n, stop), mat)], {"family": "Axles"})


# ================================================================= pins
def quick_pin(smooth=False, length=2):
    """Classic Technic-style friction pin. 2L: centred on z = 0; 3L: 1L below, 2L above."""
    h1 = BEAM_T + GAP / 2
    h2 = h1 if length == 2 else h1 + PITCH
    p = _union([_pin_half(0, -h1), _pin_half(0, h2), _collar()])
    p = p.cut(zcyl(QP_ID / 2, -h1 - 1, h2 + 1))
    if length == 3:
        return PartDef("SB-QP3", "Quick Pin 3L (friction)", [Body("pin", p, "sb_blue")], {"family": "Pins"})
    pid, title, mat = ("SB-QP2S", "Quick Pin 2L (smooth, pivots)", "sb_lgrey") if smooth else \
                      ("SB-QP2", "Quick Pin 2L (friction)", "sb_black")
    return PartDef(pid, title, [Body("pin", p, mat)], {"family": "Pins"})


def half_pin():
    head = zcyl(2.95, 0, 2.0)
    head = try_fillet(head, 0.4, edges_at_z(head, 2.0))
    p = _union([_pin_half(0.2, -BEAM_T + 0.1), head])
    p = p.cut([box(-0.4, -3, 1.2, 0.4, 3, 3), zcyl(QP_ID / 2, -9, 0.6)])
    return PartDef("SB-QP1", "Half pin 1L with stop head", [Body("pin", p, "sb_lgrey")], {"family": "Pins"})


def axle_pin(smooth=False):
    h = BEAM_T + GAP / 2
    p = _union([_pin_half(0, -h), _collar(), _axle_end(0.2, h)])
    pid, title, mat = ("SB-AP2S", "Axle pin (smooth)", "sb_lgrey") if smooth else ("SB-AP2", "Axle pin (friction)", "sb_blue")
    return PartDef(pid, title, [Body("pin", p, mat)], {"family": "Pins"})


def ball_pin():
    h = BEAM_T + GAP / 2
    p = _union([_pin_half(0, -h), _collar(), zcyl(1.6, 0, 3.0), Part.makeSphere(2.925, V(0, 0, 5.4))])
    return PartDef("SB-BP", "Ball pin (tow ball)", [Body("pin", p, "sb_dgrey")], {"family": "Pins"})


def pin_with_hole():
    h = BEAM_T + GAP / 2
    hz = QP_COLLAR_T / 2 + 3.7
    head = cyl_between(3.7, (-3.9, 0, hz), (3.9, 0, hz))
    p = _union([_pin_half(0, -h), _collar(), head, zcyl(2.4, 0, hz)])
    tools = [cyl_between(HOLE_D / 2, (-5, 0, hz), (5, 0, hz)),
             cyl_between(CB_D / 2, (-5, 0, hz), (-3.9 + CB_DEPTH, 0, hz)),
             cyl_between(CB_D / 2, (3.9 - CB_DEPTH, 0, hz), (5, 0, hz))]
    return PartDef("SB-PX", "Pin with cross hole", [Body("pin", p.cut(tools), "sb_lgrey")], {"family": "Pins"})


def bush():
    b = _union([zcyl(2.9, 0, BEAM_T), zcyl(3.7, 0, 1.3)])
    tools = [_axle_hole(0, 0, 0, BEAM_T)]
    for a in (45, 135, 225, 315):
        tools.append(zcyl(0.55, 1.6, BEAM_T + 1, 2.95 * math.cos(math.radians(a)), 2.95 * math.sin(math.radians(a))))
    return PartDef("SB-BU1", "Bush 1L", [Body("bush", b.cut(tools), "sb_lgrey")], {"family": "Pins"})


def half_bush():
    b = zcyl(3.6, 0, TC_LEN)
    tools = [_axle_hole(0, 0, 0, TC_LEN)]
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        for z in (0.0, TC_LEN):
            tools.append(cyl_between(0.5, (3.0 * math.cos(a), 3.0 * math.sin(a), z - 0.5),
                                     (3.0 * math.cos(a), 3.0 * math.sin(a), z + 0.5)))
    b = b.cut(tools)
    return PartDef("SB-BU0", "Half bush", [Body("bush", b, "sb_lgrey")], {"family": "Pins"})


def cable_clip():
    h = BEAM_T + GAP / 2
    hz = QP_COLLAR_T / 2 + 2.8
    head = cyl_between(2.8, (-2.2, 0, hz), (2.2, 0, hz)).cut(cyl_between(1.6, (-3, 0, hz), (3, 0, hz)))
    head = head.cut(box(-3, -1.15, hz, 3, 1.15, hz + 4))
    p = _union([_pin_half(0, -h), _collar(), head, box(-2.2, -1.2, 0, 2.2, 1.2, hz - 1.6)])
    return PartDef("SB-CC", "Cable clip (pin-in)", [Body("clip", p, "sb_lgrey")], {"family": "Accessories"})


# ======================================================== TwistLock family
def tl_sleeve(modules=2, smooth=False):
    depth = modules * PITCH - GAP              # far face of the stack (15.8 for 2 beams)
    zf = -depth
    rs, rl = TL_SLEEVE_D / 2, TL_LIP_D / 2
    ramp = (rl - rs) / math.tan(math.radians(TL_LIP_RAMP_DEG))
    z_top = -0.05                              # flange top: flush, just below the beam face
    z_fb = z_top - TL_FLANGE_T
    z_step = zf + CB_DEPTH                     # counterbore step on the far face
    prof = [(0, z_top), (TL_FLANGE_D / 2 - 0.15, z_top), (TL_FLANGE_D / 2, z_top - 0.15),
            (TL_FLANGE_D / 2, z_fb), (rs, z_fb),
            (rs, z_step + 0.05),                       # end of shank
            (rl, z_step + 0.05 - ramp),                # 45 deg back ramp of the catch lip
            (rl, z_step + 0.05 - ramp - 0.1),
            (rs - 0.15, zf + 0.05),                    # lead-in
            (0, zf + 0.05)]
    s = revolve_rz(prof)
    ribs = []
    zones = [(-BEAM_T + CB_DEPTH + 0.2, -1.0)]
    if not smooth:
        zones.append((zf + 0.9, zf + TL_FINGER_L - 0.3))
    for za, zb in zones:
        for a in (45, 135, 225, 315):
            ribs.append(rotated(box(rs - 0.1, -0.3, za, rs + TL_RIB_H, 0.3, zb), (0, 0, 1), a))
    s = s.fuse(ribs).removeSplitter()
    s = s.cut([zcyl(TL_BORE_D / 2, zf - 1, 1),                              # bore for the core
               zcyl(1.45, z_fb + 0.2, z_fb + 0.45),                          # snap groove for the core
               box(-3.5, -TL_SLOT_W / 2, zf - 1, 3.5, TL_SLOT_W / 2, zf + TL_FINGER_L)])  # finger slot
    return s


def tl_core(modules=2):
    depth = modules * PITCH - GAP
    zf = -depth
    z_cam = zf + TL_FINGER_L - 0.4
    knob = zcyl(TL_KNOB_D / 2, 0.0, TL_KNOB_T)
    top_edges = [e for e in knob.Edges if abs(e.BoundBox.ZMin - TL_KNOB_T) < 1e-6]
    try:
        knob = knob.makeChamfer(0.22, top_edges)
    except Exception:
        pass
    wing = box(-TL_WING_W / 2, -TL_KNOB_D / 2, TL_KNOB_T - 0.05, TL_WING_W / 2, TL_KNOB_D / 2,
               TL_KNOB_T + TL_WING_H).common(zcyl(TL_KNOB_D / 2 - 0.25, 0, 5))
    wing = try_fillet(wing, 0.45, [e for e in wing.Edges
                                   if abs(e.BoundBox.ZMin - (TL_KNOB_T + TL_WING_H)) < 1e-6
                                   and isinstance(e.Curve, Part.Line)])
    shaft = zcyl(TL_SHAFT_D / 2, z_cam - 0.3, 0.6)
    cam = zcyl(TL_CAM_D / 2, zf + 0.3, z_cam).common(
        box(-2, -TL_CAM_FLATS / 2, zf, 2, TL_CAM_FLATS / 2, 0))        # flats face +-Y = OPEN
    snap = zcyl(1.4, -0.62, -0.42)
    core = knob.fuse(wing).fuse(shaft).fuse(cam).fuse(snap).removeSplitter()
    core = core.cut([zcyl(TL_WINDOW_D / 2, -0.5, 3, sx * TL_WINDOW_R, 0) for sx in (1, -1)])
    return core


def tl_status_ring():
    """Pad-printed status ring on the sleeve flange, seen through the knob windows."""
    z0, z1 = -0.05, -0.012
    r0, r1 = TL_WINDOW_R - 0.6, TL_WINDOW_R + 0.6
    red = Part.makeCompound([sector(r0, r1, a, 76, z0, z1) for a in (0, 180)])
    green = Part.makeCompound([sector(r0, r1, a, 76, z0, z1) for a in (90, 270)])
    return red, green


def tl_pin(modules=2, smooth=False, state="open"):
    core = tl_core(modules)
    if state == "locked":
        core = rotated(core, (0, 0, 1), TL_LOCK_TURN_DEG)
    red, green = tl_status_ring()
    pid = "SB-TL%d%s" % (modules, "S" if smooth else "")
    title = "TwistLock Pin %dL%s" % (modules, " (smooth, pivots)" if smooth else " (friction)")
    return PartDef(pid, title, [
        Body("sleeve", tl_sleeve(modules, smooth), "sb_lgrey" if smooth else "sb_black"),
        Body("core", core, "sb_magenta"),
        Body("status_red", red, "ind_red", printable=False),
        Body("status_green", green, "ind_green", printable=False)],
        {"family": "Lock", "state": state})


def tl_collar(state="open", length=TC_LEN):
    """TwistLock Collar: grips an axle when the ring is turned 90 deg.
    Front (flange) at z < 0, body from z = 0 to `length`."""
    rf = 3.3
    collet = zcyl(TC_COLLET_D / 2, 0, length).fuse(zcyl(rf, -TC_FLANGE_T, 0.0))
    pads = [sector(TC_COLLET_D / 2 - 0.2, 2.86, a, 70, 0.9, length) for a in (90, 270)]
    collet = collet.fuse(pads).removeSplitter()
    collet = collet.cut([cross_prism(AXLE_HOLE_D, AXLE_HOLE_SPLINE, -2, length + 2),
                         box(-5, -TC_SLOT_W / 2, 0.8, 5, TC_SLOT_W / 2, length + 1)])
    ringb = zcyl(TC_OD / 2, 0.05, length)
    ell = Part.Ellipse(V(0, 0, 0), TC_OVAL_MAJOR / 2 + 0.06, TC_OVAL_MINOR / 2 + 0.03)
    oval = Part.Face(Part.Wire(ell.toShape())).extrude(V(0, 0, length + 2))
    oval.translate(V(0, 0, -1))
    oval = rotated(oval, (0, 0, 1), 90)                      # major axis on the jaws = OPEN
    flutes = [zcyl(0.42, 0.6, length + 1, 3.92 * math.cos(math.radians(a)), 3.92 * math.sin(math.radians(a)))
              for a in range(15, 360, 30)]
    ringb = ringb.cut([oval] + flutes)
    pointer = Part.makeCompound([sector(rf + 0.08, TC_OD / 2 - 0.05, a, 16, 0.0, 0.05) for a in (0, 180)])
    zf = -TC_FLANGE_T
    red = Part.makeCompound([sector(2.55, rf - 0.08, a, 50, zf - 0.04, zf) for a in (0, 180)])
    green = Part.makeCompound([sector(2.55, rf - 0.08, a, 50, zf - 0.04, zf) for a in (90, 270)])
    if state == "locked":
        ringb = rotated(ringb, (0, 0, 1), 90)
        pointer = rotated(pointer, (0, 0, 1), 90)
    long_ = length > TC_LEN + 0.1
    return PartDef("SB-TC%s" % ("1" if long_ else ""), "TwistLock Collar %s" % ("1L" if long_ else "1/2L"), [
        Body("collet", collet, "sb_lgrey"),
        Body("ring", ringb, "sb_magenta"),
        Body("pointer", pointer, "sb_white", printable=False),
        Body("status_red", red, "ind_red", printable=False),
        Body("status_green", green, "ind_green", printable=False)],
        {"family": "Lock", "state": state})


# ============================================================ connectors
def axle_joiner(mat="sb_dgrey"):
    L2 = 2 * PITCH - GAP
    b = revolve_rz([(0, 0), (3.4, 0), (3.68, 0.3), (3.68, L2 / 2 - 0.6), (3.35, L2 / 2), (3.68, L2 / 2 + 0.6),
                    (3.68, L2 - 0.3), (3.4, L2), (0, L2)])
    return PartDef("SB-XA2", "Axle joiner 2L", [Body("joiner", b.cut(_axle_hole(0, 0, 0, L2)), mat)],
                   {"family": "Connectors"})


def pin_joiner(mat="sb_lgrey"):
    L2 = 2 * PITCH - GAP
    b = revolve_rz([(0, 0), (3.4, 0), (3.68, 0.3), (3.68, L2 / 2 - 0.6), (3.35, L2 / 2), (3.68, L2 / 2 + 0.6),
                    (3.68, L2 - 0.3), (3.4, L2), (0, L2)])
    return PartDef("SB-XP2", "Pin joiner 2L", [Body("joiner", b.cut(_hole_cutters(0, 0, 0, L2)), mat)],
                   {"family": "Connectors"})


ANGLE_CONNECTORS = {1: (None, "sb_lgrey"), 2: (180.0, "sb_white"), 3: (157.5, "sb_dgrey"),
                    4: (135.0, "sb_yellow"), 5: (112.5, "sb_blue"), 6: (90.0, "sb_black")}


def angle_connector(num):
    ang, mat = ANGLE_CONNECTORS[num]
    h = BEAM_T / 2
    dirs = [180.0] if ang is None else [180.0 - (180.0 - ang) / 2, (180.0 - ang) / 2]
    hub = zcyl(3.7, -h, h)
    arms, tools = [], _hole_cutters(0, 0, -h, h)
    for d in dirs:
        u = (math.cos(math.radians(d)), math.sin(math.radians(d)), 0)
        p1 = (u[0] * (PITCH + 3.9), u[1] * (PITCH + 3.9), 0)
        arms.append(cyl_between(3.5, (0, 0, 0), p1))
        tools.append(frame(cross_prism(AXLE_HOLE_D, AXLE_HOLE_SPLINE, 4.3, PITCH + 5.0), (0, 0, 1),
                           (-u[1], u[0], 0)))
    body = _union([hub] + arms).cut(tools)
    title = "Angle connector #%d%s" % (num, "" if ang is None else " (%g deg)" % ang)
    return PartDef("SB-XN%d" % num, title, [Body("conn", body, mat)], {"family": "Connectors"})


def cross_block(n=2, mat="sb_dgrey"):
    """1 x n block: round pin holes (Z) at the ends, axle hole across (Y) in between."""
    z0, z1 = -BEAM_T / 2, BEAM_T / 2
    body = _soften(stadium_xy((n - 1) * PITCH, BEAM_W / 2, z0, z1), z0, z1)
    tools = []
    if n == 2:
        tools += _hole_cutters(0, 0, z0, z1)
        axle_x = [PITCH]
    else:
        tools += _hole_cutters(0, 0, z0, z1) + _hole_cutters(2 * PITCH, 0, z0, z1)
        axle_x = [PITCH]
    for x in axle_x:
        tools.append(frame(_axle_hole(0, 0, -BEAM_W / 2, BEAM_W / 2), (1, 0, 0), (0, 0, 1), (x, 0, 0)))
    return PartDef("SB-XC1%d" % n, "Cross block 1x%d" % n, [Body("block", body.cut(tools), mat)],
                   {"family": "Connectors"})


# ================================================================ gears
def gear_shape(z, thickness=GEAR_T, m=GEAR_MODULE, holes=True):
    rp = m * z / 2
    ra, rf = rp + 0.8 * m, rp - 1.1 * m
    alpha = math.radians(20)
    rb = rp * math.cos(alpha)

    def inv(a):
        return math.tan(a) - a

    half_base = ((math.pi * m / 2 - 0.1) / 2) / rp + inv(alpha)
    r_start = max(rb, rf)
    rs = [r_start + (ra - r_start) * i / 10 for i in range(11)]
    th = [half_base - inv(math.acos(min(1.0, rb / r))) for r in rs]
    pts = []

    def P(r, a):
        return (r * math.cos(a), r * math.sin(a))
    for k in range(z):
        c = 2 * math.pi * k / z
        if rf < rb:
            pts.append(P(rf, c - half_base))
        pts += [P(r, c - t) for r, t in zip(rs, th)]
        pts += [P(r, c + t) for r, t in reversed(list(zip(rs, th)))]
        if rf < rb:
            pts.append(P(rf, c + half_base))
        a0, a1 = c + half_base, c + 2 * math.pi / z - half_base
        pts += [P(rf, a0 + (a1 - a0) * i / 4) for i in range(1, 4)]
    g = prism_xy(pts, -thickness / 2, thickness / 2)
    tools = [cross_prism(AXLE_HOLE_D, AXLE_HOLE_SPLINE, -5, 5)]
    if holes and z >= 24:
        rr = (rf - 2.4 + 4.0) / 2
        for a in (45, 135, 225, 315):
            tools.append(zcyl(HOLE_D / 2, -5, 5, rr * math.cos(math.radians(a)), rr * math.sin(math.radians(a))))
    if holes and z >= 36:
        for a in range(0, 360, 45):
            tools.append(zcyl(2.6, -5, 5, (rf - 4.0) * math.cos(math.radians(a + 22.5)),
                              (rf - 4.0) * math.sin(math.radians(a + 22.5))))
    return g.cut(tools)


def gear(z, mat="sb_blue"):
    return PartDef("SB-G%02d" % z, "Gear %dT" % z, [Body("gear", gear_shape(z), mat)], {"family": "Gears"})


def bevel_gear(z, mat="sb_lgrey"):
    """Double-bevel gear: meshes parallel or at 90 deg (Technic-style 12/20/36T)."""
    t = 4.0 if z < 30 else 3.9
    ra = z / 2 + 0.8
    g = gear_shape(z, thickness=t)
    bic = revolve_rz([(0, -t / 2), (ra - t / 2, -t / 2), (ra, 0), (ra - t / 2, t / 2), (0, t / 2)])
    return PartDef("SB-G%02dB" % z, "Double-bevel gear %dT" % z, [Body("gear", g.common(bic), mat)],
                   {"family": "Gears"})


def clutch_gear():
    """24T gear with a slip clutch hub: protects motors + gears from over-torque."""
    g = gear_shape(24, holes=False)
    hub = zcyl(6.5, -BEAM_T / 2, BEAM_T / 2)
    ribs = [rotated(box(6.0, -0.6, -BEAM_T / 2 + 0.6, 9.4, 0.6, BEAM_T / 2 - 0.6), (0, 0, 1), a) for a in range(0, 360, 60)]
    body = _union([g, hub] + ribs).cut([_axle_hole(0, 0, -BEAM_T / 2, BEAM_T / 2)])
    marks = Part.makeCompound([rotated(box(7.2, -0.35, GEAR_T / 2, 9.6, 0.35, GEAR_T / 2 + 0.25), (0, 0, 1), a)
                               for a in range(30, 360, 60)])
    return PartDef("SB-G24C", "Clutch gear 24T (slips at safe torque)",
                   [Body("gear", body, "sb_white"), Body("marks", marks, "sb_magenta", False)], {"family": "Gears"})


def worm_gear(mat="sb_dgrey"):
    """Single-start m = 1 worm, built as a twisted loft of its cross-section
    (more robust than a helical sweep in OCC)."""
    L2 = 2 * PITCH - GAP
    p = math.pi * GEAR_MODULE

    def tooth_r(s):
        s = s % p
        r0, r1, top, flank = 3.1, 5.2, 0.7, 0.75
        d = abs(s - p / 2)
        if d <= top / 2:
            return r1
        if d <= top / 2 + flank:
            return r1 - (r1 - r0) * (d - top / 2) / flank
        return r0

    def section(z, n=40):
        pts = []
        for k in range(n):
            phi = 2 * math.pi * k / n
            r = tooth_r(z - p * phi / (2 * math.pi))
            pts.append(V(r * math.cos(phi), r * math.sin(phi), z))
        return Part.makePolygon(pts + [pts[0]])
    w = Part.makeLoft([section(L2 * i / 64) for i in range(65)], True, True)
    env = revolve_rz([(0, 0), (4.2, 0), (5.2, 1.0), (5.2, L2 - 1.0), (4.2, L2), (0, L2)])
    w = w.common(env).cut(_axle_hole(0, 0, 0, L2))
    return PartDef("SB-GW", "Worm gear", [Body("worm", w, mat)], {"family": "Gears"})


def gear_rack(n=4, mat="sb_lgrey"):
    Lx = n * PITCH - GAP
    base = box(0.1, -BEAM_W / 2, -BEAM_T / 2, Lx + 0.1, BEAM_W / 2, BEAM_T / 2)
    pitch = math.pi * GEAR_MODULE
    teeth = []
    x = 0.1 + pitch / 2
    while x + pitch / 2 < Lx + 0.1:
        prof = [(x - 1.1, -0.01), (x - 0.4, 1.9), (x + 0.4, 1.9), (x + 1.1, -0.01)]
        tooth = Part.Face(Part.makePolygon([V(px, -BEAM_W / 2, BEAM_T / 2 + pz) for px, pz in prof] +
                                           [V(prof[0][0], -BEAM_W / 2, BEAM_T / 2 + prof[0][1])])).extrude(V(0, BEAM_W, 0))
        teeth.append(tooth)
        x += pitch
    body = _union([base] + teeth)
    tools = []
    for i in range(n):
        tools += [frame(t, (1, 0, 0), (0, 0, 1), (4.0 + i * PITCH, 0, 0)) for t in _hole_cutters(0, 0, -BEAM_W / 2, BEAM_W / 2)]
    return PartDef("SB-GR%d" % n, "Gear rack 1x%d" % n, [Body("rack", body.cut(tools), mat)], {"family": "Gears"})


# ================================================================ wheels
def wheel_parts(D=WHEEL_D, W=WHEEL_W, rim_d=RIM_D, grooves=28):
    R, Rr = D / 2, rim_d / 2
    sh = min(3.2, W / 5)
    prof = [(Rr, 1.0), (Rr + 1.0, 0.0), (R - sh, 0.0)]
    prof += [(R - sh + sh * math.sin(math.radians(d)), sh - sh * math.cos(math.radians(d))) for d in (20, 45, 70, 90)]
    prof += [(R, W - sh)]
    prof += [(R - sh + sh * math.cos(math.radians(d)), W - sh + sh * math.sin(math.radians(d))) for d in (20, 45, 70, 90)]
    prof += [(Rr + 1.0, W), (Rr, W - 1.0)]
    tire = revolve_rz(prof)
    cuts = []
    for k in range(grooves):
        for z0, z1, off in ((sh, W / 2 - 0.6, 0.0), (W / 2 + 0.6, W - sh, 0.5)):
            cuts.append(rotated(box(R - 0.9, -0.85, z0, R + 1.0, 0.85, z1), (0, 0, 1), (k + off) * 360.0 / grooves))
    cuts.append(ring(R - 0.7, R + 1, W / 2 - 0.6, W / 2 + 0.6))
    tire = tire.cut(cuts)
    rim = ring(Rr - 2.2, Rr + 0.05, 1.0, W - 1.0)
    lips = [ring(Rr - 2.2, Rr + 1.0, 0.2, 1.0), ring(Rr - 2.2, Rr + 1.0, W - 1.0, W - 0.2)]
    web_t = min(4.0, W / 4)
    web = ring(5.5, Rr - 2.0, W - web_t - 3.0, W - 3.0)
    boss = zcyl(5.8, min(2.8, W / 5), W - 0.2)
    hub = _union([rim, web, boss] + lips)
    tools = [cross_prism(AXLE_HOLE_D, AXLE_HOLE_SPLINE, 0, W + 1)]
    nh = 5 if Rr > 15 else 4
    rr = (5.8 + Rr - 2.2) / 2
    for k in range(nh):
        a = math.radians(90 + k * 360 / nh)
        tools.append(zcyl(min(4.6, (Rr - 2.2 - 5.8) / 2 - 0.6), W - web_t - 4, W, rr * math.cos(a), rr * math.sin(a)))
    return hub.cut(tools), tire


def wheel(D=WHEEL_D, W=WHEEL_W, rim_d=RIM_D):
    hub, tire = wheel_parts(D, W, rim_d, 28 if D > 40 else 18)
    return PartDef("SB-W%d" % D, "Wheel %d x %d + tyre" % (D, W), [Body("hub", hub, "sb_blue"),
                                                                  Body("tire", tire, "rubber")],
                   {"family": "Wheels"})


def _roller(length, r_mid, r_end, p_center, axis):
    """Barrel roller centred on p_center along `axis` (unit tuple)."""
    prof = [(0, -length / 2)]
    for i in range(9):
        t = -1 + 2 * i / 8
        prof.append((r_end + (r_mid - r_end) * (1 - t * t), t * length / 2))
    prof.append((0, length / 2))
    rl = revolve_rz(prof)
    a = V(*axis)
    ref = V(0, 0, 1) if abs(a.z) < 0.9 else V(1, 0, 0)
    xd = ref.cross(a)
    xd.normalize()
    yd = a.cross(xd)
    return frame(rl, (xd.x, xd.y, xd.z), (yd.x, yd.y, yd.z), p_center)


def omni_wheel():
    R = 24.0
    plates = [zcyl(17.5, z - 1.0, z + 1.0) for z in (-4.5, 4.5)]
    boss = zcyl(5.8, -7.8, 7.8)
    hub = _union(plates + [boss])
    tools = [_axle_hole(0, 0, -8, 8)]
    for k in range(6):
        a = math.radians(30 + k * 60)
        tools.append(zcyl(3.2, -8, 8, 11.5 * math.cos(a), 11.5 * math.sin(a)))
    hub = hub.cut(tools)
    rollers = []
    for row, z in ((0, -2.6), (1, 2.6)):
        for k in range(8):
            a = math.radians(k * 45 + row * 22.5)
            c = ((R - 3.6) * math.cos(a), (R - 3.6) * math.sin(a), z)
            rollers.append(_roller(10.0, 3.6, 2.4, c, (-math.sin(a), math.cos(a), 0)))
    return PartDef("SB-WO48", "Omni wheel 48", [Body("hub", hub, "sb_dgrey"),
                                                 Body("rollers", Part.makeCompound(rollers), "rubber")],
                   {"family": "Wheels"})


def mecanum_wheel(hand=1):
    R, n = 30.0, 9
    plates = [ring(5.0, 25.0, z - 1.1, z + 1.1) for z in (-11.0, 11.0)]
    boss = zcyl(6.0, -12.0, 12.0)
    posts = []
    rollers = []
    for k in range(n):
        a = math.radians(k * 360 / n)
        radial = (math.cos(a), math.sin(a), 0)
        tang = (-math.sin(a), math.cos(a), 0)
        ax = tuple((tang[i] + hand * (0, 0, 1)[i]) / math.sqrt(2) for i in range(3))
        c = ((R - 5.2) * radial[0], (R - 5.2) * radial[1], 0)
        rollers.append(_roller(26.0, 5.2, 3.0, c, ax))
        for s in (-1, 1):
            p_end = (c[0] + ax[0] * 13.6 * s, c[1] + ax[1] * 13.6 * s, c[2] + ax[2] * 13.6 * s)
            p_in = (p_end[0] - radial[0] * 3.0, p_end[1] - radial[1] * 3.0, s * 11.0)
            posts.append(cyl_between(1.6, p_in, p_end))
    hub = _union(plates + [boss] + posts)
    tools = [_axle_hole(0, 0, -13, 13)]
    for k in range(4):
        a = math.radians(45 + k * 90)
        tools.append(zcyl(HOLE_D / 2, -13, 13, 12.0 * math.cos(a), 12.0 * math.sin(a)))
    hub = hub.cut(tools)
    name = "SB-WM60%s" % ("L" if hand > 0 else "R")
    return PartDef(name, "Mecanum wheel 60 (%s)" % ("left" if hand > 0 else "right"),
                   [Body("hub", hub, "sb_blue"), Body("rollers", Part.makeCompound(rollers), "rubber")],
                   {"family": "Wheels"})


def caster_block():
    nx, ny, nz = 2, 6, 3
    cell = (nx * PITCH, ny * PITCH, nz * PITCH)
    lx, ly, lz = cell
    shell = rounded_box(0.1, 0.1, 0.1, lx - 0.1, ly - 0.1, lz - 0.1, 1.2)
    rb = 6.5
    cz = -16.0 + rb                         # ball touches the ground 16 mm below the block
    holder = zcyl(7.8, cz - 1.5, 0.6, lx / 2, ly / 2)
    holder = try_fillet(holder, 1.0, edges_at_z(holder, cz - 1.5))
    body = shell.fuse(holder).removeSplitter()
    tools = [Part.makeSphere(rb + 0.15, V(lx / 2, ly / 2, cz))]
    from modules import grid_holes, grid
    tools += grid_holes("+y", [(x, z) for x in grid(nx) for z in grid(nz)], cell)
    tools += grid_holes("-y", [(x, z) for x in grid(nx) for z in grid(nz)], cell)
    tools += grid_holes("+z", [(x, y) for x in grid(nx) for y in grid(ny)], cell)
    body = body.cut(tools)
    ball = Part.makeSphere(rb, V(lx / 2, ly / 2, cz))
    return PartDef("SB-CASTER", "Ball caster block", [Body("block", body, "sb_dgrey"),
                                                      Body("ball", ball, "steel")], {"family": "Wheels"})


# ================================================================ tools
def semikey():
    """SemiKey multi-tool: lock key, axle-length gauge, pin lifter, ruler."""
    t = 3.2
    body = stadium_xy(76.0, 9.0, 0, t)
    body = try_fillet(body, 0.8, edges_at_z(body, 0) + edges_at_z(body, t))
    tools = [box(4.0, 2.2, 1.0, 68.0, 7.4, t + 1)]                              # axle gauge channel
    for k in range(1, 9):
        x = 4.0 + k * PITCH - GAP
        tools.append(box(x - 0.25, 0.2, t - 0.35, x + 0.25, 2.2, t + 1))
        tools.append(engrave(str(k), 3.4, 0.35, (x, -2.8, t), (1, 0, 0), (0, 1, 0)))
    tools.append(box(-4.0, -3.4, -1, -2.0, 3.4, t + 1))                          # TwistLock key slot
    tools.append(box(72.0, -1.75, -1, 86.0, 1.75, t + 1))                        # pin lifter fork
    tools.append(zcyl(1.8, -1, t + 1, 62.0, -5.0))                               # lanyard hole
    tools.append(engrave("SemiKey", 3.0, 0.3, (40.0, -6.4, t), (1, 0, 0), (0, 1, 0)))
    return PartDef("SB-KEY", "SemiKey multi-tool", [Body("key", body.cut(tools), "sb_magenta")],
                   {"family": "Accessories"})

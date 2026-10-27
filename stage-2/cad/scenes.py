"""Assemblies + render/viewer scene definitions for stage-2.

Global frame for assemblies: X forward, Y left, Z up, mm. Each scene is a list
of Instances; `SHOTS` describes cameras and callouts for the Blender renders.
"""
import math

import Part

import modules as MO
import parts as P
from params import BEAM_T, GAP, PITCH, TC_LEN, TL_LOCK_TURN_DEG
from sbcad import Body, Instance, V, cone_between, cyl_between, frame, moved, place, rotated, vec_to_gltf


# ------------------------------------------------------------- helpers
def cable_shape(pts, r=1.5):
    bs = Part.BSplineCurve()
    bs.interpolate([V(*p) for p in pts])
    t0 = bs.tangent(bs.FirstParameter)
    t0 = t0[0] if isinstance(t0, tuple) else t0
    circ = Part.Wire(Part.makeCircle(r, V(*pts[0]), t0))
    return Part.Wire(bs.toShape()).makePipeShell([circ], True, True)


def arrow_straight(p0, p1, r=0.9, head=2.6):
    p0, p1 = V(*p0), V(*p1)
    d = p1 - p0
    n = V(d)
    n.normalize()
    pm = p1 - n * (head * 1.6)
    shaft = cyl_between(r, tuple(p0), tuple(pm))
    tip = cone_between(head, 0.0, tuple(pm), tuple(p1))
    return shaft.fuse(tip)


def arrow_turn(center, axis_z, radius, start_deg, sweep_deg, r=0.55, head=1.5):
    """Curved arrow around +Z (negative sweep = clockwise seen from above)."""
    cx, cy, cz = center
    pts = []
    for i in range(25):
        a = math.radians(start_deg + sweep_deg * i / 24)
        pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a), cz))
    body = cable_shape(pts[:-3], r)
    a_end = math.radians(start_deg + sweep_deg)
    a_pre = math.radians(start_deg + sweep_deg * 21 / 24)
    pe = (cx + radius * math.cos(a_end), cy + radius * math.sin(a_end), cz)
    pp = (cx + radius * math.cos(a_pre), cy + radius * math.sin(a_pre), cz)
    return body.fuse(cone_between(head, 0.0, pp, pe))


def tl_extras(origin, zdir, state):
    return {"lock": {"pivot": vec_to_gltf(origin), "axis": vec_to_gltf(zdir, 1.0),
                     "turn": TL_LOCK_TURN_DEG, "state": state, "node": "core"}}


def explode(instances, offsets):
    out = []
    for inst in instances:
        off = offsets.get(inst.name)
        if off is None:
            for key, val in offsets.items():
                if key.endswith("*") and inst.name.startswith(key[:-1]):
                    off = val
                    break
        if off == "hide":
            continue
        if off:
            inst = Instance(inst.name, [Body(b.name, moved(b.shape, *off), b.mat, b.printable)
                                        for b in inst.bodies], inst.extras)
        out.append(inst)
    return out


# ================================================================ rover
def rover(pin_state="locked"):
    I = []
    tl = {s: P.tl_pin(2, state=s) for s in ("open", "locked")}
    rail = P.beam(15, "sb_blue")
    for side, y in (("L", 28.0), ("R", -28.0)):
        I.append(place(rail, "rail_" + side, (1, 0, 0), (0, 0, -1), (-56.0, y, 28.0),
                       {"explode": [0, 7 if y > 0 else -7, 0]}))
    mot = MO.motor_m()
    I.append(place(mot, "motor_L", origin=(-20.0, 0.0, 16.0)))
    I.append(place(mot, "motor_R", (-1, 0, 0), (0, -1, 0), (20.0, 0.0, 16.0)))
    I.append(place(MO.brain_hub(), "hub", origin=(-52.0, -24.0, 40.0), extras={"explode": [0, 0, 46]}))
    I.append(place(MO.sensor_ultrasonic(), "ultrasonic", origin=(44.0, -24.0, 16.0), extras={"explode": [34, 0, 0]}))
    I.append(place(MO.sensor_line(), "line_sensor", origin=(28.0, -24.0, 8.0), extras={"explode": [0, 0, -22]}))
    I.append(place(P.caster_block(), "caster", origin=(-60.0, -24.0, 16.0), extras={"explode": [-30, 0, 0]}))
    # wheel axles run in a bearing beam on the outside of each rail (pinned through
    # rail holes -16 / +16); wheels on 7L axles, a TwistLock Collar each side
    wh, ax, col, brg = P.wheel(), P.axle(7), P.tl_collar("locked"), P.bearing_beam()
    for side, s in (("L", 1), ("R", -1)):
        I.append(place(brg, "bearing_" + side, (1, 0, 0), (0, 0, -s), (0.0, s * 36.0, 28.0),
                       {"explode": [0, s * 14, 0]}))
        I.append(place(ax, "axle_" + side, (1, 0, 0), (0, 0, -s), (0.0, s * 17.9, 28.0),
                       {"explode": [0, s * 24, 0]}))
        I.append(place(col, "collar_in_" + side, (1, 0, 0), (0, 0, -s), (0.0, s * 40.7, 28.0),
                       {"explode": [0, s * 34, 0]}))
        I.append(place(wh, "wheel_" + side, (1, 0, 0), (0, 0, -s), (0.0, s * 44.6, 28.0),
                       {"explode": [0, s * 46, 0]}))
        I.append(place(col, "collar_out_" + side, (1, 0, 0), (0, 0, s), (0.0, s * 74.6, 28.0),
                       {"explode": [0, s * 58, 0]}))
    # 16 TwistLock pins on the outside of both rails; the 4 at -16 / +16 are 3L
    # (bearing beam + rail + motor housing)
    tl3 = {s: P.tl_pin(3, state=s) for s in ("open", "locked")}
    for x in (-56, -48, -16, 16, 32, 40, 48, 56):
        for side, s in (("L", 1), ("R", -1)):
            ydir = (0, 0, -1) if s > 0 else (0, 0, 1)
            through = abs(x) == 16
            origin = (float(x), s * (39.9 if through else 31.9), 28.0)
            ex = tl_extras(origin, (0, s, 0), pin_state)
            ex["explode"] = [0, s * (26 if through else 18), 0]
            I.append(place((tl3 if through else tl)[pin_state], "tlpin_%s_%d" % (side, x), (1, 0, 0), ydir, origin, ex))
    # SemiLink cables (plug -> cable -> plug)
    plug = MO.semilink_plug(with_cable_stub=False)
    hide = {"explode": "hide"}

    def socket_plug(name, origin, normal, up):
        n, u = V(*normal), V(*up)
        x = u.cross(n)
        I.append(place(plug, name, (x.x, x.y, x.z), up, origin, hide))

    socket_plug("plug_A", (35.9, -16.0, 58.0), (1, 0, 0), (0, 0, 1))
    socket_plug("plug_B", (35.9, 0.0, 58.0), (1, 0, 0), (0, 0, 1))
    socket_plug("plug_D", (-51.9, 16.0, 58.0), (-1, 0, 0), (0, 0, 1))
    socket_plug("plug_F", (-51.9, -16.0, 58.0), (-1, 0, 0), (0, 0, 1))
    socket_plug("plug_us", (52.0, 16.0, 39.9), (0, 0, 1), (-1, 0, 0))
    socket_plug("plug_line", (36.0, -23.9, 16.0), (0, -1, 0), (0, 0, 1))
    socket_plug("plug_mL", (-19.9, 12.0, 28.0), (-1, 0, 0), (0, 0, 1))
    socket_plug("plug_mR", (-19.9, -12.0, 28.0), (-1, 0, 0), (0, 0, 1))
    cables = {
        "cable_us": [(44.7, 0.0, 57.8), (48.5, 0.5, 58.6), (55.0, 4.0, 60.0), (58.0, 11.0, 57.5),
                     (54.0, 16.5, 54.5), (52.0, 15.8, 50.5), (52.0, 15.8, 48.6)],
        "cable_line": [(44.7, -16.0, 57.8), (49.0, -16.5, 58.0), (54.0, -22.0, 60.0), (50.0, -32.0, 56.0),
                       (42.0, -41.0, 42.0), (37.5, -42.0, 26.0), (36.0, -37.0, 17.0), (36.0, -32.7, 15.8)],
    }
    for s, side in ((1, "L"), (-1, "R")):
        cables["cable_m" + side] = [(-60.7, s * 16.0, 57.8), (-66.0, s * 16.5, 58.5), (-68.0, s * 22.0, 63.0),
                                    (-58.0, s * 31.0, 64.0), (-47.0, s * 36.0, 52.0), (-41.0, s * 34.0, 40.0),
                                    (-37.5, s * 22.0, 33.0), (-32.5, s * 13.0, 28.8), (-28.7, s * 12.2, 28.0)]
    for name, pts in cables.items():
        I.append(Instance(name, [Body("cable", cable_shape(pts), "cable", False)], hide))
    return I


# ====================================================== lock close-ups
def _beam_pair(n, origin, along=(0, 1, 0), mats=("sb_blue", "sb_yellow"), name="b"):
    """Two stacked beams under z = 0 (top beam z in [-7.8,0], bottom [-15.8,-8])."""
    a = V(*along)
    perp = V(0, 0, 1).cross(a)
    perp = (-perp.x, -perp.y, -perp.z)
    I = []
    for k, (mat, zc) in enumerate(zip(mats, (-BEAM_T / 2, -BEAM_T - GAP - BEAM_T / 2))):
        o = (origin[0], origin[1], origin[2] + zc)
        I.append(place(P.beam(n, mat), "%s_%d" % (name, k), tuple(along), perp, o))
    return I


def tl_section_scene():
    """OPEN vs LOCKED, cut on the YZ plane through the pin axis (x > 0 removed)."""
    I = []
    for state, yoff in (("open", 0.0), ("locked", 28.0)):
        I += _beam_pair(3, (0.0, yoff, 0.0), name="beam_" + state)
        I.append(place(P.tl_pin(2, state=state), "tlpin_" + state, origin=(0.0, yoff + 8.0, 0.0)))
    return I


def tl_demo_scene():
    """Viewer: a pin through two beams + a classic Quick Pin for comparison."""
    I = _beam_pair(5, (-16.0, 0.0, 0.0), along=(1, 0, 0), name="beam")
    origin = (0.0, 0.0, 0.0)
    I.append(place(P.tl_pin(2, state="open"), "tlpin", origin=origin,
                   extras=tl_extras(origin, (0, 0, 1), "open")))
    I.append(place(P.quick_pin(), "quickpin", origin=(-16.0, 0.0, -8.0)))
    I.append(place(P.tl_pin(2, smooth=True, state="open"), "tlpin_smooth", origin=(16.0, 0.0, 0.0),
                   extras=tl_extras((16.0, 0.0, 0.0), (0, 0, 1), "open")))
    return I


def tl_exploded_scene():
    """Pin lying along X: knob on the left, core pulled out to the left."""
    pin = P.tl_pin(2, state="open")
    I = []
    for b in pin.bodies:
        off = (-24.0, 0.0, 0.0) if b.name == "core" else (0.0, 0.0, 0.0)
        part = P.PartDef("x", "x", [b])
        I.append(place(part, "tl_" + b.name, (0, 0, 1), (0, 1, 0), off))
    return I


def tl_steps_scene(step):
    I = _beam_pair(3, (-8.0, 0.0, 0.0), along=(1, 0, 0), name="beam")
    state = "locked" if step == 3 else "open"     # step 0 = open, no arrows (knob close-up)
    lift = 12.0 if step == 1 else 0.0
    I.append(place(P.tl_pin(2, state=state), "tlpin", origin=(0.0, 0.0, lift)))
    if step == 1:
        I.append(Instance("arrow", [Body("arrow", arrow_straight((-7.5, 0, 25.0), (-7.5, 0, 6.0), 0.8, 2.2),
                                         "arrow", False)]))
    if step == 2:
        I.append(Instance("arrow", [Body("arrow", arrow_turn((0, 0, 4.6), 1, 6.4, 150, -220, 0.55, 1.6),
                                         "arrow", False)]))
    return I


def collar_scene():
    """Axle through an upright beam, collar on each side; OPEN vs LOCKED."""
    I = []
    for state, yoff in (("open", 0.0), ("locked", 30.0)):
        I.append(place(P.beam(3, "sb_lgrey"), "beam_" + state, (0, 0, 1), (0, 1, 0), (0.0, yoff, -8.0)))
        I.append(place(P.axle(5), "axle_" + state, (0, 1, 0), (0, 0, 1), (-19.0, yoff, 0.0)))
        col = P.tl_collar(state)
        I.append(place(col, "collar_front_" + state, (0, 1, 0), (0, 0, -1), (7.9, yoff, 0.0)))
        I.append(place(col, "collar_back_" + state, (0, 1, 0), (0, 0, 1), (-7.9, yoff, 0.0)))
    return I


def collar_exploded_scene():
    col = P.tl_collar("open")
    I = []
    for b in col.bodies:
        off = 0.0
        if b.name in ("ring", "pointer"):
            off = 9.0
        part = P.PartDef("x", "x", [b])
        I.append(place(part, "c_" + b.name, (0, 1, 0), (0, 0, 1), (-off, 0.0, 0.0)))
    I.append(place(P.axle(3), "axle", (0, 1, 0), (0, 0, 1), (-20.0, 0.0, 0.0)))
    return I


def beam_features_scene():
    I = [place(P.beam(7, "sb_blue"), "beam7", origin=(0.0, 0.0, 3.9)),
         place(P.beam(15, "sb_yellow"), "beam15", origin=(-24.0, 22.0, 3.9)),
         place(P.axle(6), "axle6", (1, 0, 0), (0, 1, 0), (0.0, -16.0, 2.4))]
    I[-1] = place(P.axle(6), "axle6", (0, 0, 1), (0, 1, 0), (0.0, -16.0, 2.4))
    return I


# ======================================================= stage-2 scenes
def _lz(k):
    """z of the centre of layer k (layer 0 sits on the ground: z 0.1 .. 7.9)."""
    return k * PITCH + PITCH / 2


def _rot(p, a_deg):
    a = math.radians(a_deg)
    return (p[0] * math.cos(a) - p[1] * math.sin(a), p[0] * math.sin(a) + p[1] * math.cos(a))


def _along(part, name, p0, p1, layer, extras=None):
    """Lay a beam from hole p0 towards p1 (XY) on layer k."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    return place(part, name, (dx / L, dy / L, 0), (-dy / L, dx / L, 0), (p0[0], p0[1], _lz(layer)), extras)


def _tl(name, xy, top_layer, modules=2, state="locked"):
    origin = (xy[0], xy[1], top_layer * PITCH + PITCH - GAP / 2)
    return place(P.tl_pin(modules, state=state), name, origin=origin, extras=tl_extras(origin, (0, 0, 1), state))


def hbeam_section_scene():
    """Stage-1 solid beam (grey) and stage-2 H-beam (blue), both cut between holes 4 and 5."""
    solid = P.PartDef("SB-B07-S1", "Beam 1x7 (stage 1, solid)", [Body("beam", P.solid_beam_shape(7), "sb_lgrey")])
    return [place(solid, "solid", origin=(0.0, 14.0, _lz(0))), place(P.beam(7, "sb_blue"), "hbeam", origin=(0.0, -14.0, _lz(0)))]


def _triangle(tag, pts, beams, mats, ox, oy):
    """Three beams pinned into a rigid triangle on layers 0, 1, 2. The corner
    where layers 0 and 2 meet gets a SemiCube spacer and a 3L TwistLock."""
    A, B, C = [(ox + x, oy + y) for x, y in pts]
    I = [_along(P.beam(beams[0], mats[0]), tag + "_ab", A, B, 0),
         _along(P.beam(beams[1], mats[1]), tag + "_bc", B, C, 1),
         _along(P.beam(beams[2], mats[2]), tag + "_ac", A, C, 2),
         place(P.semicube(), tag + "_spacer", origin=(A[0], A[1], _lz(1))),
         _tl(tag + "_pin_b", B, 1), _tl(tag + "_pin_c", C, 2), _tl(tag + "_pin_a", A, 2, modules=3)]
    return I


def angles_scene():
    """The angle toolbox: hinge elbow at 45 deg, a 3-4-5 triangle, an equilateral
    triangle and the two bent H-beams."""
    hinge = P.angle_hinge()
    c, s45 = math.cos(math.radians(45)), math.sin(math.radians(45))
    hx, hy = 0.0, 22.0                                    # back row: hinge elbow, 3-4-5 triangle
    I = [place(hinge, "hinge_a", origin=(hx, hy, _lz(0))),
         place(hinge, "hinge_b", (c, s45, 0), (s45, -c, 0), (hx, hy, _lz(1))),
         _tl("hinge_pin", (hx, hy), 1)]
    I.append(_along(P.beam(5, "sb_blue"), "elbow_a", (hx + 16.0, hy), (hx + 48.0, hy), 1))
    I += [_tl("elbow_pin_a%d" % x, (hx + x, hy), 1) for x in (16, 24)]
    I.append(_along(P.beam(5, "sb_yellow"), "elbow_b", (hx + 16 * c, hy + 16 * s45), (hx + 48 * c, hy + 48 * s45), 2))
    I += [_tl("elbow_pin_b%d" % r, (hx + r * c, hy + r * s45), 2) for r in (16, 24)]
    I += _triangle("t345", [(0, 0), (32, 0), (32, 24)], (5, 4, 6), ("sb_blue", "sb_yellow", "sb_white"), 76.0, 22.0)
    # front row: equilateral triangle, bent H-beams
    I += _triangle("t60", [(0, 0), (32, 0), (16, 16 * math.sqrt(3))], (5, 5, 5), ("sb_white", "sb_blue", "sb_yellow"),
                   4.0, -50.0)
    I.append(place(P.bent_beam(), "bent53", origin=(58.0, -54.0, _lz(0))))
    I.append(place(P.bent_beam(4, 4, 45.0, "sb_yellow"), "bent45", origin=(92.0, -58.0, _lz(0))))
    return I


def hinge_exploded_scene():
    hinge = P.angle_hinge()
    c, s45 = math.cos(math.radians(45)), math.sin(math.radians(45))
    return [place(hinge, "hinge_a", origin=(0.0, 0.0, _lz(0))),
            place(hinge, "hinge_b", (c, s45, 0), (s45, -c, 0), (0.0, 0.0, _lz(1) + 16.0)),
            place(P.tl_pin(2, state="open"), "hinge_pin", origin=(0.0, 0.0, 2 * PITCH - GAP / 2 + 34.0))]


BEARING_EXPLODE = {"br_housing": [0, 0, 0], "br_bearing_mr128": [0, 0, 12], "br_retainer": [0, 0, 20],
                   "br_axle_hub": [0, 0, 30], "collar_top": [0, 0, 40], "collar_bottom": [0, 0, -8], "axle": [0, 0, 0]}


def bearing_scene():
    """Bearing beam (layer 1) on a vertical 3L axle, a TwistLock Collar each side.
    Each body is its own node so Explode slides them up the axle."""
    I = []
    for b in P.bearing_beam().bodies:
        I.append(place(P.PartDef("x", "x", [b]), "br_" + b.name, origin=(0.0, 0.0, _lz(1)),
                       extras={"explode": BEARING_EXPLODE["br_" + b.name]}))
    I.append(place(P.axle(3), "axle", origin=(0.0, 0.0, GAP / 2), extras={"explode": [0, 0, 0]}))
    col = P.tl_collar("locked")
    I.append(place(col, "collar_bottom", (1, 0, 0), (0, -1, 0), (0.0, 0.0, PITCH - 0.6),
                   {"explode": BEARING_EXPLODE["collar_bottom"]}))
    I.append(place(col, "collar_top", origin=(0.0, 0.0, 2 * PITCH + 0.6), extras={"explode": BEARING_EXPLODE["collar_top"]}))
    return I


TT_EXPLODE = {"tt_stator": [0, 0, 0], "tt_bearing_6705": [0, 0, -14], "tt_retainer": [0, 0, -24], "tt_rotor": [0, 0, 18],
              "pinion": [24, 0, 18], "pinion_axle": [24, 0, 0], "tt_beam": [0, 0, 34], "tt_pin*": [0, 0, 46]}


def turntable_scene(angle=30.0):
    """Turntable on the ground (base layer 0, rotor layer 1) turned to `angle`, an
    8T pinion on the base's middle edge hole and an H-beam 1x7 locked on top."""
    I = []
    for b in P.turntable().bodies:
        sh = rotated(b.shape, (0, 0, 1), angle) if b.name == "rotor" else b.shape
        I.append(Instance("tt_" + b.name, [Body(b.name, moved(sh, 0, 0, PITCH), b.mat, b.printable)],
                          {"explode": TT_EXPLODE["tt_" + b.name]}))
    # pinion turns 5x the rotor's angle the other way; 22.5 deg puts a gap on the rotor tooth at 0
    for part, name, z in ((P.gear(8, "sb_dgrey"), "pinion", _lz(1)), (P.axle(2), "pinion_axle", GAP / 2)):
        inst = place(part, name, origin=(24.0, 0.0, z), extras={"explode": TT_EXPLODE[name]})
        I.append(Instance(name, [Body(b.name, rotated(b.shape, (0, 0, 1), 22.5 - 5 * angle, (24.0, 0.0, 0.0)), b.mat,
                                      b.printable) for b in inst.bodies], inst.extras))
    I.append(_along(P.beam(7, "sb_blue"), "tt_beam", _rot((-24.0, 0.0), angle), _rot((24.0, 0.0), angle), 2,
                    {"explode": TT_EXPLODE["tt_beam"]}))
    for x in (-8.0, 8.0):
        pin = _tl("tt_pin%d" % x, _rot((x, 0.0), angle), 2)
        pin.extras["explode"] = TT_EXPLODE["tt_pin*"]
        I.append(pin)
    return I


def flatlay(rows, gap=7.0, row_gap=10.0):
    """Lay parts out left-to-right in rows; each entry is (part, pose)."""
    poses = {"flat": ((1, 0, 0), (0, 1, 0)), "lay": ((0, 0, -1), (0, 1, 0)), "layr": ((0, 0, 1), (0, 1, 0))}
    out, y = [], 0.0
    for r, row in enumerate(rows):
        x, depth = 0.0, 0.0
        placed = []
        for k, (part, pose) in enumerate(row):
            xd, yd = poses[pose]
            bodies = [Body(b.name, frame(b.shape, xd, yd), b.mat, b.printable) for b in part.bodies]
            bb = bodies[0].shape.BoundBox
            for b in bodies[1:]:
                bb = bb.united(b.shape.BoundBox)
            dx, dy, dz = x - bb.XMin, y - bb.YMax, -bb.ZMin
            placed.append(Instance("%s_%d_%d" % (part.pid, r, k), [Body(b.name, moved(b.shape, dx, dy, dz), b.mat, b.printable)
                                                                   for b in bodies]))
            x += bb.XLength + gap
            depth = max(depth, bb.YLength)
        out += placed
        y -= depth + row_gap
    return out


def parts_kit_scene():
    rows = [
        [(P.beam(15, "sb_blue"), "flat"), (P.beam(11, "sb_white"), "flat"), (P.frame_beam(), "flat"), (P.lbeam(5, 3), "flat"),
         (P.bent_beam(), "flat"), (P.bent_beam(4, 4, 45.0, "sb_yellow"), "flat"), (P.turntable(), "flat")],
        [(P.beam(9, "sb_yellow"), "flat"), (P.beam(7, "sb_lgrey"), "flat"), (P.beam(5, "sb_blue"), "flat"), (P.t_beam(), "flat"),
         (P.thin_beam(5, "sb_blue"), "flat"), (P.semicube(), "flat"), (P.block_1x2(), "flat"), (P.cross_block(3), "flat"),
         (P.angle_hinge(), "flat"), (P.bearing_beam(), "flat")],
        [(P.axle(8), "lay"), (P.axle(5), "lay"), (P.axle(3, stop=True), "lay"), (P.quick_pin(), "lay"), (P.quick_pin(True), "lay"),
         (P.quick_pin(length=3), "lay"), (P.axle_pin(), "lay"), (P.ball_pin(), "lay"), (P.pin_with_hole(), "lay"),
         (P.tl_pin(2), "layr"), (P.tl_pin(3, smooth=True, state="locked"), "layr"), (P.tl_collar(), "flat"),
         (P.tl_collar("locked"), "flat"), (P.bush(), "flat"), (P.half_bush(), "flat")],
        [(P.gear(40, "sb_lgrey"), "flat"), (P.clutch_gear(), "flat"), (P.bevel_gear(36, "sb_dgrey"), "flat"),
         (P.bevel_gear(20, "sb_yellow"), "flat"), (P.gear(16, "sb_lgrey"), "flat"), (P.bevel_gear(12), "flat"),
         (P.gear(8, "sb_dgrey"), "flat"), (P.worm_gear(), "lay"), (P.gear_rack(8, "sb_yellow"), "flat")],
        [(P.wheel(), "flat"), (P.mecanum_wheel(1), "flat"), (P.omni_wheel(), "flat"), (P.wheel(30.0, 14.0, 21.0), "flat"),
         (P.angle_connector(6), "flat"), (P.angle_connector(4), "flat"), (P.angle_connector(2), "flat"),
         (P.axle_joiner(), "lay"), (P.cable_clip(), "lay"), (P.semikey(), "flat")],
    ]
    return flatlay(rows)


def modules_scene():
    I = [place(MO.brain_hub(), "hub", origin=(-110.0, -24.0, 0.0)),
         place(MO.motor_m(), "motor", origin=(-6.0, -12.0, 0.0)),
         place(MO.sensor_ultrasonic(), "ultrasonic", origin=(48.0, -24.0, 0.0)),
         place(MO.sensor_line(), "line", origin=(84.0, -24.0, 0.0)),
         place(MO.module_by_code("COLOR"), "color", origin=(120.0, -12.0, 0.0)),
         place(MO.module_by_code("BTN"), "button", origin=(-6.0, 32.0, 0.0)),
         place(MO.module_by_code("ENV"), "env", origin=(40.0, 40.0, 0.0))]
    plug = MO.semilink_plug()
    I.append(place(plug, "plug", (0, 1, 0), (0, 0, 1), (92.0, 44.0, 3.4)))
    return I


def hub_scene():
    return [place(MO.brain_hub(), "hub", origin=(-44.0, -24.0, 0.0))]


def semilink_scene():
    """Plug hovering in front of the hub port B, keyed sides aligned."""
    I = [place(MO.brain_hub(), "hub", origin=(-88.0, -24.0, 0.0))]
    plug = MO.semilink_plug()
    I.append(place(plug, "plug", (0, 1, 0), (0, 0, 1), (14.0, 0.0, 18.0)))
    return I


def semikey_scene():
    I = [place(P.semikey(), "semikey", origin=(0.0, 0.0, 0.0))]
    I.append(place(P.axle(5), "axle5", (0, 0, -1), (0, 1, 0), (4.1, 4.8, 3.4)))
    I.append(place(P.tl_pin(2, state="open"), "tlpin", (1, 0, 0), (0, 0, -1), (-20.0, -2.0, 2.4)))
    return I


# ================================================================ shots
# view.dir = direction from target to camera (CAD frame). fit = fraction of
# the frame the subject should fill. Anchors are CAD points (mm) for callouts.
def _rover_anchors():
    return [
        {"label": "Junior Brain (ESP32-S3) - screen, 6 ports", "p": [10, 0, 72]},
        {"label": "Ultrasonic 'eyes' sensor", "p": [63.1, -12.6, 35.0]},
        {"label": "TwistLock pins - green = locked", "p": [56, -34.5, 28]},
        {"label": "TwistLock collar keeps the wheel on", "p": [0, -75.2, 31.0]},
        {"label": "SemiLink-6 cable, latching plug", "p": [44, -36, 44]},
        {"label": "15L H-beam rail (Technic grid)", "p": [44.0, -31.9, 30.5]},
        {"label": "Line sensor x5 underneath", "p": [40.0, -23.9, 12.0]},
    ]


SHOTS = [
    {"name": "hero-rover", "scene": "rover", "size": [2000, 1250], "view": {"dir": [1.0, -0.95, 0.62], "lens": 70, "fit": 0.86},
     "title": "SemiBlock Junior - Junior Rover concept"},
    {"name": "rover-callouts", "scene": "rover", "size": [2000, 1250], "view": {"dir": [1.0, -0.95, 0.62], "lens": 70, "fit": 0.6},
     "title": "Junior Rover - what is in the build", "anchors": _rover_anchors()},
    {"name": "rover-exploded", "scene": "rover_exploded", "size": [2000, 1250], "view": {"dir": [1.0, -0.9, 0.7], "lens": 60, "fit": 0.9},
     "title": "Junior Rover - exploded"},
    {"name": "twistlock-exploded", "scene": "tl_exploded", "size": [2000, 900], "view": {"dir": [-0.25, -1.0, 0.55], "lens": 100, "fit": 0.6},
     "title": "TwistLock Pin - two moulded parts",
     "anchors": [
         {"label": "Knob + cam core (POM). Magenta = lock part", "p": [-24.6, -2.6, 1.5]},
         {"label": "Wing grip: turn with fingertip or SemiKey", "p": [-26.0, -2.7, 0.0]},
         {"label": "Status windows", "p": [-25.2, 0.0, 2.2]},
         {"label": "D-cam: flats = fingers free, arcs = fingers blocked", "p": [-11.0, -0.95, 0.0], "side": "bottom"},
         {"label": "Status ring: red = open, green = locked", "p": [0.04, -1.6, 1.6], "side": "top"},
         {"label": "Flange sits flush in the 6.2 mm counterbore", "p": [0.4, -2.55, -1.45], "side": "bottom"},
         {"label": "Anti-spin ribs (sleeve stays put while you turn)", "p": [4.5, -1.75, 1.75]},
         {"label": "Split fingers", "p": [12.5, 0.0, 2.4]},
         {"label": "Catch lip with 45 deg ramp", "p": [15.4, -2.3, 1.4]},
     ]},
    {"name": "twistlock-section", "scene": "tl_section", "size": [2000, 1000], "view": {"dir": [1.0, 0.18, 0.32], "lens": 120, "fit": 0.62, "ortho": True},
     "title": "TwistLock Pin - section through two beams",
     "anchors": [
         {"label": "OPEN: windows show RED", "p": [-2.2, 8.0, 1.2]},
         {"label": "Cam flats leave 0.35 mm - fingers can flex in", "p": [0, 8.0, -12.5]},
         {"label": "Lip passes the bore when pulled (45 deg ramp)", "p": [0, 10.6, -15.3]},
         {"label": "LOCKED: windows show GREEN", "p": [0, 33.8, 0.6]},
         {"label": "Cam arcs block the fingers - lip cannot retract", "p": [0, 36.0, -12.5]},
         {"label": "Lip held behind the counterbore step", "p": [0, 38.6, -15.3]},
     ]},
    {"name": "twistlock-step-1", "scene": "tl_step1", "size": [900, 900], "view": {"dir": [0.9, -1.0, 0.85], "lens": 85, "target": [0, 0, 2], "dist": 108}},
    {"name": "twistlock-step-2", "scene": "tl_step2", "size": [900, 900], "view": {"dir": [0.9, -1.0, 0.85], "lens": 85, "target": [0, 0, 2], "dist": 108}},
    {"name": "twistlock-step-3", "scene": "tl_step3", "size": [900, 900], "view": {"dir": [0.9, -1.0, 0.85], "lens": 85, "target": [0, 0, 2], "dist": 108}},
    {"name": "twistlock-knob-open", "scene": "tl_step0", "size": [600, 600], "ground": False,
     "view": {"dir": [0.3, -0.45, 1.0], "lens": 85, "target": [0, 0, 2.0], "dist": 28}},
    {"name": "twistlock-knob-locked", "scene": "tl_step3", "size": [600, 600], "ground": False,
     "view": {"dir": [0.3, -0.45, 1.0], "lens": 85, "target": [0, 0, 2.0], "dist": 28}},
    {"name": "collar", "scene": "collar", "size": [2000, 1100], "view": {"dir": [1.0, -0.45, 0.4], "lens": 100, "fit": 0.62},
     "title": "TwistLock Collar - axle lock",
     "anchors": [
         {"label": "OPEN: pointer on red, slides freely", "p": [8.5, 2.9, 0.0]},
         {"label": "LOCKED: pointer on green, grips the axle", "p": [8.5, 30.0, 2.9]},
         {"label": "Knurled ring - turn 1/4 by hand", "p": [6.0, 26.3, 0.0]},
         {"label": "Works on any 4.8 mm cross axle", "p": [14.0, 27.7, 0.0]},
     ]},
    {"name": "collar-exploded", "scene": "collar_exploded", "size": [1800, 1000], "view": {"dir": [1.0, -0.7, 0.55], "lens": 100, "fit": 0.6},
     "title": "TwistLock Collar - collet + oval cam ring",
     "anchors": [
         {"label": "Ring with oval bore (cam)", "p": [-7.0, -3.7, 0.0]},
         {"label": "Collet: two jaws + cam pads", "p": [2.0, 0.0, 2.85]},
         {"label": "Axle slides through freely when open", "p": [-14.0, -2.3, 0.0]},
     ]},
    {"name": "beam-features", "scene": "beam_features", "size": [2000, 950], "view": {"dir": [0.55, -1.0, 0.75], "lens": 85, "fit": 0.62},
     "title": "H-beam + axle - small changes that help kids",
     "anchors": [
         {"label": "8 mm pitch, 4.85 mm holes: mixes with Technic", "p": [12.0, 0.0, 7.8]},
         {"label": "Counterbore = the seat the lock lip catches", "p": [40.0, 2.75, 7.1]},
         {"label": "Length printed on a solid pad", "p": [4.0, -3.7, 3.9]},
         {"label": "H-section: pockets between the holes, 26% less plastic", "p": [20.0, -2.4, 3.9]},
         {"label": "Tick every hole, big tick every 5th", "p": [32.0, -3.7, 6.6]},
         {"label": "Axle notch every 8 mm: count = length", "p": [-15.9, -16.0, 4.75]},
     ]},
    {"name": "hbeam-section", "scene": "hbeam_section", "size": [2000, 1050],
     "view": {"dir": [1.0, -0.32, 0.45], "lens": 100, "fit": 0.7},
     "title": "H-beam vs stage-1 solid beam - cut between two holes",
     "anchors": [
         {"label": "Stage 1: solid between the holes", "p": [28.05, 16.0, 3.9]},
         {"label": "Stage 2: H-section, same outside size", "p": [28.05, -14.0, 7.0]},
         {"label": "Flanges carry the pin faces (1.8 mm)", "p": [28.05, -11.2, 6.9]},
         {"label": "Web 1.6 mm", "p": [28.05, -14.0, 3.0]},
         {"label": "Pocket on both sides", "p": [27.8, -15.5, 3.9]},
         {"label": "Tube round every hole keeps pins tight", "p": [24.0, -17.45, 3.9]},
     ]},
    {"name": "angles", "scene": "angles", "size": [2000, 1350], "view": {"dir": [0.15, -1.0, 1.25], "lens": 70, "fit": 0.86},
     "title": "Building at any angle with H-beams",
     "anchors": [
         {"label": "AngleLock hinge: 15 deg steps, one TwistLock", "p": [0.0, 22.0, 18.6]},
         {"label": "Hinge arms pin to any beam", "p": [28.0, 22.0, 15.95]},
         {"label": "3-4-5 triangle: 90, 53.13 and 36.87 deg, exact on the grid", "p": [92.0, 34.0, 23.95]},
         {"label": "SemiCube spacer + 3L pin close the triangle", "p": [78.5, 18.05, 14.0]},
         {"label": "Equal sides = 60 deg. Every triangle is rigid", "p": [10.0, -39.61, 23.95]},
         {"label": "Bent H-beams: 53 deg (on the grid) and 45 deg", "p": [110.0, -58.0, 7.95]},
     ]},
    {"name": "hinge-exploded", "scene": "hinge_exploded", "size": [1800, 1250], "view": {"dir": [0.85, -1.0, 0.8], "lens": 85, "fit": 0.62},
     "title": "AngleLock hinge - two identical halves",
     "anchors": [
         {"label": "24 face teeth: one step = 15 deg", "p": [5.2, -3.0, 8.3]},
         {"label": "Identical halves: flip one over", "p": [14.14, 14.14, 31.95]},
         {"label": "Ticks every 15 deg, long every 45 deg", "p": [3.85, -6.67, 31.95]},
         {"label": "One TwistLock Pin 2L clamps the teeth", "p": [0.0, 0.0, 52.6]},
         {"label": "Pin holes 2 and 3 modules out", "p": [16.0, 0.0, 7.95]},
     ]},
    {"name": "bearing-exploded", "scene": "bearing_exploded", "size": [1800, 1300], "view": {"dir": [0.9, -1.0, 0.55], "lens": 85, "fit": 0.66},
     "title": "Bearing beam 1x5 - four parts, assembled at the factory",
     "anchors": [
         {"label": "Housing pins to any beam through holes 1 and 5", "p": [16.0, 0.0, 15.95]},
         {"label": "MR128ZZ steel ball bearing, 8 x 12 x 3.5", "p": [-4.27, -4.27, 25.2]},
         {"label": "Retainer ring traps the bearing", "p": [0.0, -6.85, 35.4]},
         {"label": "POM hub with the axle cross turns with the axle", "p": [0.0, -4.75, 45.0]},
     ]},
    {"name": "bearing-section", "scene": "bearing_section", "size": [1800, 1150], "view": {"dir": [0.25, 1.0, 0.3], "lens": 100, "fit": 0.72},
     "title": "Bearing beam - section through the axle",
     "anchors": [
         {"label": "Outer ring pressed into the housing", "p": [5.65, 0.05, 13.1]},
         {"label": "Hub pressed into the inner ring", "p": [4.35, 0.05, 12.0]},
         {"label": "Shoulder + retainer: the bearing cannot move", "p": [5.9, 0.05, 15.4]},
         {"label": "Collars touch only the turning hub", "p": [3.0, 0.05, 16.3]},
         {"label": "Axle cross drives the hub", "p": [0.0, 0.05, 21.5]},
         {"label": "Standard pin hole to the frame", "p": [18.6, 0.05, 12.0]},
     ]},
    {"name": "turntable", "scene": "turntable", "size": [2000, 1250], "view": {"dir": [0.85, -1.0, 0.8], "lens": 85, "fit": 0.62},
     "title": "Turntable 7x7 with ball bearing",
     "anchors": [
         {"label": "Ball bearing inside (6705ZZ): the top cannot wobble", "p": [0.0, -20.85, 8.0]},
         {"label": "40T rim: an 8T gear 3 modules away turns it", "p": [25.77, -1.77, 13.9]},
         {"label": "Ticks every 15 deg: read the angle", "p": [16.42, -4.4, 15.95]},
         {"label": "Base: 24 pin holes round the 7x7 frame", "p": [-16.0, -27.3, 7.95]},
         {"label": "Beam locked on with two TwistLocks", "p": [3.46, 2.0, 23.95]},
     ]},
    {"name": "turntable-exploded", "scene": "turntable_exploded", "size": [1800, 1350], "view": {"dir": [0.9, -1.0, 0.45], "lens": 85, "fit": 0.66},
     "title": "Turntable - four parts, assembled at the factory",
     "anchors": [
         {"label": "Rotor: 40T rim, pin + axle holes on the grid", "p": [20.8, 0.0, 28.0]},
         {"label": "4 snap fingers clip under the inner ring", "p": [12.8, 0.0, 18.4]},
         {"label": "Base: bearing seat with a lip on top", "p": [-24.0, 0.0, 7.9]},
         {"label": "6705ZZ thin-section bearing, 25 x 32 x 4", "p": [0.0, -16.0, -7.4]},
         {"label": "Retainer ring pressed in from below", "p": [0.0, -15.98, -17.9]},
     ]},
    {"name": "parts-kit", "scene": "parts_kit", "size": [2200, 1250], "view": {"dir": [0.15, -1.0, 1.25], "lens": 70, "fit": 0.92},
     "title": "Stage-2 mechanical parts"},
    {"name": "hub-front", "scene": "hub", "exposure": -0.4, "size": [1800, 1150], "view": {"dir": [1.0, -0.75, 0.75], "lens": 85, "fit": 0.58},
     "title": "Junior Brain - front",
     "anchors": [
         {"label": "1.54 in colour screen", "p": [18.0, 0.0, 31.6]},
         {"label": "Main button + RGB status ring", "p": [-10.0, 0.0, 32.4]},
         {"label": "A / B buttons", "p": [-10.0, -12.5, 32.2]},
         {"label": "Speaker", "p": [-23.0, -10.0, 31.9]},
         {"label": "Ports A B C - any motor or sensor", "p": [43.9, -16.0, 18.0]},
         {"label": "Pin holes on sides and bottom", "p": [12.0, -24.0, 12.0]},
     ]},
    {"name": "hub-back", "scene": "hub", "exposure": -0.4, "size": [1800, 1150], "view": {"dir": [-1.0, 0.8, 0.6], "lens": 85, "fit": 0.58},
     "title": "Junior Brain - back",
     "anchors": [
         {"label": "Ports D E F", "p": [-43.9, 16.0, 18.0]},
         {"label": "USB-C: charge + wired upload", "p": [-43.9, 0.0, 6.5]},
         {"label": "Keyed SemiLink socket", "p": [-43.9, 0.0, 18.0]},
     ]},
    {"name": "modules", "scene": "modules", "size": [2200, 1150], "view": {"dir": [0.55, -1.0, 0.85], "lens": 70, "fit": 0.85},
     "title": "Smart modules on the same 8 mm grid",
     "anchors": [
         {"label": "Junior Brain", "p": [-66.0, 0.0, 32.0]},
         {"label": "SemiMotor M", "p": [14.0, 0.0, 23.9]},
         {"label": "Ultrasonic", "p": [56.0, 0.0, 23.9]},
         {"label": "Line x5", "p": [92.0, 0.0, 23.9]},
         {"label": "Colour", "p": [128.0, 0.0, 15.9]},
         {"label": "Big button", "p": [2.0, 44.0, 9.4]},
         {"label": "Temp / humidity / pressure", "p": [48.0, 56.0, 7.9]},
         {"label": "SemiLink-6 plug", "p": [96.0, 44.0, 6.8]},
     ]},
    {"name": "semilink", "scene": "semilink", "size": [1800, 1100], "view": {"dir": [1.0, -0.8, 0.55], "lens": 100, "target": [10, 0, 17], "dist": 150},
     "title": "SemiLink-6 connector",
     "anchors": [
         {"label": "Keyed 'house' shape: cannot go in upside down", "p": [10.0, -4.2, 20.7]},
         {"label": "Latch clicks in - press tab to release", "p": [17.0, 0.0, 22.6]},
         {"label": "6 contacts: power, GND, 2 motor, 2 data", "p": [6.6, -4.5, 17.0]},
         {"label": "Strain relief + replaceable cable", "p": [22.0, -2.0, 17.8]},
     ]},
    {"name": "semikey", "scene": "semikey", "size": [2000, 1000], "view": {"dir": [0.3, -1.0, 1.3], "lens": 85, "fit": 0.62},
     "title": "SemiKey - one tool for the whole kit",
     "anchors": [
         {"label": "Axle gauge: lay the axle in, read its length", "p": [30.0, 4.8, 5.75]},
         {"label": "TwistLock key slot (extra torque)", "p": [-3.0, 0.0, 3.2]},
         {"label": "Pin lifter fork", "p": [80.0, 2.6, 3.2]},
         {"label": "Lanyard hole", "p": [62.0, -5.0, 3.2]},
     ]},
]


def build_scenes():
    sc = {}
    sc["rover"] = rover("locked")
    sc["rover_exploded"] = explode(sc["rover"], {i.name: i.extras.get("explode") for i in sc["rover"]})
    sc["tl_section"] = tl_section_scene()
    sc["tl_demo"] = tl_demo_scene()
    sc["tl_exploded"] = tl_exploded_scene()
    for k in (0, 1, 2, 3):
        sc["tl_step%d" % k] = tl_steps_scene(k)
    sc["collar"] = collar_scene()
    sc["collar_exploded"] = collar_exploded_scene()
    sc["beam_features"] = beam_features_scene()
    sc["parts_kit"] = parts_kit_scene()
    sc["modules"] = modules_scene()
    sc["hub"] = hub_scene()
    sc["semilink"] = semilink_scene()
    sc["semikey"] = semikey_scene()
    sc["hbeam_section"] = hbeam_section_scene()
    sc["angles"] = angles_scene()
    sc["hinge_exploded"] = hinge_exploded_scene()
    sc["bearing"] = bearing_scene()
    sc["bearing_section"] = bearing_scene()
    sc["bearing_exploded"] = explode(sc["bearing"], dict(BEARING_EXPLODE, axle="hide", collar_top="hide",
                                                         collar_bottom="hide"))
    sc["turntable"] = turntable_scene()
    sc["turntable_exploded"] = explode(turntable_scene(0.0), {"tt_stator": [0, 0, 0], "tt_bearing_6705": [0, 0, -14],
                                                               "tt_retainer": [0, 0, -24], "tt_rotor": [0, 0, 18],
                                                               "pinion": "hide", "pinion_axle": "hide", "tt_beam": "hide",
                                                               "tt_pin*": "hide"})
    return sc


# section planes applied at export: scene -> (keep_side, axis, position)
SECTIONS = {"tl_section": (-1, "x", 0.0), "hbeam_section": (-1, "x", 28.0), "bearing_section": (-1, "y", 0.0)}

# scenes exported for the interactive viewer (coarser tessellation)
VIEWER_SCENES = ["rover", "tl_demo", "collar", "angles", "bearing", "turntable", "hub", "modules", "parts_kit",
                 "semikey", "semilink"]

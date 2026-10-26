"""SemiBlock Junior - electronics: hub, motors, servo, SemiLink plug and the
parametric smart-module family (every sensor / output module is generated from
the MODULES table at the bottom of this file).

Housing rules (all modules):
  * outside = n x 8 mm - 0.2 mm in every axis, so modules sit on the beam grid
  * blind Technic holes (with counterbore + lock groove) on the bottom and sides
  * one keyed SemiLink-6 socket on the back (-X) face
  * white cover + base coloured by category (blue sense, yellow output,
    teal connect, violet AI, dark grey power); short code engraved on top
Local frame: X = depth (front is +X), Y = width, Z = height, origin at a corner.
"""
import math

import Part

from params import *  # noqa: F401,F403
from sbcad import (Body, PartDef, V, box, cone_between, cross_prism, cyl_between, edges_at_z, engrave,
                   frame, prism_xy, ring, rounded_box, rounded_rect_prism, sector, try_fillet, zcyl)

CATEGORY_MAT = {"sense": "sb_blue", "env": "sb_blue", "output": "sb_yellow", "connect": "sb_teal",
                "ai": "sb_violet", "power": "sb_dgrey", "motor": "sb_yellow"}
CATEGORY_NAME = {"sense": "Sensing", "env": "Environment & science", "output": "Output",
                 "connect": "Identify & connect", "ai": "AI & voice", "power": "Power & energy"}


# ======================================================== housing helpers
def grid(n, start=4.0):
    return [start + PITCH * i for i in range(n)]


def grid_holes(face, positions, cell, depth=PITCH - 0.1):
    """Blind Technic holes (with counterbore) into a housing face.
    face: '+x','-x','+y','-y','+z','-z'; positions: (u, v) = the two other
    housing coordinates in xyz order."""
    lx, ly, lz = cell
    tools = []
    for u, v in positions:
        ax = "xyz".index(face[1])
        plane = (cell[ax] - 0.1) if face[0] == "+" else 0.1
        sgn = -1 if face[0] == "+" else 1

        def pt(d):
            p = [0.0, 0.0, 0.0]
            others = [i for i in range(3) if i != ax]
            p[others[0]], p[others[1]] = u, v
            p[ax] = plane + sgn * d
            return tuple(p)
        tools.append(cyl_between(HOLE_D / 2, pt(-1.0), pt(depth)))
        tools.append(cyl_between(CB_D / 2, pt(-1.0), pt(CB_DEPTH)))
    return tools


def housing(nx, ny, nz, r=1.6):
    cell = (nx * PITCH, ny * PITCH, nz * PITCH)
    return rounded_box(0.1, 0.1, 0.1, cell[0] - 0.1, cell[1] - 0.1, cell[2] - 0.1, r), cell


def link_profile(w, h, ch, z0, z1):
    """SemiLink 'house' profile (two keyed corners), w along X, h along Y."""
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2 - ch), (w / 2 - ch, h / 2),
           (-w / 2 + ch, h / 2), (-w / 2, h / 2 - ch)]
    return prism_xy(pts, z0, z1)


def socket_parts(origin, normal_dir, up_dir, depth=9.0):
    """Cavity cutter + dark insert + gold contacts for a SemiLink socket whose
    opening sits at `origin` on a face with outward normal `normal_dir`.
    `up_dir` is the keyed (chamfered) side of the opening."""
    n, u = V(*normal_dir), V(*up_dir)
    x = u.cross(n)
    xd, yd = (x.x, x.y, x.z), (u.x, u.y, u.z)
    cav = link_profile(SEMILINK_W + 0.4, SEMILINK_H + 0.4, 1.5, -depth, 0.5)
    insert = link_profile(SEMILINK_W + 0.4, SEMILINK_H + 0.4, 1.5, -depth, -depth + 1.6)
    tongue = box(-3.4, -1.2, -depth + 1.5, 3.4, 0.6, -depth + 5.0)
    contacts = Part.makeCompound([box(-3.1 + 1.24 * i, 0.58, -depth + 2.0, -2.5 + 1.24 * i, 0.72, -depth + 4.8)
                                  for i in range(6)])
    return (frame(cav, xd, yd, origin), frame(insert.fuse(tongue), xd, yd, origin),
            frame(contacts, xd, yd, origin))


def _two_tone(shell, tools, cell, base_mat, top_mat="sb_white", zb=2.4):
    body = shell.cut(tools)
    lx, ly, lz = cell
    slab = box(-1, -1, -1, lx + 1, ly + 1, zb)
    return [Body("base", body.common(slab), base_mat), Body("cover", body.cut(slab), top_mat)]


# ============================================================ SemiLink plug
def semilink_plug(with_cable_stub=True):
    """SemiLink-6 plug in socket frame: front (contacts) at z = -8, grip outside z > 0."""
    front = link_profile(SEMILINK_W, SEMILINK_H, 1.2, -8.0, 0.2)
    grip = rounded_box(-5.3, -3.8, 0.2, 5.3, 3.4, 5.4, 1.0)
    ridges = [box(-5.6, -2.8 + 1.2 * i, 0.8, 5.6, -2.3 + 1.2 * i, 4.6) for i in range(5)]
    latch_arm = box(-1.6, SEMILINK_H / 2 - 0.05, -6.5, 1.6, SEMILINK_H / 2 + 0.55, 3.5)
    hook = box(-1.6, SEMILINK_H / 2 + 0.5, -5.6, 1.6, SEMILINK_H / 2 + 1.05, -4.4)
    tab = rounded_box(-2.4, 3.2, 1.0, 2.4, 4.6, 5.2, 0.5)
    relief = cone_between(2.3, 1.75, (0, -0.2, 5.3), (0, -0.2, 9.5))
    body = front.fuse(ridges + [grip, latch_arm, hook, tab, relief]).removeSplitter()
    body = body.cut([box(-3.3 + 1.24 * i, -0.4, -8.5, -2.3 + 1.24 * i, 1.4, -6.8) for i in range(6)])
    bodies = [Body("plug", body, "sb_black")]
    contacts = Part.makeCompound([box(-3.1 + 1.24 * i, -0.1, -7.6, -2.5 + 1.24 * i, 0.5, -6.9) for i in range(6)])
    bodies.append(Body("contacts", contacts, "contact", printable=False))
    if with_cable_stub:
        bodies.append(Body("cable", cyl_between(1.5, (0, -0.2, 9.0), (0, -0.2, 22.0)), "cable", printable=False))
    return PartDef("SB-LINK", "SemiLink-6 plug + cable", bodies, {"family": "Motors & hub"})


# ================================================================== hub
def brain_hub():
    """Junior Brain: ESP32-S3 hub, 11 x 6 x 4 modules. Front = +X."""
    nx, ny, nz = HUB_MODULES
    shell, cell = housing(nx, ny, nz, r=2.4)
    lx, ly, lz = cell
    top = lz - 0.1
    tools, extra = [], []
    scx, scy = 62.0, ly / 2
    tools.append(rounded_rect_prism(scx, scy, 31.0, 31.0, 3.0, top - 0.9, top + 1))
    extra.append(Body("screen", rounded_rect_prism(scx, scy, 30.6, 30.6, 2.8, top - 0.9, top - 0.3), "glass_dark", False))
    face = [rounded_rect_prism(scx + 2.0, scy + sy * 6.5, 7.0, 4.2, 2.0, top - 0.3, top - 0.26) for sy in (-1, 1)]
    smile = sector(5.0, 6.3, 180, 120, top - 0.3, top - 0.26)
    smile.translate(V(scx - 3.0, scy, 0))
    extra.append(Body("screen_face", Part.makeCompound(face + [smile]), "screen_glow", False))
    bx = 34.0
    tools.append(zcyl(5.4, top - 1.6, top + 1, bx, scy))
    tools.append(ring(5.3, 6.4, top - 0.6, top + 1, bx, scy))
    extra.append(Body("button_main", zcyl(5.0, top - 1.6, top + 0.6, bx, scy), "sb_blue"))
    extra.append(Body("led_ring", ring(5.4, 6.3, top - 0.6, top - 0.15, bx, scy), "led_cyan", False))
    for sy in (-1, 1):
        tools.append(zcyl(3.3, top - 1.5, top + 1, bx, scy + sy * 12.5))
        extra.append(Body("button_%s" % ("l" if sy > 0 else "r"),
                          zcyl(3.0, top - 1.5, top + 0.4, bx, scy + sy * 12.5), "sb_lgrey"))
    for ix in range(3):
        for iy in range(9):
            tools.append(zcyl(0.6, top - 1.2, top + 1, 18.0 + 3.0 * ix, scy - 12.0 + 3.0 * iy))
    tools.append(engrave("semiblock", 4.6, 0.3, (9.0, scy, top), (0, 1, 0), (-1, 0, 0)))
    pz = 18.0
    for label, y in zip("ABC", (8.0, 24.0, 40.0)):
        cav, ins, con = socket_parts((lx - 0.1, y, pz), (1, 0, 0), (0, 0, 1))
        tools.append(cav)
        extra += [Body("port_" + label, ins, "port_black", False), Body("contacts_" + label, con, "contact", False)]
        tools.append(engrave(label, 3.6, 0.3, (lx - 0.1, y, 26.2), (0, 1, 0), (0, 0, 1)))
    for label, y in zip("DEF", (40.0, 24.0, 8.0)):
        cav, ins, con = socket_parts((0.1, y, pz), (-1, 0, 0), (0, 0, 1))
        tools.append(cav)
        extra += [Body("port_" + label, ins, "port_black", False), Body("contacts_" + label, con, "contact", False)]
        tools.append(engrave(label, 3.6, 0.3, (0.1, y, 26.2), (0, -1, 0), (0, 0, 1)))
    usb = frame(rounded_rect_prism(0, 0, 9.0, 3.3, 1.6, -7.0, 1.0), (0, -1, 0), (0, 0, 1), (0.1, scy, 6.5))
    tools.append(usb)
    extra.append(Body("usb_tongue", frame(box(-3.3, -0.35, -7.0, 3.3, 0.35, -2.0), (0, -1, 0), (0, 0, 1),
                                          (0.1, scy, 6.5)), "port_black", False))
    xs = grid(nx)
    tools += grid_holes("+y", [(x, z) for x in xs for z in (12.0, 20.0)], cell)
    tools += grid_holes("-y", [(x, z) for x in xs for z in (12.0, 20.0)], cell)
    tools += grid_holes("-z", [(x, y) for x in xs for y in grid(ny)], cell)
    body = shell.cut(tools)
    return PartDef("SB-HUB", "Junior Brain (ESP32-S3 hub)", [Body("shell", body, "sb_white")] + extra,
                   {"family": "Motors & hub"})


# =============================================================== motors
def motor(nx=5, code="M"):
    """SemiMotor: geared DC motor + encoder, output centred on the +Y face.
    Sockets on both ends (use either; second one daisy-chains)."""
    ny, nz = 3, 3
    shell, cell = housing(nx, ny, nz, r=2.0)
    lx, ly, lz = cell
    ox, oz = lx / 2, 12.0
    r_out = 7.0 if nx == 5 else 9.0
    tools = [cyl_between(r_out + 0.6, (ox, ly - 1.4, oz), (ox, ly + 1, oz))]
    out = cyl_between(r_out, (ox, ly - 1.4, oz), (ox, ly - 0.2, oz))
    out = out.fuse(cyl_between(3.6, (ox, ly - 6.0, oz), (ox, ly - 1.0, oz)))
    out = out.cut(frame(cross_prism(AXLE_HOLE_D, AXLE_HOLE_SPLINE, -7, 2), (1, 0, 0), (0, 0, 1), (ox, ly - 0.2, oz)))
    pins = 4.6 if nx == 5 else 6.4
    out = out.cut([cyl_between(0.9 if nx == 5 else HOLE_D / 2,
                               (ox + pins * math.cos(math.radians(a)), ly - 1.6, oz + pins * math.sin(math.radians(a))),
                               (ox + pins * math.cos(math.radians(a)), ly + 1, oz + pins * math.sin(math.radians(a))))
                   for a in (45, 135, 225, 315)])
    band = cyl_between(r_out + 0.55, (ox, ly - 1.35, oz), (ox, ly - 1.15, oz)).cut(
        cyl_between(r_out + 0.1, (ox, ly - 2, oz), (ox, ly, oz)))
    side = [x for x in grid(nx) if abs(x - ox) > r_out + 3]
    tools += grid_holes("+y", [(x, z) for x in side for z in (4.0, 12.0, 20.0)], cell)
    tools += grid_holes("-y", [(x, z) for x in grid(nx) for z in (4.0, 12.0, 20.0)], cell)
    tools += grid_holes("+z", [(x, y) for x in grid(nx) for y in grid(ny)], cell)
    tools += grid_holes("-z", [(x, y) for x in grid(nx) for y in grid(ny)], cell)
    extra = []
    for fx, nd in ((0.1, (-1, 0, 0)), (lx - 0.1, (1, 0, 0))):
        cav, ins, con = socket_parts((fx, 12.0, 12.0), nd, (0, 0, 1))
        tools.append(cav)
        extra += [Body("port", ins, "port_black", False), Body("contacts", con, "contact", False)]
    tools += grid_holes("+x", [(y, z) for y in (4.0, 20.0) for z in (4.0, 20.0)], cell)
    tools += grid_holes("-x", [(y, z) for y in (4.0, 20.0) for z in (4.0, 20.0)], cell)
    tools.append(engrave(code, 5.0, 0.3, (ox, 0.1, 12.0), (-1, 0, 0), (0, 0, 1)))
    body = shell.cut(tools)
    pid = "SB-MOT-%s" % code
    title = "SemiMotor %s (encoder motor%s)" % (code, ", high torque" if nx > 5 else "")
    return PartDef(pid, title, [Body("shell", body, "sb_white"), Body("output", out, "sb_yellow"),
                                Body("output_ring", band, "sb_blue", False)] + extra,
                   {"family": "Motors & hub"})


def motor_m():
    return motor(5, "M")


def servo(kind="180"):
    nx, ny, nz = 4, 2, 3
    shell, cell = housing(nx, ny, nz, r=1.6)
    lx, ly, lz = cell
    ox, oy = 20.0, 8.0
    tools = [zcyl(6.6, lz - 1.2, lz + 1, ox, oy)]
    out = zcyl(6.0, lz - 1.2, lz + 0.8, ox, oy).cut(cross_prism(AXLE_HOLE_D, AXLE_HOLE_SPLINE, lz - 2, lz + 2, ox, oy))
    out = out.cut([zcyl(0.8, lz - 0.6, lz + 2, ox + 4.2 * math.cos(math.radians(a)), oy + 4.2 * math.sin(math.radians(a)))
                   for a in (0, 90, 180, 270)])
    tools += grid_holes("+y", [(x, z) for x in (20.0, 28.0) for z in grid(nz)], cell)
    tools += grid_holes("-y", [(x, z) for x in (20.0, 28.0) for z in grid(nz)], cell)
    tools += grid_holes("-z", [(x, y) for x in (20.0, 28.0) for y in grid(ny)], cell)
    tools += grid_holes("+x", [(y, z) for y in grid(ny) for z in (4.0, 20.0)], cell)
    cav, ins, con = socket_parts((0.1, oy, 12.0), (-1, 0, 0), (0, 0, 1))
    tools.append(cav)
    tools.append(engrave(kind, 3.0, 0.3, (7.0, oy, lz - 0.1), (0, 1, 0), (-1, 0, 0)))
    parts = _two_tone(shell, tools, cell, "sb_yellow")
    title = "SemiServo %s" % ("180 deg (position)" if kind == "180" else "360 (continuous)")
    return PartDef("SB-SV%s" % kind, title, parts + [Body("output", out, "sb_white"),
                                                     Body("port", ins, "port_black", False),
                                                     Body("contacts", con, "contact", False)],
                   {"family": "Motors & hub"})


# ====================================================== face features
# Each feature works in a local "panel" frame: surface at z = 0, +z outward,
# (u, v) in the surface. It returns (cutters, [(shape, material), ...]).
def f_window(w, h, r=1.0, mat="glass_dark"):
    return [rounded_rect_prism(0, 0, w + 0.3, h + 0.3, r + 0.15, -0.8, 1.0)], \
           [(rounded_rect_prism(0, 0, w, h, r, -0.8, -0.25), mat)]


def f_dome(r, mat="dome_white", u=0.0, v=0.0):
    d = Part.makeSphere(r, V(u, v, -0.3)).common(zcyl(r + 0.1, -0.3, r + 1, u, v))
    return [zcyl(r + 0.25, -0.6, 1, u, v)], [(d, mat), (zcyl(r + 0.25, -0.6, -0.3, u, v), "sb_dgrey")]


def f_lens(r, ring_mat="led_cyan", u=0.0, v=0.0):
    cuts = [zcyl(r + 1.8, -0.9, 1, u, v)]
    bodies = [(zcyl(r, -0.9, -0.2, u, v), "glass_dark"),
              (ring(r + 0.25, r + 1.6, -0.9, -0.35, u, v), ring_mat)]
    return cuts, bodies


def f_can(r, h, top="glass_dark", body_mat="steel"):
    c = zcyl(r, -0.4, h)
    c = try_fillet(c, 0.4, edges_at_z(c, h))
    return [], [(c, body_mat), (zcyl(r * 0.45, h - 0.2, h + 0.06), top)]


def f_holes(rows, cols, pitch, r=0.55, depth=1.2):
    cuts = []
    for i in range(rows):
        for j in range(cols):
            cuts.append(zcyl(r, -depth, 1, (i - (rows - 1) / 2) * pitch, (j - (cols - 1) / 2) * pitch))
    return cuts, []


def f_circle_holes(rings=(0, 2.2, 4.4, 6.6), r=0.5, depth=1.2):
    cuts = []
    for R in rings:
        n = 1 if R == 0 else int(2 * math.pi * R / 1.9)
        for k in range(n):
            a = 2 * math.pi * k / n
            cuts.append(zcyl(r, -depth, 1, R * math.cos(a), R * math.sin(a)))
    return cuts, []


def f_button(r, mat="sb_yellow"):
    cap = zcyl(r, -0.9, 1.6)
    cap = try_fillet(cap, min(1.0, r / 3), edges_at_z(cap, 1.6))
    return [zcyl(r + 0.4, -0.9, 1)], [(cap, mat)]


def f_knob(r=4.0, h=6.0, flutes=True):
    base = zcyl(r + 0.9, -0.1, 0.6)
    k = zcyl(r, 0.5, h)
    k = try_fillet(k, 0.6, edges_at_z(k, h))
    if flutes:
        k = k.cut([zcyl(0.45, 1.2, h + 1, r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
                   for a in range(0, 360, 30)])
    mark = box(-0.45, 0.6, h - 0.2, 0.45, r - 0.8, h + 0.05)
    return [], [(base, "sb_dgrey"), (k, "sb_dgrey"), (mark, "sb_white")]


def f_slider(L):
    cuts = [rounded_rect_prism(0, 0, 1.8, L + 1.5, 0.85, -1.5, 1)]
    cap = rounded_box(-3.0, L / 4 - 2.6, 0.0, 3.0, L / 4 + 2.6, 3.4, 0.8)
    stem = box(-0.6, L / 4 - 0.6, -1.5, 0.6, L / 4 + 0.6, 0.2)
    return cuts, [(cap, "sb_dgrey"), (stem, "sb_dgrey")]


def f_joystick():
    boot = Part.makeSphere(7.0).common(zcyl(7.1, 0, 4.0))
    stick = zcyl(1.6, 3.0, 9.0)
    cap = zcyl(4.6, 8.5, 12.0)
    cap = try_fillet(cap, 1.4, edges_at_z(cap, 12.0))
    return [zcyl(7.3, -0.6, 1)], [(boot, "rubber"), (stick, "sb_dgrey"), (cap, "sb_dgrey")]


def f_keypad(rows=4, cols=3, pitch=6.8):
    keys = [rounded_rect_prism((i - (rows - 1) / 2) * pitch, (j - (cols - 1) / 2) * pitch, 5.4, 5.4, 1.2, -0.3, 0.9)
            for i in range(rows) for j in range(cols)]
    return [], [(Part.makeCompound(keys), "sb_lgrey")]


def f_pad(r):
    return [zcyl(r + 0.3, -0.4, 1)], [(zcyl(r, -0.4, -0.05), "steel"), (ring(r * 0.55, r * 0.62, -0.06, -0.02), "sb_dgrey")]


def f_force(r=4.0):
    cap = zcyl(r, 0.4, 2.2)
    cap = try_fillet(cap, 0.8, edges_at_z(cap, 2.2))
    return [], [(zcyl(r + 1.4, -0.1, 0.5), "sb_dgrey"), (cap, "sb_black")]


def f_bar(L, w=6.0, h=5.0):
    bar = box(-w / 2, -L / 2, 1.6, w / 2, L / 2, 1.6 + h)
    posts = [box(-w / 2, sx * L / 2 - (6 if sx > 0 else 0), -0.1, w / 2, sx * L / 2 + (0 if sx > 0 else 6), 1.7)
             for sx in (-1, 1)]
    screws = [zcyl(1.5, 1.6 + h, 2.2 + h, 0, sx * (L / 2 - 3)) for sx in (-1, 1)]
    return [], [(bar, "steel"), (Part.makeCompound(posts), "sb_dgrey"), (Part.makeCompound(screws), "sb_dgrey")]


def f_chip(s=4.0):
    return [box(-s / 2 - 0.2, -s / 2 - 0.2, -0.6, s / 2 + 0.2, s / 2 + 0.2, 1)], \
           [(box(-s / 2, -s / 2, -0.6, s / 2, s / 2, -0.25), "glass_dark")]


def f_coin(r=4.0, mat="steel"):
    return [], [(zcyl(r, -0.1, 0.8), mat)]


def f_piezo(r=5.5):
    return [], [(zcyl(r, -0.1, 0.4), "brass"), (zcyl(r * 0.62, 0.4, 0.55), "sb_white")]


def f_compass():
    arrow = prism_xy([(0, 4.0), (-1.8, -2.0), (0, -0.8), (1.8, -2.0)], -0.02, 0.3)
    return [], [(ring(4.6, 5.2, -0.02, 0.2), "sb_dgrey"), (arrow, "ind_red")]


def f_fork(length, w, traces=False):
    tongue = prism_xy([(-w / 2, -0.5), (w / 2, -0.5), (w / 2, length - w / 2), (0, length), (-w / 2, length - w / 2)],
                      -0.8, 0.8)
    tongue = frame(tongue, (1, 0, 0), (0, 0, 1))          # local (u, out) plane, thickness along v
    bodies = [(tongue, "pcb")]
    if traces:
        tr = [box(-w / 2 + 1.5 + i * (w - 3) / 5, 0.8, 3.0, -w / 2 + 2.3 + i * (w - 3) / 5, 0.86, length - w / 2 - 2)
              for i in range(6)]
        bodies.append((frame(Part.makeCompound(tr), (1, 0, 0), (0, 1, 0)), "contact"))
    return [], bodies


def f_probe(cable_len=26.0, tip_len=22.0, tip_r=3.0, tip_mat="steel", glass=False, pins=False):
    cab = zcyl(1.7, -0.5, cable_len)
    grom = zcyl(2.6, -0.3, 3.0)
    tip = zcyl(tip_r, cable_len, cable_len + tip_len)
    bodies = [(cab, "cable"), (grom, "sb_black"), (tip, "sb_black" if glass else tip_mat)]
    end = cable_len + tip_len
    if glass:
        bodies.append((Part.makeSphere(tip_r * 0.85, V(0, 0, end)).common(zcyl(tip_r, end, end + tip_r)), "dome_white"))
    elif pins:
        bodies.append((Part.makeCompound([zcyl(0.6, end, end + 6.0, sx * 1.6, 0) for sx in (-1, 1)]), "steel"))
    else:
        bodies.append((Part.makeSphere(tip_r, V(0, 0, end)).common(zcyl(tip_r, end, end + tip_r)), tip_mat))
    return [], bodies


def f_finger():
    groove = cyl_between(3.4, (0, -9.0, 1.6), (0, 9.0, 1.6))
    return [groove], [(box(-1.0, -1.5, -1.85, 1.0, 1.5, -1.75), "led_red")]


def f_patch(s=16.0):
    return [], [(box(-s / 2, -s / 2, -0.1, s / 2, s / 2, 2.5), "ceramic"), (zcyl(1.4, 2.5, 2.7, s * 0.12, 0), "steel")]


def f_camera():
    rim = ring(6.0, 8.0, -0.4, 2.6)
    lens = zcyl(6.0, -0.4, 1.6)
    leds = [Part.makeSphere(1.4, V(u, -9.5, 0)).common(zcyl(1.5, 0, 2, u, -9.5)) for u in (-11.0, 11.0)]
    return [zcyl(8.2, -0.6, 1)], [(rim, "steel"), (lens, "glass_dark"), (Part.makeCompound(leds), "led_white")]


def f_rfid(mat):
    arcs = [sector(R, R + 1.0, 45, 70, -0.02, 0.18) for R in (3.0, 6.0, 9.0)]
    arcs = [frame(a, (1, 0, 0), (0, 1, 0), (-6.0, -6.0, 0)) for a in arcs]
    dot = zcyl(1.4, -0.02, 0.18, -6.0, -6.0)
    return [], [(Part.makeCompound(arcs + [dot]), mat)]


def f_ring_leds(n=12, R=10.0, r=1.4):
    mats = ["led_red", "led_yellow", "led_green", "led_cyan"]
    out = {}
    cuts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        u, v = R * math.cos(a), R * math.sin(a)
        d = Part.makeSphere(r, V(u, v, -0.3)).common(zcyl(r + 0.1, -0.3, r, u, v))
        out.setdefault(mats[k % 4], []).append(d)
        cuts.append(zcyl(r + 0.2, -0.6, 1, u, v))
    return cuts, [(Part.makeCompound(v), m) for m, v in out.items()]


SMILE = ["00111100", "01000010", "10100101", "10000001", "10100101", "10011001", "01000010", "00111100"]


def f_matrix(p=2.9, s=2.3):
    lit, dark = [], []
    for i, row in enumerate(SMILE):
        for j, c in enumerate(row):
            px = rounded_rect_prism((i - 3.5) * p, (j - 3.5) * p, s, s, 0.4, -0.3, 0.2)
            (lit if c == "1" else dark).append(px)
    panel = rounded_rect_prism(0, 0, 8 * p + 1.0, 8 * p + 1.0, 1.0, -0.6, -0.29)
    return [rounded_rect_prism(0, 0, 8 * p + 1.4, 8 * p + 1.4, 1.2, -0.6, 1)], \
           [(panel, "glass_dark"), (Part.makeCompound(lit), "led_cyan"), (Part.makeCompound(dark), "port_black")]


def f_screen(w, h, lines=3):
    cuts, bodies = f_window(w, h, 1.0)
    bars = [box(-w / 2 + 1.6 + i * 3.0, -h / 2 + 2.0, -0.25, -w / 2 + 2.8 + i * 3.0, -h / 2 + 2.0 + (h - 4) * (0.9 - 0.25 * i), -0.2)
            for i in range(lines)]
    return cuts, bodies + [(Part.makeCompound(bars), "screen_glow")]


def f_segment(digits=4, dw=6.4, dh=10.0):
    cuts, bodies = f_window(dh + 3.0, digits * (dw + 2.0) + 2, 1.0)
    segs = []
    t = 0.9
    for d in range(digits):
        cu = (d - (digits - 1) / 2) * (dw + 2.0)
        w2, h2 = dw / 2 - 0.6, dh / 2 - 0.6
        for (a, b, c, e) in ((-w2, h2 - t / 2, w2, h2 + t / 2), (-w2, -t / 2, w2, t / 2), (-w2, -h2 - t / 2, w2, -h2 + t / 2),
                             (-w2 - t / 2, 0.3, -w2 + t / 2, h2 - 0.3), (w2 - t / 2, 0.3, w2 + t / 2, h2 - 0.3),
                             (-w2 - t / 2, -h2 + 0.3, -w2 + t / 2, -0.3), (w2 - t / 2, -h2 + 0.3, w2 + t / 2, -0.3)):
            segs.append(box(-e, cu + a, -0.25, -b, cu + c, -0.2))
    return cuts, bodies + [(Part.makeCompound(segs), "led_red")]


def f_fan(R=13.0):
    guard = ring(R, R + 1.4, 0, 3.0)
    spokes = [rotated_box(R + 0.5, a) for a in (45, 135, 225, 315)]
    hub = zcyl(3.2, 0, 3.4)
    blades = [frame(rounded_rect_prism(R * 0.55, 0, R * 0.8, 6.0, 2.8, 1.0, 1.9), (math.cos(math.radians(a)), math.sin(math.radians(a)), 0),
                    (-math.sin(math.radians(a)), math.cos(math.radians(a)), 0)) for a in (0, 120, 240)]
    return [zcyl(R + 0.2, -1.0, 1)], [(guard.fuse(spokes), "sb_white"), (hub, "sb_dgrey"), (Part.makeCompound(blades), "soft"),
                                      (zcyl(R + 0.2, -1.0, -0.6), "mesh_dark")]


def rotated_box(R, a):
    b = box(0, -0.6, 2.4, R, 0.6, 3.0)
    s = b.copy()
    s.rotate(V(0, 0, 0), V(0, 0, 1), a)
    return s


def f_pump():
    can = cyl_between(5.5, (-9.0, 0, 6.0), (4.0, 0, 6.0))
    head = cyl_between(6.5, (4.0, 0, 6.0), (10.0, 0, 6.0))
    feet = box(-8.0, -4.0, -0.1, 8.0, 4.0, 1.5)
    tubes = [cyl_between(1.7, (8.0, 0, 6.0 + dz), (16.0, 0, 6.0 + dz)) for dz in (-2.6, 2.6)]
    return [], [(can, "steel"), (head, "sb_white"), (feet, "sb_dgrey"), (Part.makeCompound(tubes), "tube")]


def f_terminals():
    blk = box(-4.0, -6.0, -0.1, 4.0, 6.0, 6.0)
    screws = [zcyl(1.6, 6.0, 6.4, 0.0, sy * 3.0) for sy in (-1, 1)]
    return [], [(blk, "terminal"), (Part.makeCompound(screws), "steel")]


def f_solar(w, h):
    cells, lines = [], []
    nc, nr = 4, 3
    cw, ch = (w - 2.0) / nc, (h - 2.0) / nr
    for i in range(nr):
        for j in range(nc):
            u = -h / 2 + 1.0 + ch * (i + 0.5)
            v = -w / 2 + 1.0 + cw * (j + 0.5)
            cells.append(rounded_rect_prism(u, v, ch - 0.6, cw - 0.6, 0.6, -0.3, 0.15))
            lines += [box(u - 0.1, v - cw / 2 + 0.5, 0.15, u + 0.1, v + cw / 2 - 0.5, 0.2),
                      box(u - ch / 2 + 0.5, v - 0.08, 0.15, u + ch / 2 - 0.5, v + 0.08, 0.2)]
    return [], [(Part.makeCompound(cells), "solar"), (Part.makeCompound(lines), "steel")]


def f_traffic():
    bodies, cuts = [], []
    for v, m in ((7.4, "led_red"), (0.0, "led_yellow"), (-7.4, "led_green")):
        hood = ring(3.0, 3.8, -0.2, 1.6, 0, v).cut(box(-5, v - 5, -1, 5, v - 0.2, 3))
        bodies += [(hood, "sb_black"), (Part.makeSphere(2.8, V(0, v, -0.5)).common(zcyl(3.0, -0.5, 2.0, 0, v)), m)]
        cuts.append(zcyl(3.0, -0.8, 1, 0, v))
    return cuts, bodies


def f_ir_pair():
    a = Part.makeSphere(1.5, V(-3.6, 0, 0.6)).common(zcyl(1.6, -0.3, 3, -3.6, 0)).fuse(zcyl(1.5, -0.3, 0.6, -3.6, 0))
    b = Part.makeSphere(1.5, V(3.6, 0, 0.6)).common(zcyl(1.6, -0.3, 3, 3.6, 0)).fuse(zcyl(1.5, -0.3, 0.6, 3.6, 0))
    return [zcyl(1.7, -0.5, 1, -3.6, 0), zcyl(1.7, -0.5, 1, 3.6, 0)], [(a, "ir_led"), (b, "glass_dark")]


def f_ir_txrx():
    tx = Part.makeSphere(1.8, V(-4.5, 0, 0.9)).common(zcyl(1.9, -0.3, 3, -4.5, 0)).fuse(zcyl(1.8, -0.3, 0.9, -4.5, 0))
    rxb = box(1.8, -2.6, -0.2, 7.0, 2.6, 2.6)
    rxd = Part.makeSphere(1.5, V(4.4, 0, 2.4)).common(zcyl(1.6, 2.4, 4.0, 4.4, 0))
    return [zcyl(2.0, -0.5, 1, -4.5, 0)], [(tx, "ir_led"), (rxb, "sb_black"), (rxd, "sb_black")]


def f_bumper(width):
    bar = rounded_box(-width / 2, -2.6, 4.5, width / 2, 2.6, 7.0, 0.8)
    arms = [zcyl(1.0, -0.5, 4.6, sx * (width / 2 - 4.0), 0) for sx in (-1, 1)]
    return [], [(bar, "sb_lgrey"), (Part.makeCompound(arms), "sb_dgrey")]


def f_emag(r=6.5):
    return [], [(ring(r, r + 1.2, -0.2, 2.2), "sb_dgrey"), (zcyl(r, -0.2, 2.0), "steel"), (ring(2.2, 3.0, 2.0, 2.05), "sb_dgrey")]


def f_pm():
    cuts = [box(-6.0 + 2.2 * i, -9.0, -1.0, -5.0 + 2.2 * i, 9.0, 1) for i in range(6)]
    return cuts, [(box(-7.0, -10.0, -1.4, 7.0, 10.0, -1.0), "mesh_dark")]


def f_led_row(n=4, pitch=6.4, r=1.7):
    mats = ["led_red", "led_green", "led_cyan", "led_yellow"]
    out, cuts = {}, []
    for k in range(n):
        v = (k - (n - 1) / 2) * pitch
        d = Part.makeSphere(r, V(0, v, -0.3)).common(zcyl(r + 0.1, -0.3, r, 0, v))
        out.setdefault(mats[k % 4], []).append(d)
        cuts.append(zcyl(r + 0.2, -0.6, 1, 0, v))
    return cuts, [(Part.makeCompound(v), m) for m, v in out.items()]


FACES = {"led_row": f_led_row, 
    "window": f_window, "dome": f_dome, "lens": f_lens, "can": f_can, "holes": f_holes, "circle_holes": f_circle_holes,
    "button": f_button, "knob": f_knob, "slider": f_slider, "joystick": f_joystick, "keypad": f_keypad, "pad": f_pad,
    "force": f_force, "bar": f_bar, "chip": f_chip, "coin": f_coin, "piezo": f_piezo, "compass": f_compass,
    "fork": f_fork, "probe": f_probe, "finger": f_finger, "patch": f_patch, "camera": f_camera, "rfid": f_rfid,
    "ring_leds": f_ring_leds, "matrix": f_matrix, "screen": f_screen, "segment": f_segment, "fan": f_fan, "pump": f_pump,
    "terminals": f_terminals, "solar": f_solar, "traffic": f_traffic, "ir_pair": f_ir_pair, "ir_txrx": f_ir_txrx,
    "bumper": f_bumper, "emag": f_emag, "pm": f_pm,
}


def _place_feature(where, cell, shapes, pos=(0, 0)):
    """Map panel-frame shapes to the housing: top (u->X, v->Y) or front (u->Y, v->Z)."""
    lx, ly, lz = cell
    if where == "top":
        o = (pos[0] if pos[0] else lx / 2 + 2.0, pos[1] if pos[1] else ly / 2, lz - 0.1)
        return [frame(s, (1, 0, 0), (0, 1, 0), o) for s in shapes]
    o = (lx - 0.1, pos[0] if pos[0] else ly / 2, pos[1] if pos[1] else lz / 2)
    return [frame(s, (0, 1, 0), (0, 0, 1), o) for s in shapes]


def smart_module(spec):
    nx, ny, nz = spec["size"]
    shell, cell = housing(nx, ny, nz, r=1.2 if nz == 1 else 1.6)
    lx, ly, lz = cell
    tools, bodies = [], []
    # mounting holes, kept clear of the back socket
    side_depth = min(PITCH - 0.1, ly / 2 - 0.4)
    side = [(x, z) for x in grid(nx) for z in grid(nz) if not (x < 10 and ly <= 24)]
    tools += grid_holes("+y", side, cell, side_depth)
    tools += grid_holes("-y", side, cell, side_depth)
    bot_depth = min(PITCH - 0.1, lz - 1.6)
    bottom = [(x, y) for x in grid(nx) for y in grid(ny) if not (x < 10 and abs(y - ly / 2) < 8.5)]
    if spec.get("bottom_holes", True):
        tools += grid_holes("-z", bottom, cell, bot_depth)
    cav, ins, con = socket_parts((0.1, ly / 2, lz / 2), (-1, 0, 0), (0, 0, 1), depth=min(9.0, lx - 4.0))
    tools.append(cav)
    bodies += [Body("port", ins, "port_black", False), Body("contacts", con, "contact", False)]
    for feat in spec["faces"]:
        where, name, args = feat[0], feat[1], feat[2] if len(feat) > 2 else {}
        pos = feat[3] if len(feat) > 3 else (0, 0)
        args = dict(args)
        if name == "rfid":
            args["mat"] = CATEGORY_MAT[spec["cat"]]
        cuts, bod = FACES[name](**args)
        tools += _place_feature(where, cell, cuts, pos)
        for k, (s, m) in enumerate(bod):
            bodies.append(Body("%s_%d" % (name, k), _place_feature(where, cell, [s], pos)[0], m, False))
    if spec.get("label", "top") == "top":
        tools.append(engrave(spec["code"], 2.6, 0.25, (3.6, ly / 2, lz - 0.1), (0, 1, 0), (-1, 0, 0)))
    parts = _two_tone(shell, tools, cell, CATEGORY_MAT[spec["cat"]], zb=min(2.4, lz * 0.3))
    return PartDef(spec["id"], spec["name"], parts + bodies, {"family": "Modules", "spec": spec})


# ------------------------------------------------- special-case modules
def sensor_ultrasonic():
    nx, ny, nz = SENSOR_MODULES
    shell, cell = housing(nx, ny, nz, r=1.6)
    lx, ly, lz = cell
    tools = grid_holes("+y", [(x, z) for x in grid(nx) for z in grid(nz)], cell)
    tools += grid_holes("-y", [(x, z) for x in grid(nx) for z in grid(nz)], cell)
    tools += grid_holes("-x", [(y, z) for y in grid(ny) for z in grid(nz)], cell)
    tools += grid_holes("-z", [(x, y) for x in grid(nx) for y in grid(ny)], cell)
    front = lx - 0.1
    tools.append(frame(rounded_rect_prism(0, 0, ly - 3.0, lz - 3.0, 2.0, -0.6, 1), (0, 1, 0), (0, 0, 1), (front, ly / 2, lz / 2)))
    panel = frame(rounded_rect_prism(0, 0, ly - 3.2, lz - 3.2, 1.9, -0.6, -0.1), (0, 1, 0), (0, 0, 1), (front, ly / 2, lz / 2))
    eyes, mesh, brows = [], [], []
    for sy in (-1, 1):
        cy = ly / 2 + sy * 12.6
        tools.append(cyl_between(8.2, (front - 3.0, cy, 12.0), (front + 1, cy, 12.0)))
        e = cyl_between(8.0, (front - 3.0, cy, 12.0), (front + 3.2, cy, 12.0)).cut(
            cyl_between(6.3, (front + 1.8, cy, 12.0), (front + 4, cy, 12.0)))
        eyes.append(e)
        mesh.append(cyl_between(6.4, (front + 1.6, cy, 12.0), (front + 1.9, cy, 12.0)))
        brows.append(frame(rounded_rect_prism(0, 0, 8.0, 1.5, 0.7, -0.1, 0.25), (0, 1, 0), (0, 0, 1), (front - 0.1, cy, 21.2)))
    cav, ins, con = socket_parts((8.0, 40.0, lz - 0.1), (0, 0, 1), (-1, 0, 0))
    tools.append(cav)
    tools.append(engrave("US", 3.0, 0.25, (8.0, 14.0, lz - 0.1), (0, 1, 0), (-1, 0, 0)))
    parts = _two_tone(shell, tools, cell, "sb_blue", zb=3.0)
    return PartDef("SB-S-US", "Ultrasonic distance", parts + [
        Body("panel", panel, "sb_blue", False),
        Body("eyes", Part.makeCompound(eyes), "steel", False), Body("mesh", Part.makeCompound(mesh), "mesh_dark", False),
        Body("brows", Part.makeCompound(brows), "led_cyan", False),
        Body("port", ins, "port_black", False), Body("contacts", con, "contact", False)],
        {"family": "Modules"})


def sensor_line():
    nx, ny, nz = SENSOR_MODULES
    shell, cell = housing(nx, ny, nz, r=1.6)
    lx, ly, lz = cell
    tools = grid_holes("+y", [(x, z) for x in grid(nx) for z in grid(nz)], cell)
    tools += grid_holes("-y", [(x, z) for x in grid(nx) for z in grid(nz) if not (x < 12 and z < 12)], cell)
    win, leds_on, leds_off = [], [], []
    for i, y in enumerate(grid(5, start=8.0)):
        tools.append(rounded_rect_prism(8.0, y, 4.2, 5.6, 1.2, -1, 0.7))
        win.append(rounded_rect_prism(8.0, y, 4.0, 5.4, 1.1, 0.25, 0.7))
        tools.append(zcyl(1.1, lz - 0.6, lz + 1, 12.0, y))
        dome = Part.makeSphere(1.0, V(12.0, y, lz - 0.6)).common(zcyl(1.1, lz - 0.6, lz + 1, 12.0, y))
        (leds_on if i in (1, 2) else leds_off).append(dome)
    cav, ins, con = socket_parts((8.0, 0.1, 8.0), (0, -1, 0), (0, 0, 1))
    tools.append(cav)
    tools.append(engrave("LINE", 2.6, 0.25, (4.0, 24.0, lz - 0.1), (0, 1, 0), (-1, 0, 0)))
    parts = _two_tone(shell, tools, cell, "sb_blue", zb=3.0)
    return PartDef("SB-S-LINE", "Line sensor x5", parts + [
        Body("windows", Part.makeCompound(win), "glass_dark", False),
        Body("leds_on", Part.makeCompound(leds_on), "led_red", False),
        Body("leds_off", Part.makeCompound(leds_off), "glass_dark", False),
        Body("port", ins, "port_black", False), Body("contacts", con, "contact", False)],
        {"family": "Modules"})


def angle_sensor(spec):
    """Axle-through magnetic angle sensor: an axle passes straight through."""
    p = smart_module(dict(spec, faces=[], bottom_holes=False))
    nx, ny, nz = spec["size"]
    cell = (nx * PITCH, ny * PITCH, nz * PITCH)
    cx, cy = 12.0, 12.0
    hole = zcyl(4.4, -1, cell[2] + 1, cx, cy)
    rotor = ring(2.6, 4.1, 0.6, cell[2] + 0.3, cx, cy).fuse(zcyl(2.8, 0.6, cell[2] + 0.3, cx, cy))
    rotor = rotor.cut(cross_prism(AXLE_HOLE_D, AXLE_HOLE_SPLINE, -1, cell[2] + 2, cx, cy))
    mark = box(cx - 0.35, cy + 2.9, cell[2] + 0.2, cx + 0.35, cy + 4.0, cell[2] + 0.35)
    out = []
    for b in p.bodies:
        if b.name in ("base", "cover"):
            out.append(Body(b.name, b.shape.cut(hole), b.mat))
        else:
            out.append(b)
    out += [Body("rotor", rotor, "sb_yellow", False), Body("mark", mark, "sb_dgrey", False)]
    return PartDef(spec["id"], spec["name"], out, p.meta)


# ======================================================= module catalogue
def M(code, name, zh, cat, size, faces, phase, chip, does, replaces="", label="top", **kw):
    d = dict(code=code, id="SB-%s" % code, name=name, zh=zh, cat=cat, size=size, faces=faces, phase=phase,
             chip=chip, does=does, replaces=replaces, label=label)
    d.update(kw)
    return d


S, S3, MM, C, P = (2, 2, 1), (2, 3, 1), (2, 4, 1), (2, 3, 2), (4, 4, 1)
T, F = "top", "front"

MODULES = [
    # ------------------------------------------------ sensing: distance / presence
    M("US", "Ultrasonic distance", "超聲波測距", "sense", (2, 6, 3), [], "P1", "RCWL-9610A + MCU",
      "2-400 cm distance, 'eyes' RGB LEDs", "HC-SR04 超声波模块", builder="ultrasonic"),
    M("TOF", "ToF laser distance", "激光測距 (ToF)", "sense", C, [(F, "lens", {"r": 1.4}, (8.0, 0)), (F, "lens", {"r": 1.4, "ring_mat": "sb_dgrey"}, (16.0, 0))],
      "P2", "VL53L1X (Class 1 laser, eye-safe)", "4-400 cm, narrow beam, fast", ""),
    M("IRP", "IR obstacle", "紅外避障", "sense", S3, [(F, "ir_pair", {})], "P1", "IR LED + phototransistor",
      "2-30 cm near/far, digital + analog", "避障传感器 / 光遮断"),
    M("PIR", "PIR motion", "人體紅外感應", "sense", C, [(F, "dome", {"r": 5.6})], "P1", "AM312 mini PIR",
      "detects people moving, 3-5 m", ""),
    M("RADAR", "mmWave presence", "毫米波人體存在", "sense", MM, [(T, "window", {"w": 9.0, "h": 18.0})], "P3",
      "HLK-LD2410 24 GHz", "detects people even when still", ""),
    M("ZONE", "Multi-zone ToF 8x8", "多區激光測距", "sense", C, [(F, "lens", {"r": 2.0}, (8.0, 0)), (F, "lens", {"r": 1.2, "ring_mat": "sb_dgrey"}, (16.5, 0))],
      "P3", "VL53L5CX", "8x8 depth map up to 4 m", ""),
    # ------------------------------------------------ sensing: line / colour / light
    M("LINE", "Line sensor x5", "循跡感應器 x5", "sense", (2, 6, 3), [], "P1", "5x ITR20001 + MCU auto-calibrate",
      "5-channel line position for line-follow races", "循迹传感器", builder="line"),
    M("COLOR", "Colour sensor", "顏色感應器", "sense", C, [(F, "lens", {"r": 3.0})], "P1", "TCS34725 + white LED",
      "RGB + clear light, colour sorting, light level", ""),
    M("GEST", "Gesture sensor", "手勢感應器", "sense", S3, [(T, "window", {"w": 4.0, "h": 9.0})], "P2", "APDS-9960",
      "up/down/left/right swipes, proximity", ""),
    M("LUX", "Light sensor", "光度感應器", "sense", S, [(T, "dome", {"r": 3.0})], "P1", "BH1750 (lux)",
      "ambient light in lux", "光敏电阻 / 魔术光杯"),
    M("UV", "UV index", "紫外線感應器", "sense", S, [(T, "dome", {"r": 3.0, "mat": "dome_violet"})], "P2", "LTR-390",
      "UV index + ambient light", ""),
    M("FLAME", "Flame sensor", "火焰感應器", "sense", S3, [(F, "window", {"w": 12.0, "h": 4.0, "mat": "ir_led"})], "P2",
      "3x IR phototransistor 760-1100 nm", "finds a candle flame (fire-fighting robot)", "火焰传感器"),
    M("IRT", "IR thermometer", "非接觸測溫", "sense", C, [(F, "can", {"r": 4.6, "h": 3.4})], "P2", "MLX90614",
      "no-contact temperature -70..380 C", ""),
    M("THERM", "Thermal camera 8x8", "熱成像鏡頭", "sense", C, [(F, "lens", {"r": 4.0})], "P3", "AMG8833",
      "8x8 heat image, finds warm bodies", ""),
    # ------------------------------------------------ sensing: touch / force / input
    M("BTN", "Big button", "大按鈕", "sense", S3, [(T, "button", {"r": 4.6})], "P1", "tactile switch + MCU",
      "press / release / long-press / count", "按键开关"),
    M("BUMP", "Bumper switch", "碰撞開關", "sense", S3, [(F, "bumper", {"width": 22.0})], "P1", "micro-switch",
      "robot hits a wall", ""),
    M("TOUCH", "Touch pad", "觸摸感應", "sense", S3, [(T, "pad", {"r": 4.6})], "P1", "capacitive touch",
      "touch / no touch, works through paper", "人体触摸"),
    M("FORCE", "Force sensor", "力度感應器", "sense", S3, [(T, "force", {"r": 3.6})], "P2", "strain gauge + MCU",
      "push force 0-10 N", ""),
    M("LOAD", "Weight (load cell 1 kg)", "稱重感應器", "sense", (2, 8, 1), [(T, "bar", {"L": 46.0}, (8.0, 0))], "P2",
      "1 kg load cell + HX711", "weighs objects to 1 g", ""),
    M("POT", "Rotary knob", "旋鈕", "sense", S, [(T, "knob", {"r": 3.6, "h": 6.0}, (9.6, 0))], "P1", "10k potentiometer",
      "0-100 % turn position", ""),
    M("ENC", "Rotary encoder", "旋轉編碼器", "sense", S, [(T, "knob", {"r": 3.6, "h": 8.0}, (9.6, 0))], "P1",
      "EC11 encoder + push", "endless clicks + push button", "旋转编码器"),
    M("SLIDE", "Slide control", "滑桿", "sense", (2, 6, 1), [(T, "slider", {"L": 34.0}, (9.0, 0))], "P2", "60 mm slide pot",
      "0-100 % slider position", ""),
    M("JOY", "Joystick", "搖桿", "sense", (3, 3, 1), [(T, "joystick", {}, (13.5, 0))], "P1", "2-axis + push",
      "x / y / push, drive a robot by hand", "XY摇杆"),
    M("KEYPAD", "Keypad 4x3", "鍵盤", "sense", P, [(T, "keypad", {"rows": 3, "cols": 4, "pitch": 6.2}, (19.0, 0))], "P2", "12-key capacitive",
      "enter numbers / passwords", ""),
    M("IMU", "Motion sensor (6-axis)", "動作感應 (六軸)", "sense", S, [(T, "chip", {"s": 3.0}, (10.0, 0))], "P2",
      "ICM-42670 accel + gyro", "tilt, shake, spin of a moving part", "倾斜开关 / 水银开关 / 震动开关"),
    M("KNOCK", "Knock / vibration", "敲擊 / 震動", "sense", S, [(T, "piezo", {"r": 4.4}, (9.6, 0))], "P2", "piezo disc",
      "knocks, taps, vibration strength", "敲击 / 震动开关"),
    M("ANGLE", "Angle sensor (axle-through)", "角度感應器", "sense", S3, [], "P1", "AS5600 magnetic encoder",
      "absolute angle of any axle that passes through", "", builder="angle"),
    M("MAG", "Magnetic sensor", "磁力感應器", "sense", S, [(T, "chip", {"s": 3.0}, (10.0, 0))], "P1",
      "linear Hall + threshold", "magnet near/far, N or S, strength", "霍尔 x2 / 线性霍尔 / 磁簧 x2"),
    M("COMPASS", "Compass", "電子指南針", "sense", S, [(T, "compass", {}, (9.6, 0))], "P2", "MMC5603 magnetometer",
      "heading 0-360 deg", ""),
    # ------------------------------------------------ environment & science
    M("ENV", "Temp / humidity / pressure", "溫度 / 濕度 / 氣壓", "env", MM, [(T, "holes", {"rows": 2, "cols": 6, "pitch": 2.6, "r": 0.7}, (10.0, 0))],
      "P1", "SHT40 + BMP280", "+-0.2 C, %RH, hPa, altitude", "DHT11 温湿度 / 模拟温度 / 数字温度"),
    M("PROBE", "Waterproof temp probe", "防水溫度探頭", "env", S3, [(F, "probe", {})], "P1", "DS18B20 stainless probe",
      "-55..125 C in water, soil, food", "18B20温度传感器"),
    M("SOIL", "Soil moisture", "土壤濕度", "env", S3, [(F, "fork", {"length": 46.0, "w": 12.0})], "P1",
      "capacitive (no corrosion)", "plant needs water? 0-100 %", "土壤湿度 (resistive)"),
    M("WATER", "Water level / rain", "水位 / 雨滴", "env", S3, [(F, "fork", {"length": 36.0, "w": 14.0, "traces": True})], "P2",
      "gold-plated traces", "water depth 0-35 mm, rain drops", "水位传感器"),
    M("SOUND", "Sound level", "聲音感應器", "env", S3, [(T, "circle_holes", {"rings": (0, 2.0, 4.0)}, (11.0, 0))], "P1",
      "MEMS mic + RMS", "loudness in dB, clap detect", "高感度声音 / 小麦克风"),
    M("CO2", "CO2 (NDIR)", "二氧化碳", "env", (2, 4, 2), [(T, "holes", {"rows": 2, "cols": 8, "pitch": 2.6, "r": 0.7}, (10.0, 0))],
      "P2", "Sensirion SCD40", "true CO2 ppm - classroom air", ""),
    M("AIR", "Air quality (TVOC)", "空氣質素", "env", S3, [(T, "holes", {"rows": 2, "cols": 4, "pitch": 2.6, "r": 0.7}, (10.0, 0))],
      "P2", "ENS160", "TVOC + eCO2 index", ""),
    M("PM", "Dust PM2.5", "懸浮粒子 PM2.5", "env", (4, 6, 3), [(T, "pm", {})], "P3", "Plantower PMSA003",
      "PM1 / PM2.5 / PM10 ug/m3", ""),
    M("GAS", "Gas / smoke", "氣體 / 煙霧", "env", C, [(T, "can", {"r": 5.0, "h": 7.0, "top": "mesh_dark"}, (10.4, 0))], "P3",
      "MQ-2 (heated, teacher use)", "smoke / LPG level", ""),
    M("PH", "pH probe", "酸鹼度", "env", MM, [(F, "probe", {"tip_r": 4.0, "glass": True})], "P3", "pH electrode + amp",
      "pH 0-14 for chemistry lessons", ""),
    M("TDS", "Water quality (TDS)", "水質 TDS", "env", MM, [(F, "probe", {"tip_r": 3.4, "pins": True})], "P3",
      "TDS probe + amp", "dissolved solids ppm", ""),
    M("HEART", "Heart rate & SpO2", "心率 / 血氧", "env", S3, [(T, "finger", {}, (11.0, 0))], "P2", "MAX30102",
      "pulse + oxygen for PE / biology", "手指测心跳"),
    M("GPS", "GPS", "衛星定位", "env", P, [(T, "patch", {}, (18.0, 0))], "P3", "ATGM336H GPS + BeiDou",
      "position + time outdoors", ""),
    # ------------------------------------------------ AI & voice
    M("CAM", "AI vision camera", "AI 視覺鏡頭", "ai", (3, 4, 4), [(F, "camera", {})], "P2", "ESP32-S3 + 2 MP camera",
      "face, colour, line, tag, QR, object recognition", ""),
    M("VOICE", "Offline voice", "離線語音識別", "ai", (3, 3, 1), [(T, "ring_leds", {"n": 8, "R": 6.5, "r": 1.1}, (13.5, 0)),
                                                          (T, "circle_holes", {"rings": (0,)}, (13.5, 0))], "P2",
      "ESP32-S3 / CI1302 voice chip", "Cantonese / Mandarin / English commands", ""),
    # ------------------------------------------------ identify & connect
    M("RFID", "RFID / NFC reader", "拍卡感應", "connect", P, [(T, "rfid", {}, (18.0, 0))], "P2", "PN532 13.56 MHz",
      "read cards, stickers, wristbands", ""),
    M("IRX", "IR remote send + receive", "紅外收發", "connect", S3, [(F, "ir_txrx", {})], "P1", "38 kHz IR LED + receiver",
      "TV / air-con remote codes", "红外发射 / 红外接收"),
    # ------------------------------------------------ output
    M("RGB", "RGB LED x4", "彩色燈 x4", "output", MM, [(T, "led_row", {}, (9.6, 0))],
      "P1", "4x WS2812B", "any colour, any brightness", "3色LED / 双色LED x2 / 七彩 / RGB"),
    M("RING", "LED ring x12", "燈環 x12", "output", P, [(T, "ring_leds", {"n": 12, "R": 10.2, "r": 1.4}, (19.0, 0))], "P2",
      "12x WS2812B", "spinners, timers, compass display", ""),
    M("MATRIX", "LED matrix 8x8", "點陣顯示", "output", P, [(T, "matrix", {}, (19.0, 0))], "P2", "64x WS2812-2020",
      "faces, icons, scrolling text", ""),
    M("TRAFFIC", "Traffic light", "交通燈", "output", (2, 2, 3), [(F, "traffic", {})], "P1", "3 LEDs",
      "red / yellow / green lessons", ""),
    M("OLED", "OLED screen 0.96 in", "顯示屏", "output", (3, 4, 1), [(T, "screen", {"w": 14.0, "h": 26.0}, (14.0, 0))], "P1",
      "SSD1306 128x64", "text, numbers, simple graphs", ""),
    M("SEG", "4-digit display", "數碼管", "output", (3, 6, 1), [(T, "segment", {}, (14.0, 0))], "P2", "TM1637",
      "big numbers: scores, timers", ""),
    M("SPK", "Speaker / MP3", "喇叭 / 音樂", "output", P, [(T, "circle_holes", {"rings": (0, 2.2, 4.4, 6.6, 8.8)}, (18.0, 0))],
      "P2", "I2S amp + 8 MB sound flash", "play sounds and recorded voice", "有源 / 无源蜂鸣器"),
    M("FAN", "Fan", "風扇", "output", (2, 4, 4), [(F, "fan", {})], "P1", "DC motor + soft blades + guard",
      "wind, cooling, hovercraft", ""),
    M("PUMP", "Water pump", "水泵", "output", (3, 4, 2), [(T, "pump", {}, (13.5, 0))], "P2", "5 V pump + tubes",
      "plant watering, fountains", ""),
    M("VIB", "Vibration motor", "震動馬達", "output", S, [(T, "coin", {"r": 4.4}, (9.6, 0))], "P2", "coin vibration motor",
      "buzz feedback", ""),
    M("EMAG", "Electromagnet", "電磁鐵", "output", C, [(F, "emag", {})], "P3", "5 V electromagnet",
      "pick up and drop steel parts", ""),
    M("SWITCH", "Power switch (12 V max)", "電源開關", "output", S3, [(T, "terminals", {}, (11.0, 0))], "P2",
      "MOSFET, 12 V / 2 A max", "switch lamps, pumps, LED strips safely", "继电器 (mains relay removed)"),
    # ------------------------------------------------ power & energy
    M("SOLAR", "Solar panel 1 W", "太陽能板", "power", (6, 8, 1), [(T, "solar", {"w": 58.0, "h": 40.0}, (26.0, 0))], "P2",
      "6 V 1 W panel + charge meter", "energy lessons, solar car", "", label="none"),
    M("METER", "Energy meter (V/I/W)", "電能錶", "power", MM, [(T, "screen", {"w": 8.0, "h": 18.0, "lines": 2}, (10.5, 0))],
      "P2", "INA219", "measures voltage, current, power", ""),
]


def build_module(spec):
    b = spec.get("builder")
    if b == "ultrasonic":
        return sensor_ultrasonic()
    if b == "line":
        return sensor_line()
    if b == "angle":
        return angle_sensor(spec)
    return smart_module(spec)


def module_by_code(code):
    return build_module(next(m for m in MODULES if m["code"] == code))

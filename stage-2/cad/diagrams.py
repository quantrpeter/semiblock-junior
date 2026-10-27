"""2D technical diagrams as SVG, drawn from the same params as the CAD.

    python3 stage-2/cad/diagrams.py   ->  stage-2/renders/*.svg
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from params import (AXLE_D, AXLE_SPLINE, BEAM_T, BEAM_W, CB_D, CB_DEPTH, GAP, HB_FLANGE, HB_POCKET_R,  # noqa: E402
                    HB_TUBE_D, HB_WEB, HOLE_D, PITCH, TL_BORE_D, TL_CAM_D, TL_CAM_FLATS, TL_LIP_D, TL_SLEEVE_D, TL_SLOT_W)

OUT = os.path.join(os.path.dirname(HERE), "renders")
os.makedirs(OUT, exist_ok=True)

INK, MUTED, BLUE, YEL, MAG, GREEN, RED = "#0f172a", "#5a6678", "#1f6fe5", "#ffc21a", "#c8209e", "#16a34a", "#e8322e"
FONT = "font-family='Arial, Helvetica, sans-serif'"


def svg(w, h, body, title):
    return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 %d %d' width='%d' height='%d' role='img' "
            "aria-label='%s'><rect width='100%%' height='100%%' fill='#f7f9fd'/>%s</svg>" % (w, h, w, h, title, body))


def t(x, y, s, size=16, fill=INK, anchor="start", weight="normal"):
    return "<text x='%.1f' y='%.1f' %s font-size='%d' fill='%s' text-anchor='%s' font-weight='%s'>%s</text>" % (
        x, y, FONT, size, fill, anchor, weight, s)


def arc_path(cx, cy, r0, r1, a0, a1, k):
    """Annular sector a0..a1 (deg, y up) as an SVG path, k = px per mm."""
    def P(r, a):
        return cx + r * k * math.cos(math.radians(a)), cy - r * k * math.sin(math.radians(a))
    large = 1 if (a1 - a0) % 360 > 180 else 0
    x0, y0 = P(r1, a0)
    x1, y1 = P(r1, a1)
    x2, y2 = P(r0, a1)
    x3, y3 = P(r0, a0)
    return ("M%.2f,%.2f A%.2f,%.2f 0 %d 0 %.2f,%.2f L%.2f,%.2f A%.2f,%.2f 0 %d 1 %.2f,%.2f Z"
            % (x0, y0, r1 * k, r1 * k, large, x1, y1, x2, y2, r0 * k, r0 * k, large, x3, y3))


def finger_paths(cx, cy, k, r_in, r_out, inward=0.0):
    """Two fingers (above / below the slot), optionally flexed inward by `inward` mm."""
    paths = []
    half = TL_SLOT_W / 2
    for sgn in (1, -1):
        a0 = math.degrees(math.asin(half / r_out))
        pts = []
        steps = 40
        for i in range(steps + 1):
            a = math.radians(a0 + (180 - 2 * a0) * i / steps)
            pts.append((r_out * math.cos(a), r_out * math.sin(a)))
        a_in = math.degrees(math.asin(min(1.0, half / r_in)))
        for i in range(steps + 1):
            a = math.radians(180 - a_in - (180 - 2 * a_in) * i / steps)
            pts.append((r_in * math.cos(a), r_in * math.sin(a)))
        d = "M" + " L".join("%.2f,%.2f" % (cx + x * k, cy - sgn * (y - inward) * k) for x, y in pts) + " Z"
        paths.append(d)
    return paths


def cam_path(cx, cy, k, rot_deg):
    r, f = TL_CAM_D / 2, TL_CAM_FLATS / 2
    pts = []
    for i in range(361):
        a = math.radians(i)
        x, y = r * math.cos(a), r * math.sin(a)
        if abs(y) > f:
            y = f if y > 0 else -f
            x = math.copysign(math.sqrt(max(r * r - f * f, 0)), x) if abs(x) > math.sqrt(max(r * r - f * f, 0)) else x
        pts.append((x, y))
    c, s = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
    rot = [(x * c - y * s, x * s + y * c) for x, y in pts]
    return "M" + " L".join("%.2f,%.2f" % (cx + x * k, cy - y * k) for x, y in rot) + " Z"


def cam_diagram():
    k = 50.0
    W, H = 1180, 720
    body = [t(40, 52, "TwistLock Pin - section through the fingers (at the catch lip)", 26, weight="bold"),
            t(40, 84, "Same 2 moulded parts, only the cam angle changes. Dimensions in mm, drawn to scale.", 17, MUTED)]
    for i, (state, rot) in enumerate((("OPEN", 0), ("LOCKED", 90))):
        cx, cy = 245 + i * 480, 350
        col = RED if state == "OPEN" else GREEN
        body.append("<circle cx='%.1f' cy='%.1f' r='%.1f' fill='#dbe7fb' stroke='%s' stroke-width='2'/>" % (cx, cy, 3.9 * k, BLUE))
        body.append("<circle cx='%.1f' cy='%.1f' r='%.1f' fill='#f7f9fd' stroke='%s' stroke-width='2'/>" % (cx, cy, CB_D / 2 * k, BLUE))
        body.append("<circle cx='%.1f' cy='%.1f' r='%.1f' fill='none' stroke='%s' stroke-width='2' stroke-dasharray='7 6'/>"
                    % (cx, cy, HOLE_D / 2 * k, INK))
        inward = 0.3 if state == "OPEN" else 0.0
        for d in finger_paths(cx, cy, k, TL_BORE_D / 2, TL_LIP_D / 2, inward):
            body.append("<path d='%s' fill='#3a4049' stroke='%s' stroke-width='1.5'/>" % (d, INK))
        body.append("<path d='%s' fill='%s' stroke='%s' stroke-width='1.5'/>" % (cam_path(cx, cy, k, rot), MAG, INK))
        body.append(t(cx, cy - 4.3 * k, state, 28, col, "middle", "bold"))
        if state == "OPEN":
            for sgn in (1, -1):
                y0 = cy - sgn * (TL_LIP_D / 2 + 0.55) * k
                y1 = cy - sgn * (TL_LIP_D / 2 + 0.05) * k
                body.append("<line x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f' stroke='%s' stroke-width='4' marker-end='url(#arr)'/>"
                            % (cx, y0, cx, y1, RED))
            body.append(t(cx, cy + 4.75 * k, "Flats face the fingers: 0.35 mm free travel each side.", 17, INK, "middle"))
            body.append(t(cx, cy + 4.75 * k + 24, "Pull the pin -> 45 deg lip ramp pushes the fingers in ->", 17, INK, "middle"))
            body.append(t(cx, cy + 4.75 * k + 48, "lip (now %.2f) passes the %.2f bore. Easy to remove." % (TL_LIP_D - 0.6, HOLE_D), 17, INK, "middle"))
        else:
            body.append(t(cx, cy + 4.75 * k, "Arcs face the fingers: no inward travel.", 17, INK, "middle"))
            body.append(t(cx, cy + 4.75 * k + 24, "Lip (%.1f) stays behind the %.2f bore = locked." % (TL_LIP_D, HOLE_D), 17, INK, "middle"))
            body.append(t(cx, cy + 4.75 * k + 48, "Cam preload 0.01 mm/side removes the wobble.", 17, INK, "middle"))
    lx, ly = 975, 230
    for j, (label, colr, sw) in enumerate((("beam", BLUE, "#dbe7fb"), ("counterbore %.1f" % CB_D, BLUE, "#f7f9fd"),
                                           ("bore %.2f (dashed)" % HOLE_D, INK, "none"), ("finger + lip %.1f" % TL_LIP_D, "#3a4049", "#3a4049"),
                                           ("cam %.2f / %.1f flats" % (TL_CAM_D, TL_CAM_FLATS), MAG, MAG))):
        body.append("<rect x='%d' y='%d' width='22' height='16' fill='%s' stroke='%s' stroke-width='2'%s/>"
                    % (lx, ly + j * 36 - 13, sw, colr, " stroke-dasharray='4 3'" if sw == "none" else ""))
        body.append(t(lx + 32, ly + j * 36, label, 16, colr))
    body.insert(0, "<defs><marker id='arr' markerWidth='8' markerHeight='8' refX='4' refY='4' orient='auto'>"
                   "<path d='M0,0 L8,4 L0,8 z' fill='%s'/></marker></defs>" % RED)
    return svg(W, H, "".join(body), "TwistLock cam section, open and locked")


def dim_h(x0, x1, y, label, color=INK):
    return ("<line x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f' stroke='%s' stroke-width='1.5' marker-start='url(#d)' marker-end='url(#d)'/>"
            % (x0, y, x1, y, color) + t((x0 + x1) / 2, y - 8, label, 15, color, "middle"))


def dim_v(x, y0, y1, label, color=INK, side=1):
    return ("<line x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f' stroke='%s' stroke-width='1.5' marker-start='url(#d)' marker-end='url(#d)'/>"
            % (x, y0, x, y1, color) + t(x + side * 10, (y0 + y1) / 2 + 5, label, 15, color, "start" if side > 0 else "end"))


def grid_diagram():
    k = 20.0
    W, H = 1180, 700
    b = ["<defs><marker id='d' markerWidth='10' markerHeight='10' refX='5' refY='5' orient='auto-start-reverse'>"
         "<path d='M0,1 L9,5 L0,9' fill='none' stroke='%s' stroke-width='1.5'/></marker></defs>" % INK,
         t(40, 52, "SemiBlock grid standard (Technic-compatible)", 26, weight="bold"),
         t(40, 84, "Every beam, connector and module housing follows these numbers. mm, drawn to scale.", 17, MUTED)]
    # top view of a 3-hole beam
    ox, oy = 90, 250
    r = BEAM_W / 2
    L = 2 * PITCH
    b.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' rx='%.1f' fill='#dbe7fb' stroke='%s' stroke-width='2'/>"
             % (ox - r * k, oy - r * k, (L + 2 * r) * k, 2 * r * k, r * k, BLUE))
    for i in range(3):
        cx = ox + i * PITCH * k
        b.append("<circle cx='%.1f' cy='%.1f' r='%.1f' fill='#eef3fb' stroke='%s' stroke-width='1.5'/>" % (cx, oy, CB_D / 2 * k, BLUE))
        b.append("<circle cx='%.1f' cy='%.1f' r='%.1f' fill='#f7f9fd' stroke='%s' stroke-width='2'/>" % (cx, oy, HOLE_D / 2 * k, INK))
    b.append(t(ox - r * k, oy - r * k - 60, "Top view - H-beam 1x3 (H-section between the holes)", 18, weight="bold"))
    b.append(dim_h(ox, ox + PITCH * k, oy - r * k - 22, "pitch %.1f" % PITCH))
    b.append(dim_h(ox + 2 * PITCH * k - HOLE_D / 2 * k, ox + 2 * PITCH * k + HOLE_D / 2 * k, oy + r * k + 30, "hole %.2f" % HOLE_D))
    b.append(dim_h(ox + PITCH * k - CB_D / 2 * k, ox + PITCH * k + CB_D / 2 * k, oy + r * k + 68, "counterbore %.1f" % CB_D, BLUE))
    b.append(dim_v(ox + L * k + r * k + 24, oy - r * k, oy + r * k, "width %.1f" % BEAM_W))
    # section of two stacked beams
    sx, sy = 720, 170
    hw = 1.6 * PITCH
    for j in range(2):
        y0 = sy + j * PITCH * k
        b.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' fill='%s' stroke='%s' stroke-width='2'/>"
                 % (sx, y0, hw * k, BEAM_T * k, "#dbe7fb" if j == 0 else "#fff3cf", BLUE if j == 0 else "#b8860b"))
        cx = sx + hw * k / 2
        for (yy, dd, dep) in ((y0, CB_D, CB_DEPTH), (y0 + (BEAM_T - CB_DEPTH) * k, CB_D, CB_DEPTH)):
            b.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' fill='#f7f9fd'/>" % (cx - dd / 2 * k, yy, dd * k, dep * k))
        b.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' fill='#f7f9fd'/>"
                 % (cx - HOLE_D / 2 * k, y0, HOLE_D * k, BEAM_T * k))
    b.append(t(sx, sy - 40, "Section - two stacked beams", 18, weight="bold"))
    b.append(dim_v(sx - 26, sy, sy + BEAM_T * k, "thickness %.1f" % BEAM_T, side=-1))
    b.append(t(sx - 36, sy + PITCH * k - 2, "gap %.1f" % GAP, 15, INK, "end"))
    b.append(dim_v(sx + hw * k + 26, sy, sy + CB_DEPTH * k, "counterbore %.1f deep" % CB_DEPTH, MAG))
    b.append(t(sx + hw * k + 36, sy + CB_DEPTH * k + 22, "= TwistLock lip seat", 15, MAG))
    # axle cross
    ax, ay = 400, 560
    s = AXLE_SPLINE / 2
    d = AXLE_D / 2
    pts = [(-d, -s), (-s, -s), (-s, -d), (s, -d), (s, -s), (d, -s), (d, s), (s, s), (s, d), (-s, d), (-s, s), (-d, s)]
    b.append("<polygon points='%s' fill='#3a4049' stroke='%s' stroke-width='1.5'/>"
             % (" ".join("%.1f,%.1f" % (ax + x * k * 1.6, ay + y * k * 1.6) for x, y in pts), INK))
    b.append(t(ax, ay - d * k * 1.6 - 34, "Axle cross (x1.6)", 18, weight="bold", anchor="middle"))
    b.append(dim_h(ax - d * k * 1.6, ax + d * k * 1.6, ay + d * k * 1.6 + 30, "%.2f tip to tip" % AXLE_D))
    b.append(t(ax + d * k * 1.6 + 30, ay + 6, "arm %.1f" % AXLE_SPLINE, 15))
    b.append(t(700, 560, "Rules", 18, weight="bold"))
    for i, line in enumerate(["1 module = 8.0 mm in X, Y and Z",
                              "part size = n x 8 - 0.2 mm (0.1 clearance per face)",
                              "every round hole has the 6.2 x 0.7 counterbore",
                              "module housings: holes on the same 8 mm grid",
                              "gears: module 1 -> 8/16/24/40 T mesh on the grid"]):
        b.append(t(700, 592 + i * 24, "- " + line, 16))
    return svg(W, H, "".join(b), "SemiBlock grid standard")


def h_path(cx, cy, k):
    """H-section outline (SVG path, y down) centred on (cx, cy), k = px per mm."""
    w, h, tw, r = BEAM_W / 2, BEAM_T / 2, HB_WEB / 2, HB_POCKET_R
    zp = h - HB_FLANGE

    def P(x, z):
        return "%.1f,%.1f" % (cx + x * k, cy - z * k)
    return ("M%s L%s L%s L%s A%.1f,%.1f 0 0 0 %s L%s A%.1f,%.1f 0 0 0 %s L%s L%s L%s L%s L%s "
            "A%.1f,%.1f 0 0 0 %s L%s A%.1f,%.1f 0 0 0 %s L%s Z" % (
                P(-w, -h), P(w, -h), P(w, -zp), P(tw + r, -zp), r * k, r * k, P(tw, -zp + r), P(tw, zp - r),
                r * k, r * k, P(tw + r, zp), P(w, zp), P(w, h), P(-w, h), P(-w, zp), P(-tw - r, zp),
                r * k, r * k, P(-tw, zp - r), P(-tw, -zp + r), r * k, r * k, P(-tw - r, -zp), P(-w, -zp)))


def hbeam_diagram():
    """H-section vs the stage-1 solid section, numbers from the CAD."""
    k = 26.0
    W, H = 1180, 700
    b = ["<defs><marker id='d' markerWidth='10' markerHeight='10' refX='5' refY='5' orient='auto-start-reverse'>"
         "<path d='M0,1 L9,5 L0,9' fill='none' stroke='%s' stroke-width='1.5'/></marker></defs>" % INK,
         t(40, 52, "H-beam section (stage 2) vs solid beam (stage 1)", 26, weight="bold"),
         t(40, 84, "Cut between two holes. Same outside size, holes and counterbores, so every pin and LEGO part still fits."
           " mm, drawn to scale.", 17, MUTED)]
    w, h = BEAM_W / 2 * k, BEAM_T / 2 * k
    sx, sy = 190, 300
    b.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' fill='#e3e7ee' stroke='#5a6678' stroke-width='2'/>"
             % (sx - w, sy - h, 2 * w, 2 * h))
    b.append(t(sx, sy - h - 40, "Stage 1: solid", 18, weight="bold", anchor="middle"))
    b.append(dim_h(sx - w, sx + w, sy + h + 34, "%.1f" % BEAM_W))
    b.append(dim_v(sx - w - 26, sy - h, sy + h, "%.1f" % BEAM_T, side=-1))
    hx, hy = 560, 300
    b.append("<path d='%s' fill='#dbe7fb' stroke='%s' stroke-width='2'/>" % (h_path(hx, hy, k), BLUE))
    b.append(t(hx, hy - h - 40, "Stage 2: H-section", 18, BLUE, "middle", "bold"))
    b.append(dim_h(hx - w, hx + w, hy + h + 34, "%.1f" % BEAM_W))
    b.append(dim_v(hx - w - 26, hy - h, hy + h, "%.1f" % BEAM_T, side=-1))
    zp = BEAM_T / 2 - HB_FLANGE
    b.append(dim_v(hx + w + 22, hy - h, hy - zp * k, "flange %.1f" % HB_FLANGE, BLUE))
    b.append(dim_v(hx + w + 72, hy - zp * k, hy + zp * k, "pocket %.1f" % (2 * zp), MUTED))
    b.append(dim_h(hx - HB_WEB / 2 * k, hx + HB_WEB / 2 * k, hy - 12, ""))
    b.append(t(hx - HB_WEB / 2 * k - 8, hy - 6, "web %.1f" % HB_WEB, 15, INK, "end"))
    b.append(dim_h(hx + HB_WEB / 2 * k, hx + w, hy + 26, "%.1f deep" % (BEAM_W / 2 - HB_WEB / 2), MUTED))
    b.append(t(hx, hy + h + 70, "tube round every hole: wall %.2f" % ((HB_TUBE_D - HOLE_D) / 2), 15, MUTED, "middle"))
    b.append("<line x1='%d' y1='%d' x2='%d' y2='%d' stroke='%s' stroke-width='2' marker-start='url(#d)' marker-end='url(#d)'/>"
             % (hx - w - 110, hy - 60, hx - w - 110, hy + 60, MAG))
    b.append(t(hx - w - 120, hy - 70, "pin axis", 15, MAG, "middle"))
    rows = [("", "Stage 1", "Stage 2", ""),
            ("Plastic in a 1x15 beam", "100%", "74%", "26% less"),
            ("Stiffness lying flat", "100%", "91%", "load along the holes"),
            ("Stiffness on edge", "100%", "63%", "load across the holes"),
            ("Strength at the holes", "100%", "~85%", "weakest section"),
            ("Thickest wall", "3.2 mm", "1.8 mm", "~1/3 the cooling time")]
    tx, ty = 800, 170
    for i, row in enumerate(rows):
        y = ty + i * 46
        if i:
            b.append("<line x1='%d' y1='%d' x2='%d' y2='%d' stroke='#d6dde8' stroke-width='1'/>" % (tx, y - 30, tx + 360, y - 30))
        for j, (cell, x) in enumerate(zip(row, (0, 175, 245, 0))):
            if j == 3:
                b.append(t(tx, y + 20, cell, 13, MUTED))
            else:
                b.append(t(tx + x, y, cell, 16, BLUE if j == 2 else INK, weight="bold" if i == 0 or j == 2 else "normal"))
    b.append(t(800, 470, "Lying flat (holes vertical) the H is stiffer per gram", 16, INK))
    b.append(t(800, 494, "than the solid beam. On edge it is softer: brace long", 16, INK))
    b.append(t(800, 518, "rails with a frame or a triangle (section 6).", 16, INK))
    b.append(t(40, 670, "Numbers measured on the stage-2 CAD (section properties averaged along one 8 mm pitch). "
               "To confirm with 3-point bending tests (prototype plan).", 15, MUTED))
    return svg(W, H, "".join(b), "H-beam section compared with the stage-1 solid beam")


def triangles_diagram():
    """Pinned triangles: which angles land exactly on the 8 mm grid."""
    k = 7.0
    W, H = 1180, 640
    b = [t(40, 52, "Triangles set the angle: three pinned beams are always rigid", 26, weight="bold"),
         t(40, 84, "Dots = the 8 mm grid. Numbers = hole spacings (modules) between the corner pins.", 17, MUTED)]

    def tri(ox, oy, pts, labels, title, sub, colour, angles):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        for gx in range(int(min(xs)) - 1, int(max(xs)) + 2):
            for gy in range(int(min(ys)) - 1, int(max(ys)) + 2):
                b.append("<circle cx='%.1f' cy='%.1f' r='2.2' fill='#c3ccd8'/>" % (ox + gx * 8 * k, oy - gy * 8 * k))
        P = [(ox + x * 8 * k, oy - y * 8 * k) for x, y in pts]
        b.append("<polygon points='%s' fill='%s' fill-opacity='0.12' stroke='%s' stroke-width='9' stroke-linejoin='round'/>"
                 % (" ".join("%.1f,%.1f" % p for p in P), colour, colour))
        for p in P:
            b.append("<circle cx='%.1f' cy='%.1f' r='8' fill='#fff' stroke='%s' stroke-width='3'/>" % (p[0], p[1], MAG))
        for i, lab in enumerate(labels):
            a, c = P[i], P[(i + 1) % 3]
            mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
            cx, cy = sum(p[0] for p in P) / 3, sum(p[1] for p in P) / 3
            dx, dy = mx - cx, my - cy
            n = max((dx * dx + dy * dy) ** 0.5, 1)
            b.append(t(mx + dx / n * 26, my + dy / n * 26 + 6, lab, 18, INK, "middle", "bold"))
        for i, ang in enumerate(angles):                  # label on the angle bisector, clear of both sides
            p, q1, q2 = P[i], P[(i + 1) % 3], P[(i + 2) % 3]
            u = [(q[0] - p[0], q[1] - p[1]) for q in (q1, q2)]
            u = [(x / (x * x + y * y) ** 0.5, y / (x * x + y * y) ** 0.5) for x, y in u]
            bx, by = u[0][0] + u[1][0], u[0][1] + u[1][1]
            n = (bx * bx + by * by) ** 0.5
            half = math.acos(max(-1.0, min(1.0, u[0][0] * u[1][0] + u[0][1] * u[1][1]))) / 2
            d = min(110.0, max(48.0, 30.0 / math.sin(half)))
            b.append(t(p[0] + bx / n * d, p[1] + by / n * d + 6, ang, 16, colour, "middle", "bold"))
        b.append(t(ox + 8 * k * (min(xs) + max(xs)) / 2, oy + 60, title, 18, INK, "middle", "bold"))
        b.append(t(ox + 8 * k * (min(xs) + max(xs)) / 2, oy + 84, sub, 15, MUTED, "middle"))
    tri(90, 470, [(0, 0), (4, 0), (4, 3)], ["4", "3", "5"], "3-4-5", "exact on the grid", BLUE, ["36.87°", "90°", "53.13°"])
    tri(470, 470, [(0, 0), (4, 0), (2, 2 * 3 ** 0.5)], ["4", "4", "4"], "4-4-4", "top corner floats off the grid", "#e6a000",
        ["60°", "60°", "60°"])
    b.append(t(840, 170, "More grid-exact triangles", 18, weight="bold"))
    for i, line in enumerate(["3-4-5 and 6-8-10: 36.87° / 53.13°", "5-12-13: 22.62° / 67.38°", "8-15-17: 28.07° / 61.93°",
                              "Bent H-beam 1x9 uses 3-4-5 (53°)", "", "Not on the grid: 30°, 45°, 60°.",
                              "Use the AngleLock hinge (15° steps),", "the 45° bent H-beam or the turntable."]):
        b.append(t(840, 204 + i * 28, line, 16, MUTED if i >= 5 else INK))
    return svg(W, H, "".join(b), "Pinned triangles and the angles they make")


def box_node(x, y, w, h, title, lines, color, fill="#ffffff"):
    out = ["<rect x='%d' y='%d' width='%d' height='%d' rx='14' fill='%s' stroke='%s' stroke-width='2.5'/>" % (x, y, w, h, fill, color),
           "<rect x='%d' y='%d' width='%d' height='8' rx='4' fill='%s'/>" % (x, y, w, color),
           t(x + 18, y + 38, title, 19, INK, weight="bold")]
    for i, ln in enumerate(lines):
        out.append(t(x + 18, y + 66 + i * 23, ln, 15, MUTED))
    return "".join(out)


def arrow(x0, y0, x1, y1, label="", color=INK):
    s = "<line x1='%d' y1='%d' x2='%d' y2='%d' stroke='%s' stroke-width='2.5' marker-end='url(#a)' marker-start='url(#a)'/>" % (
        x0, y0, x1, y1, color)
    if label:
        s += t((x0 + x1) / 2 + 8, (y0 + y1) / 2 - 8, label, 14, MUTED)
    return s


def architecture_diagram():
    W, H = 1180, 760
    b = ["<defs><marker id='a' markerWidth='9' markerHeight='9' refX='5' refY='4.5' orient='auto-start-reverse'>"
         "<path d='M0,0 L9,4.5 L0,9 z' fill='%s'/></marker></defs>" % INK,
         t(40, 52, "System architecture", 26, weight="bold"),
         t(40, 84, "One code path from the semiblock.ai editor to every motor and sensor.", 17, MUTED)]
    b.append(box_node(30, 120, 290, 190, "semiblock.ai (browser)", ["blocks + MicroPython editor", "simulator / digital twin",
                                                                       "class dashboard, data logs", "AI model training"], MAG))
    b.append(box_node(430, 120, 320, 210, "Junior Brain (ESP32-S3)", ["MicroPython runtime + device ID", "1.54 in screen, 3 buttons, RGB",
                                                                       "IMU, mic, speaker, light sensor", "2S Li-ion, USB-C charge",
                                                                       "6 SemiLink ports (A-F)"], BLUE))
    b.append(box_node(860, 120, 290, 190, "Other robots / remotes", ["ESP-NOW messages", "BLE gamepads", "Wi-Fi for IoT lessons"], "#12a89a"))
    b.append(arrow(320, 215, 430, 215))
    b.append(t(375, 200, "USB-C / BLE", 14, MUTED, "middle"))
    b.append(t(375, 245, "Wi-Fi", 14, MUTED, "middle"))
    b.append(arrow(750, 215, 860, 215))
    b.append(t(805, 200, "ESP-NOW", 14, MUTED, "middle"))
    b.append(box_node(30, 430, 290, 200, "SemiMotor M / L / Servo", ["H-bridge on the port", "encoder: speed + angle",
                                                                      "2 ports: daisy-chain", "auto-detected by ID"], "#e6a000"))
    b.append(box_node(430, 430, 320, 230, "Smart modules (60+)", ["tiny MCU in every module", "same I2C protocol + ID",
                                                                   "auto-detect, safe hot-plug", "calibration stored on module",
                                                                   "2 ports: chain up to 8"], BLUE))
    b.append(box_node(860, 430, 290, 200, "SemiLink-6 cable", ["1 M+  2 M-  3 GND", "4 VCC 3.3/5 V", "5 SDA/TX/encA  6 SCL/RX/encB",
                                                              "keyed + latched, replaceable"], INK))
    b.append(arrow(540, 330, 200, 430, "ports A-F"))
    b.append(arrow(590, 330, 590, 430, "ports A-F"))
    b.append(arrow(750, 540, 860, 540))
    b.append(t(440, 700, "Same physical port for motors and sensors: kids never pick the wrong one.", 16, INK, weight="bold"))
    return svg(W, H, "".join(b), "SemiBlock Junior system architecture")


if __name__ == "__main__":
    for name, fn in (("twistlock-cam-section.svg", cam_diagram), ("grid-standard.svg", grid_diagram),
                     ("system-architecture.svg", architecture_diagram), ("hbeam-numbers.svg", hbeam_diagram),
                     ("grid-triangles.svg", triangles_diagram)):
        with open(os.path.join(OUT, name), "w") as fh:
            fh.write(fn())
        print("wrote", name)

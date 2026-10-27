"""SVG side of the manufacturing drawings: A3 sheet, first-angle view layout,
ISO-style dimensions, leaders, hatching and a bilingual (EN / 简体中文)
title block. Pure Python; the geometry comes from dwg_geom.py.

Paper units are mm (A3 landscape 420 x 297). A view maps model point
(x, y) to paper (ox + s*x, oy - s*y).
"""
import html
import math

W, H = 420.0, 297.0
M = 10.0                       # frame margin
TB_H = 50.0                    # title block strip height
COL_W = 98.0                   # right column (iso view + notes)
AREA = (M + 4, M + 4, W - M - COL_W - 4, H - M - TB_H - 4)    # x0, y0, x1, y1 for the views
SCALES = [20, 10, 5, 4, 2.5, 2, 1.5, 1, 0.5]
LANE0, LANE = 7.0, 6.5         # first dimension line offset, spacing between dimension lanes
TXT = 3.0                      # dimension text height
FONT = "Arial, 'PingFang SC', 'Heiti SC', 'Hiragino Sans GB', sans-serif"
LW = {"vis": 0.5, "hid": 0.25, "thin": 0.18, "hatch": 0.12, "frame": 0.7}


def esc(s):
    return html.escape(str(s), quote=True)


def text_w(s, size):
    w = 0.0
    for ch in str(s):
        o = ord(ch)
        w += size * (1.0 if o > 0x2E80 else (0.3 if ch in " .,:;|il1()[]'" else 0.56))
    return w


def scale_label(s):
    if s >= 1:
        return "%g:1" % s
    return "1:%g" % (1 / s)


def fmt(v):
    s = "%.2f" % v
    s = s.rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


# ------------------------------------------------------------- primitives
class Svg:
    def __init__(self):
        self.out = []

    def add(self, s):
        self.out.append(s)

    def line(self, x0, y0, x1, y1, w=LW["thin"], dash=None, cap="butt"):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        self.add('<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#000" stroke-width="%.3f" stroke-linecap="%s"%s/>'
                 % (x0, y0, x1, y1, w, cap, d))

    def poly(self, pts, w=LW["vis"], dash=None, close=False):
        if len(pts) < 2:
            return
        d = "M" + " L".join("%.3f %.3f" % p for p in pts) + (" Z" if close else "")
        ds = ' stroke-dasharray="%s"' % dash if dash else ""
        self.add('<path d="%s" fill="none" stroke="#000" stroke-width="%.3f" stroke-linejoin="round" stroke-linecap="round"%s/>'
                 % (d, w, ds))

    def circle(self, cx, cy, r, w=LW["vis"], dash=None, fill="none"):
        ds = ' stroke-dasharray="%s"' % dash if dash else ""
        self.add('<circle cx="%.3f" cy="%.3f" r="%.3f" fill="%s" stroke="#000" stroke-width="%.3f"%s/>' % (cx, cy, r, fill, w, ds))

    def rect(self, x, y, w, h, lw=LW["thin"], fill="none"):
        self.add('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="%s" stroke="#000" stroke-width="%.3f"/>'
                 % (x, y, w, h, fill, lw))

    def text(self, x, y, s, size=TXT, anchor="start", rot=0, weight="normal", fill="#000"):
        tr = ' transform="rotate(%.1f %.3f %.3f)"' % (rot, x, y) if rot else ""
        self.add('<text x="%.3f" y="%.3f" font-size="%.2f" font-family="%s" text-anchor="%s" font-weight="%s" fill="%s"%s>%s</text>'
                 % (x, y, size, FONT, anchor, weight, fill, tr, esc(s)))

    def arrow(self, x, y, dx, dy, ln=2.6, hw=0.48):
        """Filled arrowhead with its tip at (x, y) pointing along (dx, dy)."""
        n = math.hypot(dx, dy) or 1.0
        dx, dy = dx / n, dy / n
        bx, by = x - dx * ln, y - dy * ln
        self.add('<path d="M%.3f %.3f L%.3f %.3f L%.3f %.3f Z" fill="#000"/>'
                 % (x, y, bx - dy * hw, by + dx * hw, bx + dy * hw, by - dx * hw))


def hatch_path(loops, angle_deg, gap):
    """Even-odd hatch of paper-space loops as explicit line segments (no SVG
    <pattern>, so FreeCAD TechDraw and other viewers draw it too)."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    rot = [[(x * ca + y * sa, -x * sa + y * ca) for x, y in lp] for lp in loops if len(lp) >= 3]
    if not rot:
        return ""
    ys = [p[1] for lp in rot for p in lp]
    out = []
    y = math.floor(min(ys) / gap) * gap + gap / 2
    while y < max(ys):
        xs = []
        for lp in rot:
            for (x0, y0), (x1, y1) in zip(lp, lp[1:] + lp[:1]):
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        for xa, xb in zip(xs[0::2], xs[1::2]):
            if xb - xa > 0.05:
                pa = (xa * ca - y * sa, xa * sa + y * ca)
                pb = (xb * ca - y * sa, xb * sa + y * ca)
                out.append("M%.2f %.2f L%.2f %.2f" % (pa[0], pa[1], pb[0], pb[1]))
        y += gap
    return " ".join(out)


HATCH = [(45, 1.1), (-45, 1.1), (45, 0.7)]


def hatch(g, loops, k=0):
    ang, gap = HATCH[k % 3]
    d = hatch_path(loops, ang, gap)
    if d:
        g.add('<path d="%s" fill="none" stroke="#000" stroke-width="%.2f"/>' % (d, LW["hatch"]))


# ------------------------------------------------------------- dimensions
class Dim:
    """Linear dimension between two model points of a view.
    axis 'h' measures x, 'v' measures y. side: top/bottom/left/right lane."""

    def __init__(self, p1, p2, axis, side, text, tol="", ctf=False, ref=False):
        self.p1, self.p2, self.axis, self.side = p1, p2, axis, side
        self.text, self.tol, self.ctf, self.ref = text, tol, ctf, ref
        self.lane = 0

    def label(self):
        t = self.text + ((" " + self.tol) if self.tol else "")
        return "(%s)" % t if self.ref else t

    def render(self, g, vb):
        a, b = vb.paper(self.p1), vb.paper(self.p2)
        off = LANE0 + LANE * self.lane
        x0, y0, x1, y1 = vb.paper_bbox()
        if self.axis == "h":
            yl = (y0 - off) if self.side == "top" else (y1 + off)
            sgn = -1 if self.side == "top" else 1
            for p in (a, b):
                g.line(p[0], p[1] + sgn * 0.8, p[0], yl + sgn * 1.5)
            xa, xb = sorted((a[0], b[0]))
            _dim_line(g, (xa, yl), (xb, yl), self.label(), self.ctf, "h")
        else:
            xl = (x0 - off) if self.side == "left" else (x1 + off)
            sgn = -1 if self.side == "left" else 1
            for p in (a, b):
                g.line(p[0] + sgn * 0.8, p[1], xl + sgn * 1.5, p[1])
            ya, yb = sorted((a[1], b[1]))
            _dim_line(g, (xl, yb), (xl, ya), self.label(), self.ctf, "v", side_out=sgn)


class InlineDim:
    """Dimension drawn straight across a feature (shaft diameters, details)."""

    def __init__(self, p1, p2, text, tol="", ctf=False, text_side=1, shift=0.0):
        self.p1, self.p2, self.text, self.tol, self.ctf = p1, p2, text, tol, ctf
        self.text_side, self.shift = text_side, shift

    def render(self, g, vb):
        a, b = vb.paper(self.p1), vb.paper(self.p2)
        axis = "v" if abs(a[0] - b[0]) < abs(a[1] - b[1]) else "h"
        if axis == "v":
            a, b = (a, b) if a[1] > b[1] else (b, a)        # a = bottom
        else:
            a, b = (a, b) if a[0] < b[0] else (b, a)
        lab = self.text + ((" " + self.tol) if self.tol else "")
        _dim_line(g, a, b, lab, self.ctf, axis, self.text_side, self.shift, horiz_short=True)


def _dim_line(g, a, b, label, ctf, axis, text_side=-1, shift=0.0, horiz_short=False, side_out=0):
    """Dimension line from a to b with arrows, label centred (or outside)."""
    ln = math.hypot(b[0] - a[0], b[1] - a[1])
    tw = text_w(label, TXT) + (3.2 if ctf else 0)
    ux, uy = (b[0] - a[0]) / (ln or 1), (b[1] - a[1]) / (ln or 1)
    inside = ln >= 7.0
    if inside:
        g.line(a[0], a[1], b[0], b[1])
        g.arrow(a[0], a[1], -ux, -uy)
        g.arrow(b[0], b[1], ux, uy)
    else:
        g.line(a[0] - ux * 4, a[1] - uy * 4, b[0] + ux * 4, b[1] + uy * 4)
        g.arrow(a[0], a[1], ux, uy)
        g.arrow(b[0], b[1], -ux, -uy)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if axis == "v" and (not inside or ln < tw + 2) and side_out:
        # lane dimension too short for its text: horizontal text outside the lane
        ty = my + 1.0
        if side_out > 0:
            g.text(a[0] + 1.5, ty, label, anchor="start")
            if ctf:
                _ctf(g, a[0] + 1.5 + text_w(label, TXT) + 1.6, ty - TXT * 0.36)
        else:
            g.text(a[0] - 1.5 - (3.2 if ctf else 0), ty, label, anchor="end")
            if ctf:
                _ctf(g, a[0] - 2.4, ty - TXT * 0.36)
        return
    if axis == "v" and (not inside or ln < tw + 2) and horiz_short:
        # short vertical dimension: horizontal text beside the upper end
        g.text(b[0] + 1.2, b[1] - 1.4, label, anchor="start")
        if ctf:
            _ctf(g, b[0] + 1.2 + text_w(label, TXT) + 1.6, b[1] - 1.4 - TXT * 0.36)
        return
    if not inside or ln < tw + 2:
        # text beyond the second end
        if axis == "h":
            tx, ty = b[0] + 5 + tw / 2, b[1] - 1.0
        else:
            tx, ty = b[0] - 1.0, b[1] - 5 - tw / 2
    else:
        tx, ty = (mx, my - 1.0) if axis == "h" else (mx - 1.0, my)
    tx += ux * shift
    ty += uy * shift
    if axis == "h":
        g.text(tx - (1.6 if ctf else 0), ty, label, anchor="middle")
        if ctf:
            _ctf(g, tx + tw / 2 - 1.2, ty - TXT * 0.36)
    else:
        if text_side > 0 and inside and ln >= tw + 2:
            tx = mx + 1.0 + TXT * 0.8
        g.text(tx, ty + (1.6 if ctf else 0), label, anchor="middle", rot=-90)
        if ctf:
            _ctf(g, tx - TXT * 0.36, ty - tw / 2 + 1.2)


def _ctf(g, x, y, r=1.15):
    g.add('<path d="M%.3f %.3f L%.3f %.3f L%.3f %.3f L%.3f %.3f Z" fill="#000"/>'
          % (x, y - r, x + r, y, x, y + r, x - r, y))


class Leader:
    """Note with an arrow to a model point. side 'right': text in a column to
    the right of the view; side 'top': text stacked above the view."""

    def __init__(self, p, lines, side="right", ctf=False):
        self.p, self.lines, self.side, self.ctf = p, lines, side, ctf
        self.slot = None            # paper (x, y): left end + baseline of the last line

    def size(self):
        return (max(text_w(s, TXT) for s in self.lines) + (3.4 if self.ctf else 0), len(self.lines) * 4.3)

    def render(self, g, vb):
        ax, ay = vb.paper(self.p)
        tx, ty = self.slot
        w, h = self.size()
        n = len(self.lines)
        if self.side == "top":
            g.line(ax, ay, ax, ty + 1.2)
            g.line(ax, ty + 1.2, tx + w + 0.5, ty + 1.2)
            g.arrow(ax, ay, 0, 1, ln=2.4)
        else:
            sx = tx - 1.5
            g.line(ax, ay, sx - 3, ty + 1.2)
            g.line(sx - 3, ty + 1.2, sx + w + 1.5, ty + 1.2)
            g.arrow(ax, ay, ax - (sx - 3), ay - (ty + 1.2), ln=2.4)
        for i, s in enumerate(self.lines):
            g.text(tx, ty - 0.2 - (n - 1 - i) * 4.3, s)
        if self.ctf:
            _ctf(g, tx + w - 1.2, ty - 1.0 - (n - 1) * 4.3)


# ------------------------------------------------------------------ views
class ViewBlock:
    """One drawn view: projected geometry + its annotations."""

    def __init__(self, name, geo, label=None, kind="ortho", fixed_scale=None):
        self.name, self.geo, self.label, self.kind = name, geo, label, kind
        self.fixed_scale = fixed_scale
        self.dims, self.leaders, self.marks, self.axes, self.cuts, self.extra = [], [], [], [], [], []
        self.s, self.ox, self.oy = 1.0, 0.0, 0.0
        self.lanes = {"top": 0, "bottom": 0, "left": 0, "right": 0}
        self.mode = "right"
        self.s_hint = 1.0

    # ---- building
    def dim(self, d):
        d.lane = self.lanes[d.side]
        self.lanes[d.side] += 1
        self.dims.append(d)
        return d

    @property
    def bbox(self):
        return self.geo["bbox"]

    def scale(self, s):
        return self.fixed_scale or s

    def set_mode(self, mode):
        self.mode = mode
        for ld in self.leaders:
            ld.side = mode

    def _lane_pad(self, side):
        n = self.lanes[side]
        if not n:
            return 3.0
        pad = LANE0 + LANE * (n - 1) + TXT + 2.0
        if side in ("left", "right"):
            for d in self.dims:
                if d.side == side and d.axis == "v":
                    ln = abs(d.p2[1] - d.p1[1]) * self.s_hint
                    tw = text_w(d.label(), TXT) + (3.2 if d.ctf else 0)
                    if ln < tw + 2:
                        pad = max(pad, LANE0 + LANE * d.lane + 2.0 + tw)
        return pad

    def _top_stack(self):
        """Leaders above the view, nearest row = rightmost anchor (no crossings)."""
        rows, acc = [], 0.0
        for ld in sorted(self.leaders, key=lambda ld: -ld.p[0]):
            w, h = ld.size()
            rows.append((ld, acc))
            acc += h + 2.5
        return rows, acc

    def pads(self, s):
        """Paper space needed around the geometry on each side."""
        sc = self.scale(s)
        self.s_hint = sc
        p = {side: self._lane_pad(side) for side in ("top", "bottom", "left", "right")}
        x0, y0, x1, y1 = self.bbox
        if self.mode == "top" and self.leaders:
            rows, acc = self._top_stack()
            p["top"] += acc + 3.0
            for ld, _ in rows:
                w, _h = ld.size()
                need = (ld.p[0] - x0) * sc + 1.5 + w - (x1 - x0) * sc
                p["right"] = max(p["right"], need + 2.0)
        elif self.leaders:
            w = max(ld.size()[0] for ld in self.leaders)
            lh = sum(ld.size()[1] + 3 for ld in self.leaders)
            p["right"] += w + 10
            extra = max(0.0, lh - (y1 - y0) * sc - p["top"] - p["bottom"])
            p["top"] += extra / 2
            p["bottom"] += extra / 2
        if self.label:
            p["top"] += 9.0
        for ex in self.extra:                  # e.g. cutting-plane letters outside the view
            for side, v in ex.get("pad", {}).items():
                p[side] = max(p[side], v)
        return p

    def footprint(self, s):
        x0, y0, x1, y1 = self.bbox
        sc = self.scale(s)
        p = self.pads(s)
        return (x1 - x0) * sc + p["left"] + p["right"], (y1 - y0) * sc + p["top"] + p["bottom"], p

    def paper(self, pt):
        return (self.ox + self.s * pt[0], self.oy - self.s * pt[1])

    def paper_bbox(self):
        x0, y0, x1, y1 = self.bbox
        a, b = self.paper((x0, y1)), self.paper((x1, y0))
        return a[0], a[1], b[0], b[1]

    # ---- drawing
    def render(self, g):
        sv = self.s
        geo = self.geo
        for k, loops in geo.get("hatch", []):
            hatch(g, [[self.paper(p) for p in lp] for lp in loops], k)
        for pl in geo["hid"][0]:
            g.poly([self.paper(p) for p in pl], LW["hid"], dash="1.6 0.9")
        for cx, cy, r in geo["hid"][1]:
            c = self.paper((cx, cy))
            g.circle(c[0], c[1], r * sv, LW["hid"], dash="1.6 0.9")
        for pl in geo["vis"][0]:
            g.poly([self.paper(p) for p in pl], LW["vis"] if self.kind != "iso" else 0.3)
        for cx, cy, r in geo["vis"][1]:
            c = self.paper((cx, cy))
            g.circle(c[0], c[1], r * sv, LW["vis"] if self.kind != "iso" else 0.3)
        for (cx, cy), r in self.marks:                       # centre marks
            c = self.paper((cx, cy))
            e = r * sv + 1.6
            dash = "4 0.8 0.6 0.8" if e > 5 else None
            g.line(c[0] - e, c[1], c[0] + e, c[1], LW["thin"], dash)
            g.line(c[0], c[1] - e, c[0], c[1] + e, LW["thin"], dash)
        for a, b in self.axes:                               # axis lines
            pa, pb = self.paper(a), self.paper(b)
            ln = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) or 1
            ux, uy = (pb[0] - pa[0]) / ln, (pb[1] - pa[1]) / ln
            g.line(pa[0] - ux * 2, pa[1] - uy * 2, pb[0] + ux * 2, pb[1] + uy * 2, LW["thin"], "6 1 0.8 1")
        for ex in self.extra:                                # pitch circles
            if "circle" in ex:
                (cx, cy), r = ex["circle"]
                c = self.paper((cx, cy))
                g.circle(c[0], c[1], r * sv, LW["thin"], dash="6 1 0.8 1")
        for c in self.cuts:
            _cutting_line(g, self, c)
        for d in self.dims:
            d.render(g, self)
        stack = self._place_leaders()
        for ld in self.leaders:
            ld.render(g, self)
        if self.label:
            x0, y0, x1, y1 = self.paper_bbox()
            top = y0 - self._lane_pad("top") - stack - 3.0
            g.text((x0 + x1) / 2, top, self.label, 4.2, "middle", weight="bold")

    def _place_leaders(self):
        """Set each leader's text slot; returns the height used above the view."""
        if not self.leaders:
            return 0.0
        x0, y0, x1, y1 = self.paper_bbox()
        if self.mode == "top":
            rows, acc = self._top_stack()
            base = y0 - self._lane_pad("top") - 1.0
            for ld, off in rows:
                ax, _ = self.paper(ld.p)
                ld.slot = (ax + 1.5, base - off - 1.2)
            return acc + 1.0
        lds = sorted(self.leaders, key=lambda ld: self.paper(ld.p)[1])
        n_l = self.lanes["right"]
        off = (LANE0 + LANE * (n_l - 1) + TXT + 6) if n_l else 8.0
        heights = [ld.size()[1] + 3 for ld in lds]
        ys = [self.paper(ld.p)[1] for ld in lds]
        pos = []
        for i, y in enumerate(ys):
            pos.append(max(y, (pos[-1] + heights[i - 1]) if pos else -1e9))
        shift = (sum(ys) - sum(pos)) / len(pos)
        pos = [p + shift for p in pos]
        for i in range(1, len(pos)):
            pos[i] = max(pos[i], pos[i - 1] + heights[i - 1])
        for ld, y in zip(lds, pos):
            ld.slot = (x1 + off, y + (len(ld.lines) - 1) * 4.3)
        return 0.0


def _cutting_line(g, vb, c):
    """Cutting plane: line (n.x * x + n.y * y = k) in model coords, short thick
    ends just outside the outline, arrows in the viewing direction, letters."""
    (nx, ny), k, (adx, ady), letter = c["n"], c["k"], c["arrow"], c["letter"]
    x0, y0, x1, y1 = vb.bbox
    ext = 3.5 / vb.s
    if abs(ny) > abs(nx):        # mostly horizontal line
        y = k / ny
        a, b = (x0 - ext, y), (x1 + ext, y)
    else:
        x = k / nx
        a, b = (x, y0 - ext), (x, y1 + ext)
    pa, pb = vb.paper(a), vb.paper(b)
    g.line(pa[0], pa[1], pb[0], pb[1], LW["thin"], "6 1 0.8 1")
    ln = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) or 1
    ux, uy = (pb[0] - pa[0]) / ln, (pb[1] - pa[1]) / ln
    adx, ady = adx, -ady                       # model -> paper (y flips)
    an = math.hypot(adx, ady) or 1
    adx, ady = adx / an, ady / an
    for p, sgn in ((pa, 1), (pb, -1)):
        q = (p[0] + ux * 3 * sgn, p[1] + uy * 3 * sgn)
        g.line(p[0], p[1], q[0], q[1], 0.7)
        tip = (p[0] + adx * 5, p[1] + ady * 5)
        g.line(p[0], p[1], tip[0], tip[1], LW["thin"])
        g.arrow(tip[0], tip[1], adx, ady)
        g.text(tip[0] + adx * 3.2, tip[1] + ady * 3.2 + 1.5, letter, 4.0, "middle", weight="bold")


# ------------------------------------------------------------------ tables
class Table:
    def __init__(self, title, rows, widths, size=2.6):
        self.title, self.rows, self.widths, self.size = title, rows, widths, size
        self.rh = size * 1.75

    def footprint(self):
        return sum(self.widths), (len(self.rows) + 1) * self.rh

    def render(self, g, x, y):
        w = sum(self.widths)
        rh = self.rh
        g.rect(x, y, w, rh * (len(self.rows) + 1), 0.35)
        g.add('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="#e8e8e8" stroke="none"/>' % (x + 0.2, y + 0.2, w - 0.4, rh - 0.4))
        g.text(x + 1.5, y + rh * 0.72, self.title, self.size, weight="bold")
        for i, row in enumerate(self.rows):
            yy = y + rh * (i + 1)
            g.line(x, yy, x + w, yy, 0.18)
            xx = x
            for j, cell in enumerate(row):
                if j:
                    g.line(xx, yy, xx, yy + rh, 0.18)
                g.text(xx + 1.2, yy + rh * 0.72, cell, self.size)
                xx += self.widths[j]


class Detail:
    """Enlarged profile (axle cross, D-cam, oval bore) drawn from 2D loops."""

    def __init__(self, label, loops, scale, dims=(), circles=(), hatch=True):
        self.label, self.loops, self.scale_, self.dims = label, loops, scale, list(dims)
        self.circles, self.hatch = list(circles), hatch
        xs = [p[0] for lp in loops for p in lp] + [c[0] + s * c[2] for c in circles for s in (-1, 1)]
        ys = [p[1] for lp in loops for p in lp] + [c[1] + s * c[2] for c in circles for s in (-1, 1)]
        self.bb = (min(xs), min(ys), max(xs), max(ys))

    def footprint(self):
        x0, y0, x1, y1 = self.bb
        return (x1 - x0) * self.scale_ + 34, (y1 - y0) * self.scale_ + 30

    def render(self, g, x, y):
        x0, y0, x1, y1 = self.bb
        s = self.scale_
        ox, oy = x + 17 - x0 * s, y + 18 + y1 * s

        class _VB:
            pass
        vb = _VB()
        vb.paper = lambda p: (ox + s * p[0], oy - s * p[1])
        vb.s = s
        if self.hatch:
            hatch(g, [[vb.paper(p) for p in lp] for lp in self.loops], 0)
        for lp in self.loops:
            g.poly([vb.paper(p) for p in lp], LW["vis"], close=True)
        for cx, cy, r in self.circles:
            c = vb.paper((cx, cy))
            g.circle(c[0], c[1], r * s, LW["thin"], dash="4 0.8 0.6 0.8")
        c = vb.paper(((x0 + x1) / 2, (y0 + y1) / 2))
        e = (x1 - x0) * s / 2 + 3
        g.line(c[0] - e, c[1], c[0] + e, c[1], LW["thin"], "4 0.8 0.6 0.8")
        e = (y1 - y0) * s / 2 + 3
        g.line(c[0], c[1] - e, c[0], c[1] + e, LW["thin"], "4 0.8 0.6 0.8")
        for d in self.dims:
            d.render(g, vb)
        g.text(x + 17 + (x1 - x0) * s / 2, y + 7, "%s (%s)" % (self.label, scale_label(s)), 3.6, "middle",
               weight="bold")


# ------------------------------------------------------------------ sheet
def _frame_and_title(g, info):
    g.rect(M, M, W - 2 * M, H - 2 * M, LW["frame"])
    for x in (W / 2,):                      # centring marks
        g.line(x, 0, x, M, 0.5)
        g.line(x, H - M, x, H, 0.5)
    for y in (H / 2,):
        g.line(0, y, M, y, 0.5)
        g.line(W - M, y, W, y, 0.5)
    y0 = H - M - TB_H
    g.line(M, y0, W - M, y0, LW["frame"])
    # --- block 1: part data
    x = M
    cw = [27, 46, 27, 46]
    rows = [
        (("Material", "材料"), info["material"], ("Weight", "重量"), info["weight"]),
        (("Colour", "颜色"), info["colour"], ("Qty / kit", "每套数量"), info["qty"]),
        (("Finish", "表面"), info["finish"], ("Scale", "比例"), info["scale"]),
        (("Unit", "单位"), "mm", ("Projection", "投影"), ""),
        (("Status", "状态"), info["status"], ("Sheet", "页"), info["sheet"]),
    ]
    rh = TB_H / len(rows)
    for i, row in enumerate(rows):
        yy = y0 + i * rh
        if i:
            g.line(x, yy, x + sum(cw), yy, 0.25)
        xx = x
        for j in range(4):
            if j:
                g.line(xx, yy, xx, yy + rh, 0.25)
            cell = row[j]
            if j % 2 == 0:
                g.text(xx + 1.2, yy + 3.6, cell[0], 2.4, weight="bold")
                g.text(xx + 1.2, yy + 7.6, cell[1], 2.4, fill="#333")
            else:
                s = str(cell)
                sz = 2.9
                while text_w(s, sz) > cw[j] - 2.4 and sz > 1.9:
                    sz -= 0.1
                if "\n" in s:
                    a, b = s.split("\n", 1)
                    g.text(xx + 1.2, yy + 4.0, a, min(sz, 2.6))
                    g.text(xx + 1.2, yy + 8.0, b, min(sz, 2.6))
                else:
                    g.text(xx + 1.2, yy + 6.2, s, sz)
            xx += cw[j]
    _projection_symbol(g, x + cw[0] + cw[1] + cw[2] + 23, y0 + 3 * rh + rh / 2)
    x += sum(cw)
    g.line(x, y0, x, H - M, LW["frame"])
    # --- block 2: general tolerances + revision + sign-off
    tw = [24, 13, 13]
    g.text(x + 1.2, y0 + 3.6, "General tolerances 未注公差 (mm)", 2.4, weight="bold")
    g.text(x + 1.2, y0 + 7.4, "rigid ABS/POM  硬胶 | TPE 软胶", 2.2, fill="#333")
    trows = [("0 – 6", "±0.05", "±0.15"), ("6 – 18", "±0.08", "±0.2"), ("18 – 50", "±0.12", "±0.3"),
             ("50 – 120", "±0.2", "±0.5"), ("angles 角度", "±0.5°", "±1°")]
    yy = y0 + 9.4
    for r in trows:
        xx = x
        g.line(x, yy, x + sum(tw), yy, 0.18)
        for j, c in enumerate(r):
            if j:
                g.line(xx, yy, xx, yy + 4.6, 0.18)
            g.text(xx + 1.2, yy + 3.3, c, 2.4)
            xx += tw[j]
        yy += 4.6
    g.line(x, yy, x + sum(tw), yy, 0.18)
    g.text(x + 1.2, yy + 3.6, "◆ = critical dimension 关键尺寸", 2.3)
    g.text(x + 1.2, yy + 7.2, "FAI 100%, Cpk ≥ 1.33", 2.3)
    x2 = x + sum(tw)
    g.line(x2, y0, x2, H - M, 0.35)
    # revision + sign-off
    rw = [9, 47, 19]
    hdr = [("Rev", "版本"), ("Description 修改内容", ""), ("Date 日期", "")]
    xx = x2
    for j, (a, b) in enumerate(hdr):
        g.text(xx + 1.0, y0 + 3.6, a, 2.3, weight="bold")
        if b:
            g.text(xx + 1.0, y0 + 7.2, b, 2.3, weight="bold")
        xx += rw[j]
    g.line(x2, y0 + 8.6, x2 + sum(rw), y0 + 8.6, 0.25)
    g.text(x2 + 1.0, y0 + 12.4, info["rev"], 2.6)
    if info["rev"] == "B":
        g.text(x2 + rw[0] + 1.0, y0 + 12.4, "H-section between holes; fit unchanged", 2.3)
        g.text(x2 + rw[0] + 1.0, y0 + 15.6, "改为孔间工字截面，装配尺寸不变", 2.3)
    else:
        g.text(x2 + rw[0] + 1.0, y0 + 12.4, "First issue for quotation & samples", 2.3)
        g.text(x2 + rw[0] + 1.0, y0 + 15.6, "首次发布 · 报价及打样", 2.3)
    g.text(x2 + rw[0] + rw[1] + 1.0, y0 + 12.4, info["date"], 2.4)
    xx = x2
    for j in range(1, 3):
        xx += rw[j - 1]
        g.line(xx, y0, xx, y0 + 18.5, 0.18)
    sy = y0 + 18.5
    g.line(x2, sy, x2 + sum(rw), sy, 0.25)
    for i, (a, b, v) in enumerate((("Drawn", "设计", info["drawn"]), ("Checked", "审核", ""), ("Approved", "批准", ""))):
        yy = sy + i * 10.5
        if i:
            g.line(x2, yy, x2 + sum(rw), yy, 0.18)
        g.text(x2 + 1.0, yy + 4.0, a, 2.3, weight="bold")
        g.text(x2 + 1.0, yy + 7.8, b, 2.3)
        g.line(x2 + 17, yy, x2 + 17, yy + 10.5, 0.18)
        g.text(x2 + 18.5, yy + 6.2, v, 2.5)
        g.line(x2 + sum(rw) - 19, yy, x2 + sum(rw) - 19, yy + 10.5, 0.18)
        g.text(x2 + sum(rw) - 18, yy + 6.2, info["date"] if v else "", 2.4)
    x3 = x2 + sum(rw)
    g.line(x3, y0, x3, H - M, LW["frame"])
    # --- block 3: owner, part number, name
    xe = W - M
    g.text(x3 + 3, y0 + 7.5, "semiblock.ai", 6.0, weight="bold")
    g.text(xe - 3, y0 + 7.5, "SemiBlock Junior", 3.2, "end", fill="#333")
    g.line(x3, y0 + 11, xe, y0 + 11, 0.35)
    g.text(x3 + 2, y0 + 14.5, "Part No. 零件号", 2.3, weight="bold")
    g.text(x3 + 2, y0 + 23.5, info["pid"], 7.5 if len(info["pid"]) < 13 else 6.0, weight="bold")
    g.line(x3, y0 + 26.5, xe, y0 + 26.5, 0.35)
    g.text(x3 + 2, y0 + 30, "Name 名称", 2.3, weight="bold")
    t = info["title"]
    sz = 4.0
    while text_w(t, sz) > xe - x3 - 4 and sz > 2.6:
        sz -= 0.1
    g.text(x3 + 2, y0 + 35.5, t, sz, weight="bold")
    tz = info["title_zh"]
    g.text(x3 + 2, y0 + 41.0, tz, min(3.6, sz))
    g.line(x3, y0 + 43.5, xe, y0 + 43.5, 0.25)
    g.text(x3 + 2, y0 + 47.6, "Dwg %s · Rev %s · A3 · 3D: %s.step / .FCStd" % (info["pid"], info["rev"], info["file_id"]), 2.3)


def _projection_symbol(g, cx, cy):
    """First-angle projection symbol (ISO 5456-2 / GB/T 14692)."""
    s = 1.0
    # truncated cone side view (right) + circles (left) = first angle
    x0 = cx - 7 * s
    g.circle(x0, cy, 2.6 * s, 0.25)
    g.circle(x0, cy, 1.3 * s, 0.25)
    g.line(x0 - 4 * s, cy, x0 + 4 * s, cy, 0.13, "1.5 0.5 0.3 0.5")
    xa = cx + 1.5 * s
    g.poly([(xa, cy - 1.3 * s), (xa + 6 * s, cy - 2.6 * s), (xa + 6 * s, cy + 2.6 * s), (xa, cy + 1.3 * s)], 0.25, close=True)
    g.line(xa - 1, cy, xa + 7 * s, cy, 0.13, "1.5 0.5 0.3 0.5")


def _notes(g, x, y, w, notes, ymax):
    g.text(x, y, "Technical requirements 技术要求", 3.0, weight="bold")
    yy = y + 5.0
    size = 2.35
    for i, (en, zh) in enumerate(notes):
        for k, s in enumerate(_wrap("%d. %s" % (i + 1, en), w, size) + _wrap("   " + zh, w, size)):
            if yy > ymax:
                return yy
            g.text(x, yy, s, size, fill="#000" if k == 0 or not _has_cjk(s) else "#222")
            yy += size * 1.38
        yy += 0.9
    return yy


def _has_cjk(s):
    return any(ord(ch) > 0x2E80 for ch in s)


def _wrap(s, w, size):
    words = s.split(" ") if not _has_cjk(s) else list(s)
    lines, cur = [], ""
    for wd in words:
        trial = (cur + (" " if cur and not _has_cjk(s) else "") + wd) if cur else wd
        if text_w(trial, size) > w and cur:
            lines.append(cur)
            cur = ("   " + wd) if not _has_cjk(s) else ("   " + wd)
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def layout(main, iso, boxes):
    """Choose the scale and place front/left/top views (first angle), the iso
    view in the right column and detail boxes / tables in free space.
    main: dict name -> ViewBlock (front, left, top; any may be missing).
    boxes: objects with footprint()/render(g, x, y)."""
    ax0, ay0, ax1, ay1 = AREA
    fr, le, tp = main.get("front"), main.get("left"), main.get("top")
    for s, mode in [(sc, m) for sc in SCALES for m in ("right", "top")]:
        for vb in main.values():
            vb.set_mode(mode)
        fw, fh, fp = fr.footprint(s)
        lw_, lh_, lp = le.footprint(s) if le else (0, 0, None)
        tw_, th_, tpp = tp.footprint(s) if tp else (0, 0, None)
        gap = 6.0
        width = max(fw + (gap + lw_ if le else 0), tw_)
        height = max(fh, lh_) + (gap + th_ if tp else 0)
        if width > ax1 - ax0 or height > ay1 - ay0:
            continue
        # spread spare room evenly
        sx = (ax1 - ax0 - width) / 3
        sy = (ay1 - ay0 - height) / 3
        left0 = ax0 + min(sx, 18)
        top0 = ay0 + min(sy, 14)
        gx = min(sx, 22)
        gy = min(sy, 16)
        # front + left share the paper y of model z; front + top share paper x of model x
        x0f, y0f, x1f, y1f = fr.bbox
        ox = left0 + max(fp["left"] - x0f * s, (tpp["left"] - tp.bbox[0] * s) if tp else -1e9)
        oy_top = top0 + max(fp["top"] + y1f * s, (lp["top"] + le.bbox[3] * le.scale(s)) if le else -1e9)
        fr.s, fr.ox, fr.oy = s, ox, oy_top
        front_right = ox + x1f * s + fp["right"]
        front_bottom = oy_top - y0f * s + fp["bottom"]
        if le:
            le.s = le.scale(s)
            le.ox = front_right + gap + gx + lp["left"] - le.bbox[0] * le.s
            le.oy = oy_top
            left_bottom = le.oy - le.bbox[1] * le.s + lp["bottom"]
            left_right = le.ox + le.bbox[2] * le.s + lp["right"]
        else:
            left_bottom, left_right = front_bottom, front_right
        if tp:
            tp.s = s
            tp.ox = ox
            top_top = front_bottom + gap + gy
            tp.oy = top_top + tpp["top"] + tp.bbox[3] * s
            top_right = ox + tp.bbox[2] * s + tpp["right"]
            top_bottom = tp.oy - tp.bbox[1] * s + tpp["bottom"]
        else:
            top_right, top_bottom = front_right, front_bottom
        if max(left_right, top_right) > ax1 + 0.5 or max(top_bottom, left_bottom) > ay1 + 0.5:
            continue
        # free spaces for boxes: right of the top view below the left view, then below everything
        slots = [(max(top_right, ox + x1f * s + 6) + 6, left_bottom + 6, ax1, ay1),
                 (ax0, max(top_bottom, left_bottom) + 6, ax1, ay1)]
        placed = _pack(boxes, slots)
        if placed is None:
            continue
        return s, placed
    return None, None


def _pack(boxes, slots):
    """Shelf packing of detail boxes / tables into the free slots."""
    placed = []
    state = [[x0, y0, 0.0] for x0, y0, x1, y1 in slots]      # cursor x, band top, band height
    for b in boxes:
        bw, bh = b.footprint()
        ok = False
        for st, (sx0, sy0, sx1, sy1) in zip(state, slots):
            cx, by, bhh = st
            if cx + bw > sx1:                                  # new band
                cx, by, bhh = sx0, by + bhh + 6, 0.0
            if cx + bw <= sx1 and by + bh <= sy1:
                placed.append((b, cx, by))
                st[0], st[1], st[2] = cx + bw + 6, by, max(bhh, bh)
                ok = True
                break
        if not ok:
            return None
    return placed


def render_sheet(info, main, iso, boxes_placed, notes):
    g = Svg()
    g.add('<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %g %g">' % (W, H, W, H))
    g.add('<rect x="0" y="0" width="%g" height="%g" fill="#fff"/>' % (W, H))
    _frame_and_title(g, info)
    for vb in main.values():
        vb.render(g)
    # right column: iso + notes
    cx0 = W - M - COL_W
    g.line(cx0, M, cx0, H - M - TB_H, 0.35)
    if iso:
        iso.render(g)
        g.text(cx0 + COL_W / 2, M + 6, iso.label_text, 3.0, "middle", weight="bold")
    ny = (iso.notes_top if iso else M + 8)
    g.line(cx0, ny - 6, W - M, ny - 6, 0.25)
    _notes(g, cx0 + 3, ny, COL_W - 6, notes, H - M - TB_H - 3)
    for b, x, y in boxes_placed:
        b.render(g, x, y)
    g.add("</svg>")
    return "\n".join(g.out)


def place_iso(iso, s_main):
    """Fit the iso view into the top of the right column."""
    x0, y0, x1, y1 = iso.bbox
    cw, chmax = COL_W - 10, 78.0
    s = max([sc for sc in SCALES if (x1 - x0) * sc <= cw and (y1 - y0) * sc <= chmax - 14] or [SCALES[-1]])
    iso.s = s
    w, h = (x1 - x0) * s, (y1 - y0) * s
    cx0 = W - M - COL_W
    iso.ox = cx0 + (COL_W - w) / 2 - x0 * s
    iso.oy = M + 12 + y1 * s + max(0, (chmax - 14 - h) / 2)
    iso.label_text = "ISOMETRIC 轴测图 (%s, ref.)" % scale_label(s)
    iso.notes_top = M + 12 + max(h, 20) + max(0, (chmax - 14 - h)) + 12

"""Geometry side of the 2D manufacturing drawings (runs in FreeCAD's Python).

    pose()      turn a component so its longest side runs left-right on paper
    project()   hidden-line projection of one orthographic / iso view
    section()   full section through the view's centre plane, with hatch loops
    features()  holes, counterbores, axle-cross holes, shafts and arcs found
                from the cylindrical faces of the solid

All 2D results are in "view mm" (model units): x to the right, y up.
dwg_sheet.py turns them into an SVG sheet.
"""
import math

import FreeCAD as App
import Part
import TechDraw

V = App.Vector

# view basis rows (u = paper right, v = paper up, w = towards the viewer),
# first-angle projection with CAD Z up and the part's front facing -Y
VIEWS = {
    "front": (V(1, 0, 0), V(0, 0, 1), V(0, -1, 0)),
    "top": (V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)),
    "left": (V(0, -1, 0), V(0, 0, 1), V(-1, 0, 0)),
}
_iso_w = V(1, -1, 1).normalize()
_iso_u = V(0, 0, 1).cross(_iso_w).normalize()
VIEWS["iso"] = (_iso_u, _iso_w.cross(_iso_u).normalize(), _iso_w)


def matrix(rows):
    u, v, w = rows
    return App.Matrix(u.x, u.y, u.z, 0, v.x, v.y, v.z, 0, w.x, w.y, w.z, 0, 0, 0, 0, 1)


def to_view(rows, p):
    u, v, w = rows
    return (u.dot(p), v.dot(p), w.dot(p))


# ------------------------------------------------------------------ pose
def pose(shape, axis_hint=None, z_left=False):
    """Matrix that rotates `shape` so its longest extent is X (paper
    horizontal) and moves its bounding box minimum to the origin.
    axis_hint ('x'|'y'|'z') forces which CAD axis becomes X; z_left puts the
    +Z end (e.g. a TwistLock knob) on the left."""
    pre = _align_axisymmetric(shape)
    if pre is not None:
        shape = shape.transformed(pre)
    bb = shape.optimalBoundingBox()
    ext = {"x": bb.XLength, "y": bb.YLength, "z": bb.ZLength}
    longest = axis_hint or max("xyz", key=lambda k: (round(ext[k], 2), "zyx".index(k)))
    if longest == "z" and z_left:            # rotate -90 about Y: Z -> -X
        rot = App.Matrix(0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1)
    elif longest == "z":                     # rotate +90 about Y: Z -> X
        rot = App.Matrix(0, 0, 1, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 0, 1)
    elif longest == "y":                     # rotate -90 about Z: Y -> X
        rot = App.Matrix(0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    else:
        rot = App.Matrix()
    s = shape.transformed(rot)
    b2 = s.optimalBoundingBox()
    mv = App.Matrix()
    mv.move(V(-b2.XMin, -b2.YMin, -b2.ZMin))
    m = mv.multiply(rot)
    return m.multiply(pre) if pre is not None else m


def _align_axisymmetric(shape):
    """Rotation that puts the symmetry axis of a round part (e.g. a roller
    modelled at an angle inside its wheel) along Z; None if not needed."""
    if len(shape.Solids) != 1:
        return None
    try:
        pp = shape.Solids[0].PrincipalProperties
    except Exception:
        return None
    mom = pp["Moments"]
    axes = [pp["FirstAxisOfInertia"], pp["SecondAxisOfInertia"], pp["ThirdAxisOfInertia"]]
    for i in range(3):
        j, k = [x for x in range(3) if x != i]
        if abs(mom[j] - mom[k]) <= 0.01 * max(mom) and abs(mom[i] - mom[j]) > 0.05 * max(mom):
            a = V(axes[i])
            a.normalize()
            if max(abs(a.x), abs(a.y), abs(a.z)) > 0.999:
                return None
            r = App.Rotation(a, V(0, 0, 1))
            c = shape.Solids[0].CenterOfMass
            pl = App.Placement(V(0, 0, 0), r, c)
            return pl.toMatrix()
    return None


def rotation_part(m):
    r = App.Matrix(m)
    r.A14 = r.A24 = r.A34 = 0
    return r


# ------------------------------------------------------------- projection
def _polylines(comp, defl):
    lines, circles = [], []
    if comp is None:
        return lines, circles
    for e in comp.Edges:
        c = e.Curve
        if isinstance(c, Part.Circle) and e.isClosed():
            circles.append((c.Center.x, c.Center.y, c.Radius))
            continue
        if isinstance(c, Part.Line) or isinstance(c, Part.LineSegment):
            p0, p1 = e.Vertexes[0].Point, e.Vertexes[-1].Point
            lines.append([(p0.x, p0.y), (p1.x, p1.y)])
            continue
        try:
            pts = e.discretize(Deflection=defl)
        except Exception:
            pts = [v.Point for v in e.Vertexes]
        if len(pts) >= 2:
            lines.append([(p.x, p.y) for p in pts])
    return lines, circles


def project(shape, rows, defl=0.004, hidden=True):
    """Visible + hidden edges of `shape` seen through view `rows`."""
    s = shape.transformed(matrix(rows))
    r = TechDraw.projectEx(s, V(0, 0, 1))
    vis = Part.makeCompound([x for x in (r[0], r[3]) if x is not None and not x.isNull()])
    out = {"vis": _polylines(vis, defl)}
    if hidden:
        hid = Part.makeCompound([x for x in (r[5], r[8]) if x is not None and not x.isNull()])
        out["hid"] = _polylines(hid, defl)
    else:
        out["hid"] = ([], [])
    out["bbox"] = _bbox2(out["vis"])
    return out


def _bbox2(pc):
    xs, ys = [], []
    for pl in pc[0]:
        for x, y in pl:
            xs.append(x)
            ys.append(y)
    for cx, cy, r in pc[1]:
        xs += [cx - r, cx + r]
        ys += [cy - r, cy + r]
    if not xs:
        return (0, 0, 0, 0)
    return (min(xs), min(ys), max(xs), max(ys))


def edge_length(pc):
    n = 0.0
    for pl in pc[0]:
        for a, b in zip(pl, pl[1:]):
            n += math.hypot(b[0] - a[0], b[1] - a[1])
    for _, _, r in pc[1]:
        n += 2 * math.pi * r
    return n


def _wire_points(w, defl):
    """Points along a wire in order (edge orientation respected)."""
    try:
        return [(p.x, p.y) for p in w.discretize(Deflection=defl)]
    except Exception:
        pts = []
        for e in w.OrderedEdges:
            ps = [v.Point for v in e.Vertexes]
            if pts and ps and (V(*pts[-1], 0) - ps[0]).Length > (V(*pts[-1], 0) - ps[-1]).Length:
                ps.reverse()
            pts += [(p.x, p.y) for p in ps]
        return pts


def section(shapes, rows, c, defl=0.004):
    """Full section (see _section); retries slightly off-plane when the
    boolean cut fails on a plane that coincides with internal faces."""
    for dc in (0.0, 0.013, -0.017):
        out = _section(shapes, rows, c + dc, defl)
        if out["vis"][0] or out["vis"][1]:
            return out
    return None


def _section(shapes, rows, c, defl=0.004):
    """Full section: remove everything nearer to the viewer than w = c, then
    project. `shapes` is a list (one per body) so each body gets its own
    hatch angle. Returns the projection plus hatch loops per body."""
    m = matrix(rows)
    cut_shapes, hatches = [], []
    for k, sh in enumerate(shapes):
        s = sh.transformed(m)
        bb = s.BoundBox
        if bb.ZMax <= c + 1e-6:
            cut_shapes.append(s)
            continue
        if bb.ZMin >= c - 1e-6:
            continue
        tool = Part.makeBox(bb.XLength + 20, bb.YLength + 20, bb.ZMax - c + 10, V(bb.XMin - 10, bb.YMin - 10, c))
        try:
            r = s.cut(tool)
        except Exception:
            continue
        if r.isNull() or not r.Solids:
            continue
        cut_shapes.append(r)
        for f in r.Faces:
            fb = f.BoundBox
            if isinstance(f.Surface, Part.Plane) and abs(fb.ZMin - c) < 1e-4 and abs(fb.ZMax - c) < 1e-4:
                loops = [_wire_points(w, defl) for w in f.Wires]
                hatches.append((k, [lp for lp in loops if len(lp) >= 3]))
    comp = Part.makeCompound(cut_shapes)
    r = TechDraw.projectEx(comp, V(0, 0, 1))
    vis = Part.makeCompound([x for x in (r[0], r[3]) if x is not None and not x.isNull()])
    hid = Part.makeCompound([x for x in (r[5], r[8]) if x is not None and not x.isNull()])
    out = {"vis": _polylines(vis, defl), "hid": _polylines(hid, defl), "hatch": hatches}
    out["bbox"] = _bbox2(out["vis"])
    return out


# --------------------------------------------------------------- features
def _canon(d):
    d = V(d)
    d.normalize()
    k = max(range(3), key=lambda i: abs(d[i]))
    if d[k] < 0:
        d = d * -1
    return d


def _ref_frame(d):
    ref = V(0, 0, 1) if abs(d.z) < 0.9 else V(1, 0, 0)
    e1 = ref.cross(d)
    e1.normalize()
    e2 = d.cross(e1)
    return e1, e2


def _union_len(intervals):
    """Total length of a union of [a, b] intervals."""
    tot, cur = 0.0, None
    for a, b in sorted(intervals):
        if cur is None or a > cur[1]:
            if cur:
                tot += cur[1] - cur[0]
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur:
        tot += cur[1] - cur[0]
    return tot


def _merge(intervals, gap=0.02):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _ang_coverage(arcs):
    """Union of angular intervals (radians, any range) in degrees."""
    iv = []
    for a, w in arcs:
        a0 = (a - w / 2) % (2 * math.pi)
        a1 = a0 + w
        if a1 > 2 * math.pi:
            iv += [(a0, 2 * math.pi), (0, a1 - 2 * math.pi)]
        else:
            iv.append((a0, a1))
    return math.degrees(_union_len(iv))


class CylGroup:
    """All cylindrical faces sharing one axis line, split by radius."""

    def __init__(self, d, q, concave):
        self.d, self.q, self.concave = d, q, concave
        self.levels = {}          # radius -> {"t": [(t0,t1)], "arcs": [(mid, width)], "n": faces}

    def add(self, r, t0, t1, mid, width):
        lv = self.levels.setdefault(round(r, 3), {"t": [], "arcs": [], "n": 0})
        lv["t"].append((min(t0, t1), max(t0, t1)))
        lv["arcs"].append((mid, width))
        lv["n"] += 1

    def point(self, t):
        return self.q + self.d * t


def cylinders(shape, min_r=0.3):
    """Group the cylindrical faces of `shape` by axis line + concavity."""
    groups = {}
    for f in shape.Faces:
        s = f.Surface
        if not isinstance(s, Part.Cylinder) or s.Radius < min_r:
            continue
        d = _canon(s.Axis)
        c = s.Center
        q = c - d * c.dot(d)
        u0, u1, v0, v1 = f.ParameterRange
        um, vm = (u0 + u1) / 2, (v0 + v1) / 2
        p = f.valueAt(um, vm)
        n = f.normalAt(um, vm)
        foot = q + d * (p - q).dot(d)
        radial = p - foot
        if radial.Length < 1e-9:
            continue
        concave = n.dot(radial) < 0
        e1, e2 = _ref_frame(d)
        mid = math.atan2(radial.dot(e2), radial.dot(e1))
        width = abs(u1 - u0)
        sa = s.Axis
        sa.normalize()
        t_a = (c + sa * v0 - q).dot(d)
        t_b = (c + sa * v1 - q).dot(d)
        key = (round(d.x, 3), round(d.y, 3), round(d.z, 3), round(q.x, 2), round(q.y, 2), round(q.z, 2), concave)
        g = groups.get(key)
        if g is None:
            g = groups[key] = CylGroup(d, q, concave)
        g.add(s.Radius, t_a, t_b, mid, width)
    return list(groups.values())


def _inside(shape, p):
    try:
        return shape.isInside(p, 1e-4, True)
    except Exception:
        return False


def holes(shape, groups, axle_r=2.425):
    """Hole stacks: round holes (with counterbores) and axle-cross holes."""
    out = []
    for g in groups:
        if not g.concave:
            continue
        segs, cross = [], None
        for r, lv in g.levels.items():
            cov = _ang_coverage(lv["arcs"])
            ts = _merge(lv["t"])
            if abs(r - axle_r) < 0.02 and cov < 300 and lv["n"] >= 4:
                w = sorted(x[1] for x in lv["arcs"])[len(lv["arcs"]) // 2]
                cross = {"d": 2 * r, "s": 2 * r * math.sin(w / 2), "t": (ts[0][0], ts[-1][1])}
                continue
            if cov < 200:
                continue
            for a, b in ts:
                segs.append((r, a, b))
        if not segs and not cross:
            continue
        e1, _ = _ref_frame(g.d)
        if cross:
            t0, t1 = cross["t"]
            thru = all(not _inside(shape, g.point(t) + e1 * 0.2) for t in (t0 - 0.05, t1 + 0.05))
            out.append({"kind": "cross", "d": g.d, "q": g.q, "D": cross["d"], "s": cross["s"],
                        "t0": t0, "t1": t1, "thru": thru})
        if segs:
            segs.sort(key=lambda s: s[1])
            main = max(segs, key=lambda s: (s[2] - s[1], -s[0]))
            t0, t1 = min(s[1] for s in segs), max(s[2] for s in segs)
            cb = [s for s in segs if s[0] > main[0] + 0.05 and (abs(s[1] - t0) < 0.02 or abs(s[2] - t1) < 0.02)]
            thru = all(not _inside(shape, g.point(t) + e1 * main[0] * 0.5) for t in (t0 - 0.05, t1 + 0.05))
            hole = {"kind": "round", "d": g.d, "q": g.q, "D": 2 * main[0], "t0": t0, "t1": t1,
                    "len": main[2] - main[1], "thru": thru, "segs": segs}
            if cb:
                hole["cb_D"] = 2 * cb[0][0]
                hole["cb_depth"] = cb[0][2] - cb[0][1]
                hole["cb_both"] = len(cb) >= 2
            out.append(hole)
    return out


def shafts(groups, axle_r=2.375):
    """Convex cylinders: shaft segments (coverage >= 200 deg), axle crosses
    and partial arcs (outline radii)."""
    segs, crosses, arcs = [], [], []
    for g in groups:
        if g.concave:
            continue
        for r, lv in g.levels.items():
            cov = _ang_coverage(lv["arcs"])
            ts = _merge(lv["t"])
            if abs(r - axle_r) < 0.02 and cov < 300 and lv["n"] >= 4:
                w = sorted(x[1] for x in lv["arcs"])[len(lv["arcs"]) // 2]
                crosses.append({"d": g.d, "q": g.q, "D": 2 * r, "s": 2 * r * math.sin(w / 2),
                                "t0": ts[0][0], "t1": ts[-1][1]})
            elif cov >= 200:
                for a, b in ts:
                    segs.append({"d": g.d, "q": g.q, "r": r, "t0": a, "t1": b, "cov": cov})
            else:
                arcs.append({"d": g.d, "q": g.q, "r": r, "t0": ts[0][0], "t1": ts[-1][1], "cov": cov,
                             "arcs": lv["arcs"]})
    return segs, crosses, arcs


def axis_view(rows, d, tol=0.02):
    """True when direction d points along the view direction (circle view)."""
    return abs(abs(rows[2].dot(d)) - 1) < tol


def in_plane(rows, d, tol=0.02):
    return abs(rows[2].dot(d)) < tol


def section_plane(rows, groups, bb_w):
    """w-position for a section of this view: through the most hole/shaft axes
    lying in planes w = const, else the middle."""
    votes = {}
    for g in groups:
        if not in_plane(rows, g.d):
            continue
        if not g.concave and not any(_ang_coverage(lv["arcs"]) >= 200 for lv in g.levels.values()):
            continue
        w = round(rows[2].dot(g.q), 2)
        votes[w] = votes.get(w, 0) + (2 if g.concave else 1)
    mid = (bb_w[0] + bb_w[1]) / 2
    if not votes:
        return mid
    return max(votes, key=lambda w: (votes[w], -abs(w - mid)))


def profile_slice(shape, d, t, q):
    """Wires of a slice perpendicular to axis d at q + t*d (for profile details)."""
    p = q + d * t
    try:
        wires = shape.slice(d, d.dot(p))
    except Exception:
        return []
    e1, e2 = _ref_frame(d)
    out = []
    for w in wires:
        pts = []
        for e in w.OrderedEdges:
            try:
                ps = e.discretize(Deflection=0.002)
            except Exception:
                ps = [v.Point for v in e.Vertexes]
            pts += [((x - p).dot(e1), (x - p).dot(e2)) for x in ps]
        out.append(pts)
    return out

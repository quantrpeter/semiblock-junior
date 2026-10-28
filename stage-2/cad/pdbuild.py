"""Rebuild a recorded solid (sbcad.Rec) as a Part Design feature tree.

Used by fcstd_export.py, with sbcad.RECORD on while the parts are built.
Every recorded step becomes a Part Design feature on the body's running solid:

  * an extruded outline       -> Sketch + Pad (Pocket when it cuts)
  * a revolved outline        -> Sketch + Revolution (Groove when it cuts)
  * spheres and cones         -> additive / subtractive primitives
  * fillets and chamfers      -> Fillet / Chamfer on the same edges
  * an intersection of two outlines along one axis -> one Pad of the common outline
  * outlines from one builder line in one plane    -> one sketch, one Pad / Pocket

A step that has no feature of its own here (cutting with a filleted tool,
intersecting two different solids ...) is built in a hidden helper body and
joined with a Part Design Boolean. Every step is checked against the kernel's
own result and rebuilt the safer way if it differs, so the tree always
reproduces the generated solid. Features are named after the builder's
comments and variables (# bore for the core -> Pocket "bore for the core").
"""
import linecache
import re

import FreeCAD as App
import Part

from sbcad import Rec, prism_recipe

V = App.Vector
OP_OF = {"add": "fuse", "sub": "cut", "common": "common"}
BOOL_OF = {"add": "Fuse", "sub": "Cut", "common": "Common"}


class NotDirect(Exception):
    """No Part Design feature applies this step directly: use a helper body."""


# ----------------------------------------------------------------- names
def _clip(text):
    return re.split(r" \(|;|: | - | -> |, ", text.strip())[0].strip()[:48]


def _good(name):
    return name and len(name) >= 3 and not name.startswith("_") and name not in ("shape", "tools", "out")


# what a helper's outline is called when nothing in the builder names it: (adds, cuts)
KIND_WORDS = {"box": ("block", "cut-out"), "zcyl": ("cylinder", "hole"), "cyl_between": ("cylinder", "hole"),
              "cone_between": ("cone", "countersink"), "ring": ("ring", "ring groove"),
              "sector": ("sector", "sector cut"), "cross_prism": ("cross", "axle hole"),
              "stadium_xy": ("bar", "slot"), "prism_xy": ("outline", "outline cut"),
              "rounded_rect_prism": ("rounded block", "rounded pocket"), "text_solid": ("text", "engraving"),
              "revolve_rz": ("turned profile", "turned groove")}


def label(node, kind, cuts=False):
    """(feature name, True if it is a bare variable name). Order: the builder's
    comment on that line (or the line above), the variable the solid is assigned
    to (for a helper call, only when it is the first thing assigned), the variable
    it was passed in as, a private helper function's name, then what it is."""
    if node.name:
        return node.name, False
    if node.src:
        fn, ln, func = node.src
        line = linecache.getline(fn, ln)
        m = re.search(r"\s\s#\s*(.+?)\s*$", line)
        if m and "noqa" not in m.group(1):
            return _clip(m.group(1)), False
        prev = linecache.getline(fn, ln - 1).strip()
        if prev.startswith("#") and not re.match(r"#\s*[-=]{3}", prev):
            return _clip(prev.lstrip("# ")), False
        m = re.match(r"\s*([A-Za-z_]\w*)\s*\+?=\s*", line)
        if m and _good(m.group(1)) and line[m.end() - 1:m.end() + 1] != "==" and (node.col is None or node.col == m.end()):
            return m.group(1), True
    if _good(node.var):
        return node.var, True
    if node.src and node.src[2].startswith("_"):
        return node.src[2].strip("_").replace("_", " "), False
    if node.kind in KIND_WORDS:
        return KIND_WORDS[node.kind][cuts], False
    return kind, False


# --------------------------------------------------------------- geometry
def _placed(shape, m):
    s = shape.copy()
    s.transformShape(m)
    return s


def _same(a, b, tol=1e-6):
    if a is None or b is None or a.isNull() or b.isNull():
        return False
    for x, y in ((a.Volume, b.Volume), (a.Area, b.Area)):
        if abs(x - y) > tol * max(1.0, abs(y)):
            return False
    A, B = a.BoundBox, b.BoundBox
    return all(abs(x - y) < 1e-4 for x, y in zip((A.XMin, A.YMin, A.ZMin, A.XMax, A.YMax, A.ZMax),
                                                  (B.XMin, B.YMin, B.ZMin, B.XMax, B.YMax, B.ZMax)))


def _xor_small(a, b, failed=True):
    """a and b fill the same space. Measured on a (the Part Design result): an
    intermediate kernel solid can report a wrong Volume (e.g. a common() with
    split faces before removeSplitter) while its booleans are still right."""
    try:
        return a.cut(b).Volume + b.cut(a).Volume < 1e-5 * max(1.0, a.Volume)
    except Exception:
        return failed               # boolean failed: the caller decides


def _matches(a, b):
    return a is not None and b is not None and (_same(a, b) or _xor_small(a, b, failed=False))


def _flat(p):
    return V(p.x, p.y, 0)


def _geom(e):
    """Sketch geometry for an edge lying in the z = 0 plane."""
    c, a, b = e.Curve, e.FirstParameter, e.LastParameter
    if isinstance(c, Part.Line):
        return Part.LineSegment(_flat(e.valueAt(a)), _flat(e.valueAt(b)))
    if isinstance(c, Part.Circle):
        if e.isClosed():
            return Part.Circle(_flat(c.Center), V(0, 0, 1), c.Radius)
        return Part.ArcOfCircle(_flat(e.valueAt(a)), _flat(e.valueAt((a + b) / 2)), _flat(e.valueAt(b)))
    if isinstance(c, Part.Ellipse) and e.isClosed():
        x = V(c.XAxis)
        x.normalize()
        return Part.Ellipse(_flat(c.Center + x * c.MajorRadius), _flat(c.Center + V(0, 0, 1).cross(x) * c.MinorRadius),
                            _flat(c.Center))
    bs = c.copy() if isinstance(c, Part.BSplineCurve) else e.toNurbs().Edges[0].Curve
    if isinstance(c, Part.BSplineCurve):
        bs.segment(a, b)
    for i, p in enumerate(bs.getPoles()):
        bs.setPole(i + 1, _flat(p))
    return bs


_XZ = App.Matrix(1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1)    # sketch (u, v) -> (x, z)


def _resolve(node, M):
    """Follow moves down to the node that does the work; recognise plain solids."""
    while node.op == "move":
        M = M * node.args[1]
        if node.args[0].var is None:          # ribs.append(rotated(box(...))): the box is a rib
            node.args[0].var = node.var
        node = node.args[0]
    if node.op == "solid":
        node = _recognise(node) or node
    return node, M


def _like(node, op, args, m):
    leaf = Rec.__new__(Rec)
    leaf.__dict__.update(node.__dict__)
    leaf.op, leaf.args, leaf.m = op, args, m
    return leaf


def _recognise(node):
    """A sphere, or an extrusion along X, Y or Z, made without the helpers."""
    if getattr(node, "_seen", False):
        return node._recog
    node._seen, node._recog = True, None
    s = node.shape
    if len(s.Solids) == 1 and len(s.Faces) == 1 and type(s.Faces[0].Surface).__name__ == "Sphere":
        sp = s.Faces[0].Surface
        node._recog = _like(node, "sphere", (sp.Radius,), App.Placement(sp.Center, App.Rotation()).toMatrix())
        return node._recog
    for m in (App.Matrix(), App.Matrix(0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1),
              App.Matrix(0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1)):
        r = prism_recipe(s, m)
        if r:
            node._recog = _like(node, "prism", r[:2], r[2])
            return node._recog
    return None


def _in_frame(leaf, M, F):
    """leaf's outline faces expressed in frame F, if they lie in its z = 0 plane
    and extrude along +Z there; else None."""
    R = F.inverse() * M * leaf.m
    p = App.Placement(R)
    if (p.Rotation.multVec(V(0, 0, 1)) - V(0, 0, 1)).Length > 1e-9 or abs(p.Base.z) > 1e-9:
        return None
    return [_placed(f, R) for f in leaf.args[0]]


def _merge_common(node, M):
    """common() of extrusions along one axis -> one extrusion of the common outline."""
    a, Ma = _resolve(node.args[0], App.Matrix())
    if a.op != "prism":
        return None
    faces, h = a.args
    F = Ma * a.m
    lo, hi = 0.0, h
    for b in node.args[1:]:
        b, Mb = _resolve(b, App.Matrix())
        if b.op != "prism":
            return None
        R = F.inverse() * Mb * b.m
        p = App.Placement(R)
        z = p.Rotation.multVec(V(0, 0, 1))
        if abs(abs(z.z) - 1) > 1e-9:
            return None
        zb = p.Base.z
        b_lo, b_hi = (zb, zb + b.args[1]) if z.z > 0 else (zb - b.args[1], zb)
        lo, hi = max(lo, b_lo), min(hi, b_hi)
        fb = [_placed(f, R).translated(V(0, 0, -zb)) for f in b.args[0]]
        faces = Part.makeCompound(faces).common(Part.makeCompound(fb)).removeSplitter().Faces
        if not faces or hi - lo < 1e-9:
            return None
    leaf = _like(a, "prism", (faces, hi - lo), F * App.Placement(V(0, 0, lo), App.Rotation()).toMatrix())
    leaf.shape, leaf.src, leaf.var, leaf.name = node.shape, node.src, node.var, node.name
    return leaf


# ------------------------------------------------------------------ emitter
class Emitter:
    def __init__(self, doc, body, adopt, created):
        self.doc, self.body, self.adopt, self.created = doc, body, adopt, created
        self.xy = [o for o in body.Origin.OriginFeatures if o.Role == "XY_Plane"][0]

    def new(self, kind, name):
        o = self.body.newObject(kind, kind.split("::")[1])
        o.Label = name
        if "Refine" in o.PropertiesList:
            o.Refine = False
        self.created.append(o)
        return o

    def attach(self, o, M):
        o.AttachmentSupport = [(self.xy, "")]
        o.MapMode = "FlatFace"
        o.AttachmentOffset = App.Placement(M)

    def mark(self):
        return len(self.created), self.body.Tip

    def rollback(self, mk):
        n, tip = mk
        for o in reversed(self.created[n:]):
            try:
                names = [x.Name for x in o.OutListRecursive] if o.TypeId == "PartDesign::Body" else []
                names.append(o.Name)
            except Exception:
                continue
            for name in names:
                if self.doc.getObject(name) is not None:
                    self.doc.removeObject(name)
        del self.created[n:]
        if tip is None:
            self.body.BaseFeature = None
        self.body.Tip = tip

    def valid_since(self, mk):
        return all(not ({"Invalid", "Error"} & set(o.State)) for o in self.created[mk[0]:]
                   if self.doc.getObject(o.Name) is not None)

    # -------------------------------------------------------------- steps
    def step(self, node, M, mode):
        """Apply node to the running solid; keep the features only if the result is
        the kernel's own, else build node in a helper body + Boolean."""
        before = self.body.Tip.Shape.copy() if self.body.Tip else None
        try:                        # refined: a raw boolean result can report a wrong Volume
            s = _placed(node.shape, M).removeSplitter()
            target = (s if mode == "base" else getattr(before, OP_OF[mode])(s)).removeSplitter()
        except Exception:
            target = None
        mk = self.mark()
        try:
            self.direct(node, M, mode)
            self.doc.recompute()
            if self.valid_since(mk) and (target is None or _matches(self.body.Tip.Shape, target)):
                return
        except NotDirect:
            pass
        self.rollback(mk)
        self.helper(node, M, mode)

    def sequence(self, items, M):
        """Steps in order; neighbouring outlines from one builder line in one plane
        go into one sketch."""
        groups = []
        for node, mode in items:
            leaf, LM = _resolve(node, M)
            g = groups[-1] if groups else None
            if (g and mode == g["mode"] != "base" and leaf.op == "prism" == g["leaf"].op
                    and abs(leaf.args[1] - g["leaf"].args[1]) < 1e-9
                    and label(leaf, "", mode == "sub")[0] == label(g["leaf"], "", mode == "sub")[0]):
                faces = _in_frame(leaf, LM, g["F"])
                if faces and Part.makeCompound(g["faces"]).distToShape(Part.makeCompound(faces))[0] > 1e-6:
                    g["faces"] += faces
                    g["shapes"].append(_placed(leaf.shape, LM))
                    continue
            groups.append({"node": node, "mode": mode, "leaf": leaf, "F": LM * leaf.m,
                           "faces": list(leaf.args[0]) if leaf.op == "prism" else [],
                           "shapes": [_placed(leaf.shape, LM)]})
        for g in groups:
            if len(g["shapes"]) == 1:
                self.step(g["node"], M, g["mode"])
            else:
                merged = _like(g["leaf"], "prism", (g["faces"], g["leaf"].args[1]), g["F"])
                merged.shape = Part.makeCompound(g["shapes"])
                merged.name = label(g["leaf"], "", g["mode"] == "sub")[0] or None
                self.step(merged, App.Matrix(), g["mode"])

    def direct(self, node, M, mode):
        op = node.op
        if op == "move":
            if node.args[0].var is None:
                node.args[0].var = node.var
            return self.direct(node.args[0], M * node.args[1], mode)
        if op == "solid":
            leaf = _recognise(node)
            if leaf is None:
                raise NotDirect
            return self.leaf(leaf, M, mode)
        if op in ("prism", "revolve", "sphere", "cone"):
            return self.leaf(node, M, mode)
        if op == "refine":
            self.direct(node.args[0], M, mode)
            if mode == "base" and self.body.Tip is not None and "Refine" in self.body.Tip.PropertiesList:
                self.body.Tip.Refine = True
            return
        a, rest = node.args[0], node.args[1:]
        if op in ("fuse", "compound"):
            if mode == "common":
                raise NotDirect
            more = "sub" if mode == "sub" else "add"
            return self.sequence([(a, mode)] + [(b, more) for b in rest], M)
        if op == "cut":
            if mode in ("base", "add"):
                return self.sequence([(a, mode)] + [(b, "sub") for b in rest], M)
            if mode == "sub":           # right when the cut-away part misses the body: the check decides
                return self.step(a, M, "sub")
            raise NotDirect
        if op == "common":
            leaf = _merge_common(node, M=App.Matrix())
            if leaf is not None:
                return self.leaf(leaf, M, mode)
            if mode != "base":
                raise NotDirect
            return self.sequence([(a, "base")] + [(b, "common") for b in rest], M)
        if op in ("fillet", "chamfer"):
            if mode not in ("base", "add"):
                raise NotDirect
            self.direct(a, M, mode)
            return self.dress(node, M)
        raise NotDirect

    # ------------------------------------------------------------ features
    def leaf(self, node, M, mode):
        F = M * node.m
        op = node.op
        if mode == "common":
            raise NotDirect
        add = mode in ("base", "add")
        if op == "prism":
            faces, h = node.args
            name = label(node, "Pad" if add else "Pocket", not add)[0]
            sk = self.sketch(faces, F if add else F * App.Placement(V(0, 0, h), App.Rotation()).toMatrix(), name)
            f = self.new("PartDesign::Pad" if add else "PartDesign::Pocket", name)
            f.Profile = sk
            f.Length = h
        elif op == "revolve":
            name = label(node, "Revolution" if add else "Groove", not add)[0]
            face = _placed(node.args[0], _XZ.inverse())
            sk = self.sketch([face], F * _XZ, name)
            f = self.new("PartDesign::Revolution" if add else "PartDesign::Groove", name)
            f.Profile = sk
            f.ReferenceAxis = (sk, ["V_Axis"])
            f.Angle = 360
        elif op == "sphere":
            f = self.new("PartDesign::AdditiveSphere" if add else "PartDesign::SubtractiveSphere", label(node, "Sphere", not add)[0])
            f.Radius = node.args[0]
            self.attach(f, F)
        elif op == "cone":
            f = self.new("PartDesign::AdditiveCone" if add else "PartDesign::SubtractiveCone", label(node, "Cone", not add)[0])
            f.Radius1, f.Radius2, f.Height = node.args
            self.attach(f, F)
        else:
            raise NotDirect

    def sketch(self, faces, M, name):
        sk = self.new("Sketcher::SketchObject", name + " sketch")
        self.attach(sk, M)
        sk.addGeometry([_geom(e) for f in faces for w in f.Wires for e in w.Edges], False)
        sk.Visibility = False
        return sk

    def dress(self, node, M):
        """Fillet / chamfer the running solid's edges that lie on the recorded ones."""
        self.doc.recompute()
        tip = self.body.Tip
        _, size, edges = node.args
        want = Part.makeCompound([_placed(e, M) for e in edges])
        box = want.BoundBox
        box.enlarge(1e-4)
        names, total = [], 0.0
        for i, e in enumerate(tip.Shape.Edges):
            if not box.intersect(e.BoundBox):
                continue
            a, b = e.FirstParameter, e.LastParameter
            if all(Part.Vertex(e.valueAt(t)).distToShape(want)[0] < 1e-5 for t in (a, (a + b) / 2, b)):
                names.append("Edge%d" % (i + 1))
                total += e.Length
        if not names or abs(total - sum(e.Length for e in edges)) > 1e-4 * max(1.0, total):
            raise NotDirect
        name, bare = label(node, node.op.title())
        name = name + " " + node.op if bare else name
        f = self.new("PartDesign::Fillet" if node.op == "fillet" else "PartDesign::Chamfer", name)
        f.Base = (tip, names)
        if node.op == "fillet":
            f.Radius = size
        else:
            f.Size = size

    def helper(self, node, M, mode):
        name = label(node, "solid")[0]
        if mode == "base":                    # nothing to join to: the solid itself starts the body
            src = self.doc.addObject("Part::Feature", "Solid")
            src.Shape = _placed(node.shape, M)
            src.Label = "%s source solid" % name
            src.Visibility = False
            self.adopt(src)
            self.created.append(src)
            self.body.BaseFeature = src
            self.body.Group[0].Label = name
            self.created.append(self.body.Group[0])
            self.doc.recompute()
            return
        h = self.doc.addObject("PartDesign::Body", "Body")     # the Boolean holds it, not the part
        h.Label = name
        self.created.append(h)
        Emitter(self.doc, h, lambda o: None, self.created).step(node, M, "base")
        h.Visibility = False
        b = self.new("PartDesign::Boolean", name)
        b.Type = BOOL_OF[mode]
        b.addObjects([h])
        self.doc.recompute()
        h.Visibility = False


def build(doc, body, shape, adopt):
    """Fill an empty Part Design body with features that rebuild shape (a Rec
    or a plain solid). adopt(obj) puts helper objects in the part's container.
    Returns (features, helper bodies, True if it fell back to the plain solid)."""
    node = shape if isinstance(shape, Rec) else Rec(shape)
    if not isinstance(shape, Rec):
        node.src = None
    created = []
    em = Emitter(doc, body, adopt, created)
    em.step(node, App.Matrix(), "base")
    doc.recompute()
    fell_back = False
    if not (_matches(body.Shape, node.shape) and _xor_small(body.Shape, node.shape)):
        em.rollback((0, None))
        em.helper(node, App.Matrix(), "base")
        fell_back = True
    for o in body.Group:
        o.Visibility = o == body.Tip
    feats = [o for o in body.Group if not o.TypeId.startswith("Sketcher")]
    helpers = [o for o in created if o.TypeId == "PartDesign::Body" and doc.getObject(o.Name) is not None]
    return len(feats), len(helpers), fell_back

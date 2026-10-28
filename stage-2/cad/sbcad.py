"""SemiBlock CAD helpers on top of FreeCAD's Part (OpenCascade) kernel.

Runs inside FreeCAD's bundled Python (freecadcmd). Provides:
  * small solid-modelling helpers (boxes, cylinders, revolves, text engraving)
  * a tiny Part / Instance / Scene model (a part = several coloured bodies)
  * exporters: STEP + STL per part, GLB per scene (shared by Blender + viewer)
"""
import json
import math
import os
import re
import struct

import FreeCAD as App
import Part
import numpy as np

V = App.Vector
FONT_DIR = "/System/Library/Fonts/Supplemental/"
FONT = "Arial Rounded Bold.ttf"


# ---------------------------------------------------------------- primitives
def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def zcyl(r, z0, z1, x=0.0, y=0.0):
    return Part.makeCylinder(r, z1 - z0, V(x, y, z0))


def cyl_between(r, p0, p1):
    p0, p1 = V(*p0), V(*p1)
    d = p1 - p0
    n = V(d)
    n.normalize()
    return Part.makeCylinder(r, d.Length, p0, n)


def cone_between(r0, r1, p0, p1):
    p0, p1 = V(*p0), V(*p1)
    d = p1 - p0
    n = V(d)
    n.normalize()
    return Part.makeCone(r0, r1, d.Length, p0, n)


def revolve_rz(pts):
    """Solid of revolution around Z from an (r, z) outline."""
    poly = [V(r, 0, z) for r, z in pts]
    if (poly[0] - poly[-1]).Length > 1e-9:
        poly.append(poly[0])
    return Part.Face(Part.makePolygon(poly)).revolve(V(0, 0, 0), V(0, 0, 1), 360)


def prism_xy(pts, z0, z1):
    poly = [V(x, y, z0) for x, y in pts]
    if (poly[0] - poly[-1]).Length > 1e-9:
        poly.append(poly[0])
    return Part.Face(Part.makePolygon(poly)).extrude(V(0, 0, z1 - z0))


def stadium_xy(length, r, z0, z1):
    """Beam outline: centre line from (0,0) to (length,0), radius r."""
    s = zcyl(r, z0, z1, 0, 0)
    if length > 0:
        s = s.fuse([box(0, -r, z0, length, r, z1), zcyl(r, z0, z1, length, 0)])
    return s.removeSplitter()


def ring(r0, r1, z0, z1, x=0.0, y=0.0):
    return zcyl(r1, z0, z1, x, y).cut(zcyl(r0, z0 - 1, z1 + 1, x, y))


def sector(r0, r1, a_center_deg, span_deg, z0, z1, steps=24):
    """Annular sector (used for pad-printed status rings)."""
    a0 = math.radians(a_center_deg - span_deg / 2)
    a1 = math.radians(a_center_deg + span_deg / 2)
    outer = [(r1 * 1.05 * math.cos(a0 + (a1 - a0) * i / steps),
              r1 * 1.05 * math.sin(a0 + (a1 - a0) * i / steps)) for i in range(steps + 1)]
    wedge = prism_xy([(0, 0)] + outer, z0, z1)
    return wedge.common(ring(r0, r1, z0, z1))


def cross_prism(d, s, z0, z1, x=0.0, y=0.0):
    """Axle cross (tip-to-tip d, arm thickness s) with round arm tips."""
    c = box(x - d / 2, y - s / 2, z0, x + d / 2, y + s / 2, z1).fuse(
        box(x - s / 2, y - d / 2, z0, x + s / 2, y + d / 2, z1))
    return c.common(zcyl(d / 2, z0, z1, x, y)).removeSplitter()


def rounded_box(x0, y0, z0, x1, y1, z1, r):
    b = box(x0, y0, z0, x1, y1, z1)
    if r > 0:
        try:
            b = b.makeFillet(r, b.Edges)
        except Exception:
            pass
    return b


def rounded_rect_prism(cx, cy, w, h, r, z0, z1):
    """Rectangle w x h centred at (cx, cy) with rounded corners, extruded in Z."""
    r = min(r, w / 2 - 1e-3, h / 2 - 1e-3)
    s = box(cx - w / 2 + r, cy - h / 2, z0, cx + w / 2 - r, cy + h / 2, z1).fuse([
        box(cx - w / 2, cy - h / 2 + r, z0, cx + w / 2, cy + h / 2 - r, z1),
        zcyl(r, z0, z1, cx - w / 2 + r, cy - h / 2 + r), zcyl(r, z0, z1, cx + w / 2 - r, cy - h / 2 + r),
        zcyl(r, z0, z1, cx - w / 2 + r, cy + h / 2 - r), zcyl(r, z0, z1, cx + w / 2 - r, cy + h / 2 - r)])
    return s.removeSplitter()


def try_fillet(shape, r, edges):
    if not edges:
        return shape
    try:
        return shape.makeFillet(r, edges)
    except Exception:
        return shape


def edges_at_z(shape, z, tol=1e-6):
    return [e for e in shape.Edges
            if abs(e.BoundBox.ZMin - z) < tol and abs(e.BoundBox.ZMax - z) < tol]


# ------------------------------------------------------------- placement
def frame(shape, xdir, ydir, origin=(0, 0, 0)):
    """Re-express a shape built in a local frame: local X->xdir, Y->ydir, Z->X x Y."""
    x, y = V(*xdir), V(*ydir)
    z = x.cross(y)
    m = App.Matrix(x.x, y.x, z.x, origin[0],
                   x.y, y.y, z.y, origin[1],
                   x.z, y.z, z.z, origin[2],
                   0, 0, 0, 1)
    s = shape.copy()
    s.transformShape(m)
    return s


def moved(shape, dx=0.0, dy=0.0, dz=0.0):
    s = shape.copy()
    s.translate(V(dx, dy, dz))
    return s


def rotated(shape, axis, angle_deg, center=(0, 0, 0)):
    s = shape.copy()
    s.rotate(V(*center), V(*axis), angle_deg)
    return s


# ------------------------------------------------------------------ text
def text_solid(text, size, depth, font=FONT):
    """Extruded text, centred on the origin in XY, from z=0 to z=depth."""
    faces = []
    for wires in Part.makeWireString(text, FONT_DIR, font, size, 0):
        if wires:
            f = Part.makeFace(wires, "Part::FaceMakerBullseye")
            faces.extend(f.Faces)
    comp = Part.makeCompound(faces)
    bb = comp.BoundBox
    comp.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, 0))
    return comp.extrude(V(0, 0, depth))


def engrave(text, size, depth, center, read_dir, up_dir, font=FONT):
    """Cutter for text engraved into a face. read_dir/up_dir lie in the face;
    the face normal is read_dir x up_dir (pointing out of the part)."""
    t = text_solid(text, size, depth + 0.2, font)
    t.translate(V(0, 0, -depth))
    return frame(t, read_dir, up_dir, center)


def emboss(text, size, height, center, read_dir, up_dir, font=FONT):
    """Raised text sitting on a face (separate body, e.g. for a second colour)."""
    t = text_solid(text, size, height + 0.02, font)
    t.translate(V(0, 0, -0.02))
    return frame(t, read_dir, up_dir, center)


# ------------------------------------------------------------- materials
def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


# name: (sRGB hex, metallic, roughness, alpha, emissive strength)
PALETTE = {
    "sb_blue":     ("#1F6FE5", 0.0, 0.32, 1.0, 0.0),
    "sb_yellow":   ("#FFC21A", 0.0, 0.32, 1.0, 0.0),
    "sb_white":    ("#F2F4F7", 0.0, 0.35, 1.0, 0.0),
    "sb_lgrey":    ("#B4BCC6", 0.0, 0.35, 1.0, 0.0),
    "sb_dgrey":    ("#5B636D", 0.0, 0.38, 1.0, 0.0),
    "sb_black":    ("#24282E", 0.0, 0.40, 1.0, 0.0),
    "sb_magenta":  ("#C8209E", 0.0, 0.30, 1.0, 0.0),
    "ind_red":     ("#E8322E", 0.0, 0.30, 1.0, 0.0),
    "ind_green":   ("#1DC45A", 0.0, 0.30, 1.0, 0.0),
    "rubber":      ("#1C1F23", 0.0, 0.85, 1.0, 0.0),
    "steel":       ("#C9CED6", 1.0, 0.22, 1.0, 0.0),
    "glass_dark":  ("#0D1422", 0.0, 0.22, 1.0, 0.0),
    "screen_glow": ("#4FD1FF", 0.0, 0.40, 1.0, 2.5),
    "led_cyan":    ("#53E0FF", 0.0, 0.25, 1.0, 1.6),
    "led_red":     ("#FF3B30", 0.0, 0.25, 1.0, 1.4),
    "port_black":  ("#0E1013", 0.0, 0.55, 1.0, 0.0),
    "contact":     ("#D4A537", 1.0, 0.30, 1.0, 0.0),
    "cable":       ("#191B1F", 0.0, 0.60, 1.0, 0.0),
    "mesh_dark":   ("#2B3038", 0.6, 0.45, 1.0, 0.0),
    "arrow":       ("#FF6A13", 0.0, 0.40, 1.0, 0.0),
    "ghost":       ("#9FB4CC", 0.0, 0.40, 0.25, 0.0),
    "sb_teal":     ("#12A89A", 0.0, 0.32, 1.0, 0.0),
    "sb_violet":   ("#7447EE", 0.0, 0.32, 1.0, 0.0),
    "dome_white":  ("#F4F2EA", 0.0, 0.45, 1.0, 0.0),
    "dome_violet": ("#B9A6F2", 0.0, 0.30, 1.0, 0.0),
    "pcb":         ("#1E3554", 0.0, 0.45, 1.0, 0.0),
    "ceramic":     ("#D8C49A", 0.0, 0.55, 1.0, 0.0),
    "tube":        ("#9FD8F5", 0.0, 0.15, 1.0, 0.0),
    "led_green":   ("#3DFF7E", 0.0, 0.25, 1.0, 1.4),
    "led_yellow":  ("#FFD23F", 0.0, 0.25, 1.0, 1.4),
    "led_white":   ("#FFFFFF", 0.0, 0.25, 1.0, 1.2),
    "brass":       ("#C9A24A", 1.0, 0.30, 1.0, 0.0),
    "solar":       ("#1C2E68", 0.3, 0.12, 1.0, 0.0),
    "soft":        ("#FFC21A", 0.0, 0.60, 1.0, 0.0),
    "terminal":    ("#2E9E57", 0.0, 0.45, 1.0, 0.0),
    "ir_led":      ("#4B2B6E", 0.0, 0.10, 1.0, 0.0),
}


# ------------------------------------------------------- part / scene model
class Body:
    def __init__(self, name, shape, mat, printable=True):
        self.name, self.shape, self.mat, self.printable = name, shape, mat, printable


class PartDef:
    """A catalogue part made of one or more coloured bodies."""

    def __init__(self, pid, title, bodies, meta=None):
        self.pid, self.title, self.bodies, self.meta = pid, title, bodies, meta or {}


class Instance:
    def __init__(self, name, bodies, extras=None):
        self.name, self.bodies, self.extras = name, bodies, extras or {}


def place(part, name, xdir=(1, 0, 0), ydir=(0, 1, 0), origin=(0, 0, 0), extras=None):
    bodies = [Body(b.name, frame(b.shape, xdir, ydir, origin), b.mat, b.printable)
              for b in part.bodies]
    return Instance(name, bodies, extras)


# ------------------------------------------------------------- sectioning
def section_bodies(bodies, keep_side, plane_axis, plane_pos):
    """Cut bodies with an axis-aligned plane. Faces lying on the cut plane get
    material '<mat>__cut' so renderers can tint them like a CAD section."""
    big = 1000.0
    lo = [-big, -big, -big]
    hi = [big, big, big]
    ax = "xyz".index(plane_axis)
    if keep_side < 0:   # keep the negative side -> remove positive half-space
        lo[ax] = plane_pos
    else:
        hi[ax] = plane_pos
    tool = box(*lo, *hi)
    out = []
    for b in bodies:
        s = b.shape.cut(tool)
        if s.isNull() or not s.Faces:
            continue
        cut_faces, skin = [], []
        for f in s.Faces:
            on_plane = all(abs(v.Point[ax] - plane_pos) < 1e-5 for v in f.Vertexes)
            (cut_faces if on_plane else skin).append(f)
        if skin:
            out.append(Body(b.name, Part.makeCompound(skin), b.mat, b.printable))
        if cut_faces:
            out.append(Body(b.name + "_cut", Part.makeCompound(cut_faces), b.mat + "__cut", False))
    return out


# ------------------------------------------------------------- meshing
def mesh_shape(shape, tol, ang=0.25):
    """Mesh a shape once with MeshPart (explicit linear + angular deflection),
    then split it per B-rep face so normals are smooth inside a face and crisp
    at edges. Returns (positions, normals, indices) in mm."""
    import MeshPart
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=tol, AngularDeflection=ang, Relative=False, Segments=True)
    pts, fac = m.Topology
    if not fac:
        return None
    P = np.array([[p.x, p.y, p.z] for p in pts], dtype=np.float64)
    F = np.array(fac, dtype=np.int64)
    segs = [m.getSegment(i) for i in range(m.countSegments())] or [list(range(len(F)))]
    outP, outN, outI, base = [], [], [], 0
    for seg in segs:
        if not seg:
            continue
        sf = F[np.array(seg, dtype=np.int64)]
        uniq, inv = np.unique(sf.reshape(-1), return_inverse=True)
        lp, li = P[uniq], inv.reshape(-1, 3)
        fn = np.cross(lp[li[:, 1]] - lp[li[:, 0]], lp[li[:, 2]] - lp[li[:, 0]])
        vn = np.zeros_like(lp)
        for j in range(3):
            np.add.at(vn, li[:, j], fn)
        vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
        outP.append(lp)
        outN.append(vn)
        outI.append(li + base)
        base += len(lp)
    return np.vstack(outP), np.vstack(outN), np.vstack(outI)


def to_gltf_frame(P):
    """CAD (mm, Z-up) -> glTF (m, Y-up)."""
    return np.stack([P[:, 0], P[:, 2], -P[:, 1]], axis=1) * 0.001


def vec_to_gltf(v, scale=0.001):
    return [v[0] * scale, v[2] * scale, -v[1] * scale]


def write_glb(path, instances, tol=0.03, meta=None, ang=0.25):
    bin_chunks, buffer_views, accessors = [], [], []
    meshes, nodes, materials, mat_index = [], [], [], {}
    offset = 0

    def add_view(data, target):
        nonlocal offset
        pad = (-len(data)) % 4
        bin_chunks.append(data + b"\x00" * pad)
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data), "target": target})
        offset += len(data) + pad
        return len(buffer_views) - 1

    def material(name):
        if name in mat_index:
            return mat_index[name]
        base = name.split("__")[0]
        hexc, metal, rough, alpha, emis = PALETTE.get(base, ("#FF00FF", 0, 0.5, 1, 0))
        rgb = hex_rgb(hexc)
        if name.endswith("__cut"):                 # section faces: darker tint
            rgb = [int(c * 0.62) for c in rgb]
        lin = [srgb_to_linear(c) for c in rgb]
        m = {"name": name,
             "pbrMetallicRoughness": {"baseColorFactor": lin + [alpha],
                                      "metallicFactor": metal, "roughnessFactor": rough},
             "doubleSided": name.endswith("__cut")}
        if alpha < 1:
            m["alphaMode"] = "BLEND"
        if emis > 0:
            m["emissiveFactor"] = lin
            m["extensions"] = {"KHR_materials_emissive_strength": {"emissiveStrength": emis}}
        materials.append(m)
        mat_index[name] = len(materials) - 1
        return mat_index[name]

    root_children = []
    for inst in instances:
        child_ids = []
        for b in inst.bodies:
            res = mesh_shape(b.shape, tol, ang)
            if res is None:
                continue
            Pm, Nm, Im = res
            Pg = to_gltf_frame(Pm).astype(np.float32)
            Ng = np.stack([Nm[:, 0], Nm[:, 2], -Nm[:, 1]], axis=1).astype(np.float32)
            small = len(Pg) < 65535
            Ig = Im.astype(np.uint16 if small else np.uint32).reshape(-1)
            vp = add_view(Pg.tobytes(), 34962)
            vn = add_view(Ng.tobytes(), 34962)
            vi = add_view(Ig.tobytes(), 34963)
            accessors.append({"bufferView": vp, "componentType": 5126, "count": len(Pg), "type": "VEC3",
                              "min": Pg.min(axis=0).tolist(), "max": Pg.max(axis=0).tolist()})
            ap = len(accessors) - 1
            accessors.append({"bufferView": vn, "componentType": 5126, "count": len(Ng), "type": "VEC3"})
            an = len(accessors) - 1
            accessors.append({"bufferView": vi, "componentType": 5123 if small else 5125, "count": len(Ig), "type": "SCALAR"})
            ai = len(accessors) - 1
            meshes.append({"name": b.name, "primitives": [
                {"attributes": {"POSITION": ap, "NORMAL": an}, "indices": ai, "material": material(b.mat)}]})
            nodes.append({"name": b.name, "mesh": len(meshes) - 1})
            child_ids.append(len(nodes) - 1)
        if not child_ids:
            continue
        node = {"name": inst.name, "children": child_ids}
        if inst.extras:
            node["extras"] = inst.extras
        nodes.append(node)
        root_children.append(len(nodes) - 1)

    gltf = {"asset": {"version": "2.0", "generator": "SemiBlock Junior stage-2 CAD (FreeCAD/OCC)"},
            "scene": 0, "scenes": [{"nodes": root_children, "extras": meta or {}}],
            "nodes": nodes, "meshes": meshes, "materials": materials,
            "accessors": accessors, "bufferViews": buffer_views,
            "buffers": [{"byteLength": offset}]}
    if any("extensions" in m for m in materials):
        gltf["extensionsUsed"] = ["KHR_materials_emissive_strength"]
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((-len(js)) % 4)
    bin_data = b"".join(bin_chunks)
    total = 12 + 8 + len(js) + 8 + len(bin_data)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A))
        fh.write(js)
        fh.write(struct.pack("<II", len(bin_data), 0x004E4942))
        fh.write(bin_data)
    return os.path.getsize(path)


def _step_colours(path, colours):
    """Give every solid of the named STEP products a surface colour (AP214
    styled items, as OCC writes them from the GUI; headless FreeCAD writes none).
    colours: product name -> sRGB hex. Returns the names that got a colour."""
    with open(path) as fh:
        txt = fh.read()
    ents = {int(i): e for i, e in re.findall(r"^#(\d+) = (.*?);$", txt, re.S | re.M)}

    def refs(i, kind):
        e = ents.get(i, "")
        return [int(r) for r in re.findall(r"#(\d+)", e)] if e.startswith(kind + "(") else []

    n, new, styles, done = max(ents), [], {}, set()

    def add(e):
        nonlocal n
        n += 1
        new.append("#%d = %s;" % (n, e))
        return n

    for i in sorted(ents):
        sdr = refs(i, "SHAPE_DEFINITION_REPRESENTATION")      # (#pds, #rep)
        if not sdr:
            continue
        pd = (refs(sdr[0], "PRODUCT_DEFINITION_SHAPE") or [0])[0]
        pdf = (refs(pd, "PRODUCT_DEFINITION") or [0])[0]
        prod = (refs(pdf, "PRODUCT_DEFINITION_FORMATION") or [0])[0]
        m = re.match(r"PRODUCT\('((?:[^']|'')*)'", ents.get(prod, ""))
        name = m.group(1).replace("''", "'") if m else None
        rep = [int(r) for r in re.findall(r"#(\d+)", ents[sdr[1]])]   # items..., context
        solids = [s for s in rep[:-1] if ents[s].startswith(("MANIFOLD_SOLID_BREP(", "BREP_WITH_VOIDS("))]
        if name not in colours or not solids:
            continue
        hexc = colours[name]
        if hexc not in styles:
            rgb = add("COLOUR_RGB('',%.4f,%.4f,%.4f)" % tuple(c / 255.0 for c in hex_rgb(hexc)))
            fill = add("FILL_AREA_STYLE('',(#%d))" % add("FILL_AREA_STYLE_COLOUR('',#%d)" % rgb))
            side = add("SURFACE_SIDE_STYLE('',(#%d))" % add("SURFACE_STYLE_FILL_AREA(#%d)" % fill))
            styles[hexc] = add("PRESENTATION_STYLE_ASSIGNMENT((#%d))" % add("SURFACE_STYLE_USAGE(.BOTH.,#%d)" % side))
        items = [add("STYLED_ITEM('color',(#%d),#%d)" % (styles[hexc], s)) for s in solids]
        add("MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',(%s),#%d)"
            % (",".join("#%d" % s for s in items), rep[-1]))
        done.add(name)
    head, sep, tail = txt.rpartition("ENDSEC;")
    with open(path, "w") as fh:
        fh.write(head + "\n".join(new) + "\n" + sep + tail)
    return done


def export_step(part, path):
    """STEP for suppliers: one named, coloured solid per moulded part. A part made
    of several (sleeve + core, collet + ring, base + cover ...) is an assembly
    whose components carry the drawing numbers <pid>-01, -02 ... ("purchased"
    for steel bearings and balls), so every CAD tool opens them as separate parts."""
    import Import
    printable = [b for b in part.bodies if b.printable]
    doc = App.newDocument("step_export")
    try:
        objs, colours = [], {}
        for i, b in enumerate(printable):
            o = doc.addObject("Part::Feature", "c%d" % i)
            o.Shape = b.shape
            if len(printable) == 1:
                o.Label = "%s %s" % (part.pid, part.title)
            else:
                o.Label = "%s %s" % ("purchased" if b.mat == "steel" else "%s-%02d" % (part.pid, i + 1), b.name)
            colours[o.Label] = PALETTE.get(b.mat, ("#FF00FF",))[0]
            objs.append(o)
        if len(objs) > 1:
            root = doc.addObject("App::Part", "Part")
            root.Label = "%s %s" % (part.pid, part.title)
            for o in objs:
                root.addObject(o)
            objs = [root]
        doc.recompute()
        Import.export(objs, path)
    finally:
        App.closeDocument(doc.Name)
    missing = set(colours) - _step_colours(path, colours)
    if missing:
        print("STEP %s: no colour for %s" % (part.pid, ", ".join(sorted(missing))), flush=True)


def export_part(part, step_dir, stl_dir, tol=0.02):
    export_step(part, os.path.join(step_dir, part.pid + ".step"))
    comp = Part.makeCompound([b.shape for b in part.bodies if b.printable])
    # STL: printable bodies only, one file per part (mm)
    import Mesh
    import MeshPart
    m = MeshPart.meshFromShape(Shape=comp, LinearDeflection=tol, AngularDeflection=0.3, Relative=False)
    Mesh.Mesh(m).write(os.path.join(stl_dir, part.pid + ".stl"))

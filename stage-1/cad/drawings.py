"""2D manufacturing drawings for every stage-1 part (run with freecadcmd).

    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd stage-1/cad/drawings.py

    SB_PIDS="SB-B05 SB-TL2"   limit to these parts

Outputs:
    drawings/<id>.pdf            A3 sheets: assembly (if several components) + one per component
    cad/build/dwg/<sheet>.svg    intermediate SVG per sheet
    drawings/index.json          sheet list (used by fcstd_export.py, make_docs.py, the viewer)
    drawings/SemiBlock-Junior-drawings-RevA.pdf   every sheet behind a drawing index
    drawings/SemiBlock-Junior-parts-list.csv      RFQ parts list (opens in Excel)
Mechanical parts get full drawings; electronic modules get outline &
interface drawings (their enclosure internals are a stage-2 design task).
"""
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402

import catalog as CAT  # noqa: E402
import dwg_data as D  # noqa: E402
import dwg_geom as G  # noqa: E402
import dwg_sheet as S  # noqa: E402
import params as PR  # noqa: E402

V = App.Vector
STAGE = os.path.dirname(HERE)
OUT_PDF = os.path.join(STAGE, "drawings")
OUT_SVG = os.path.join(HERE, "build", "dwg")
for d in (OUT_PDF, OUT_SVG):
    os.makedirs(d, exist_ok=True)
PIDS = os.environ.get("SB_PIDS", "").split()
fmt = S.fmt


# ------------------------------------------------------------ components
class Comp:
    def __init__(self, name, shape, mat, qty=1):
        self.name, self.shape, self.mat, self.qty = name, shape, mat, qty


def components(part):
    out = []
    for b in part.bodies:
        if not b.printable:
            continue
        sol = b.shape.Solids
        if len(sol) > 1 and all(abs(s.Volume - sol[0].Volume) < 1e-3 * sol[0].Volume for s in sol):
            out.append(Comp(b.name, sol[0], b.mat, len(sol)))
        else:
            out.append(Comp(b.name, b.shape, b.mat, 1))
    return out


def analyse(shape):
    groups = G.cylinders(shape)
    segs, crosses, arcs = G.shafts(groups)
    return {"groups": groups, "holes": G.holes(shape, groups), "segs": segs, "crosses": crosses, "arcs": arcs}


def main_axis(shape, an):
    bb = shape.optimalBoundingBox()
    c = bb.Center
    tol_c = max(0.35, 0.02 * max(bb.XLength, bb.YLength, bb.ZLength))
    best = {}
    for f in an["segs"] + an["crosses"] + an["holes"]:
        v = c - f["q"]
        perp = v - f["d"] * v.dot(f["d"])
        if perp.Length < tol_c:
            k = (round(f["d"].x, 2), round(f["d"].y, 2), round(f["d"].z, 2))
            ln = abs(f["t1"] - f["t0"])
            if k not in best or ln > best[k][2]:
                best[k] = (f["d"], f["q"], ln)
    if not best:
        return None
    d, q, _ = max(best.values(), key=lambda x: x[2])
    return d, q


def strategy(family, shape, an):
    if family in D.MODULE_FAMILIES:
        return "outline", None
    ax = main_axis(shape, an)
    if ax:
        d = ax[0]
        bb = shape.optimalBoundingBox()
        ext = [bb.XLength, bb.YLength, bb.ZLength]
        k = max(range(3), key=lambda i: abs(d[i]))
        perp = [ext[i] for i in range(3) if i != k]
        if abs(perp[0] - perp[1]) <= 0.12 * max(perp):
            if k == 0:
                return "turned", ax
            if k == 2:
                return "disc", ax
    return "prismatic", ax


# ----------------------------------------------------------------- views
def _same(a, b):
    la, lb = G.edge_length(a["vis"]), G.edge_length(b["vis"])
    ba, bb = a["bbox"], b["bbox"]
    return abs(la - lb) <= 0.02 * max(la, lb, 1e-6) and \
        all(abs((ba[i + 2] - ba[i]) - (bb[i + 2] - bb[i])) < 0.05 for i in (0, 1))


def build_views(shape, shapes_for_section, an, strat, letters, ax=None):
    proj = {n: G.project(shape, G.VIEWS[n]) for n in ("front", "top", "left")}
    names = ["front", "left", "top"]
    if strat == "turned" and _same(proj["top"], proj["front"]):
        names.remove("top")
    if strat == "disc" and _same(proj["left"], proj["front"]):
        names.remove("left")
    if strat == "prismatic" and _same(proj["left"], proj["front"]):
        names.remove("left")
    bb = shape.optimalBoundingBox()
    vbs = {}
    for n in names:
        rows = G.VIEWS[n]
        geo = proj[n]
        label = None
        sec = None
        want_sec = strat != "outline" and n in ("front", "left") and not (strat == "turned" and n == "left") \
            and not (strat == "disc" and n == "left")
        if want_sec and any(g.concave and G.in_plane(rows, g.d) for g in an["groups"]):
            ws = [G.to_view(rows, V(x, y, z))[2] for x in (bb.XMin, bb.XMax) for y in (bb.YMin, bb.YMax)
                  for z in (bb.ZMin, bb.ZMax)]
            if ax is not None and strat in ("turned", "disc", "assembly") and G.in_plane(rows, ax[0]):
                c = G.to_view(rows, ax[1])[2]
            else:
                c = G.section_plane(rows, an["groups"], (min(ws), max(ws)))
            sgeo = G.section(shapes_for_section, rows, c)
            if sgeo is not None:
                geo = sgeo
                geo["hid"] = ([], [])
                letter = letters.pop(0)
                label = "%s–%s" % (letter, letter)
                sec = {"letter": letter, "c": c, "n": rows[2]}
        elif G.edge_length(geo["hid"]) > 1.2 * G.edge_length(geo["vis"]) or strat == "outline":
            geo["hid"] = ([], [])
        vb = S.ViewBlock(n, geo, label)
        vb.rows = rows
        vb.sec = sec
        vbs[n] = vb
    # cutting-plane lines on a host view
    for vb in list(vbs.values()):
        if not vb.sec:
            continue
        n3 = vb.sec["n"]
        for host in ("top", "left", "front"):
            h = vbs.get(host)
            if h is None or h is vb or h.sec or abs(h.rows[2].dot(n3)) > 0.02:
                continue
            nx, ny = n3.dot(h.rows[0]), n3.dot(h.rows[1])
            h.cuts.append({"n": (nx, ny), "k": vb.sec["c"], "arrow": (-nx, -ny), "letter": vb.sec["letter"]})
            h.extra.append({"pad": {"top": 12, "bottom": 12, "left": 12, "right": 12}})
            break
    iso_geo = G.project(shape, G.VIEWS["iso"], hidden=False)
    iso = S.ViewBlock("iso", iso_geo, None, kind="iso")
    return vbs, iso


# ------------------------------------------------------------ annotations
def view_for_axis(vbs, d, order=("top", "front", "left")):
    for n in order:
        vb = vbs.get(n)
        if vb is not None and G.axis_view(vb.rows, d):
            return vb
    return None


def P2(vb, p):
    x, y, _ = G.to_view(vb.rows, p)
    return (x, y)


def hole_lines(hs):
    h = hs[0]
    n = len(hs)
    pre = ("%d× " % n) if n > 1 else ""
    if h["kind"] == "cross":
        t1, c1 = D.tol("xhole", h["D"])
        t2, c2 = D.tol("xhole_s", h["s"])
        return ["%sAxle hole 十字孔 +%s %s / %s %s" % (pre, fmt(h["D"]), t1, fmt(h["s"]), t2),
                "%s · see detail 见详图" % ("THRU 通孔" if h["thru"] else "depth %s 深" % fmt(h["t1"] - h["t0"]))], c1 or c2
    t, ctf = D.tol("hole", h["D"])
    lines = ["%sØ%s %s %s" % (pre, fmt(h["D"]), t, "THRU 通孔" if h["thru"] else "↧%s" % fmt(h["len"]))]
    if "cb_D" in h:
        t2, c2 = D.tol("cbore", h["cb_D"])
        t3, c3 = D.tol("cbdepth", h["cb_depth"])
        lines.append("沉孔 CBORE Ø%s %s × %s %s deep" % (fmt(h["cb_D"]), t2, fmt(h["cb_depth"]), t3))
        if h.get("cb_both"):
            lines.append("both sides 两面")
        ctf = ctf or c2 or c3
    return [s.replace("  ", " ") for s in lines], ctf


def annotate_holes(vbs, an, strat, ax, details, ctx):
    groups = {}
    for h in an["holes"]:
        if strat in ("turned",) and ax and abs(h["d"].dot(ax[0])) > 0.98:
            c = h["q"] - ax[1]
            if (c - ax[0] * c.dot(ax[0])).Length < 0.3:
                continue                       # bore on the main axis: dimensioned as a diameter
        vb = view_for_axis(vbs, h["d"])
        if vb is None:
            continue
        sig = (vb.name, h["kind"], round(h["D"], 2), round(h.get("s", 0), 2), h["thru"],
               round(h.get("cb_D", 0), 2), round(h.get("cb_depth", 0), 2), bool(h.get("cb_both")))
        groups.setdefault(sig, []).append(h)
    done = {}
    for sig, hs in groups.items():
        vb = vbs[sig[0]]
        cs = []
        for h in hs:
            c = P2(vb, h["q"] + h["d"] * ((h["t0"] + h["t1"]) / 2))
            cs.append(c)
            vb.marks.append((c, h["D"] / 2))
        k = max(range(len(cs)), key=lambda i: cs[i][0] + cs[i][1])
        r = hs[0]["D"] / 2
        anchor = (cs[k][0] + r * 0.707, cs[k][1] + r * 0.707)
        lines, ctf = hole_lines(hs)
        pcd = None
        if strat == "disc" and ax and len(hs) >= 3:
            c0 = P2(vb, ax[1])
            ds = [math.hypot(c[0] - c0[0], c[1] - c0[1]) for c in cs]
            if max(ds) - min(ds) < 0.02 and min(ds) > 0.5:
                pcd = 2 * ds[0]
                lines.append("EQ. SP. on PCD Ø%s 均布" % fmt(pcd))
                vb.extra.append({"circle": (c0, pcd / 2)})
                ctx["pcd_views"].add(vb.name)
        vb.leaders.append(S.Leader(anchor, lines, "right", ctf))
        if pcd is None and (strat != "outline" or abs(hs[0]["D"] - PR.HOLE_D) < 0.01):
            position_dims(vb, cs, done.setdefault(vb.name, set()))
        if hs[0]["kind"] == "cross":
            ctx["axle_holes"] = True
            if "xhole" not in ctx["details"]:
                ctx["details"].add("xhole")
                details.append(cross_detail("Axle hole 十字孔", hs[0]["D"], hs[0]["s"], "xhole"))
        elif abs(hs[0]["D"] - PR.HOLE_D) < 0.01:
            ctx["pin_holes"] = True
    # axis lines where holes are seen from the side
    for vb in vbs.values():
        for h in an["holes"]:
            if G.in_plane(vb.rows, h["d"]):
                a, b = P2(vb, h["q"] + h["d"] * h["t0"]), P2(vb, h["q"] + h["d"] * h["t1"])
                vb.axes.append((a, b))


def position_dims(vb, cs, done):
    x0, y0, x1, y1 = vb.bbox
    for axis in ("h", "v"):
        vals = sorted(set(round(c[0] if axis == "h" else c[1], 2) for c in cs))
        if not vals:
            continue
        if axis == "h":
            def pt(v):
                return (v, y0)
            side, lo = "bottom", x0
        else:
            def pt(v):
                return (x1, v)
            side, lo = "right", y0
        if vals[0] - lo > 0.05 and (len(vals) > 1 or abs(vals[0] - ((x0 + x1) / 2 if axis == "h" else (y0 + y1) / 2)) > 0.05) \
                and (axis, round(vals[0], 2)) not in done:
            done.add((axis, round(vals[0], 2)))
            vb.dim(S.Dim(pt(lo), pt(vals[0]), axis, side, fmt(vals[0] - lo)))
        key = (axis, tuple(vals))
        if key in done:
            continue
        done.add(key)
        if len(vals) >= 2:
            diffs = [b - a for a, b in zip(vals, vals[1:])]
            p = diffs[0]
            if all(abs(d - p) < 0.02 for d in diffs):
                t, ctf = D.tol("pitch", p)
                if len(vals) == 2:
                    vb.dim(S.Dim(pt(vals[0]), pt(vals[1]), axis, side, fmt(p), t, ctf))
                else:
                    vb.dim(S.Dim(pt(vals[0]), pt(vals[-1]), axis, side,
                                 "%d× %s %s (=%s)" % (len(vals) - 1, fmt(p), t, fmt(vals[-1] - vals[0])), "", ctf))
            else:
                for v in vals[1:6]:
                    vb.dim(S.Dim(pt(vals[0]), pt(v), axis, side, fmt(v - vals[0])))


def overall_dims(vbs, strat):
    def ext(vb, i):
        b = vb.bbox
        return b[i + 2] - b[i]
    fr, tp, le = vbs.get("front"), vbs.get("top"), vbs.get("left")
    if strat in ("prismatic", "outline"):
        x0, y0, x1, y1 = fr.bbox
        t, c = D.tol("len", ext(fr, 0))
        fr.dim(S.Dim((x0, y1), (x1, y1), "h", "top", fmt(ext(fr, 0)), t, c))
        t, c = D.tol("len", ext(fr, 1))
        fr.dim(S.Dim((x0, y0), (x0, y1), "v", "left", fmt(ext(fr, 1)), t, c))
        other = tp or le
        if other is tp and tp is not None:
            x0, y0, x1, y1 = tp.bbox
            t, c = D.tol("len", ext(tp, 1))
            tp.dim(S.Dim((x0, y0), (x0, y1), "v", "left", fmt(ext(tp, 1)), t, c))
        elif le is not None:
            x0, y0, x1, y1 = le.bbox
            t, c = D.tol("len", ext(le, 0))
            le.dim(S.Dim((x0, y1), (x1, y1), "h", "top", fmt(ext(le, 0)), t, c))


def radius_notes(vbs, an):
    seen = set()
    for a in an["arcs"]:
        if a["r"] < 1.0 or a["cov"] > 200:
            continue
        vb = view_for_axis(vbs, a["d"], ("top", "front", "left"))
        if vb is None:
            continue
        key = (vb.name, round(a["r"], 2))
        if key in seen:
            continue
        seen.add(key)
        e1, e2 = G._ref_frame(a["d"])
        mid = max(a["arcs"], key=lambda m: math.cos(m[0]) + math.sin(m[0]))[0]
        p = a["q"] + a["d"] * ((a["t0"] + a["t1"]) / 2) + (e1 * math.cos(mid) + e2 * math.sin(mid)) * a["r"]
        n = sum(1 for b in an["arcs"] if abs(b["r"] - a["r"]) < 0.01 and abs(abs(b["d"].dot(a["d"])) - 1) < 0.02)
        vb.leaders.append(S.Leader(P2(vb, p), ["%sR%s" % ("%d× " % n if n > 1 else "", fmt(a["r"]))], "right"))


def turned_dims(vbs, an, ax, details, ctx):
    fr = vbs["front"]
    d, q = ax
    y_axis = P2(fr, q)[1]
    x0, y0, x1, y1 = fr.bbox
    L = x1 - x0
    fr.axes.append(((x0, y_axis), (x1, y_axis)))
    for vb in vbs.values():
        if vb is not fr and G.in_plane(vb.rows, d):
            a = P2(vb, q + d * 0)
            vb.axes.append(((vb.bbox[0], a[1]), (vb.bbox[2], a[1])))
        elif vb is not fr and G.axis_view(vb.rows, d):
            vb.marks.append((P2(vb, q), 0.8))
    fr.dim(S.Dim((x0, y1), (x1, y1), "h", "top", fmt(L)))

    def coaxial(f):
        if abs(abs(f["d"].dot(d)) - 1) > 0.02:
            return False
        c = f["q"] - q
        return (c - d * c.dot(d)).Length < 0.08
    used = []

    def free_x(t0, t1):
        for frac in (0.5, 0.3, 0.7, 0.15, 0.85):
            x = t0 + (t1 - t0) * frac
            if all(abs(x - u) > 0.07 * L for u in used):
                return x
        return (t0 + t1) / 2
    by_r = {}
    for sgm in an["segs"]:
        if coaxial(sgm) and sgm["t1"] - sgm["t0"] >= 0.35:
            r = round(sgm["r"], 3)
            if r not in by_r or (sgm["t1"] - sgm["t0"]) > (by_r[r]["t1"] - by_r[r]["t0"]):
                by_r[r] = sgm
    side = 1
    if not by_r and not any(coaxial(c) for c in an["crosses"]):
        xm = (x0 + x1) / 2
        fr.dims.append(S.InlineDim((xm, y0), (xm, y1), "Ø%s max" % fmt(y1 - y0)))
        used.append(xm)
    for r, sgm in sorted(by_r.items(), key=lambda kv: -kv[0]):
        a, b = sorted((P2(fr, q + d * sgm["t0"])[0], P2(fr, q + d * sgm["t1"])[0]))
        x = free_x(a, b)
        used.append(x)
        t, c = D.tol("shaft", 2 * r)
        fr.dims.append(S.InlineDim((x, y_axis - r), (x, y_axis + r), "Ø" + fmt(2 * r), t, c, side))
        side = -side
    for h in an["holes"]:
        if h["kind"] == "round" and coaxial(h):
            for r, ta, tb in h["segs"]:
                a, b = sorted((P2(fr, q + d * ta)[0], P2(fr, q + d * tb)[0]))
                x = free_x(a, b)
                used.append(x)
                t, c = D.tol("hole", 2 * r)
                fr.dims.append(S.InlineDim((x, y_axis - r), (x, y_axis + r), "Ø" + fmt(2 * r), t, c, side))
                side = -side
                break
    # axial positions (baseline from the left end), significant steps only
    ts = set()
    for sgm in by_r.values():
        for t in (sgm["t0"], sgm["t1"]):
            ts.add(round(P2(fr, q + d * t)[0], 2))
    for cr in an["crosses"]:
        if coaxial(cr):
            for t in (cr["t0"], cr["t1"]):
                ts.add(round(P2(fr, q + d * t)[0], 2))
    ts = sorted(t for t in ts if x0 + 0.2 < t < x1 - 0.2)
    keep = []
    for t in ts:
        if not keep or t - keep[-1] > 0.25:
            keep.append(t)
    for t in keep[:6]:
        fr.dim(S.Dim((x0, y0), (t, y0), "h", "bottom", fmt(t - x0)))
    for cr in an["crosses"]:
        if coaxial(cr) and "xshaft" not in ctx["details"]:
            ctx["details"].add("xshaft")
            details.append(cross_detail("Axle profile 十字轴截面", cr["D"], cr["s"], "xshaft"))
            mid = (P2(fr, q + d * cr["t0"])[0] + P2(fr, q + d * cr["t1"])[0]) / 2
            t1, c1 = D.tol("xshaft", cr["D"])
            fr.leaders.append(S.Leader((mid, y_axis + cr["D"] / 2), ["Axle cross 十字 +%s %s / %s, see detail" %
                                                                     (fmt(cr["D"]), t1, fmt(cr["s"]))], "right", c1))


def disc_dims(vbs, an, ax, strat_family, tip=None):
    fr = vbs["front"]
    d, q = ax
    x_axis = P2(fr, q)[0]
    x0, y0, x1, y1 = fr.bbox
    fr.axes.append(((x_axis, y0), (x_axis, y1)))
    for vb in vbs.values():
        if G.axis_view(vb.rows, d):
            vb.marks.append((P2(vb, q), (x1 - x0) / 2))
    t, c = D.tol("len", y1 - y0)
    fr.dim(S.Dim((x0, y0), (x0, y1), "v", "left", fmt(y1 - y0), t, c))

    def coaxial(f):
        if abs(abs(f["d"].dot(d)) - 1) > 0.02:
            return False
        cc = f["q"] - q
        return (cc - d * cc.dot(d)).Length < 0.08
    outer = x1 - x0
    rs = sorted(set(round(s["r"], 3) for s in an["segs"] if coaxial(s)), reverse=True)
    if not rs or abs(2 * rs[0] - outer) > 0.1:
        t, c = D.tol("tip", outer) if strat_family == "Gears & motion" else ("", False)
        lab = ("tip Ø" if strat_family == "Gears & motion" else "Ø") + fmt(tip or outer)
        fr.dim(S.Dim((x0, y1), (x1, y1), "h", "top", lab, t, c))
    for r in rs[:3]:
        segs = [s for s in an["segs"] if coaxial(s) and abs(s["r"] - r) < 0.002]
        ytop = max(P2(fr, q + d * s["t1"])[1] for s in segs + [{"t1": s["t0"]} for s in segs])
        t, c = D.tol("shaft", 2 * r)
        fr.dim(S.Dim((x_axis - r, ytop), (x_axis + r, ytop), "h", "top", "Ø" + fmt(2 * r), t, c))
    zs = set()
    for s in an["segs"]:
        if coaxial(s):
            for t in (s["t0"], s["t1"]):
                zs.add(round(P2(fr, q + d * t)[1], 2))
    zs = sorted(z for z in zs if y0 + 0.2 < z < y1 - 0.2)
    for z in zs[:3]:
        fr.dim(S.Dim((x0, y0), (x0, z), "v", "left", fmt(z - y0)))


def cross_detail(label, Dd, s, kind):
    R = Dd / 2
    a = math.asin(s / 2 / R)
    pts = []
    for k in range(4):
        base = k * math.pi / 2
        for i in range(9):
            th = base - a + 2 * a * i / 8
            pts.append((R * math.cos(th), R * math.sin(th)))
        c = base + math.pi / 4
        pts.append((s / 2 * math.sqrt(2) * math.cos(c), s / 2 * math.sqrt(2) * math.sin(c)))
    t1, c1 = D.tol(kind, Dd)
    t2, c2 = D.tol(kind + "_s", s)
    dims = [S.InlineDim((-R, 0), (R, 0), fmt(Dd), t1, c1, shift=0),
            S.InlineDim((-R * 0.62, -s / 2), (-R * 0.62, s / 2), fmt(s), t2, c2)]
    return S.Detail(label, [pts], 10, dims, hatch=(kind == "xshaft"))


def dcam_detail(R, f):
    b = math.asin(f / 2 / R)
    pts = [(R * math.cos(-b + 2 * b * i / 12), R * math.sin(-b + 2 * b * i / 12)) for i in range(13)]
    pts += [(R * math.cos(math.pi - b + 2 * b * i / 12), R * math.sin(math.pi - b + 2 * b * i / 12)) for i in range(13)]
    t1, c1 = D.tol("cam", 2 * R)
    t2, c2 = D.tol("flats", f)
    dims = [S.InlineDim((-R, -0.05), (R, -0.05), fmt(2 * R), t1, c1),
            S.InlineDim((0.35, -f / 2), (0.35, f / 2), fmt(f), t2, c2)]
    return S.Detail("D-cam 凸轮截面", [pts], 20, dims)


def oval_detail(a, b):
    pts = [(a / 2 * math.cos(2 * math.pi * i / 72), b / 2 * math.sin(2 * math.pi * i / 72)) for i in range(72)]
    t1, c1 = D.tol("oval", a)
    t2, c2 = D.tol("oval", b)
    dims = [S.InlineDim((-a / 2, 0), (a / 2, 0), fmt(a), t1, c1),
            S.InlineDim((0.6, -b / 2), (0.6, b / 2), fmt(b), t2, c2)]
    return S.Detail("Oval cam bore 椭圆凸轮孔", [pts], 10, dims, hatch=False)


def gear_table(pid, title):
    z = None
    for tok in title.replace("T", " T").split():
        if tok.isdigit():
            z = int(tok)
    rows = []
    if pid == "SB-GW":
        rows = [("Type 类型", "worm, 1 start 单头蜗杆"), ("Module 模数 m", "1"), ("Axial pitch 轴向齿距", "3.1416"),
                ("Lead 导程", "3.1416, right hand 右旋"), ("Tip Ø 齿顶圆", "10.4"), ("Root Ø 齿根圆", "6.2"),
                ("Tooth form 齿形", "trapezoid, see 3D 见3D")]
    elif pid.startswith("SB-GR"):
        n = int(pid[5:])
        Lx = n * PR.PITCH - PR.GAP
        teeth = 0
        x = 0.1 + math.pi / 2
        while x + math.pi / 2 < Lx + 0.1:
            teeth += 1
            x += math.pi
        rows = [("Type 类型", "straight rack 直齿条"), ("Module 模数 m", "1"), ("Pressure angle 压力角", "20°"),
                ("Pitch 齿距", "3.1416"), ("Teeth 齿数", str(teeth)), ("Tooth height 齿高", "1.9"),
                ("Tip width 齿顶宽", "0.8")]
    elif z:
        rp = z / 2
        rows = [("Module 模数 m", "1"), ("Teeth 齿数 z", str(z)), ("Pressure angle 压力角", "20°"),
                ("Pitch Ø 分度圆", fmt(2 * rp)), ("Tip Ø 齿顶圆", fmt(2 * rp + 1.6)),
                ("Root Ø 齿根圆", fmt(2 * rp - 2.2)), ("Tooth thickness 齿厚", "%s (backlash 侧隙 0.1)" % fmt(math.pi / 2 - 0.1)),
                ("Profile 齿形", "involute, addendum 0.8m 渐开线")]
        if "bevel" in title:
            rows.append(("Bevel 锥面", "45° double cone trim 双面45°"))
        rows.append(("Accuracy 精度", "ISO 1328-1 grade 10 (proposed)"))
    if not rows:
        return None
    return S.Table("Gear data 齿轮参数", rows, [34, 44])


def hooks(pid, comp, vbs, details, ctx, to_posed):
    """Extra dimensions / notes for features the generic analysis does not read."""
    def note(view_order, p_orig, lines, ctf=False):
        p = to_posed(p_orig)
        for n in view_order:
            vb = vbs.get(n)
            if vb is not None:
                vb.leaders.append(S.Leader(P2(vb, p), lines, "right", ctf))
                return
    name = comp.name
    if name == "sleeve":
        depth = (2 if pid.startswith("SB-TL2") else 3) * PR.PITCH - PR.GAP
        zf = -depth
        t, c = D.tol("slot", PR.TL_SLOT_W)
        note(("top", "front"), V(1.0, 0, zf + PR.TL_FINGER_L * 0.5),
             ["Slot 槽 %s %s × %s deep (2 fingers 两爪)" % (fmt(PR.TL_SLOT_W), t, fmt(PR.TL_FINGER_L))], c)
        note(("front", "top"), V(0, PR.TL_LIP_D / 2, zf + 0.6),
             ["Catch lip Ø%s, 45° back ramp 45°倒扣斜面" % fmt(PR.TL_LIP_D)], True)
        note(("left", "front"), V(PR.TL_SLEEVE_D / 2 * 0.7, PR.TL_SLEEVE_D / 2 * 0.7, -3.0),
             ["4× anti-spin rib 防转筋 %s high × 0.6" % fmt(PR.TL_RIB_H)])
        note(("front", "top"), V(PR.TL_FLANGE_D / 2, 0, -0.4),
             ["Pad print red/green status ring", "移印红/绿状态环 (see sheet 1)"])
    elif name == "core":
        details.append(dcam_detail(PR.TL_CAM_D / 2, PR.TL_CAM_FLATS))
        note(("left", "front"), V(PR.TL_WINDOW_R, 0, PR.TL_KNOB_T),
             ["2× status window 状态窗 %d°, R%s–R%s THRU" % (PR.TL_WINDOW_ARC, fmt(PR.TL_WINDOW_R - 0.55),
                                                         fmt(PR.TL_WINDOW_R + 0.55))])
        note(("front", "top"), V(0, PR.TL_KNOB_D / 2 - 0.4, PR.TL_KNOB_T + PR.TL_WING_H),
             ["Wing grip 拨翼 %s × %s" % (fmt(PR.TL_WING_W), fmt(PR.TL_WING_H)),
              "Lock = 1/4 turn clockwise 顺时针90°锁紧"])
    elif name == "ring":
        details.append(oval_detail(PR.TC_OVAL_MAJOR, PR.TC_OVAL_MINOR))
        note(("top", "front"), V(3.92, 0, 1.0), ["12× grip flute 防滑槽 R0.42"])
    elif name == "collet":
        note(("top", "front"), V(0, 0, 2.0), ["Jaw slot 夹爪槽 %s × 2" % fmt(PR.TC_SLOT_W)])
    if pid.startswith("SB-QP") and pid != "SB-QP1":
        note(("top", "front"), V(0, 0, 2.0), ["Slit 开槽 %s × %s, both ends 两端" % (fmt(PR.QP_SLIT_W), fmt(PR.QP_SLIT_L))])
    if pid.startswith("SB-A") and pid[4:6].isdigit() and comp.name == "axle":
        note(("front",), V(0, PR.AXLE_D / 2, 4.0), ["Length notch every 8 mm 每 8 mm 刻痕 (see 3D)"])
    if name == "tire":
        bb = comp.shape.BoundBox
        note(("front",), V(bb.XMax, bb.Center.y, bb.Center.z), ["Tread pattern per 3D 胎纹按 3D",
                                                                "Stretch-fit on hub 过盈套装于轮毂"])
    if name == "rollers":
        note(("front",), comp.shape.CenterOfMass, ["Roller axle / bearing design to be",
                                                   "finalised with supplier 滚轮轴待定"])
    if pid == "SB-G24C":
        note(("top",), V(8.0, 0, 3.9), ["Slip torque 打滑扭矩: set by test", "below motor stall torque 低于电机堵转扭矩"])


# -------------------------------------------------------------- the sheet
def colour_desc(mat):
    c = D.COLOURS.get(mat, ("—", "—", "", ""))
    return "%s %s %s" % (c[0], c[1], c[2])


def sheet_info(pid, title, title_zh, comp_mats, weight, qty, scale, sheet, file_id):
    mk = [D.material_for(*m) for m in comp_mats]
    m0 = mk[0]
    mat = D.MATERIALS[m0]
    if len(set(mk)) > 1:
        material = " + ".join(sorted(set(mk))) + "\nsee BOM 见明细表"
        colour = "see BOM 见明细表"
        finish = "see BOM 见明细表"
    else:
        material = "%s\n%s" % D.MAT_SHORT[m0]
        colour = colour_desc(comp_mats[0][2])
        finish = "%s\n%s" % mat[3]
    return {"pid": pid, "title": title, "title_zh": title_zh, "material": material, "colour": colour,
            "finish": finish, "weight": "%.2f g" % weight if weight < 10 else "%.1f g" % weight,
            "qty": str(qty) if qty else "option 选配", "scale": S.scale_label(scale), "sheet": sheet,
            "status": "Rev A quotation\n报价及打样", "rev": D.REV, "date": D.DATE, "drawn": "semiblock.ai",
            "file_id": file_id}


def colour_note(mats_comp):
    lines = []
    for fam, body, mat in mats_comp:
        mk = D.material_for(fam, body, mat)
        m = D.MATERIALS[mk]
        c = D.COLOURS.get(mat)
        cs = ("colour %s %s (sRGB %s, std %s); colour plaque approved before production" % (c[0], c[1], c[2], c[3])
              if c else "")
        cz = ("颜色 %s（%s，色号 %s），量产前确认色板" % (c[1], c[2], c[3]) if c else "")
        lines.append(("Material %s; %s." % (m[0], cs), "材料：%s；%s。" % (m[1], cz)))
    return lines


def make_sheet(svg_name, info, vbs, iso, boxes, notes):
    s, placed = S.layout(vbs, iso, boxes)
    if s is None:                     # drop the boxes before giving up
        s, placed = S.layout(vbs, iso, [])
        placed = placed or []
    if s is None:
        raise RuntimeError("views do not fit on A3: " + svg_name)
    S.place_iso(iso, s)
    info["scale"] = S.scale_label(s)
    svg = S.render_sheet(info, vbs, iso, placed, notes)
    path = os.path.join(OUT_SVG, svg_name + ".svg")
    with open(path, "w") as fh:
        fh.write(svg)
    return path, s


def component_sheet(item, part, comp, sheet_pid, title, title_zh, sheet_no, qty_kit, file_id):
    fam = item["family"]
    m = G.pose(comp.shape, z_left=fam.startswith("TwistLock"))
    shape = comp.shape.transformed(m)
    rot = G.rotation_part(m)

    def to_posed(p):
        return m.multVec(p)
    an = analyse(shape)
    strat, ax = strategy(fam, shape, an)
    letters = ["A", "B"]
    vbs, iso = build_views(shape, [shape], an, strat, letters, ax)
    details, ctx = [], {"details": set(), "pcd_views": set(), "pin_holes": False, "axle_holes": False}
    overall_dims(vbs, strat)
    if strat == "turned":
        turned_dims(vbs, an, ax, details, ctx)
    if strat == "disc":
        z = [int(t[:-1]) for t in part.title.split() if t.endswith("T") and t[:-1].isdigit()]
        disc_dims(vbs, an, ax, fam, (z[0] + 1.6) if (z and fam == "Gears & motion") else None)
    annotate_holes(vbs, an, strat, ax, details, ctx)
    if strat in ("prismatic", "outline"):
        radius_notes(vbs, an)
    hooks(part.pid, comp, vbs, details, ctx, to_posed)
    boxes = list(details)
    if fam == "Gears & motion":
        t = gear_table(part.pid, part.title)
        if t:
            boxes.insert(0, t)
    mk = D.material_for(fam, comp.name, comp.mat)
    weight = comp.shape.Volume / 1000.0 * D.MATERIALS[mk][2]
    info = sheet_info(sheet_pid, title, title_zh, [(fam, comp.name, comp.mat)], weight,
                      qty_kit, 1, sheet_no, file_id)
    notes = D.notes_for(strat, [mk], ctx["pin_holes"], ctx["axle_holes"], colour_note([(fam, comp.name, comp.mat)]),
                        file_id + ".step")
    _ = rot
    return make_sheet(sheet_pid, info, vbs, iso, boxes, notes)


def assembly_sheet(item, part, comps, sheet_no, file_id):
    fam = item["family"]
    allb = [b for b in part.bodies if b.printable]
    comp_shape = Part.makeCompound([b.shape for b in allb])
    m = G.pose(comp_shape, z_left=fam.startswith("TwistLock"))
    shapes = [b.shape.transformed(m) for b in allb]
    shape = Part.makeCompound(shapes)
    an = analyse(shape)
    strat, ax = strategy(fam, shape, an)
    vbs, iso = build_views(shape, shapes, {"groups": [g for g in an["groups"]]}, "assembly" if strat != "outline" else strat,
                           ["A", "B"], main_axis(shape, an))
    # assembly: overall size only + balloons + BOM
    fr = vbs["front"]
    x0, y0, x1, y1 = fr.bbox
    fr.dim(S.Dim((x0, y1), (x1, y1), "h", "top", fmt(x1 - x0)))
    fr.dim(S.Dim((x0, y0), (x0, y1), "v", "left", fmt(y1 - y0)))
    tp = vbs.get("top")
    if tp:
        x0, y0, x1, y1 = tp.bbox
        tp.dim(S.Dim((x0, y0), (x0, y1), "v", "left", fmt(y1 - y0)))
    rows = []
    weight = 0.0
    for i, (c, b) in enumerate(zip(comps, allb)):
        mk = D.material_for(fam, c.name, c.mat)
        w = c.shape.Volume / 1000.0 * D.MATERIALS[mk][2] * c.qty
        weight += w
        en, zh = D.COMP_NAME.get(c.name, (c.name.title(), c.name))
        cpid = "%s-%02d" % (part.pid, i + 1) if mk != "STEEL" else "purchased 外购"
        rows.append((str(i + 1), cpid, "%s %s" % (en, zh), D.MATERIALS[mk][0].split(",")[0].split(" (")[0],
                     D.COLOURS.get(c.mat, ("—",))[0], str(c.qty), "%.2f" % w))
        # balloon
        bb = b.shape.transformed(m).BoundBox
        p = V(bb.Center.x, bb.Center.y, bb.ZMax if fr.sec is None else bb.Center.z)
        fr.leaders.append(S.Leader(P2(fr, p), ["(%d) %s" % (i + 1, en)], "right"))
    for b in part.bodies:
        if b.printable:
            continue
        what = {"ind_red": ("Pad print 移印 red 红", "ink Pantone 485 C"), "ind_green": ("Pad print 移印 green 绿", "ink Pantone 7481 C"),
                "sb_white": ("Pad print 移印 white 白", "pointer marks"), "sb_magenta": ("Pad print 移印 magenta 品红", "marks"),
                }.get(b.mat)
        if b.name == "card":
            what = ("Write-on card 书写卡", "PET 0.35, printed")
        if what:
            rows.append(("—", "process 工艺", what[0], what[1], "", "", ""))
    t = S.Table("Bill of materials 明细表", [("#", "Part No. 零件号", "Name 名称", "Material 材料", "Colour", "Qty", "g")] + rows,
                [6, 24, 34, 30, 16, 8, 10], size=2.3)
    mats = [(fam, c.name, c.mat) for c in comps]
    info = sheet_info(part.pid, part.title + " — assembly 装配图", D.NAME_ZH.get(part.pid, ""), mats, weight,
                      item["qty"], 1, sheet_no, file_id)
    notes = [("Assembly drawing: components per BOM, each with its own drawing (sheets 2…).",
              "装配图：零件见明细表，各零件另有图纸（第 2 页起）。")]
    if part.pid.startswith("SB-TL"):
        notes += [("Core snaps into the sleeve (snap groove). Core turns 90° with ≤ 0.05 axial play; OPEN = flats "
                   "facing the fingers, red status visible.",
                   "锁芯卡入套管卡槽，可转 90°，轴向间隙≤0.05；开锁时凸轮平面对正两爪，状态窗显示红色。"),
                  ("Function test 100%: lock / unlock 10× by hand, windows show green when locked.",
                   "100% 功能测试：手动锁/开 10 次，锁紧时状态窗显示绿色。")]
    if part.pid.startswith("SB-TC"):
        notes += [("Ring snaps over the collet; turning the ring 90° squeezes the jaws onto the axle.",
                   "锁环套装于夹套上，转动 90° 夹紧十字轴。")]
    if part.pid.startswith("SB-W") or part.pid.startswith("SB-WM") or part.pid.startswith("SB-WO"):
        notes += [("Tyre / rollers fitted on the hub; wheel must run true within 0.3 TIR.",
                   "轮胎/滚轮装于轮毂上，径向跳动≤0.3。")]
    notes += D.notes_for("assembly", [D.material_for(*x) for x in mats], False, False, [], file_id + ".step")[-3:]
    return make_sheet(part.pid + "-ASM", info, vbs, iso, [t], notes)


def outline_sheet(item, part, file_id):
    fam = item["family"]
    allb = [b.shape for b in part.bodies]
    printable = [b for b in part.bodies if b.printable]
    shape0 = Part.makeCompound(allb)
    m = G.pose(Part.makeCompound([b.shape for b in printable]))
    shape = shape0.transformed(m)
    housing = Part.makeCompound([b.shape for b in printable]).transformed(m)
    an = analyse(housing)
    vbs, iso = build_views(shape, [shape], an, "outline", [])
    ctx = {"details": set(), "pcd_views": set(), "pin_holes": False, "axle_holes": False}
    overall_dims(vbs, "outline")
    details = []
    annotate_holes(vbs, an, "outline", None, details, ctx)
    hb = housing.BoundBox
    ports = [sol for b in part.bodies if b.name == "port" for sol in b.shape.transformed(m).Solids]
    face_view = {(0, -1, 0): "front", (0, 0, 1): "top", (-1, 0, 0): "left"}
    face_name = {(1, 0, 0): "right end 右端面", (0, 1, 0): "back face 背面", (0, 0, -1): "bottom 底面",
                 (0, -1, 0): "front face 正面", (0, 0, 1): "top face 顶面", (-1, 0, 0): "left end 左端面"}
    located = False
    for sol in ports:
        pb = sol.BoundBox
        dists = {(-1, 0, 0): pb.XMin - hb.XMin, (1, 0, 0): hb.XMax - pb.XMax, (0, -1, 0): pb.YMin - hb.YMin,
                 (0, 1, 0): hb.YMax - pb.YMax, (0, 0, -1): pb.ZMin - hb.ZMin, (0, 0, 1): hb.ZMax - pb.ZMax}
        # the socket opens towards the face it can "see" through the housing
        opened = []
        for nv, dist in dists.items():
            nd = V(*nv)
            face_c = pb.Center + V(nd.x * pb.XLength / 2, nd.y * pb.YLength / 2, nd.z * pb.ZLength / 2)
            steps = [0.3 + 0.4 * i for i in range(int(max(dist, 0) / 0.4) + 3)]
            if not any(housing.isInside(face_c + nd * k, 1e-4, True) for k in steps):
                opened.append((dist, nv))
        n = min(opened)[1] if opened else min(dists, key=dists.get)
        p = pb.Center
        vb = vbs.get(face_view.get(n, ""))
        if vb is not None:
            c = P2(vb, p)
            vb.leaders.append(S.Leader(c, ["SemiLink-6 port 接口 (%s)" % face_name[n], "socket per SL-6 spec"], "right"))
            if not located:
                located = True
                x0, y0, x1, y1 = vb.bbox
                vb.dim(S.Dim((x0, y0), (c[0], y0), "h", "bottom", fmt(c[0] - x0)))
                vb.dim(S.Dim((x1, y0), (x1, c[1]), "v", "right", fmt(c[1] - y0)))
        else:
            for name in ("front", "top", "left"):
                vb = vbs.get(name)
                if vb is not None and abs(vb.rows[2].dot(V(*n))) < 0.02:
                    vb.leaders.append(S.Leader(P2(vb, p), ["SemiLink-6 port 接口 on %s" % face_name[n]], "right"))
                    break
    weight = sum(b.shape.Volume / 1000.0 * D.MATERIALS[D.material_for(fam, b.name, b.mat)][2] for b in printable)
    mats = [(fam, b.name, b.mat) for b in printable if b.name in ("base", "cover", "shell", "plug")] or \
        [(fam, printable[0].name, printable[0].mat)]
    info = sheet_info(part.pid, part.title + " — outline 外形图", D.NAME_ZH.get(part.pid, ""), mats, weight,
                      item["qty"], 1, "1 / 1", file_id)
    info["weight"] = "≈ %.0f g housing" % weight
    info["material"] = "%s\n%s" % D.MAT_SHORT[D.material_for(*mats[0])]
    info["colour"] = " / ".join(D.COLOURS.get(x[2], ("—",))[0] for x in mats)
    notes = D.notes_for("outline", [D.material_for(*x) for x in mats], ctx["pin_holes"], False,
                        colour_note(mats), file_id + ".step")
    return make_sheet(part.pid, info, vbs, iso, [], notes)


# ------------------------------------------------------------------ main
def to_pdf(svgs, pdf):
    subprocess.run(["rsvg-convert", "-f", "pdf", "-o", pdf] + svgs, check=True)


def parts_rows(item, part):
    """One parts-list row per manufactured component (+ purchased items)."""
    fam = item["family"]
    rows = []
    name_zh = D.NAME_ZH.get(part.pid, "")
    if fam in D.MODULE_FAMILIES:
        pr = [b for b in part.bodies if b.printable]
        housing = [b for b in pr if b.name in ("base", "cover", "shell", "plug")] or pr[:1]
        mk = D.material_for(fam, housing[0].name, housing[0].mat)
        w = sum(b.shape.Volume / 1000.0 * D.MATERIALS[D.material_for(fam, b.name, b.mat)][2] for b in pr)
        rows.append([part.pid, part.pid, part.title, name_zh, "electronic module (outline drawing)",
                     D.MATERIALS[mk][0], " / ".join(D.COLOURS.get(b.mat, ("—",))[0] for b in housing),
                     " / ".join(D.COLOURS.get(b.mat, ("", "", "", "—"))[3] for b in housing),
                     "%s %s" % D.MATERIALS[mk][3], "%.1f" % w, item["qty"] or ""])
        return rows
    comps = components(part)
    for i, c in enumerate(comps):
        mk = D.material_for(fam, c.name, c.mat)
        cno = ("%s-%02d" % (part.pid, i + 1)) if len(comps) > 1 else part.pid
        en, zh = D.COMP_NAME.get(c.name, (c.name.title(), c.name))
        col = D.COLOURS.get(c.mat, ("—", "", "", "—"))
        rows.append([part.pid, cno if mk != "STEEL" else "purchased",
                     part.title + ("" if len(comps) == 1 else " — %s" % en),
                     name_zh + ("" if len(comps) == 1 else " — %s" % zh),
                     "purchased part" if mk == "STEEL" else "injection moulded",
                     D.MATERIALS[mk][0], "%s %s %s" % (col[0], col[1], col[2]), col[3], "%s %s" % D.MATERIALS[mk][3],
                     "%.2f" % (c.shape.Volume / 1000.0 * D.MATERIALS[mk][2]),
                     (item["qty"] * c.qty) if item["qty"] else ""])
    return rows


def drawing_for(item, part):
    fam = item["family"]
    file_id = part.pid
    sheets = []
    if fam in D.MODULE_FAMILIES:
        sheets.append(outline_sheet(item, part, file_id)[0])
    else:
        comps = components(part)
        drawn = [c for c in comps if D.material_for(fam, c.name, c.mat) != "STEEL"]
        total = len(drawn) + (1 if len(comps) > 1 else 0)
        k = 1
        if len(comps) > 1:
            sheets.append(assembly_sheet(item, part, comps, "%d / %d" % (k, total), file_id)[0])
            k += 1
        for i, c in enumerate(comps):
            if c not in drawn:
                continue
            if len(comps) > 1:
                en, zh = D.COMP_NAME.get(c.name, (c.name.title(), c.name))
                spid = "%s-%02d" % (part.pid, i + 1)
                title = "%s — %s%s" % (part.title, en, (" (×%d)" % c.qty) if c.qty > 1 else "")
                tzh = "%s — %s" % (D.NAME_ZH.get(part.pid, ""), zh)
                qty = item["qty"] * c.qty if item["qty"] else 0
            else:
                spid, title, tzh, qty = part.pid, part.title, D.NAME_ZH.get(part.pid, ""), item["qty"]
            sheets.append(component_sheet(item, part, c, spid, title, tzh, "%d / %d" % (k, total), qty, file_id)[0])
            k += 1
    pdf = os.path.join(OUT_PDF, part.pid + ".pdf")
    to_pdf(sheets, pdf)
    return {"id": part.pid, "title": part.title, "family": fam, "pdf": "drawings/%s.pdf" % part.pid,
            "fcstd": "cad/fcstd/%s.FCStd" % part.pid, "step": "cad/step/%s.step" % part.pid,
            "sheets": [os.path.basename(s)[:-4] for s in sheets], "rows": parts_rows(item, part)}


def index_sheets(index):
    """Drawing list pages (A3) for the front of the combined PDF."""
    per = 44
    rows = [(r["id"], r["title"], D.NAME_ZH.get(r["id"], ""), str(len(r["sheets"])),
             "outline 外形图" if r["family"] in D.MODULE_FAMILIES else "part 零件图", r["family"]) for r in index]
    pages = []
    chunks = [rows[i:i + per * 2] for i in range(0, len(rows), per * 2)]
    for n, chunk in enumerate(chunks):
        g = S.Svg()
        g.add('<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %g %g">' % (S.W, S.H, S.W, S.H))
        g.add('<rect x="0" y="0" width="%g" height="%g" fill="#fff"/>' % (S.W, S.H))
        g.rect(S.M, S.M, S.W - 2 * S.M, S.H - 2 * S.M, S.LW["frame"])
        g.text(S.M + 6, S.M + 12, "SemiBlock Junior — drawing list 图纸目录", 7, weight="bold")
        g.text(S.W - S.M - 6, S.M + 12, "semiblock.ai · Rev %s · %s · page %d / %d" % (D.REV, D.DATE, n + 1, len(chunks)),
               3.2, "end")
        g.text(S.M + 6, S.M + 19, "Rev A drawings are for quotation, DFM review and T0/T1 samples. A 版图纸用于报价、DFM 评审及打样。"
               " Each part: PDF drawing + STEP + FreeCAD (.FCStd) with the same part number.", 3.0)
        for col in range(2):
            part_rows = chunk[col * per:(col + 1) * per]
            if not part_rows:
                continue
            t = S.Table("Part No. 零件号 · name 名称 · sheets 页数 · type 类型",
                        [(a, b[:34], c[:16], d, e) for a, b, c, d, e, _ in part_rows], [22, 66, 38, 9, 54], size=2.5)
            t.render(g, S.M + 6 + col * 198, S.M + 25)
        g.add("</svg>")
        path = os.path.join(OUT_SVG, "_index_%d.svg" % (n + 1))
        with open(path, "w") as fh:
            fh.write("\n".join(g.out))
        pages.append(path)
    return pages


def write_pack(index):
    import csv
    with open(os.path.join(OUT_PDF, "SemiBlock-Junior-parts-list.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Part No. 零件号", "Component No. 零件编号", "Name", "名称", "Type 类型", "Material 材料",
                    "Colour 颜色", "Colour std 色号", "Finish 表面", "Weight g 重量", "Qty per Core kit 每套数量",
                    "Drawing 图纸", "3D STEP", "FreeCAD"])
        for r in index:
            for row in r["rows"]:
                w.writerow(row + [r["pdf"], r["step"], r["fcstd"]])
    sheets = index_sheets(index) + [os.path.join(OUT_SVG, s + ".svg") for r in index for s in r["sheets"]]
    to_pdf(sheets, os.path.join(OUT_PDF, "SemiBlock-Junior-drawings-Rev%s.pdf" % D.REV))


def main():
    index = []
    idx_path = os.path.join(OUT_PDF, "index.json")
    if PIDS and os.path.exists(idx_path):
        index = [r for r in json.load(open(idx_path)) if r["id"] not in PIDS]
    for item in CAT.ITEMS:
        part = CAT.build(item)
        if PIDS and part.pid not in PIDS:
            continue
        try:
            row = drawing_for(item, part)
            index.append(row)
            print("drawing", part.pid, len(row["sheets"]), "sheet(s)", flush=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("FAILED", part.pid, e, flush=True)
    order = {it: i for i, it in enumerate(r["id"] for r in json.load(open(os.path.join(STAGE, "viewer", "catalog.json"))))}
    index.sort(key=lambda r: order.get(r["id"], 999))
    with open(idx_path, "w") as fh:
        json.dump(index, fh, indent=1, ensure_ascii=False)
    if not PIDS or os.environ.get("SB_PACK") == "1":
        write_pack(index)


main()

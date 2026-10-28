"""Write one FreeCAD file per part: coloured bodies + part data + the 2D
drawing sheets as TechDraw pages. Every moulded or purchased component is a
Part Design Body built from sketches, pads, pockets, revolutions, fillets ...
(pdbuild.py, from the recorded construction in parts.py / modules.py), so
every feature can be opened and changed. Needs FreeCAD's GUI layer for
colours, so it runs offscreen (no window):

    QT_QPA_PLATFORM=offscreen /Applications/FreeCAD.app/Contents/MacOS/FreeCAD stage-2/cad/fcstd_export.py

    SB_PIDS="SB-B05 SB-TL2"   limit to these parts
Outputs cad/fcstd/<id>.FCStd and a log in cad/build/fcstd.log.
Run drawings.py first: the sheets come from cad/build/dwg/.
"""
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import FreeCAD as App  # noqa: E402

import sbcad  # noqa: E402
sbcad.RECORD = True             # the parts keep how they were made, for the feature trees
import catalog as CAT  # noqa: E402
import dwg_data as D  # noqa: E402
import pdbuild  # noqa: E402
from sbcad import PALETTE, hex_rgb  # noqa: E402

OUT = os.path.join(HERE, "fcstd")
DWG = os.path.join(HERE, "build", "dwg")
IDX = os.path.join(os.path.dirname(HERE), "drawings", "index.json")
os.makedirs(OUT, exist_ok=True)
PIDS = os.environ.get("SB_PIDS", "").split()
LOG = open(os.path.join(HERE, "build", "fcstd.log"), "w")


def log(*a):
    LOG.write(" ".join(str(x) for x in a) + "\n")
    LOG.flush()


def colour(obj, mat):
    vo = getattr(obj, "ViewObject", None)
    if vo is None or mat not in PALETTE:
        return
    rgb = tuple(c / 255.0 for c in hex_rgb(PALETTE[mat][0]))
    try:
        m = App.Material()
        m.DiffuseColor = rgb
        vo.ShapeAppearance = [m]
    except Exception:
        vo.ShapeColor = rgb
    if PALETTE[mat][3] < 1.0:
        vo.Transparency = int((1 - PALETTE[mat][3]) * 100)


def add_str(obj, name, value, group="SemiBlock", doc=""):
    obj.addProperty("App::PropertyString", name, group, doc)
    setattr(obj, name, str(value))


def export(item, part, sheets):
    fam = item["family"]
    doc = App.newDocument(part.pid.replace("-", "_"))
    doc.Label = part.pid
    doc.Comment = part.title
    doc.Company = "semiblock.ai"
    doc.CreatedBy = "semiblock.ai stage-2 CAD (generated)"
    doc.License = "semiblock.ai — confidential, for quotation"
    root = doc.addObject("App::Part", "Part")
    root.Label = "%s %s" % (part.pid, part.title)
    add_str(root, "PartNumber", part.pid)
    add_str(root, "NameEN", part.title)
    add_str(root, "NameZH", D.NAME_ZH.get(part.pid, ""))
    add_str(root, "Family", fam)
    add_str(root, "QtyPerKit", item["qty"] or "option")
    add_str(root, "Revision", D.rev_for(part.pid))
    add_str(root, "Drawing", "drawings/%s.pdf" % part.pid)
    add_str(root, "Step", "cad/step/%s.step" % part.pid)
    k = 0
    for b in part.bodies:
        mk = D.material_for(fam, b.name, b.mat)
        if b.printable:
            k += 1
            comp_no = "%s-%02d" % (part.pid, k) if len([x for x in part.bodies if x.printable]) > 1 else part.pid
            if mk == "STEEL":                       # purchased (bearing, ball): no drawing number, as in the BOM
                comp_no = "purchased"
            # a Part Design body whose sketches, pads, pockets ... rebuild the generated solid
            o = doc.addObject("PartDesign::Body", b.name)
            o.Label = "%s %s" % (comp_no if mk != "STEEL" else D.COMP_NAME.get(b.name, (b.name,))[0], b.name)
            root.addObject(o)
            n, helpers, plain = pdbuild.build(doc, o, b.recipe or b.shape, root.addObject)
            log("  %-16s %3d features, %d helper bodies%s" % (b.name, n, helpers, ", PLAIN SOLID" if plain else ""))
            add_str(o, "ComponentNo", comp_no)
            add_str(o, "Material", D.MATERIALS[mk][0])
            add_str(o, "Process", "purchased" if mk == "STEEL" else "injection moulding")
        else:
            o = doc.addObject("Part::Feature", b.name)
            o.Shape = b.shape
            o.Label = "%s (%s)" % (b.name, "pad print / insert" if fam not in D.MODULE_FAMILIES else "electronics / window")
            add_str(o, "Process", "pad print" if b.mat.startswith("ind_") or b.name in ("marks", "pointer")
                    else "reference only")
        c = D.COLOURS.get(b.mat)
        if c:
            add_str(o, "Colour", "%s %s %s (%s)" % (c[0], c[1], c[2], c[3]))
        if o not in root.Group:
            root.addObject(o)
        colour(o, b.mat)
    for i, name in enumerate(sheets):
        svg = os.path.join(DWG, name + ".svg")
        if not os.path.exists(svg):
            continue
        tpl = doc.addObject("TechDraw::DrawSVGTemplate", "Template%d" % (i + 1))
        tpl.Template = svg
        page = doc.addObject("TechDraw::DrawPage", "Sheet%d" % (i + 1))
        page.Template = tpl
        page.Label = "Drawing %d of %d — %s" % (i + 1, len(sheets), name)
    doc.recompute()
    path = os.path.join(OUT, part.pid + ".FCStd")
    if os.path.exists(path):        # else FreeCAD leaves a .FCBak beside it
        os.remove(path)
    doc.saveAs(path)
    App.closeDocument(doc.Name)
    return path


def main():
    idx = {r["id"]: r["sheets"] for r in json.load(open(IDX))}
    n = 0
    for item in CAT.ITEMS:
        try:
            part = CAT.build(item)
        except Exception:
            log("FAILED build", traceback.format_exc())
            continue
        if PIDS and part.pid not in PIDS:
            continue
        try:
            log(part.pid)
            export(item, part, idx.get(part.pid, []))
            n += 1
            log("fcstd", part.pid)
        except Exception:
            log("FAILED", part.pid, traceback.format_exc())
    log("DONE", n)


try:
    main()
except Exception:
    log("FATAL", traceback.format_exc())
LOG.close()
os._exit(0)

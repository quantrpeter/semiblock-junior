"""Build everything for stage-2 (run with FreeCAD's headless interpreter).

    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd stage-2/cad/build.py

Env vars:
    SB_ONLY="parts scenes"   steps to run (default both)
    SB_PIDS="SB-B07 SB-TL2"  limit the part step to these ids
    SB_SCENES="rover"        limit the scene step to these scenes
Outputs:
    cad/step/<id>.step, cad/stl/<id>[_body].stl     printable CAD per part (mm)
    cad/build/render/parts/<id>.glb, <scene>.glb     fine meshes for Blender
    cad/build/shots.json                             every camera + callout
    viewer/models/<name>.js                          lazy-loaded meshes for the viewer
    viewer/catalog.json                              part list (viewer + docs)
"""
import base64
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import catalog as CAT  # noqa: E402
import scenes as S  # noqa: E402
from sbcad import Instance, export_part, frame, section_bodies, write_glb, Body  # noqa: E402

STAGE = os.path.dirname(HERE)
OUT = {
    "step": os.path.join(HERE, "step"),
    "stl": os.path.join(HERE, "stl"),
    "render": os.path.join(HERE, "build", "render"),
    "render_parts": os.path.join(HERE, "build", "render", "parts"),
    "viewer": os.path.join(STAGE, "viewer", "models"),
}
for d in OUT.values():
    os.makedirs(d, exist_ok=True)

ONLY = os.environ.get("SB_ONLY", "parts scenes").split()
PIDS = os.environ.get("SB_PIDS", "").split()
PICK = os.environ.get("SB_SCENES", "").split()

POSES = {"flat": ((1, 0, 0), (0, 1, 0)), "lay": ((0, 0, -1), (0, 1, 0)),
         "layr": ((0, 0, 1), (0, 1, 0)), "stand": ((1, 0, 0), (0, 0, 1))}
VIEW = {"flat": [0.5, -1.0, 0.95], "lay": [0.35, -1.0, 0.7], "layr": [-0.7, -1.0, 0.65], "stand": [0.5, -1.0, 0.45]}
FAMILY_VIEW = {"Smart modules": [1.0, -0.85, 0.75], "Hub, motors & cables": [1.0, -0.85, 0.75],
               "Gears & motion": [0.3, -1.0, 1.25], "Connectors": [0.75, -1.0, 0.85]}


def viewer_js(name, glb_path):
    import gzip
    data = base64.b64encode(gzip.compress(open(glb_path, "rb").read(), 9)).decode()
    with open(os.path.join(OUT["viewer"], name + ".js"), "w") as fh:
        fh.write('SBV.register("%s","%s");\n' % (name, data))


def tol_for(bb_diag):
    return 0.008 if bb_diag < 30 else (0.015 if bb_diag < 70 else 0.03)


def build_parts():
    rows, shots = [], []
    tmp_glb = os.path.join(HERE, "build", "viewer_tmp.glb")
    for item in CAT.ITEMS:
        t = time.time()
        part = CAT.build(item)
        if PIDS and part.pid not in PIDS:
            continue
        export_part(part, OUT["step"], OUT["stl"])
        printable = [b for b in part.bodies if b.printable]
        if len(printable) > 1:
            import Mesh
            import MeshPart
            for b in printable:
                m = MeshPart.meshFromShape(Shape=b.shape, LinearDeflection=0.02, AngularDeflection=0.3, Relative=False)
                Mesh.Mesh(m).write(os.path.join(OUT["stl"], "%s_%s.stl" % (part.pid, b.name)))
        bb = None
        for b in printable:
            bb = b.shape.BoundBox if bb is None else bb.united(b.shape.BoundBox)
        xd, yd = POSES[item["pose"]]
        posed = [Instance(part.pid, [Body(b.name, frame(b.shape, xd, yd), b.mat, b.printable) for b in part.bodies])]
        diag = bb.DiagonalLength
        # coarse viewer mesh FIRST: OCC keeps the finest triangulation it has made
        write_glb(tmp_glb, posed, tol=0.05, ang=0.4)
        viewer_js(part.pid, tmp_glb)
        write_glb(os.path.join(OUT["render_parts"], part.pid + ".glb"), posed, tol=tol_for(diag), ang=0.2)
        row = {"id": part.pid, "title": part.title, "family": item["family"], "qty": item["qty"],
               "note": item["note"], "size_mm": [round(bb.XLength, 1), round(bb.YLength, 1), round(bb.ZLength, 1)],
               "bodies": [b.name for b in printable], "materials": sorted({b.mat for b in part.bodies})}
        if "module" in item:
            m = item["module"]
            row["module"] = {k: m[k] for k in ("code", "zh", "cat", "phase", "chip", "does", "replaces", "size")}
        rows.append(row)
        view = FAMILY_VIEW.get(item["family"], VIEW[item["pose"]])
        shots.append({"name": "part-" + part.pid, "scene": "parts/" + part.pid, "size": [640, 480],
                      "view": {"dir": view, "lens": 85, "fit": 0.8}, "kind": "part",
                      "title": part.title, "pid": part.pid})
        print("part %-12s %-42s %.2fs" % (part.pid, part.title, time.time() - t), flush=True)
    if os.path.exists(tmp_glb):
        os.remove(tmp_glb)
    if not PIDS:
        with open(os.path.join(STAGE, "viewer", "catalog.json"), "w") as fh:
            json.dump(rows, fh, indent=1, ensure_ascii=False)
        with open(os.path.join(HERE, "build", "part_shots.json"), "w") as fh:
            json.dump(shots, fh, indent=1)


def finalize(name, insts):
    if name in S.SECTIONS:
        keep, axis, pos = S.SECTIONS[name]
        insts = [Instance(i.name, section_bodies(i.bodies, keep, axis, pos), i.extras) for i in insts]
    return insts


FINE = {"tl_section": 0.008, "tl_exploded": 0.008, "tl_step1": 0.012, "tl_step2": 0.012, "tl_step3": 0.012,
        "collar": 0.008, "collar_exploded": 0.006, "tl_demo": 0.01, "hbeam_section": 0.01, "angles": 0.015,
        "hinge_exploded": 0.006, "bearing_exploded": 0.006, "bearing_section": 0.006, "turntable": 0.012,
        "turntable_exploded": 0.012}


def build_scenes():
    scenes = S.build_scenes()
    tmp_glb = os.path.join(HERE, "build", "viewer_tmp.glb")
    for name, insts in scenes.items():
        if PICK and name not in PICK:
            continue
        t = time.time()
        insts = finalize(name, insts)
        msg = "scene %-16s" % name
        if name in S.VIEWER_SCENES:      # coarse viewer mesh first (see build_parts)
            tol = 0.03 if name in ("tl_demo", "collar", "bearing") else 0.07
            write_glb(tmp_glb, insts, tol=tol, ang=0.45)
            viewer_js("scene-" + name, tmp_glb)
            msg += " viewer %5.1f MB" % (os.path.getsize(tmp_glb) / 1e6)
        size = write_glb(os.path.join(OUT["render"], name + ".glb"), insts, tol=FINE.get(name, 0.025), ang=0.2)
        msg += " render %5.1f MB" % (size / 1e6)
        print(msg + " %.1fs" % (time.time() - t), flush=True)
    if os.path.exists(tmp_glb):
        os.remove(tmp_glb)
    with open(os.path.join(HERE, "build", "shots.json"), "w") as fh:
        json.dump(S.SHOTS, fh, indent=1)


t0 = time.time()
if "parts" in ONLY:
    build_parts()
if "scenes" in ONLY:
    build_scenes()
print("done in %.1fs" % (time.time() - t0))

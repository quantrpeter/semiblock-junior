"""Render stage-1 shots with Blender + Cycles (tested with Blender 5.1).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P stage-1/cad/render_blender.py -- [shot ...]

Reads cad/build/shots.json + cad/build/render/<scene>.glb and writes
cad/build/raw/<shot>.png (transparent) + <shot>.json (2D callout anchors).
Env: SB_SCALE=0.5 renders at half size for quick checks, SB_SAMPLES=64.
"""
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
RAW = os.path.join(BUILD, "raw")
os.makedirs(RAW, exist_ok=True)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SCALE = float(os.environ.get("SB_SCALE", "1"))
SAMPLES = int(os.environ.get("SB_SAMPLES", "96"))
MM = 0.001


def cad(p):
    """CAD mm (Z-up) -> Blender metres (Z-up; the glTF importer converts back)."""
    return Vector((p[0] * MM, p[1] * MM, p[2] * MM))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup(w, h):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = "GPU"
    except Exception as e:  # CPU fallback
        print("GPU setup failed:", e)
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.render.resolution_x, sc.render.resolution_y = int(w * SCALE), int(h * SCALE)
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = os.environ.get("SB_VIEW", "Standard")
    for look in os.environ.get("SB_LOOKS", "Medium Contrast|None").split("|"):
        try:
            sc.view_settings.look = look
            break
        except Exception:
            pass
    sc.view_settings.exposure = float(os.environ.get("SB_EXPOSURE", "-0.5"))
    world = bpy.data.worlds.new("studio")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.86, 0.9, 0.96, 1.0)
    bg.inputs["Strength"].default_value = float(os.environ.get("SB_WORLD", "0.38"))
    sc.world = world


def tune_materials():
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        name = m.name

        def setv(key, val):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
        if name.endswith("__cut"):
            setv("Roughness", 0.75)
            setv("Coat Weight", 0.0)
        elif name.startswith("sb_"):
            if name == "sb_lgrey":          # keep light grey distinct from white
                c = bsdf.inputs["Base Color"].default_value
                setv("Base Color", (c[0] * 0.72, c[1] * 0.72, c[2] * 0.72, 1.0))
            setv("Coat Weight", 0.18)
            setv("Coat Roughness", 0.12)
            if name in ("sb_white",):
                setv("Subsurface Weight", 0.04)
        elif name == "glass_dark":
            setv("Coat Weight", 1.0)
            setv("Coat Roughness", 0.02)
        elif name in ("ind_red", "ind_green"):
            setv("Emission Color", bsdf.inputs["Base Color"].default_value)
            setv("Emission Strength", 0.6)


def import_scene(glb):
    bpy.ops.import_scene.gltf(filepath=glb)
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return objs, lo, hi


def look_at(obj, target):
    d = (target - obj.location).normalized()
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def frame_camera(view, lo, hi, w, h):
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam_data.sensor_width = 36.0
    cam_data.lens = view.get("lens", 70)
    cam_data.clip_start = 0.001
    cam_data.clip_end = 20
    target = cad(view["target"]) if "target" in view else (lo + hi) / 2
    d = Vector(view["dir"]).normalized()
    up = Vector((0, 0, 1))
    right = d.cross(up).normalized() * -1
    upv = right.cross(d).normalized() * -1
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    fit = view.get("fit", 0.8)
    aspect = w / h
    if view.get("ortho"):
        cam_data.type = "ORTHO"
        xs = [abs((c - target).dot(right)) for c in corners]
        ys = [abs((c - target).dot(upv)) for c in corners]
        span = max(max(xs) * 2 / fit, max(ys) * 2 * aspect / fit)
        cam_data.ortho_scale = span
        dist = (hi - lo).length * 3
    else:
        tx = math.tan(math.atan(18.0 / cam_data.lens)) * fit
        ty = tx / aspect
        dist = 0.0
        for c in corners:
            v = c - target
            x, y, z = v.dot(right), v.dot(upv), v.dot(d)
            dist = max(dist, abs(x) / tx + z, abs(y) / ty + z)
    cam.location = target + d * dist
    look_at(cam, target)
    return cam, dist


def add_lights(cam, target, dist, radius):
    sc = bpy.context.scene
    fwd = (target - cam.location).normalized()
    up = Vector((0, 0, 1))
    right = fwd.cross(up).normalized()

    def area(name, pos, size, power, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.size = size
        ld.energy = power
        ld.color = color
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = pos
        look_at(lo, target)
    r = max(radius, 0.01)
    k = (r / 0.08) ** 2 * float(os.environ.get("SB_LIGHT", "1"))
    area("key", target - right * 2.2 * r + up * 3.2 * r - fwd * 1.2 * r, 2.6 * r, 3.0 * k)
    area("fill", target + right * 3.0 * r + up * 1.2 * r - fwd * 1.6 * r, 3.2 * r, 1.0 * k, (0.92, 0.96, 1.0))
    area("rim", target + fwd * 3.0 * r + up * 2.4 * r, 2.4 * r, 1.8 * k)
    area("top", target + up * 4.5 * r, 4.0 * r, 0.7 * k)


def refine_framing(cam, objs, fit, w, h, passes=3):
    """Centre the projected bounding boxes and scale them to `fit` of the frame."""
    sc = bpy.context.scene
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    for _ in range(passes):
        bpy.context.view_layer.update()
        cs = [world_to_camera_view(sc, cam, p) for p in pts]
        xs, ys = [c.x for c in cs], [c.y for c in cs]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        span = max((x1 - x0) / fit, (y1 - y0) / fit)
        aspect_y = h / w if w >= h else 1.0
        aspect_x = 1.0 if w >= h else w / h
        cam.data.shift_x += ((x0 + x1) / 2 - 0.5) * aspect_x
        cam.data.shift_y += ((y0 + y1) / 2 - 0.5) * aspect_y
        if cam.data.type == "ORTHO":
            cam.data.ortho_scale *= span
            cam.data.shift_x /= span
            cam.data.shift_y /= span
        else:
            fwd = (cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))).normalized()
            target_dist = 0.0
            for p in pts:
                target_dist = max(target_dist, (p - cam.location).dot(fwd))
            near = min((p - cam.location).dot(fwd) for p in pts)
            mid = (near + target_dist) / 2
            cam.location += fwd * (mid - mid * span)


def add_ground(lo, hi):
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z - 0.00005))
    g = bpy.context.active_object
    s = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z) * 30
    g.scale = (s, s, 1)
    g.is_shadow_catcher = True


def project_anchors(shot, cam):
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    w, h = sc.render.resolution_x, sc.render.resolution_y
    out = []
    for a in shot.get("anchors", []):
        p = cad(a["p"])
        co = world_to_camera_view(sc, cam, p)
        origin = cam.matrix_world.translation
        if cam.data.type == "ORTHO":
            fwd = (cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))).normalized()
            origin = p - fwd * 5.0
        direction = (p - origin).normalized()
        hit, loc, *_ = sc.ray_cast(dg, origin, direction)
        occluded = bool(hit and (loc - origin).length < (p - origin).length - 0.0006)
        out.append({"label": a["label"], "x": co.x * w / SCALE, "y": (1 - co.y) * h / SCALE,
                    "occluded": occluded, "side": a.get("side", "auto")})
        if occluded:
            print("  [anchor occluded] %s: %s" % (shot["name"], a["label"]))
    return out


def render_shot(shot):
    reset()
    w, h = shot["size"]
    setup(w, h)
    if shot.get("kind") == "part":
        bpy.context.scene.cycles.samples = min(SAMPLES, 32)
        bpy.context.scene.view_settings.exposure -= 0.3
    objs, lo, hi = import_scene(os.path.join(BUILD, "render", shot["scene"] + ".glb"))
    tune_materials()
    cam, dist = frame_camera(shot["view"], lo, hi, w, h)
    target = (lo + hi) / 2 if "target" not in shot["view"] else cad(shot["view"]["target"])
    add_lights(cam, target, dist, (hi - lo).length / 2)
    refine_framing(cam, objs, shot["view"].get("fit", 0.8), w, h)
    if shot.get("ground", True):
        add_ground(lo, hi)
    anchors = project_anchors(shot, cam)
    out_png = os.path.join(RAW, shot["name"] + ".png")
    bpy.context.scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)
    with open(os.path.join(RAW, shot["name"] + ".json"), "w") as fh:
        json.dump({"name": shot["name"], "title": shot.get("title", ""), "size": shot["size"],
                   "anchors": anchors}, fh, indent=1)
    print("rendered", shot["name"])


def wanted(shot):
    """argv: exact shot names, or 'parts' / 'scenes' groups. Unchanged shots are
    skipped (PNG newer than its GLB) unless SB_FORCE=1."""
    if argv:
        group = "parts" if shot.get("kind") == "part" else "scenes"
        if shot["name"] not in argv and group not in argv:
            return False
    png = os.path.join(RAW, shot["name"] + ".png")
    glb = os.path.join(BUILD, "render", shot["scene"] + ".glb")
    if os.environ.get("SB_FORCE") != "1" and os.path.exists(png) and os.path.getmtime(png) > os.path.getmtime(glb):
        return False
    return True


shots = json.load(open(os.path.join(BUILD, "shots.json")))
part_shots = os.path.join(BUILD, "part_shots.json")
if os.path.exists(part_shots):
    shots += json.load(open(part_shots))
for s in shots:
    if wanted(s):
        render_shot(s)

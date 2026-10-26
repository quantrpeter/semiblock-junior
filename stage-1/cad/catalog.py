"""Single source of truth for every stage-1 part: builder, pose for its
catalogue picture, core-kit quantity and a one-line design note.
Used by build.py (CAD/mesh export), render_blender.py (via shots) and
make_docs.py (tables in the design MD)."""
import parts as P
import modules as MO

# pose: how the part lies for its catalogue picture
#   flat  = as modelled (beams/gears lie flat, modules stand on their base)
#   lay   = part Z axis -> +X (pins, axles, joiners lie on their side)
#   layr  = part Z axis -> -X (TwistLock pins: knob on the left)
#   stand = part Z axis -> -Y (wheels stand up, face the camera)
FAMILIES = ["Beams", "Connectors", "Pins & bushes", "TwistLock (lock system)", "Axles", "Gears & motion",
            "Wheels", "Accessories & tools", "Hub, motors & cables", "Smart modules"]


def E(family, make, pose="flat", qty=0, note=""):
    return {"family": family, "make": make, "pose": pose, "qty": qty, "note": note}


B, C, PN, L, A, G, W, T, H = FAMILIES[:9]
ITEMS = [
    # ---------------------------------------------------------------- beams
    E(B, lambda: P.crank_beam(), qty=8, note="1 pin hole + 1 axle hole: cranks, levers"),
    E(B, lambda: P.beam(3, "sb_yellow"), qty=12, note="length engraved on both edges"),
    E(B, lambda: P.beam(5, "sb_blue"), qty=12, note="hole ticks; long tick every 5th hole"),
    E(B, lambda: P.beam(7, "sb_blue"), qty=10, note="most-used length"),
    E(B, lambda: P.beam(9, "sb_yellow"), qty=8),
    E(B, lambda: P.beam(11, "sb_white"), qty=6),
    E(B, lambda: P.beam(13, "sb_lgrey"), qty=4),
    E(B, lambda: P.beam(15, "sb_blue"), qty=6, note="chassis rails"),
    E(B, lambda: P.thin_beam(3), qty=6, note="half thickness, axle holes at the ends"),
    E(B, lambda: P.thin_beam(5, "sb_blue"), qty=6, note="half thickness: linkages, flat panels"),
    E(B, lambda: P.lbeam(4, 2, "sb_blue"), qty=6),
    E(B, lambda: P.lbeam(5, 3, "sb_yellow"), qty=6),
    E(B, lambda: P.t_beam(), qty=4),
    E(B, lambda: P.bent_beam(), qty=4, note="53 deg bend = 3-4-5 triangle, ends stay on the grid"),
    E(B, lambda: P.frame_beam(5, 7), qty=2, note="one-piece rigid chassis frame"),
    # ----------------------------------------------------------- connectors
    E(C, lambda: P.semicube(), qty=8, note="NEW: 6-way node, builds 3D frames fast"),
    E(C, lambda: P.block_1x2(), qty=6, note="NEW: pin holes on 4 faces + axle through"),
    E(C, lambda: P.cross_block(2), qty=10, note="pin hole + perpendicular axle hole"),
    E(C, lambda: P.cross_block(3), qty=6),
    E(C, lambda: P.axle_joiner(), "lay", qty=6),
    E(C, lambda: P.pin_joiner(), "lay", qty=6),
    *[E(C, (lambda n=n: P.angle_connector(n)), qty=4, note="colour = angle, kids match by colour")
      for n in (1, 2, 3, 4, 5, 6)],
    # ---------------------------------------------------------------- pins
    E(PN, lambda: P.quick_pin(), "lay", qty=60, note="Technic-style friction pin"),
    E(PN, lambda: P.quick_pin(True), "lay", qty=20, note="smooth: free pivot"),
    E(PN, lambda: P.quick_pin(length=3), "lay", qty=20),
    E(PN, lambda: P.half_pin(), "lay", qty=10),
    E(PN, lambda: P.axle_pin(), "lay", qty=12),
    E(PN, lambda: P.axle_pin(True), "lay", qty=8),
    E(PN, lambda: P.ball_pin(), "lay", qty=4),
    E(PN, lambda: P.pin_with_hole(), "lay", qty=6),
    E(PN, lambda: P.bush(), qty=10),
    E(PN, lambda: P.half_bush(), qty=20),
    # ------------------------------------------------------------ TwistLock
    E(L, lambda: P.tl_pin(2), "layr", qty=40, note="push in, 1/4 turn = locked, green window"),
    E(L, lambda: P.tl_pin(2, smooth=True), "layr", qty=16, note="locked axially but still pivots"),
    E(L, lambda: P.tl_pin(3), "layr", qty=16, note="joins 3 layers"),
    E(L, lambda: P.tl_pin(3, smooth=True), "layr", qty=8),
    E(L, lambda: P.tl_collar(), qty=16, note="replaces the half bush: wheels never fall off"),
    E(L, lambda: P.tl_collar(length=7.8), qty=8, note="1L version, more grip"),
    # ----------------------------------------------------------------- axles
    *[E(A, (lambda n=n: P.axle(n)), "lay", qty=q, note=nt) for n, q, nt in
      ((2, 10, "notch every 8 mm: count notches = length"), (3, 10, ""), (4, 8, ""), (5, 8, ""), (6, 6, ""),
       (7, 4, ""), (8, 4, ""), (10, 4, ""), (12, 2, "odd = grey, even = black"))],
    E(A, lambda: P.axle(3, stop=True), "lay", qty=6),
    E(A, lambda: P.axle(4, stop=True), "lay", qty=6),
    # ---------------------------------------------------------- gears & motion
    E(G, lambda: P.gear(8, "sb_dgrey"), qty=4),
    E(G, lambda: P.bevel_gear(12, "sb_lgrey"), qty=4, note="double bevel: parallel or 90 deg"),
    E(G, lambda: P.gear(16, "sb_lgrey"), qty=4),
    E(G, lambda: P.bevel_gear(20, "sb_yellow"), qty=4),
    E(G, lambda: P.gear(24, "sb_blue"), qty=4),
    E(G, lambda: P.clutch_gear(), qty=2, note="NEW: slips before motors or teeth break"),
    E(G, lambda: P.bevel_gear(36, "sb_dgrey"), qty=2),
    E(G, lambda: P.gear(40, "sb_lgrey"), qty=2),
    E(G, lambda: P.worm_gear(), "lay", qty=2),
    E(G, lambda: P.gear_rack(4), qty=4, note="pin holes on the side, m = 1 teeth"),
    E(G, lambda: P.gear_rack(8, "sb_yellow"), qty=2),
    # ----------------------------------------------------------------- wheels
    E(W, lambda: P.wheel(), "stand", qty=4),
    E(W, lambda: P.wheel(30.0, 14.0, 21.0), "stand", qty=4),
    E(W, lambda: P.omni_wheel(), "stand", qty=2, note="NEW vs Technic: rolls sideways"),
    E(W, lambda: P.mecanum_wheel(1), "stand", qty=2, note="NEW: drive in any direction (pair L + R)"),
    E(W, lambda: P.mecanum_wheel(-1), "stand", qty=2),
    E(W, lambda: P.caster_block(), qty=1),
    # ------------------------------------------------------------ accessories
    E(T, lambda: P.semikey(), qty=1, note="key + axle gauge + pin lifter + ruler"),
    E(T, lambda: P.cable_clip(), "lay", qty=12, note="NEW: snaps into any hole, tidies cables"),
    E(T, lambda: P.name_plate(), qty=2, note="write a name, pin it on"),
    # -------------------------------------------------------- hub / motors / link
    E(H, MO.brain_hub, qty=1, note="ESP32-S3, 1.54 in screen, 6 ports, IMU, mic, speaker"),
    E(H, MO.motor_m, qty=2, note="encoder: speed + position, both ends have a port"),
    E(H, lambda: MO.motor(7, "L"), qty=1, note="high torque, 4 pin holes on the output"),
    E(H, lambda: MO.servo("180"), qty=1, note="position servo, axle output"),
    E(H, lambda: MO.servo("360"), qty=0, note="continuous rotation"),
    E(H, lambda: MO.semilink_plug(), "flat", qty=8, note="keyed + latching, cable is replaceable"),
]
for m in MO.MODULES:
    core = m["code"] in ("US", "LINE", "COLOR", "BTN", "TOUCH", "LUX", "SOUND", "ENV", "RGB", "IRP", "ANGLE", "POT")
    ITEMS.append(E(FAMILIES[9], (lambda m=m: MO.build_module(m)), qty=1 if core else 0, note=m["does"]))
    ITEMS[-1]["module"] = m


def build(item):
    part = item["make"]()
    item["pid"], item["title"] = part.pid, part.title
    return part

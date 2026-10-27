"""SemiBlock Junior - Stage-2 parametric dimensions (all values in mm).

Grid values marked [T] match the Technic-style 8 mm system so SemiBlock parts
mix with LEGO(R) Technic(TM) parts. Everything else is a Stage-2 proposal and
must be validated with prototypes (see the prototype plan in the design doc).
"""

# --- Grid ---------------------------------------------------------------
PITCH = 8.0             # [T] 1 module = hole-to-hole pitch
GAP = 0.2               # [T] clearance between neighbouring parts (0.1 per face)
BEAM_T = PITCH - GAP    # [T] 7.8  beam thickness along the hole axis
BEAM_W = 7.4            # [T] beam width across the hole axis
HOLE_D = 4.85           # [T] round pin / axle hole
CB_D = 6.2              # [T] counterbore diameter (both faces of every hole)
CB_DEPTH = 0.7          # [T] counterbore depth
AXLE_D = 4.75           # [T] axle cross, tip to tip
AXLE_SPLINE = 1.8       # [T] axle cross arm thickness
AXLE_HOLE_D = 4.85      # [T] cross hole, tip to tip
AXLE_HOLE_SPLINE = 1.9  # [T] cross hole arm width

# --- H-beam section (stage 2) ------------------------------------------------
# Same outside size, holes and counterbores as a Technic beam; between the holes
# the section is an H: top + bottom flanges carry the pin faces, a web joins
# them, a tube surrounds every hole and both sides are pocketed.
HB_FLANGE = 1.8         # flange thickness (pin faces); counterbore leaves 1.1 under it
HB_WEB = 1.6            # centre web
HB_TUBE_D = 6.8         # tube around each hole (wall 0.98)
HB_POCKET_R = 0.5       # pocket corner radius (mould)

# --- AngleLock hinge (stage 2) ----------------------------------------------
# Two identical halves, 24 Hirth face teeth = 15 deg steps, clamped by one
# TwistLock Pin 2L through the pivot.
AH_TEETH = 24
AH_DISC_D = 15.4        # 2-module disc around the pivot
AH_TEETH_RI = 3.5       # tooth ring, inner radius (outside the 6.2 counterbore)
AH_TEETH_RO = 7.4       # tooth ring, outer radius
AH_TOOTH_ANGLE = 90     # included angle of the tooth (deg)

# --- Bearings (stage 2) -----------------------------------------------------
# Axle bearing: MR128ZZ 8 x 12 x 3.5, chrome steel, shields both sides.
BRG_D, BRG_DO, BRG_B = 8.0, 12.0, 3.5
BRG_SEAT_D = 11.96      # housing seat: press fit 0.02-0.06 on the 12.00 outer ring
BRG_HUB_D = 8.02        # axle hub on the 8.00 inner ring: press fit 0.01-0.03
BRG_SHOULDER_D = 10.4   # housing shoulder: touches the outer ring only
BRG_RET_D = 13.6        # retainer ring recess
BRG_BOSS_D = 15.2       # housing boss around the bearing
BRG_HUB_HEAD_D = 9.4    # hub head: touches the inner ring only
# Turntable bearing: 6705ZZ 25 x 32 x 4 thin section.
TT_D, TT_DO, TT_B = 25.0, 32.0, 4.0
TT_SEAT_D = 31.96
TT_HUB_D = 25.02
TT_LIP_D = 29.4         # stator lip / retainer bore: outer ring only
TT_GEAR_Z = 40          # rotor rim teeth, m = 1 (8T pinion meshes 24 mm = 3 modules away)

# --- Quick Pin (friction pin, double ended, Technic-style) -----------------
QP_D = 4.8
QP_ID = 3.1
QP_COLLAR_D = 5.6
QP_COLLAR_T = 0.7
QP_LIP_D = 5.0
QP_LIP_T = 0.55
QP_SLIT_W = 0.75
QP_SLIT_L = 4.0

# --- TwistLock Pin (TL-pin) -----------------------------------------------
# Sleeve: slip-fit shank with split fingers + catch lip at the far end.
# Core:   knob + D-shaped cam. Flats facing the fingers = fingers free (OPEN);
#         turn 90 deg so the arcs face the fingers = fingers blocked (LOCKED).
TL_SLEEVE_D = 4.8
TL_BORE_D = 2.6
TL_FLANGE_D = 5.9       # sits inside the 6.2 counterbore -> flush with beam face
TL_FLANGE_T = 0.65
TL_LIP_D = 5.4          # catch lip, relaxed: 0.3 mm/side behind counterbore step
TL_LIP_RAMP_DEG = 45    # back-face ramp: pull-out possible only while OPEN
TL_SLOT_W = 0.9         # through slot that splits the far end into 2 fingers
TL_FINGER_L = 6.8
TL_RIB_H = 0.12         # anti-spin friction ribs on the near half of the shank
TL_CAM_D = 2.62         # cam across arcs (0.01 mm/side preload = zero play)
TL_CAM_FLATS = 1.9      # cam across flats -> 0.35 mm/side finger travel
TL_SHAFT_D = 2.5
TL_KNOB_D = 6.0         # fits inside the 8 mm grid with 2 mm to the next knob
TL_KNOB_T = 1.2
TL_WING_W = 1.6
TL_WING_H = 1.4         # total protrusion above beam face = KNOB_T + WING_H
TL_WINDOW_ARC = 50      # two 50 deg arc status windows in the knob (readable from ~1 m)
TL_WINDOW_R = 2.2       # radius of the status windows / status ring
TL_LOCK_TURN_DEG = -90  # clockwise quarter turn (seen from the knob)

# --- TwistLock Collar (axle lock, replaces bushes) --------------------------
TC_LEN = 3.9            # half-module long, like a half bush
TC_OD = 7.4
TC_COLLET_D = 5.6
TC_FLANGE_T = 0.6
TC_OVAL_MAJOR = 5.72    # ring bore across the major axis (jaws free)
TC_OVAL_MINOR = 5.44    # ring bore across the minor axis (jaws squeezed 0.08/side)
TC_SLOT_W = 0.7

# --- Wheels / gears -------------------------------------------------------
GEAR_MODULE = 1.0       # [T] m = 1 -> 8/16/24/40 T gears mesh on the 8 mm grid
GEAR_T = 3.7
WHEEL_D = 56.0
WHEEL_W = 26.0
RIM_D = 43.2

# --- Electronics housings (all multiples of the grid) -----------------------
HUB_MODULES = (11, 6, 4)        # Junior Brain: 88 x 48 x 32 mm
MOTOR_MODULES = (5, 3, 3)       # SemiMotor M: 40 x 24 x 24 mm
SENSOR_MODULES = (2, 6, 3)      # wide sensors (ultrasonic, line): 16 x 48 x 24 mm
SEMILINK_W = 9.0                # SemiLink-6 plug body
SEMILINK_H = 6.0
SEMILINK_L = 13.0


def L(n):
    """Outside length of an n-module housing / axle (n * pitch - gap)."""
    return n * PITCH - GAP

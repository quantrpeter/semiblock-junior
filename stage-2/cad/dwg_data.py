"""Manufacturing data for the drawings: Chinese part names, materials,
colours, critical tolerances and the technical-requirement notes.
Everything here is a stage-2 proposal for quotation and DFM review."""

DATE = "2026-10-27"
REV = "A"
# Stage 2 changed the section of these beams to an H. Outside size, holes and fit
# are unchanged (interchangeable), so they keep their part numbers at Rev B.
# Every other part (and every new stage-2 part) is Rev A.
REV_B = {"SB-B02X", "SB-B03", "SB-B05", "SB-B07", "SB-B09", "SB-B11", "SB-B13", "SB-B15", "SB-L24", "SB-L35",
         "SB-T33", "SB-K46", "SB-F57"}
PACK = "SemiBlock-Junior-drawings-stage2.pdf"


def rev_for(pid):
    base = pid[:-3] if len(pid) > 3 and pid[-3] == "-" and pid[-2:].isdigit() else pid   # SB-TL2-01 -> SB-TL2
    return "B" if base in REV_B else "A"


NAME_ZH = {
    "SB-B02X": "工字孔梁 1×2（圆孔+十字孔）", "SB-S03": "薄孔梁 1×3（半厚）", "SB-S05": "薄孔梁 1×5（半厚）",
    "SB-L24": "L形工字孔梁 2×4", "SB-L35": "L形工字孔梁 3×5", "SB-T33": "T形工字孔梁 3×3",
    "SB-K46": "弯工字孔梁 1×9（53°）", "SB-K44": "弯工字孔梁 1×7（45°）", "SB-F57": "工字截面框架 5×7",
    "SB-AH": "角度铰链（15° 分度）", "SB-BR5": "轴承梁 1×5（滚珠轴承）", "SB-TT7": "转盘 7×7（滚珠轴承）", "SB-C111": "六向连接块 1×1×1", "SB-C121": "连接块 1×2×1（四面销孔）",
    "SB-XC12": "十字连接块 1×2", "SB-XC13": "十字连接块 1×3", "SB-XA2": "轴连接器 2L", "SB-XP2": "销连接器 2L",
    "SB-XN1": "角度连接器 #1", "SB-XN2": "角度连接器 #2（180°）", "SB-XN3": "角度连接器 #3（157.5°）",
    "SB-XN4": "角度连接器 #4（135°）", "SB-XN5": "角度连接器 #5（112.5°）", "SB-XN6": "角度连接器 #6（90°）",
    "SB-QP2": "摩擦销 2L", "SB-QP2S": "光滑销 2L（可转动）", "SB-QP3": "摩擦销 3L", "SB-QP1": "半销 1L（带挡头）",
    "SB-AP2": "轴销（摩擦）", "SB-AP2S": "轴销（光滑）", "SB-BP": "球头销（拖车球）", "SB-PX": "带十字孔销",
    "SB-BU1": "轴套 1L", "SB-BU0": "半轴套", "SB-TL2": "旋锁销 2L（摩擦）", "SB-TL2S": "旋锁销 2L（光滑，可转动）",
    "SB-TL3": "旋锁销 3L（摩擦）", "SB-TL3S": "旋锁销 3L（光滑，可转动）", "SB-TC": "旋锁轴环 1/2L",
    "SB-TC1": "旋锁轴环 1L", "SB-A03S": "带挡十字轴 3", "SB-A04S": "带挡十字轴 4",
    "SB-G08": "直齿轮 8齿", "SB-G12B": "双面锥齿轮 12齿", "SB-G16": "直齿轮 16齿", "SB-G20B": "双面锥齿轮 20齿",
    "SB-G24": "直齿轮 24齿", "SB-G24C": "离合齿轮 24齿（过载打滑）", "SB-G36B": "双面锥齿轮 36齿",
    "SB-G40": "直齿轮 40齿", "SB-GW": "蜗杆", "SB-GR4": "齿条 1×4", "SB-GR8": "齿条 1×8",
    "SB-W56": "车轮 56×26（含轮胎）", "SB-W30": "车轮 30×14（含轮胎）", "SB-WO48": "全向轮 48",
    "SB-WM60L": "麦克纳姆轮 60（左）", "SB-WM60R": "麦克纳姆轮 60（右）", "SB-CASTER": "万向球座",
    "SB-KEY": "SemiKey 多功能工具", "SB-CC": "线夹（插销式）", "SB-N26": "名牌 2×6（可书写）",
    "SB-HUB": "主控盒 Junior Brain（ESP32-S3）", "SB-MOT-M": "编码电机 M", "SB-MOT-L": "编码电机 L（大扭矩）",
    "SB-SV180": "舵机 180°", "SB-SV360": "360° 连续旋转舵机", "SB-LINK": "SemiLink-6 插头及线缆",
    "SB-US": "超声波测距模块", "SB-TOF": "激光测距模块（ToF）", "SB-IRP": "红外避障模块", "SB-PIR": "人体红外感应模块",
    "SB-RADAR": "毫米波人体存在模块", "SB-ZONE": "多区激光测距模块", "SB-LINE": "循迹传感器 ×5",
    "SB-COLOR": "颜色传感器", "SB-GEST": "手势传感器", "SB-LUX": "光照传感器", "SB-UV": "紫外线传感器",
    "SB-FLAME": "火焰传感器", "SB-IRT": "非接触测温模块", "SB-THERM": "热成像模块 8×8", "SB-BTN": "大按钮模块",
    "SB-BUMP": "碰撞开关模块", "SB-TOUCH": "触摸传感器", "SB-FORCE": "压力传感器", "SB-LOAD": "称重传感器（1 kg）",
    "SB-POT": "旋钮电位器", "SB-ENC": "旋转编码器", "SB-SLIDE": "滑动电位器", "SB-JOY": "摇杆模块",
    "SB-KEYPAD": "4×3 键盘", "SB-IMU": "六轴姿态传感器", "SB-KNOCK": "敲击/震动传感器", "SB-ANGLE": "角度传感器（轴穿式）",
    "SB-MAG": "磁场传感器", "SB-COMPASS": "电子罗盘", "SB-ENV": "温湿度气压传感器", "SB-PROBE": "防水温度探头",
    "SB-SOIL": "土壤湿度传感器", "SB-WATER": "水位/雨滴传感器", "SB-SOUND": "声音传感器",
    "SB-CO2": "二氧化碳传感器（NDIR）", "SB-AIR": "空气质量传感器（TVOC）", "SB-PM": "PM2.5 粉尘传感器",
    "SB-GAS": "气体/烟雾传感器", "SB-PH": "pH 酸碱度探头", "SB-TDS": "水质 TDS 传感器", "SB-HEART": "心率血氧传感器",
    "SB-GPS": "GPS 定位模块", "SB-CAM": "AI 视觉摄像头", "SB-VOICE": "离线语音识别模块", "SB-RFID": "RFID/NFC 读卡器",
    "SB-IRX": "红外收发模块", "SB-RGB": "RGB 彩灯 ×4", "SB-RING": "LED 灯环 ×12", "SB-MATRIX": "8×8 点阵屏",
    "SB-TRAFFIC": "交通灯模块", "SB-OLED": "0.96 寸 OLED 显示屏", "SB-SEG": "四位数码管", "SB-SPK": "喇叭/MP3 模块",
    "SB-FAN": "风扇模块", "SB-PUMP": "水泵模块", "SB-VIB": "震动马达模块", "SB-EMAG": "电磁铁模块",
    "SB-SWITCH": "电源开关（≤12 V）", "SB-SOLAR": "太阳能板 1 W", "SB-METER": "电能表（电压/电流/功率）",
}
for _n in (3, 5, 7, 9, 11, 13, 15):
    NAME_ZH["SB-B%02d" % _n] = "工字孔梁 1×%d" % _n
for _n in (2, 3, 4, 5, 6, 7, 8, 10, 12):
    NAME_ZH["SB-A%02d" % _n] = "十字轴 %d" % _n

COMP_NAME = {   # body name -> (EN, 中文)
    "sleeve": ("Sleeve", "套管"), "core": ("Core", "锁芯"), "collet": ("Collet", "夹套"), "ring": ("Lock ring", "锁环"),
    "hub": ("Hub", "轮毂"), "tire": ("Tyre", "轮胎"), "rollers": ("Roller", "滚轮"), "block": ("Housing", "球座"),
    "ball": ("Steel ball", "钢球"), "plate": ("Plate", "名牌板"), "card": ("Write-on card", "书写卡"),
    "hinge": ("Hinge half", "铰链半件"), "housing": ("Bearing housing", "轴承座"), "axle_hub": ("Axle hub", "十字轴芯"),
    "retainer": ("Retainer ring", "压圈"), "stator": ("Base", "底座"), "rotor": ("Rotor 40T", "转盘齿圈 40齿"),
    "bearing_mr128": ("Bearing MR128ZZ", "轴承"), "bearing_6705": ("Bearing 6705ZZ", "轴承"),
}

# colour code: (EN, 中文, sRGB hex, colour standard code)
COLOURS = {
    "sb_blue": ("Blue", "蓝", "#1F6FE5", "SB-C01"), "sb_yellow": ("Yellow", "黄", "#FFC21A", "SB-C02"),
    "sb_white": ("White", "白", "#F2F4F7", "SB-C03"), "sb_lgrey": ("Light grey", "浅灰", "#B4BCC6", "SB-C04"),
    "sb_dgrey": ("Dark grey", "深灰", "#5B636D", "SB-C05"), "sb_black": ("Black", "黑", "#24282E", "SB-C06"),
    "sb_magenta": ("Magenta", "品红", "#C8209E", "SB-C07"), "sb_teal": ("Teal", "青绿", "#12A89A", "SB-C08"),
    "sb_violet": ("Violet", "紫", "#7447EE", "SB-C09"), "rubber": ("Black", "黑", "#1C1F23", "SB-C10"),
    "steel": ("Bright steel", "本色", "#C9CED6", "—"),
}

# material key -> EN, 中文, density g/cm3, finish (EN, 中文), ISO 11469 code
MATERIALS = {
    "ABS": ("ABS, e.g. CHIMEI PA-757 or equiv.", "ABS（奇美 PA-757 或同等）", 1.05,
            ("VDI 3400 Ref 18", "细哑光纹理"), ">ABS<"),
    "POM": ("POM copolymer, e.g. Hostaform C 9021", "POM 共聚甲醛（C 9021 或同等）", 1.41,
            ("SPI B-2", "光滑面"), ">POM<"),
    "TPE": ("TPE, Shore A 65 ±5", "TPE 邵氏 A 65±5", 1.15, ("VDI 3400 Ref 27", "哑光纹理"), ">TPE<"),
    "TPU": ("TPU, Shore A 85 ±5", "TPU 邵氏 A 85±5", 1.20, ("VDI 3400 Ref 24", "哑光纹理"), ">TPU<"),
    "PCABS": ("PC/ABS, UL94 V-0", "PC/ABS 阻燃 UL94 V-0", 1.18, ("VDI 3400 Ref 18", "细哑光纹理"), ">PC+ABS<"),
    "PA66GF": ("PA66-GF30, e.g. Zytel 70G30 or equiv.", "PA66+30%玻纤（杜邦 70G30 或同等）", 1.36,
               ("VDI 3400 Ref 21", "细哑光纹理"), ">PA66-GF30<"),
    "STEEL": ("Chrome steel GCr15 (purchased)", "铬钢 GCr15（外购件）", 7.85, ("polished", "抛光"), ""),
}

MAT_SHORT = {"ABS": ("ABS (PA-757 or equiv.)", "ABS 奇美 PA-757 或同等"), "POM": ("POM copolymer", "POM 共聚甲醛"),
             "TPE": ("TPE Shore A 65", "TPE 邵氏 A65"), "TPU": ("TPU Shore A 85", "TPU 邵氏 A85"),
             "PCABS": ("PC/ABS UL94 V-0", "PC/ABS 阻燃 V-0"), "STEEL": ("Chrome steel GCr15", "铬钢（外购）"),
             "PA66GF": ("PA66-GF30", "PA66+30%玻纤")}

MODULE_FAMILIES = ("Hub, motors & cables", "Smart modules")


def material_for(family, body, mat):
    if mat == "rubber":
        return "TPU" if body == "rollers" else "TPE"
    if mat == "steel":
        return "STEEL"
    if family in ("Pins & bushes", "TwistLock (lock system)", "Axles", "Gears & motion"):
        return "POM"
    if family == "Accessories & tools" and body == "clip":
        return "POM"
    if family == "Bearings":
        return "PA66GF" if body in ("housing", "stator") else "POM"   # press-fit seats need low creep
    if body == "hinge":
        return "POM"
    if family == "Hub, motors & cables" and body in ("base", "cover", "shell"):
        return "PCABS"
    return "ABS"


# critical-to-function tolerances by feature kind + nominal size (mm)
TOL_RULES = [
    ("hole", 4.85, "±0.02", True), ("cbore", 6.2, "±0.05", True), ("cbdepth", 0.7, "±0.05", True),
    ("hole", 2.6, "+0.02/0", True), ("hole", 3.1, "±0.05", False), ("hole", 5.2, "±0.05", False),
    ("shaft", 4.8, "±0.02", True), ("shaft", 5.4, "±0.02", True), ("shaft", 5.9, "±0.03", True),
    ("shaft", 2.5, "±0.02", True), ("shaft", 5.6, "±0.05", False), ("shaft", 7.36, "±0.05", True),
    ("xhole", 4.85, "±0.02", True), ("xhole_s", 1.9, "±0.02", True),
    ("xshaft", 4.75, "±0.02", True), ("xshaft_s", 1.8, "±0.02", True),
    ("len", 7.8, "±0.05", True), ("len", 7.4, "±0.05", True), ("len", 3.8, "±0.05", True),
    ("pitch", 8.0, "±0.02", True), ("cam", 2.62, "±0.01", True), ("flats", 1.9, "±0.02", True),
    ("slot", 0.9, "±0.03", True), ("oval", 5.72, "±0.02", True), ("oval", 5.44, "±0.02", True),
    ("tip", 0, "±0.05", False),
    # bearings (stage 2): seats and hubs are press fits on standard ball bearings
    ("hole", 11.96, "+0.02/0", True), ("hole", 10.4, "±0.05", False), ("hole", 13.6, "+0.02/0", True),
    ("shaft", 8.02, "±0.01", True), ("shaft", 9.4, "±0.05", False), ("shaft", 13.6, "+0.06/+0.03", True),
    ("hole", 31.96, "+0.03/0", True), ("hole", 29.4, "±0.05", False), ("shaft", 25.02, "±0.01", True),
    ("shaft", 31.96, "+0.08/+0.05", True),
]


def tol(kind, nominal):
    for k, v, t, ctf in TOL_RULES:
        if k == kind and (v == 0 or abs(v - nominal) < 0.006):
            return t, ctf
    return "", False


def notes_for(kind, mat_keys, has_pin_holes, has_axle_holes, colour_lines, step_name):
    """Technical requirements (EN, 中文) for one sheet."""
    n = []
    if kind == "outline":
        n += [("OUTLINE & INTERFACE drawing: fixes the envelope, the 8 mm pin-hole grid and the port position only. "
               "Enclosure internals (walls ≥ 1.2, PCB, bosses, snaps, battery) are designed by the supplier and "
               "approved by semiblock.ai.",
               "外形及接口图：仅规定外形、8 mm 销孔网格和接口位置。外壳内部结构（壁厚≥1.2、PCB、螺柱、卡扣、电池）由供应商设计并经 semiblock.ai 批准。"),
              ("Pin holes Ø4.85 ±0.02 ◆ on 8.00 ±0.02 ◆ pitch must accept SemiBlock and LEGO® Technic™ pins.",
               "Ø4.85 销孔及 8 mm 孔距为关键尺寸，须兼容 SemiBlock 及乐高机械组销。"),
              ("Electrical: SemiLink-6 port, ≤ 12 V. Safety: EN 62115 / GB 19865 (electric toys); radio modules CE RED / FCC / SRRC.",
               "电气：SemiLink-6 接口，≤12 V。安全：EN 62115 / GB 19865 电玩具标准；无线模块需 CE RED / FCC / SRRC。")]
    else:
        n.append(("3D model %s is the master; dimensions not shown are taken from it." % step_name,
                  "以 3D 模型 %s 为准，未注尺寸按 3D 数据。" % step_name))
    for line in colour_lines:
        n.append(line)
    if kind != "outline":
        n += [("Draft ≤ 0.5° on outer walls, added by the tool maker within tolerance. Pin / axle holes and ◆ "
               "features: draft ≤ 0.25°, ◆ size held over the full depth.",
               "外壁拔模≤0.5°（模具厂在公差内添加）；销孔、十字孔及◆特征拔模≤0.25°，全深度保持◆尺寸。"),
              ("Parting line, gate and ejector marks: not on visible faces or inside holes, flush to +0.05. "
               "Positions to be agreed in DFM.",
               "分模线、浇口、顶针痕不得在外观面及孔内，凸起≤0.05，位置于 DFM 时确认。"),
              ("No flash > 0.05, sink marks, short shots, silver streaks or voids. Holes free of burrs.",
               "无大于0.05的披锋，无缩水、缺料、银纹、气泡；孔内无毛刺。"),
              ("Unspecified edge radii R0.2–R0.35 as in 3D. No sharp edges or points (toy safety).",
               "未注圆角 R0.2–R0.35（按 3D），不得有锐边锐角（玩具安全）。")]
    if has_pin_holes:
        n.append(("Pin holes: GO Ø4.83 / NO-GO Ø4.88 plug gauge. Fit test with SemiBlock and LEGO® Technic™ pins; "
                  "push-in / pull-out force agreed at T1.",
                  "销孔用 Ø4.83 通规 / Ø4.88 止规检验；与 SemiBlock 及乐高销做装配测试，插拔力于 T1 确认。"))
    if has_axle_holes:
        n.append(("Axle (+) holes: GO gauge = cross 4.83 / 1.88. Standard axle must slide in by hand without play "
                  "> 0.05.", "十字孔用 4.83/1.88 十字通规；标准十字轴可手推插入，间隙≤0.05。"))
    codes = " ".join(sorted(set(MATERIALS[m][4] for m in mat_keys if MATERIALS[m][4])))
    if codes:
        n.append(("Mark cavity number and material code %s on a hidden face where space allows (ISO 11469)." % codes,
                  "在不可见面标注穴号及材料代码 %s（ISO 11469），空间不足可省略。" % codes))
    n += [("Toy safety: EN 71-1/-2/-3, ASTM F963, GB 6675.1–.4; RoHS and REACH. Supply material certificates.",
           "玩具安全：EN 71-1/-2/-3、ASTM F963、GB 6675.1–.4；符合 RoHS、REACH，提供材料证明。"),
          ("◆ = critical dimension: FAI report on every ◆ at T1 (5 pcs per cavity); production Cpk ≥ 1.33.",
           "◆为关键尺寸：T1 每穴 5 件全尺寸首件报告；量产 Cpk≥1.33。"),
          ("Stage-2 drawings are for quotation, DFM review and T0/T1 samples. No mass production before written "
           "sample approval.", "第二阶段图纸用于报价、DFM 评审及 T0/T1 打样；样品书面确认前不得量产。")]
    return n

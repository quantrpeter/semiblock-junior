"""Compose final images from Blender renders (system Python + Pillow).

    python3 stage-1/cad/annotate.py

  renders/<shot>.png           callout diagrams (title + labelled leader lines)
  renders/twistlock-steps.png  push / twist / locked strip
  renders/parts/<id>.png       one card per catalogue part
  renders/sheets/<family>.png  contact sheet per family
"""
import json
import os
import re
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.dirname(HERE)
RAW = os.path.join(HERE, "build", "raw")
OUT = os.path.join(STAGE, "renders")
PARTS = os.path.join(OUT, "parts")
SHEETS = os.path.join(OUT, "sheets")
for d in (OUT, PARTS, SHEETS):
    os.makedirs(d, exist_ok=True)

F_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
F_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
F_CJK = "/System/Library/Fonts/STHeiti Medium.ttc"
INK, MUTED, LINE = (15, 23, 42), (90, 102, 120), (51, 65, 85)
BLUE, MAGENTA = (31, 111, 229), (200, 32, 158)
CAT_COLORS = {"sense": (31, 111, 229), "env": (31, 111, 229), "output": (230, 160, 0), "connect": (18, 168, 154),
              "ai": (116, 71, 238), "power": (91, 99, 109)}


def font(path, size):
    return ImageFont.truetype(path, size)


def background(w, h, top=(247, 249, 253), bottom=(232, 238, 246)):
    bg = Image.new("RGB", (w, h), top)
    px = ImageDraw.Draw(bg)
    for y in range(h):
        t = y / max(h - 1, 1)
        px.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return bg.convert("RGBA")


def has_cjk(s):
    return any("　" <= ch <= "鿿" for ch in s)


def text(draw, xy, s, size, bold=False, fill=INK, anchor="la"):
    f = font(F_CJK if has_cjk(s) else (F_BOLD if bold else F_REG), size)
    draw.text(xy, s, font=f, fill=fill, anchor=anchor)
    return f


# ------------------------------------------------------------- callouts
def callout_image(meta):
    src = Image.open(os.path.join(RAW, meta["name"] + ".png")).convert("RGBA")
    w, h = src.size
    header = 96 if meta.get("title") else 0
    canvas = background(w, h + header)
    canvas.alpha_composite(src, (0, header))
    d = ImageDraw.Draw(canvas)
    if meta.get("title"):
        text(d, (48, 30), meta["title"], 40, bold=True)
        text(d, (w - 48, 40), "SemiBlock Junior  |  Stage-1 concept", 22, fill=MUTED, anchor="ra")
        d.line([(48, header - 8), (w - 48, header - 8)], fill=(214, 222, 234), width=2)
    anchors = meta.get("anchors", [])
    if not anchors:
        return canvas
    f = font(F_BOLD, 25)
    pad, gap, margin = 14, 18, 40
    max_w = int(w * 0.215)
    sides = {"left": [], "right": [], "top": [], "bottom": []}
    for a in anchors:
        side = a.get("side", "auto")
        if side == "auto":
            side = "left" if a["x"] < w / 2 else "right"
        sides[side].append(a)

    def measure(a):
        lines = textwrap.wrap(a["label"], 24) or [""]
        tw = max(d.textlength(t, font=f) for t in lines)
        return lines, min(max_w, tw + 2 * pad), len(lines) * 32 + 2 * pad - 6

    placed = []      # (anchor, lines, bx, by, bw, bh, leader points)
    for side in ("left", "right"):
        items = sorted(sides[side], key=lambda a: a["y"])
        boxes = []
        for a in items:
            lines, bw, bh = measure(a)
            boxes.append([a, lines, bw, bh, a["y"] + header - bh / 2])
        for i, b in enumerate(boxes):
            b[4] = max(b[4], header + 20 if i == 0 else boxes[i - 1][4] + boxes[i - 1][3] + gap)
        for i in range(len(boxes) - 1, -1, -1):
            limit = h + header - 20 if i == len(boxes) - 1 else boxes[i + 1][4] - gap
            boxes[i][4] = min(boxes[i][4], limit - boxes[i][3])
        for a, lines, bw, bh, by in boxes:
            bx = margin if side == "left" else w - margin - bw
            ex = bx + bw if side == "left" else bx
            ey = by + bh / 2
            elbow = ex + (30 if side == "left" else -30)
            placed.append((a, lines, bx, by, bw, bh, [(ex, ey), (elbow, ey), (a["x"], a["y"] + header)]))
    for side in ("top", "bottom"):
        items = sorted(sides[side], key=lambda a: a["x"])
        boxes = []
        for a in items:
            lines, bw, bh = measure(a)
            boxes.append([a, lines, bw, bh, min(max(a["x"] - bw / 2, margin), w - margin - bw)])
        for i in range(1, len(boxes)):
            boxes[i][4] = max(boxes[i][4], boxes[i - 1][4] + boxes[i - 1][2] + gap)
        for a, lines, bw, bh, bx in boxes:
            by = header + 24 if side == "top" else h + header - 24 - bh
            ex, ey = bx + bw / 2, (by + bh if side == "top" else by)
            elbow = ey + (30 if side == "top" else -30)
            placed.append((a, lines, bx, by, bw, bh, [(ex, ey), (ex, elbow), (a["x"], a["y"] + header)]))
    for a, lines, bx, by, bw, bh, pts in placed:          # halo first so crossings stay readable
        d.line(pts, fill=(255, 255, 255), width=8, joint="curve")
    for a, lines, bx, by, bw, bh, pts in placed:
        ax, ay = pts[-1]
        d.line(pts, fill=LINE, width=3, joint="curve")
        d.ellipse([ax - 8, ay - 8, ax + 8, ay + 8], fill=(255, 255, 255), outline=LINE, width=3)
        d.ellipse([ax - 3.5, ay - 3.5, ax + 3.5, ay + 3.5], fill=MAGENTA)
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=12, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
        for k, t in enumerate(lines):
            d.text((bx + pad, by + pad + k * 32), t, font=f, fill=INK)
    return canvas


def steps_strip():
    labels = [("1", "Push in", "slides in like a normal pin"), ("2", "Turn 1/4 clockwise", "fingertip or SemiKey"),
              ("3", "Green = locked", "red = still open")]
    tiles = []
    for k in (1, 2, 3):
        p = os.path.join(RAW, "twistlock-step-%d.png" % k)
        if not os.path.exists(p):
            return None
        tiles.append(Image.open(p).convert("RGBA"))
    tw, th = tiles[0].size
    W, H = tw * 3 + 80, th + 230
    canvas = background(W, H)
    d = ImageDraw.Draw(canvas)
    text(d, (48, 30), "TwistLock Pin - how to lock", 40, bold=True)
    text(d, (W - 48, 40), "SemiBlock Junior  |  Stage-1 concept", 22, fill=MUTED, anchor="ra")
    for i, (tile, (num, head, sub)) in enumerate(zip(tiles, labels)):
        x = 20 + i * (tw + 20)
        canvas.alpha_composite(tile, (x, 100))
        cx, cy = x + 60, 140
        col = (34, 197, 94) if num == "3" else BLUE
        d.ellipse([cx - 32, cy - 32, cx + 32, cy + 32], fill=col)
        text(d, (cx, cy + 2), num, 38, bold=True, fill=(255, 255, 255), anchor="mm")
        text(d, (x + tw / 2, H - 100), head, 36, bold=True, anchor="mm")
        text(d, (x + tw / 2, H - 55), sub, 26, fill=MUTED, anchor="mm")
        if i < 2:
            ax = x + tw + 10
            d.polygon([(ax - 12, 100 + th / 2 - 22), (ax + 12, 100 + th / 2), (ax - 12, 100 + th / 2 + 22)], fill=(148, 163, 184))
    return canvas


# ----------------------------------------------------------- part cards
def part_card(row, scale=1.0):
    src = Image.open(os.path.join(RAW, "part-%s.png" % row["id"])).convert("RGBA")
    if src.width != 800:
        src = src.resize((800, int(src.height * 800 / src.width)), Image.LANCZOS)
    w, h = src.size
    band = 118
    card = background(w, h + band, (250, 251, 254), (238, 242, 248))
    card.alpha_composite(src, (0, 0))
    d = ImageDraw.Draw(card)
    mod = row.get("module")
    accent = CAT_COLORS.get(mod["cat"], BLUE) if mod else (MAGENTA if row["family"].startswith("TwistLock") else BLUE)
    d.rectangle([0, h, w, h + 6], fill=accent)
    title = row["title"]
    f = font(F_BOLD, 34)
    while d.textlength(title, font=f) > w - 60 and f.size > 22:
        f = font(F_BOLD, f.size - 2)
    d.text((28, h + 22), title, font=f, fill=INK)
    sz = " x ".join("%g" % v for v in row["size_mm"])
    sub = "%s   |   %s mm" % (row["id"], sz)
    text(d, (28, h + 72), sub, 24, fill=MUTED)
    if mod:
        text(d, (w - 28, h + 72), mod["zh"], 26, fill=accent, anchor="ra")
        pill = mod["phase"]
        pw = d.textlength(pill, font=font(F_BOLD, 22)) + 24
        d.rounded_rectangle([w - 28 - pw, 22, w - 28, 58], radius=18, fill=accent)
        text(d, (w - 28 - pw / 2, 41), pill, 22, bold=True, fill=(255, 255, 255), anchor="mm")
    elif row.get("qty"):
        text(d, (w - 28, h + 72), "core kit x%d" % row["qty"], 24, fill=accent, anchor="ra")
    if scale != 1.0:
        card = card.resize((int(card.width * scale), int(card.height * scale)), Image.LANCZOS)
    return card


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def contact_sheet(title, rows, cols=5, scale=0.5):
    cards = [part_card(r, scale) for r in rows if os.path.exists(os.path.join(RAW, "part-%s.png" % r["id"]))]
    if not cards:
        return None
    cw, ch = cards[0].size
    g = 16
    n_rows = (len(cards) + cols - 1) // cols
    W = cols * cw + (cols + 1) * g
    H = 110 + n_rows * (ch + g) + g
    sheet = background(W, H)
    d = ImageDraw.Draw(sheet)
    text(d, (g + 8, 34), title, 38, bold=True)
    text(d, (W - g - 8, 46), "SemiBlock Junior  |  %d parts" % len(cards), 22, fill=MUTED, anchor="ra")
    for i, c in enumerate(cards):
        x = g + (i % cols) * (cw + g)
        y = 110 + (i // cols) * (ch + g)
        shadow = Image.new("RGBA", (cw + 20, ch + 20), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([10, 12, cw + 10, ch + 10], radius=14, fill=(15, 23, 42, 40))
        sheet.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)), (x - 10, y - 8))
        mask = Image.new("L", c.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw - 1, ch - 1], radius=14, fill=255)
        sheet.paste(c, (x, y), mask)
    return sheet


def main():
    n = 0
    for fn in sorted(os.listdir(RAW)):
        if not fn.endswith(".json") or fn.startswith("part-") or fn.startswith("twistlock-step"):
            continue
        meta = json.load(open(os.path.join(RAW, fn)))
        callout_image(meta).convert("RGB").save(os.path.join(OUT, meta["name"] + ".png"), optimize=True)
        n += 1
    strip = steps_strip()
    if strip:
        strip.convert("RGB").save(os.path.join(OUT, "twistlock-steps.png"), optimize=True)
    catalog = json.load(open(os.path.join(STAGE, "viewer", "catalog.json")))
    for row in catalog:
        if os.path.exists(os.path.join(RAW, "part-%s.png" % row["id"])):
            part_card(row, 0.6).convert("RGB").save(os.path.join(PARTS, row["id"] + ".png"), optimize=True)
            n += 1
    groups = {}
    for row in catalog:
        key = row["family"]
        if row.get("module"):
            key = "Modules - " + {"sense": "Sensing", "env": "Environment & science", "output": "Output",
                                  "connect": "Identify & connect", "ai": "AI & voice", "power": "Power & energy"}[row["module"]["cat"]]
        groups.setdefault(key, []).append(row)
    for title, rows in groups.items():
        sheet = contact_sheet(title, rows)
        if sheet:
            sheet.convert("RGB").save(os.path.join(SHEETS, slug(title) + ".png"), optimize=True)
    print("images:", n, "sheets:", len(groups))


if __name__ == "__main__":
    main()

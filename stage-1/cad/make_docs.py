"""Fill the generated tables in SemiBlock-Junior-Design.md from viewer/catalog.json
and write viewer/catalog.js (the viewer reads the catalogue as a script so it
works from file://).

    python3 stage-1/cad/make_docs.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.dirname(HERE)
DOC = os.path.join(STAGE, "SemiBlock-Junior-Design.md")
CAT = json.load(open(os.path.join(STAGE, "viewer", "catalog.json")))

FAMILY_ORDER = ["Beams", "Connectors", "Pins & bushes", "TwistLock (lock system)", "Axles", "Gears & motion", "Wheels",
                "Accessories & tools", "Hub, motors & cables"]
CAT_ORDER = [("sense", "Sensing (distance, light, touch, motion)"), ("env", "Environment & science"),
             ("ai", "AI & voice"), ("connect", "Identify & connect"), ("output", "Output (light, sound, motion)"),
             ("power", "Power & energy")]
PHASE = {"P1": "P1 launch", "P2": "P2 add-on", "P3": "P3 later"}


def img(pid, w=150):
    return '<img src="renders/parts/%s.png" width="%d" alt="%s">' % (pid, w, pid)


def esc(s):
    return str(s).replace("|", "\\|")


def size(r):
    return " x ".join("%g" % v for v in r["size_mm"])


def catalog_md():
    out = []
    for fam in FAMILY_ORDER:
        rows = [r for r in CAT if r["family"] == fam]
        if not rows:
            continue
        out.append("### %s (%d types)\n" % (fam, len(rows)))
        out.append("| 3D | ID | Part | Size (mm) | Core kit | Notes |")
        out.append("|---|---|---|---|---:|---|")
        for r in rows:
            out.append("| %s | [`%s`](viewer/index.html#part=%s) | %s | %s | %s | %s |" % (
                img(r["id"]), r["id"], r["id"], esc(r["title"]), size(r), r["qty"] or "-", esc(r["note"])))
        out.append("")
    return "\n".join(out)


def modules_md():
    out = []
    mods = [r for r in CAT if r.get("module")]
    for cat, title in CAT_ORDER:
        rows = [r for r in mods if r["module"]["cat"] == cat]
        if not rows:
            continue
        out.append("### %s (%d)\n" % (title, len(rows)))
        out.append("| 3D | ID | Module | 中文 | What it does | Candidate chip | Phase | Replaces (45-in-1 kit) |")
        out.append("|---|---|---|---|---|---|---|---|")
        for r in rows:
            m = r["module"]
            out.append("| %s | [`%s`](viewer/index.html#part=%s) | %s | %s | %s | %s | %s | %s |" % (
                img(r["id"], 120), r["id"], r["id"], esc(r["title"]), m["zh"], esc(m["does"]), esc(m["chip"]),
                PHASE[m["phase"]], esc(m["replaces"]) or "new"))
        out.append("")
    return "\n".join(out)


def kit_md():
    mech = [r for r in CAT if not r.get("module")]
    mods = [r for r in CAT if r.get("module")]
    core_pieces = sum(r["qty"] for r in mech)
    core_mods = [r for r in mods if r["qty"]]
    by_phase = {p: sum(1 for r in mods if r["module"]["phase"] == p) for p in ("P1", "P2", "P3")}
    fam_rows = []
    for fam in FAMILY_ORDER:
        rows = [r for r in mech if r["family"] == fam]
        if rows:
            fam_rows.append("| %s | %d | %d |" % (fam, len(rows), sum(r["qty"] for r in rows)))
    return "\n".join([
        "| Family | Part types | Pieces in Core Set |", "|---|---:|---:|", *fam_rows,
        "| **Mechanical + hub total** | **%d** | **%d** |" % (len(mech), core_pieces),
        "",
        "Smart modules modelled: **%d** (P1 launch %d, P2 add-on %d, P3 later %d). "
        "Core Set includes %d of them: %s." % (len(mods), by_phase["P1"], by_phase["P2"], by_phase["P3"], len(core_mods),
                                              ", ".join(r["title"] for r in core_mods)),
    ])


def inject(text, key, body):
    pat = re.compile(r"(<!-- BEGIN:%s -->\n).*?(<!-- END:%s -->)" % (key, key), re.S)
    if not pat.search(text):
        raise SystemExit("marker %s missing in %s" % (key, DOC))
    return pat.sub(lambda m: m.group(1) + body + "\n" + m.group(2), text)


def main():
    with open(os.path.join(STAGE, "viewer", "catalog.js"), "w") as fh:
        fh.write("window.SB_CATALOG = %s;\n" % json.dumps(CAT, ensure_ascii=False))
    if os.path.exists(DOC):
        text = open(DOC).read()
        for key, fn in (("catalog", catalog_md), ("modules", modules_md), ("kit", kit_md)):
            text = inject(text, key, fn())
        open(DOC, "w").write(text)
        print("tables updated in", os.path.basename(DOC))
    print("catalog.js written (%d parts)" % len(CAT))


if __name__ == "__main__":
    main()

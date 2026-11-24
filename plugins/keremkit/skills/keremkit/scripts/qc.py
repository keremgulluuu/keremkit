#!/usr/bin/env python3
"""KeremKit render QC - check a finished video and pick thumbnail frames (ffmpeg, stdlib only).

  check  RENDER [--target -14] [--black 0.5] [--freeze 1.0] [--silence 2.0]
         black frames, frozen picture, long silences, loudness, true peak, duration
         -> one line per issue with its time, then a verdict
  thumbs RENDER [-n 6] -o DIR
         sharp, representative frames spread over the video, saved as JPG for the user
  ae-postcheck EXPORT.json [--comp NAME] [--samples S.json] [--palette "#hex,..." | --style SLUG]
         [--bounds B.json --min-gap PX --edge PX --size WxH] [--subject SUBJ.json]
         [--max-depth 2] [--allow-nested LIB_]
         measured gate before an AE build is called done (references/qc.md "AE postcheck"):
         FAIL banned SFX in the project, heavy effects outside HVY_ comps (optimize.mode on),
              keys on an element's own transform incl. opacity (only NULL_/CTRL_/ADJ_/CAM_/LGT_ may be keyed),
              layer colour label None, comp nesting deeper than --max-depth (insides of LIB_ comps are free);
         WARN HVY_ comp fps != optimize.heavy_fps, label != organize.labels for its prefix, parent that is not
              a NULL_/CTRL_ rig, sampled colours far from the palette, overlaps / gaps below the minimum /
              too close to the edge, an element covering the subject box (SUBJ.json = [{"t","box":[l,t,r,b]}]).
         EXPORT = ae_project_export_json(outPath=...). S.json = [{"layer","rgb":[r,g,b] 0-1 or 0-255}],
         B.json = [{"layer","left","top","width","height"} or {"layer","box":[l,t,r,b]}] at the rest frame.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys

HEAVY_FX = re.compile(r"ADBE Glo2|PEDG|Deep ?Glow|CC Force Motion Blur|RSMB|RE:Vision|ReelSmart|ADBE Displacement Map|"
                      r"ADBE Turbulent Displace|CC Glass|ADBE Fractal Noise|ADBE Echo|Pixel Motion Blur|Keylight|"
                      r"VIDEOCOPILOT 3DArray|tc Particular|Trapcode|ADBE Camera Lens Blur|Optical Flares|"
                      r"Saber|S_Glow|Sapphire", re.I)
RIG_PREFIX = ("NULL_", "CTRL_", "ADJ_", "CAM_", "LGT_")
OWN_TRANSFORM = {"ADBE Position", "ADBE Position_0", "ADBE Position_1", "ADBE Position_2", "ADBE Scale",
                 "ADBE Rotate Z", "ADBE Rotate X", "ADBE Rotate Y", "ADBE Orientation", "ADBE Anchor Point",
                 "ADBE Opacity"}


def run(args):
    if not shutil.which("ffmpeg"):
        sys.exit("ERROR: ffmpeg not found")
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True)


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def mmss(t):
    m, s = divmod(max(0.0, float(t)), 60)
    return f"{int(m):02d}:{s:04.1f}"


def cmd_check(a):
    issues = []
    dur = duration(a.render)
    r = run(["-i", a.render, "-vf", f"blackdetect=d={a.black}:pix_th=0.10,freezedetect=n=0.003:d={a.freeze}",
             "-af", f"silencedetect=noise=-50dB:d={a.silence},loudnorm=I={a.target}:TP=-1:LRA=11:print_format=json",
             "-f", "null", "-"])
    err = r.stderr or ""
    for s, e in re.findall(r"black_start:([\d.]+)\s+black_end:([\d.]+)", err):
        issues.append(f"BLACK {mmss(s)}-{mmss(e)}")
    fs = re.findall(r"freeze_start:\s*([\d.]+)", err)
    fe = re.findall(r"freeze_end:\s*([\d.]+)", err)
    for i, s in enumerate(fs):
        issues.append(f"FROZEN {mmss(s)}-{mmss(fe[i]) if i < len(fe) else 'end'}")
    ss = re.findall(r"silence_start:\s*([\d.]+)", err)
    se = re.findall(r"silence_end:\s*([\d.]+)", err)
    for i, s in enumerate(ss):
        issues.append(f"SILENCE {mmss(s)}-{mmss(se[i]) if i < len(se) else 'end'}")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    if m:
        ld = json.loads(m.group(0))
        i, tp = float(ld["input_i"]), float(ld["input_tp"])
        if abs(i - a.target) > 1:
            issues.append(f"LOUDNESS {i:.1f} LUFS (target {a.target:g})")
        if tp > -1:
            issues.append(f"TRUE_PEAK {tp:.1f} dBTP (above -1, may clip)")
        loud = f"LUFS={i:.1f} TP={tp:.1f}"
    else:
        loud = "LUFS=? (no audio)"
    for x in issues:
        print(x)
    print(f"{'OK' if not issues else 'ISSUES=' + str(len(issues))} duration={dur and round(dur, 2)}s {loud}")


def cmd_thumbs(a):
    dur = duration(a.render)
    if not dur:
        sys.exit("ERROR: cannot read duration")
    os.makedirs(a.output, exist_ok=True)
    paths = []
    for k in range(a.n):
        t = dur * (k + 0.5) / a.n
        out = os.path.join(a.output, f"thumb_{k + 1:02d}_{mmss(t).replace(':', 'm')}.jpg")
        # thumbnail filter picks the most representative frame of the next ~60 frames
        r = run(["-y", "-ss", f"{max(0.0, t - 1):.2f}", "-i", a.render, "-vf", "thumbnail=60", "-frames:v", "1",
                 "-q:v", "2", out])
        if r.returncode == 0 and os.path.exists(out):
            paths.append(out)
    print(f"OK thumbs={len(paths)} -> {a.output}")


# ---------------------------------------------------------------- AE postcheck
def home_dir(override=None):
    if override:
        return override
    try:
        with open(os.path.join(os.path.expanduser("~"), ".keremkit.json"), encoding="utf-8") as f:
            h = json.load(f).get("home")
        if h:
            return h
    except (OSError, ValueError):
        pass
    return os.path.join(os.path.expanduser("~"), "Documents", "KeremKit")


def rjson(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def hex_rgb(h):
    h = h.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        return None
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def to_unit(rgb):
    v = [float(x) for x in rgb[:3]]
    return [x / 255 for x in v] if max(v) > 1.0 else v


def lab(rgb):
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [lin(c) for c in rgb]
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a, b):
    return math.dist(lab(a), lab(b))


def style_palette(home, slug):
    st = rjson(os.path.join(home, "styles", slug, "style.json"), {}) or {}
    out = []

    def walk(n):
        if isinstance(n, dict):
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
        elif isinstance(n, str):
            for h in re.findall(r"#[0-9a-fA-F]{6}\b", n):
                out.append(h)
    walk((st.get("look") or {}).get("palette") or st.get("look") or {})
    return list(dict.fromkeys(out))


def box_of(b):
    if "box" in b:
        return [float(x) for x in b["box"][:4]]
    l, t = float(b.get("left", 0)), float(b.get("top", 0))
    return [l, t, l + float(b.get("width", 0)), t + float(b.get("height", 0))]


def cmd_postcheck(a):
    home = home_dir(a.home)
    prefs = rjson(os.path.join(home, "settings", "preferences.json"), {}) or {}
    data = rjson(a.export)
    if data is None:
        sys.exit(f"ERROR: cannot read {a.export}")
    items = data.get("items") or []
    by_id = {i.get("id"): i for i in items if isinstance(i, dict)}
    comps = {i["id"]: i for i in items if isinstance(i, dict) and i.get("type") == "CompItem"}
    fails, warns = [], []

    def children(cid):
        return {L.get("sourceId") for L in comps[cid].get("layers") or [] if L.get("sourceId") in comps}

    def reach(roots):
        seen, todo = set(), list(roots)
        while todo:
            c = todo.pop()
            if c in seen:
                continue
            seen.add(c)
            todo += list(children(c))
        return seen

    scope = set(comps)
    if a.comp:
        root = [c for c, v in comps.items() if v.get("name") == a.comp]
        if not root:
            sys.exit(f"ERROR: comp '{a.comp}' not found")
        scope = reach(root)
    used = {L.get("sourceId") for c in scope for L in comps[c].get("layers") or []}

    # 1. banned SFX
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import sfx  # noqa: E402  (sibling kit tool: banned list)
    banned = sfx.banned_list(home)
    for i in items:
        f = (i or {}).get("file") or (i or {}).get("missingFootagePath")
        if i.get("type") == "FootageItem" and f and sfx.is_banned(f, banned):
            fails.append(f"BANNED_SFX {os.path.basename(f)} (item '{i.get('name')}'{', used' if i.get('id') in used else ', unused - remove it'})")

    # 2. heavy effects outside HVY_ comps
    opt = prefs.get("optimize") or {}
    hvy = reach([c for c, v in comps.items() if str(v.get("name", "")).startswith("HVY_")])
    if opt.get("mode", "on") == "on":
        for c in sorted(scope - hvy):
            for L in comps[c].get("layers") or []:
                fx = [g.get("name") or g.get("matchName") for g in ((L.get("effectsGroup") or {}).get("groups") or [])
                      if HEAVY_FX.search(f"{g.get('matchName', '')} {g.get('name', '')}")]
                if fx and L.get("enabled", True):
                    fails.append(f"HEAVY_OUTSIDE_HVY {comps[c].get('name')} / {L.get('name')}: {', '.join(fx)} "
                                 f"-> HVY_ precomp at {opt.get('heavy_fps', 30)} fps (optimization.md §1-2)")
    for c in hvy & scope:
        v = comps[c]
        if str(v.get("name", "")).startswith("HVY_") and v.get("frameRate") and opt.get("heavy_fps") \
                and abs(float(v["frameRate"]) - float(opt["heavy_fps"])) > 0.01:
            warns.append(f"HVY_FPS {v.get('name')} runs at {v['frameRate']} fps, optimize.heavy_fps={opt['heavy_fps']}")

    # 4. GOLDEN RULE 1: keys on an element's own transform (FAIL; rig = NULL_/CTRL_ null, ADJ_, Transform effect)
    if (prefs.get("motion") or {}).get("transform_rig", "parent_null") != "direct":
        for c in sorted(scope):
            for L in comps[c].get("layers") or []:
                n = str(L.get("name", ""))
                if n.startswith(RIG_PREFIX) or L.get("type") in ("CameraLayer", "LightLayer"):
                    continue
                keyed = [p.get("name") or p.get("matchName") for p in ((L.get("transformGroup") or {}).get("properties") or [])
                         if p.get("matchName") in OWN_TRANSFORM and p.get("keyframes")]
                if keyed:
                    fails.append(f"OWN_TRANSFORM_KEYS {comps[c].get('name')} / {n}: {', '.join(keyed)} "
                                 "-> move the keys to a NULL_/CTRL_ parent, an ADJ_ layer or an extra Transform effect")

    # 6. GOLDEN RULE 3: every layer has a colour label (FAIL on None, WARN on a label that differs from organize.labels)
    labels = {str(k).upper(): v for k, v in ((prefs.get("organize") or {}).get("labels") or {}).items()}
    for c in sorted(scope):
        for L in comps[c].get("layers") or []:
            n = str(L.get("name", ""))
            lab_ = L.get("label")
            if lab_ is None:
                continue
            if int(lab_) == 0:
                fails.append(f"LABEL_NONE {comps[c].get('name')} / {n} -> label from organize.labels")
                continue
            pre = n.split("_", 1)[0].upper() if "_" in n else ""
            if pre in labels and labels[pre] is not None and int(labels[pre]) != int(lab_):
                warns.append(f"LABEL {comps[c].get('name')} / {n} is {lab_}, organize.labels[{pre}]={labels[pre]}")

    # 7. GOLDEN RULE 2: no needless nesting (FAIL depth > max), parents only on rig nulls (WARN)
    allow = tuple(p for p in (a.allow_nested or "").split(",") if p)
    free = reach([c for c in comps if allow and str(comps[c].get("name", "")).startswith(allow)])
    roots = [c for c in scope if not any(c in children(p) for p in scope)] if not a.comp else \
        [c for c, v in comps.items() if v.get("name") == a.comp]
    depth = {}
    todo = [(r, 1, (r,)) for r in roots]
    while todo:
        cid, d, path = todo.pop()
        if depth.get(cid, 0) >= d:
            continue
        depth[cid] = d
        for ch in children(cid):
            if ch not in path:
                todo.append((ch, d + 1, path + (ch,)))
    for cid, d in sorted(depth.items(), key=lambda x: -x[1]):
        if d > a.max_depth and cid not in free:
            fails.append(f"NESTED_DEPTH {comps[cid].get('name')} is {d} levels deep (max {a.max_depth}: main -> one precomp) "
                         "-> put its layers in the parent comp")
    for c in sorted(scope):
        lays = comps[c].get("layers") or []
        by_idx = {L.get("index"): L for L in lays}
        for L in lays:
            p = by_idx.get(L.get("parentIndex")) if L.get("parentIndex") else None
            if p is not None and not str(p.get("name", "")).startswith(("NULL_", "CTRL_")):
                warns.append(f"PARENT {comps[c].get('name')} / {L.get('name')} -> parent '{p.get('name')}' is not a NULL_/CTRL_ rig")

    # 3. sampled colours vs palette
    if a.samples:
        pal = [hex_rgb(h) for h in (a.palette.split(",") if a.palette else style_palette(home, a.style) if a.style else [])]
        pal = [p for p in pal if p]
        if not pal:
            warns.append("COLOUR no palette (pass --palette or --style with look.palette) - colours not checked")
        for s in rjson(a.samples, []) or []:
            if not s.get("rgb"):
                continue
            c = to_unit(s["rgb"])
            d = min(delta_e(c, p) for p in pal) if pal else 0
            if pal and d > a.max_de:
                h = "#%02X%02X%02X" % tuple(round(x * 255) for x in c)
                warns.append(f"COLOUR {s.get('layer')} measured {h}, nearest palette colour dE={d:.0f} (> {a.max_de:g})")

    # 5. spacing
    if a.bounds:
        bx = [(b.get("layer"), box_of(b)) for b in (rjson(a.bounds, []) or [])]
        for i in range(len(bx)):
            for j in range(i + 1, len(bx)):
                (n1, p), (n2, q) = bx[i], bx[j]
                ox, oy = min(p[2], q[2]) - max(p[0], q[0]), min(p[3], q[3]) - max(p[1], q[1])
                inside = (p[0] <= q[0] and p[1] <= q[1] and p[2] >= q[2] and p[3] >= q[3]) or \
                         (q[0] <= p[0] and q[1] <= p[1] and q[2] >= p[2] and q[3] >= p[3])
                if ox > 0 and oy > 0 and not inside:
                    warns.append(f"OVERLAP {n1} x {n2} ({ox:.0f}x{oy:.0f} px)")
                elif a.min_gap and not inside:
                    gap = max(-ox, -oy)
                    if 0 <= gap < a.min_gap:
                        warns.append(f"GAP {n1} - {n2} {gap:.0f} px (< {a.min_gap:g})")
        if a.subject:
            for s in rjson(a.subject, []) or []:
                sb = box_of(s)
                for n, p in bx:
                    ox, oy = min(p[2], sb[2]) - max(p[0], sb[0]), min(p[3], sb[3]) - max(p[1], sb[1])
                    area = max((p[2] - p[0]) * (p[3] - p[1]), 1.0)
                    if ox > 0 and oy > 0 and ox * oy / area > a.subject_max:
                        at = f" at {s['t']}s" if s.get("t") is not None else ""
                        warns.append(f"SUBJECT {n} covers the subject{at} ({ox * oy / area:.0%} of the element) "
                                     "-> move it to a free zone or note 'covers subject on purpose'")
        if a.edge and a.size:
            w, h = [float(x) for x in a.size.lower().split("x")]
            for n, p in bx:
                m = min(p[0], p[1], w - p[2], h - p[3])
                if m < a.edge:
                    warns.append(f"EDGE {n} {m:.0f} px from the frame edge (< {a.edge:g})")

    for tag, lst in (("FAIL", fails), ("WARN", warns)):
        if len(lst) > a.max_lines:
            cnt = {}
            for x in lst:
                cnt[x.split(" ", 1)[0]] = cnt.get(x.split(" ", 1)[0], 0) + 1
            print(f"{tag}S by check: " + ", ".join(f"{k}={v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])))
        for x in lst[:a.max_lines]:
            print(f"{tag} {x}")
        if len(lst) > a.max_lines:
            print(f"{tag} ... {len(lst) - a.max_lines} more (--max-lines to see them)")
    print(f"POSTCHECK {'FAIL' if fails else 'OK'} fail={len(fails)} warn={len(warns)} comps={len(scope)}"
          + ("" if fails else " (OK = nothing measured failed; WARN lines still go to the user)"))
    if fails:
        sys.exit(1)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("check")
    c.add_argument("render")
    c.add_argument("--target", type=float, default=-14.0)
    c.add_argument("--black", type=float, default=0.5)
    c.add_argument("--freeze", type=float, default=1.0)
    c.add_argument("--silence", type=float, default=2.0)
    t = sp.add_parser("thumbs")
    t.add_argument("render")
    t.add_argument("-n", type=int, default=6)
    t.add_argument("-o", "--output", required=True)
    pc = sp.add_parser("ae-postcheck")
    pc.add_argument("export")
    pc.add_argument("--comp", help="check this comp and everything nested in it (default: all comps)")
    pc.add_argument("--samples")
    pc.add_argument("--palette")
    pc.add_argument("--style")
    pc.add_argument("--max-de", type=float, default=12.0, help="colour distance that counts as off-palette")
    pc.add_argument("--bounds")
    pc.add_argument("--min-gap", type=float, default=0.0)
    pc.add_argument("--edge", type=float, default=0.0)
    pc.add_argument("--size", help="comp size WxH for --edge")
    pc.add_argument("--max-lines", type=int, default=15, help="lines printed per FAIL/WARN list")
    pc.add_argument("--max-depth", type=int, default=2, help="comp nesting levels allowed (main=1)")
    pc.add_argument("--allow-nested", default="LIB_", help="comma list of comp name prefixes whose insides may nest")
    pc.add_argument("--subject", help="subject boxes JSON [{t?, box:[l,t,r,b]}] - WARN when --bounds overlap it")
    pc.add_argument("--subject-max", type=float, default=0.25, help="share of an element box that may cover the subject")
    pc.add_argument("--home")
    a = ap.parse_args()
    {"check": cmd_check, "thumbs": cmd_thumbs, "ae-postcheck": cmd_postcheck}[a.cmd](a)


if __name__ == "__main__":
    main()

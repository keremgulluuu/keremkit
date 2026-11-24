#!/usr/bin/env python3
"""Storyboard preview - scenes and transitions as one HTML player, before anything is built in AE.

  new   -o scenes.json [--title T] [--parts "Intro: ..." ...] [--scenes N] [--dur S]
        [--format 16x9|9x16|1x1] [--size WxH] [--fps F] [--style SLUG] [--home H]
                                             a scene list skeleton: comp size, fps, colours, fonts and layout
                                             tokens from the style / preferences; one scene per part
  check scenes.json                          validate: fields, timing, the fixed vocabulary; ERR / WARN lines
  build scenes.json [-o out.html] [--lang en|tr]
                                             check, then write one self-contained HTML player (no internet):
                                             play / pause, scrub, scene list, loop a scene or a transition,
                                             safe areas, layer names
  vocab                                      the layer types, animations, transitions and easings in a few lines

Claude writes only scenes.json; the user opens the HTML in a browser. Nothing here renders frames for
Claude to look at. The approved scenes.json is the plan the AE build follows (references/storyboard.md).
"""
import argparse
import json
import os
import re
import sys

LAYER_TYPES = {
    "text": ("text",),
    "box": ("w", "h"),
    "circle": ("r",),
    "line": ("x1", "y1", "x2", "y2"),
    "image": ("w", "h"),
    "counter": ("to",),
    "subject": ("box",),
    "footage": (),
}
ANIMS = ("fade", "slide-up", "slide-down", "slide-left", "slide-right", "scale-in", "pop", "blur-in",
         "wipe-left", "wipe-right", "wipe-up", "wipe-down", "mask-reveal", "typewriter", "count-up")
TRANSITIONS = ("cut", "crossfade", "push", "slide", "zoom", "blur", "whip", "flash", "dip", "wipe")
DIRECTED = ("push", "slide", "whip", "wipe")
DIRS = ("left", "right", "up", "down")
EASES = ("linear", "easeIn", "easeOut", "easeInOut", "easyEase", "easyEaseIn", "easyEaseOut",
         "cubicOut", "quartOut", "expoIn", "expoOut", "expoInOut", "backIn", "backOut")
KEY_PROPS = ("x", "y", "scale", "rot", "opacity")
CSS_NAMES = {"white", "black", "transparent", "red", "green", "blue", "yellow", "orange", "purple", "gray", "grey"}
DEFAULT_COMP = {"16x9": [1920, 1080, 30], "9x16": [1080, 1920, 30], "1x1": [1080, 1080, 30]}


def rjson(p, default=None):
    if p and os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return default


def home_dir(override):
    if override:
        return os.path.abspath(override)
    ptr = rjson(os.path.join(os.path.expanduser("~"), ".keremkit.json"), {})
    return ptr.get("home") or os.path.join(os.path.expanduser("~"), "Documents", "KeremKit")


def to_hex(v):
    """Palette value -> #rrggbb: [r,g,b] in 0-1 or 0-255, or a string kept as is."""
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)) and len(v) >= 3 and all(isinstance(c, (int, float)) for c in v[:3]):
        scale = 255 if max(v[:3]) <= 1 else 1
        return "#" + "".join(f"{max(0, min(255, round(c * scale))):02x}" for c in v[:3])
    return None


def slug(text, i):
    s = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:24]
    return s or f"S{i}"


# ---------------------------------------------------------------- new
def cmd_new(a):
    h = home_dir(a.home)
    prefs = rjson(os.path.join(h, "settings", "preferences.json"), {}) or {}
    comps = dict(DEFAULT_COMP)
    comps.update(((prefs.get("standards") or {}).get("default_comp")) or {})
    w, hh, fps = comps.get(a.format, DEFAULT_COMP["16x9"])
    tokens = {"colors": {"bg": "#101014", "text": "#ffffff", "accent": "#ffc800"}, "fonts": {}, "layout": {}}
    if a.style:
        st = rjson(os.path.join(h, "styles", a.style, "style.json"))
        if st is None:
            sys.exit(f"ERROR: style '{a.style}' not found in {os.path.join(h, 'styles')}")
        look = st.get("look") or {}
        for k, v in (look.get("palette") or {}).items():
            hx = to_hex(v)
            if hx:
                tokens["colors"][k] = hx
        for f in look.get("fonts") or []:
            if isinstance(f, dict) and f.get("font"):
                tokens["fonts"][slug(str(f.get("use") or "font"), 0).lower()] = f["font"]
        tokens["layout"] = st.get("layout") or look.get("layout") or {}
    if a.size:
        m = re.match(r"^(\d+)x(\d+)$", a.size)
        if not m:
            sys.exit("ERROR: --size must look like 1080x1920")
        w, hh = int(m.group(1)), int(m.group(2))
    if a.fps:
        fps = a.fps
    parts = a.parts or [f"Scene {i}" for i in range(1, a.scenes + 1)]
    font = next(iter(tokens["fonts"]), None)
    scenes = []
    for i, p in enumerate(parts, 1):
        name = p.split(":", 1)[0].strip() or f"Scene {i}"
        note = p.split(":", 1)[1].strip() if ":" in p else ""
        title = {"id": "TXT_Title", "type": "text", "text": note or name, "x": w // 2, "y": hh // 2,
                 "size": round(min(w, hh) * 0.07), "color": "text", "align": "center",
                 "in": {"anim": "slide-up", "t": 0.1, "dur": 0.5, "ease": "expoOut"}}
        if font:
            title["font"] = font
        sc = {"id": f"S{i}", "name": name, "dur": a.dur, "bg": "bg", "note": note, "layers": [title]}
        if i < len(parts):
            sc["transition"] = {"type": "crossfade", "dur": 0.4, "ease": "easyEase"}
        scenes.append(sc)
    data = {"kind": "keremkit-storyboard", "version": 1, "title": a.title or "Storyboard",
            "comp": {"w": w, "h": hh, "fps": fps}, "tokens": tokens,
            "safe": (prefs.get("standards") or {}).get("safe_area") or {"action": 0.93, "title": 0.90},
            "scenes": scenes}
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    if os.path.exists(a.output) and not a.overwrite:
        sys.exit(f"ERROR: {a.output} exists (use --overwrite)")
    with open(a.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"OK -> {a.output} scenes={len(scenes)} comp={w}x{hh}@{fps} colors={len(tokens['colors'])} "
          f"fonts={len(tokens['fonts'])}")


# ---------------------------------------------------------------- check
def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def ease_ok(e):
    return e is None or e in EASES or (isinstance(e, list) and len(e) == 4 and all(num(x) for x in e))


def validate(d):
    errs, warns = [], []
    if not isinstance(d, dict) or not isinstance(d.get("scenes"), list) or not d["scenes"]:
        return ["ERR file: needs a non-empty \"scenes\" list"], [], 0.0
    c = d.get("comp") or {}
    for k in ("w", "h", "fps"):
        if not num(c.get(k)) or c.get(k) <= 0:
            errs.append(f"ERR comp.{k}: must be a positive number")
    W, H = (c.get("w") or 0), (c.get("h") or 0)
    tok = d.get("tokens") or {}
    colors = set((tok.get("colors") or {}).keys())

    def color(where, v):
        if v is None or not isinstance(v, str):
            if v is not None:
                errs.append(f"ERR {where}: colour must be a string")
            return
        if v in colors or v.startswith(("#", "rgb", "hsl", "linear-gradient", "radial-gradient")) or v in CSS_NAMES:
            return
        warns.append(f"WARN {where}: colour '{v}' is not a token ({', '.join(sorted(colors)) or 'none'}) or #hex")

    def anim(where, x, sdur):
        if x is None:
            return
        if not isinstance(x, dict):
            errs.append(f"ERR {where}: must be an object {{anim, t, dur, ease}}")
            return
        if x.get("anim") not in ANIMS:
            errs.append(f"ERR {where}: unknown anim '{x.get('anim')}' (known: {', '.join(ANIMS)})")
        for k in ("t", "dur"):
            if k in x and (not num(x[k]) or x[k] < 0):
                errs.append(f"ERR {where}.{k}: must be a number >= 0")
        if not ease_ok(x.get("ease")):
            errs.append(f"ERR {where}.ease: unknown '{x.get('ease')}' (known: {', '.join(EASES)} or [x1,y1,x2,y2])")
        end = (x.get("t") or 0) + (x.get("dur") if num(x.get("dur")) else 0.5)
        if num(sdur) and end > sdur + 1e-6:
            warns.append(f"WARN {where}: ends at {end:.2f}s, after the scene ({sdur}s)")

    total, ids = 0.0, set()
    sc_list = d["scenes"]
    for si, s in enumerate(sc_list):
        sid = s.get("id") or f"#{si + 1}"
        if sid in ids:
            errs.append(f"ERR {sid}: duplicate scene id")
        ids.add(sid)
        dur = s.get("dur")
        if not num(dur) or dur <= 0:
            errs.append(f"ERR {sid}.dur: must be a number > 0")
            dur = None
        else:
            total += dur
        color(f"{sid}.bg", s.get("bg"))
        lids = set()
        for li, L in enumerate(s.get("layers") or []):
            lid = f"{sid}/{L.get('id') or '#' + str(li + 1)}"
            if L.get("id") in lids:
                errs.append(f"ERR {lid}: duplicate layer id in the scene")
            lids.add(L.get("id"))
            t = L.get("type")
            if t not in LAYER_TYPES:
                errs.append(f"ERR {lid}: unknown type '{t}' (known: {', '.join(LAYER_TYPES)})")
                continue
            for k in LAYER_TYPES[t]:
                if k not in L:
                    errs.append(f"ERR {lid}: type {t} needs '{k}'")
            for k in ("x", "y", "w", "h", "r", "size", "x1", "y1", "x2", "y2", "scale", "rot", "opacity",
                      "start", "end", "from", "to"):
                if k in L and not num(L[k]):
                    errs.append(f"ERR {lid}.{k}: must be a number")
            if t == "subject" and not (isinstance(L.get("box"), list) and len(L["box"]) == 4
                                       and all(num(v) for v in L["box"])):
                errs.append(f"ERR {lid}.box: [left, top, right, bottom] in comp pixels")
            for k in ("color", "fill", "bg"):
                color(f"{lid}.{k}", L.get(k))
            if isinstance(L.get("stroke"), dict):
                color(f"{lid}.stroke.color", L["stroke"].get("color"))
            anim(f"{lid}.in", L.get("in"), dur)
            anim(f"{lid}.out", L.get("out"), dur)
            for ax in ("in", "out"):
                x = L.get(ax) or {}
                if x.get("anim") == "count-up" and t != "counter":
                    errs.append(f"ERR {lid}.{ax}: count-up is for counter layers")
                if x.get("anim") == "typewriter" and t not in ("text", "counter"):
                    errs.append(f"ERR {lid}.{ax}: typewriter is for text layers")
            keys = L.get("keys")
            if keys is not None:
                if not isinstance(keys, list):
                    errs.append(f"ERR {lid}.keys: must be a list of {{t, x, y, scale, rot, opacity, ease}}")
                else:
                    last = -1
                    for ki, k in enumerate(keys):
                        if not isinstance(k, dict) or not num(k.get("t")):
                            errs.append(f"ERR {lid}.keys[{ki}]: needs a time 't'")
                            continue
                        if k["t"] < last:
                            errs.append(f"ERR {lid}.keys[{ki}]: times must go up")
                        last = k["t"]
                        if not any(p in k for p in KEY_PROPS):
                            warns.append(f"WARN {lid}.keys[{ki}]: sets none of {', '.join(KEY_PROPS)}")
                        if not ease_ok(k.get("ease")):
                            errs.append(f"ERR {lid}.keys[{ki}].ease: unknown '{k.get('ease')}'")
            if num(L.get("x")) and num(L.get("y")) and W and H and not (0 <= L["x"] <= W and 0 <= L["y"] <= H):
                warns.append(f"WARN {lid}: centre ({L['x']}, {L['y']}) is outside the {W}x{H} comp")
        tr = s.get("transition")
        if tr is not None:
            if si == len(sc_list) - 1:
                warns.append(f"WARN {sid}.transition: last scene - ignored")
            elif not isinstance(tr, dict) or tr.get("type") not in TRANSITIONS:
                errs.append(f"ERR {sid}.transition: unknown type '{(tr or {}).get('type')}' "
                            f"(known: {', '.join(TRANSITIONS)})")
            else:
                td = tr.get("dur", 0.4 if tr["type"] != "cut" else 0)
                nxt = sc_list[si + 1].get("dur")
                if not num(td) or td < 0:
                    errs.append(f"ERR {sid}.transition.dur: must be a number >= 0")
                elif num(dur) and num(nxt) and td > min(dur, nxt):
                    errs.append(f"ERR {sid}.transition.dur: {td}s is longer than a scene it joins")
                if tr["type"] in DIRECTED and tr.get("dir", "left") not in DIRS:
                    errs.append(f"ERR {sid}.transition.dir: one of {', '.join(DIRS)}")
                if not ease_ok(tr.get("ease")):
                    errs.append(f"ERR {sid}.transition.ease: unknown '{tr.get('ease')}'")
                color(f"{sid}.transition.color", tr.get("color"))
    return errs, warns, total


def summary(d, total):
    nl = sum(len(s.get("layers") or []) for s in d.get("scenes") or [])
    nt = sum(1 for s in (d.get("scenes") or [])[:-1] if s.get("transition"))
    return f"scenes={len(d.get('scenes') or [])} layers={nl} transitions={nt} duration={total:.2f}s"


def load(path):
    try:
        return rjson(path)
    except json.JSONDecodeError as e:
        sys.exit(f"ERR json: {e}")


def cmd_check(a):
    d = load(a.file)
    if d is None:
        sys.exit(f"ERROR: {a.file} not found")
    errs, warns, total = validate(d)
    for x in errs + warns:
        print(x)
    print(("FAIL" if errs else "OK") + f" errors={len(errs)} warnings={len(warns)} " + summary(d, total))
    sys.exit(1 if errs else 0)


# ---------------------------------------------------------------- build
def cmd_build(a):
    d = load(a.file)
    if d is None:
        sys.exit(f"ERROR: {a.file} not found")
    errs, warns, total = validate(d)
    for x in errs + warns:
        print(x)
    if errs:
        print(f"FAIL errors={len(errs)} - nothing written")
        sys.exit(1)
    base = os.path.dirname(os.path.abspath(a.file))
    for s in d["scenes"]:
        for L in s.get("layers") or []:
            src = L.get("src")
            if src and not re.match(r"^(https?:|data:|file:)", src):
                p = src if os.path.isabs(src) else os.path.join(base, src)
                L["src"] = "file:///" + os.path.abspath(p).replace("\\", "/").lstrip("/")
    blob = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    html = PLAYER.replace("__TITLE__", _esc(str(d.get("title") or "Storyboard"))) \
                 .replace("__LANG__", a.lang).replace("__DATA__", blob)
    out = a.output or os.path.splitext(os.path.abspath(a.file))[0] + ".html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK -> {out} ({os.path.getsize(out)} bytes) warnings={len(warns)} " + summary(d, total))


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cmd_vocab(a):
    print("LAYERS " + " | ".join(f"{t}({', '.join(r) or '-'})" for t, r in LAYER_TYPES.items())
          + "  common: id x y (centre, comp px) scale rot opacity start end color font size in out keys; "
            "layers[0] = top (AE layer 1)")
    print("ANIMS " + " ".join(ANIMS) + "  (in/out: {anim, t, dur, ease, dist})")
    print("TRANSITIONS " + " ".join(TRANSITIONS) + f"  (centred on the cut; dir {'/'.join(DIRS)} for "
          + "/".join(DIRECTED) + "; dip/flash: color)")
    print("EASES " + " ".join(EASES) + " or [x1,y1,x2,y2]")
    print("KEYS [{t, x, y, scale, rot, opacity, ease}] - eased into each key from the previous one")


# ---------------------------------------------------------------- player
PLAYER = r"""<!doctype html>
<html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--ui:#16161b;--ui2:#22222a;--line:#34343f;--txt:#e9e9ee;--dim:#9a9aa8;--acc:#ffc800}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#0b0b0e;color:var(--txt);font:13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
#app{display:grid;grid-template-columns:1fr 260px;grid-template-rows:auto 1fr auto;height:100vh}
header{grid-column:1/3;display:flex;gap:12px;align-items:center;padding:8px 14px;background:var(--ui);border-bottom:1px solid var(--line)}
header b{font-size:14px}header span{color:var(--dim)}
#view{position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center}
#fit{position:absolute;left:0;top:0;transform-origin:0 0}
#stage{position:relative;overflow:hidden;background:#000;box-shadow:0 0 0 1px var(--line)}
.scene{position:absolute;left:0;top:0;overflow:hidden;display:none}
.L{position:absolute;left:0;top:0;transform-origin:50% 50%;will-change:transform,opacity}
.Li{position:relative;width:100%;height:100%}
.ph{display:flex;align-items:center;justify-content:center;border:3px dashed rgba(255,255,255,.35);color:rgba(255,255,255,.6);font:600 28px system-ui;background:repeating-linear-gradient(45deg,rgba(255,255,255,.04) 0 20px,rgba(255,255,255,.08) 20px 40px)}
.tag{position:absolute;left:0;top:-22px;font:600 13px system-ui;color:#000;background:var(--acc);padding:1px 6px;border-radius:4px;white-space:nowrap;display:none}
.names .tag{display:block}
#over{position:absolute;inset:0;pointer-events:none}
.safe{position:absolute;border:2px dashed rgba(0,255,170,.55);display:none}.showsafe .safe{display:block}
.grid{position:absolute;inset:0;display:none;background-image:linear-gradient(rgba(255,255,255,.12) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.12) 1px,transparent 1px)}.showgrid .grid{display:block}
#flashL{position:absolute;inset:0;pointer-events:none;opacity:0}
aside{background:var(--ui);border-left:1px solid var(--line);overflow:auto;padding:10px}
aside h3{margin:6px 0 8px;font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.06em}
.sc{padding:8px 10px;border:1px solid var(--line);border-radius:8px;margin-bottom:6px;cursor:pointer;background:var(--ui2)}
.sc.on{border-color:var(--acc)}.sc small{color:var(--dim);display:block}.sc .tr{color:var(--acc);font-size:11px;margin-top:3px}
footer{grid-column:1/3;background:var(--ui);border-top:1px solid var(--line);padding:8px 14px;display:flex;flex-direction:column;gap:6px}
#bar{position:relative;height:34px;background:var(--ui2);border-radius:6px;cursor:pointer;user-select:none}
.seg{position:absolute;top:0;bottom:0;border-right:1px solid #0b0b0e;overflow:hidden;padding:3px 6px;font-size:11px;color:var(--dim);white-space:nowrap}
.seg.on{background:rgba(255,200,0,.12);color:var(--txt)}
.trm{position:absolute;top:0;bottom:0;background:rgba(255,200,0,.28)}
#head{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--acc);pointer-events:none}
#loopR{position:absolute;top:0;bottom:0;border:1px solid var(--acc);background:rgba(255,200,0,.06);pointer-events:none;display:none}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
button,select{background:var(--ui2);color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:5px 10px;font:inherit;cursor:pointer}
button.on{border-color:var(--acc);color:var(--acc)}#time{font-variant-numeric:tabular-nums;min-width:200px}
#note{color:var(--dim)}kbd{background:var(--ui2);border:1px solid var(--line);border-radius:3px;padding:0 4px;font-size:11px}
</style></head><body>
<div id="app">
<header><b id="ttl"></b><span id="meta"></span></header>
<div id="view"><div id="fit"><div id="stage"><div id="flashL"></div><div id="over"><div class="grid"></div><div class="safe" id="safeA"></div><div class="safe" id="safeT"></div></div></div></div></div>
<aside><h3 id="hScenes"></h3><div id="list"></div><h3 id="hNote"></h3><div id="note"></div><h3 id="hKeys"></h3><div id="keys" style="color:var(--dim);font-size:12px"></div></aside>
<footer>
<div id="bar"><div id="loopR"></div><div id="head"></div></div>
<div class="row">
<button id="play">&#9654;</button><span id="time"></span>
<select id="loop"></select><select id="speed"><option value="0.25">0.25x</option><option value="0.5">0.5x</option><option value="1" selected>1x</option></select>
<button id="bSafe"></button><button id="bGrid"></button><button id="bNames"></button>
</div></footer></div>
<script type="application/json" id="kk-data">__DATA__</script>
<script>
(function(){
const LANG="__LANG__";
const TX={en:{scenes:"Scenes",note:"Scene note",keys:"Keys",all:"Loop: all",scene:"Loop: scene",trans:"Loop: transition",off:"No loop",safe:"Safe areas",grid:"Grid",names:"Layer names",
 help:"<kbd>Space</kbd> play · <kbd>&larr;</kbd><kbd>&rarr;</kbd> frame · <kbd>Shift</kbd>+arrows 1 s · <kbd>1</kbd>-<kbd>9</kbd> scene · <kbd>L</kbd> loop mode · <kbd>S</kbd> safe · <kbd>N</kbd> names",tr:"transition"},
 tr:{scenes:"Sahneler",note:"Sahne notu",keys:"Kısayollar",all:"Döngü: hepsi",scene:"Döngü: sahne",trans:"Döngü: geçiş",off:"Döngü yok",safe:"Güvenli alan",grid:"Izgara",names:"Katman adları",
 help:"<kbd>Boşluk</kbd> oynat · <kbd>&larr;</kbd><kbd>&rarr;</kbd> kare · <kbd>Shift</kbd>+ok 1 sn · <kbd>1</kbd>-<kbd>9</kbd> sahne · <kbd>L</kbd> döngü · <kbd>S</kbd> güvenli alan · <kbd>N</kbd> adlar",tr:"geçiş"}};
const T=TX[LANG]||TX.en;
const D=JSON.parse(document.getElementById("kk-data").textContent);
const C=D.comp,W=C.w,H=C.h,FPS=C.fps;const TOK=D.tokens||{};const COL=TOK.colors||{};const FON=TOK.fonts||{};
const $=id=>document.getElementById(id);
// ---------- easing
function bez(x1,y1,x2,y2){return function(x){if(x<=0)return 0;if(x>=1)return 1;let lo=0,hi=1,t=x;for(let k=0;k<32;k++){t=(lo+hi)/2;const u=1-t,cx=3*x1*t*u*u+3*x2*t*t*u+t*t*t;if(cx<x)lo=t;else hi=t;}const u=1-t;return 3*y1*t*u*u+3*y2*t*t*u+t*t*t;}}
const E={linear:x=>x,easeIn:bez(.42,0,1,1),easeOut:bez(0,0,.58,1),easeInOut:bez(.42,0,.58,1),easyEase:bez(.33,0,.67,1),
 easyEaseIn:bez(0,0,.67,1),easyEaseOut:bez(.33,0,1,1),cubicOut:bez(.33,1,.68,1),quartOut:bez(.25,1,.5,1),
 expoIn:bez(.7,0,.84,0),expoOut:bez(.16,1,.3,1),expoInOut:bez(.87,0,.13,1),
 backIn:x=>2.70158*x*x*x-1.70158*x*x,backOut:x=>{const u=x-1;return 1+2.70158*u*u*u+1.70158*u*u;}};
function ease(e,def){if(Array.isArray(e))return bez(e[0],e[1],e[2],e[3]);return E[e]||E[def]||E.easeOut;}
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const col=v=>v==null?null:(COL[v]!==undefined?COL[v]:v);
// ---------- fonts: tokens and literal PostScript names through local()
const fontCss=[];const fam={};let nf=0;
function font(v){if(!v)return null;const ps=FON[v]||v;if(fam[ps])return fam[ps];const n="kkf"+(nf++);fam[ps]=n;
 const spaced=ps.replace(/-/g," ");fontCss.push(`@font-face{font-family:"${n}";src:local("${ps}"),local("${spaced}");}`);return `"${n}","${ps}","${ps.split("-")[0]}",system-ui,sans-serif`;}
function weight(ps){ps=(FON[ps]||ps||"").toLowerCase();const m=[["thin",100],["extralight",200],["ultralight",200],["light",300],["medium",500],["semibold",600],["demibold",600],["extrabold",800],["ultrabold",800],["heavy",900],["black",900],["bold",700]];for(const [k,w] of m)if(ps.includes(k))return w;return 400;}
// ---------- timeline
let acc=0;const S=D.scenes.map((s,i)=>{const o=Object.assign({},s,{i:i,start:acc,end:acc+s.dur});acc+=s.dur;return o;});
const TOTAL=acc;
S.forEach((s,i)=>{const tr=s.transition;if(i<S.length-1&&tr&&tr.type!=="cut"){s.tr=Object.assign({dur:0.4,dir:"left"},tr);}else s.tr=null;});
// ---------- build DOM
const stage=$("stage");stage.style.width=W+"px";stage.style.height=H+"px";
const nodes=[];
function phBox(el,label){el.classList.add("ph");el.textContent=label;}
function fmtNum(v,L){const d=L.decimals||0;let s=v.toFixed(d);if(L.sep){const p=s.split(".");p[0]=p[0].replace(/\B(?=(\d{3})+(?!\d))/g,L.sep);s=p.join(L.decimal||(L.sep==="."?",":"."));}return (L.prefix||"")+s+(L.suffix||"");}
S.forEach(s=>{const sc=document.createElement("div");sc.className="scene";sc.style.width=W+"px";sc.style.height=H+"px";sc.style.background=col(s.bg)||"#000";
 const ls=s.layers||[];const items=[];
 ls.forEach((L,li)=>{const o=document.createElement("div");o.className="L";const inn=document.createElement("div");inn.className="Li";o.appendChild(inn);
  o.style.zIndex=String(ls.length-li);let w=L.w,h=L.h;const t=L.type;
  if(t==="text"||t==="counter"){inn.style.whiteSpace="pre-wrap";inn.style.fontSize=(L.size||64)+"px";inn.style.color=col(L.color)||"#fff";
   const f=font(L.font);if(f)inn.style.fontFamily=f;inn.style.fontWeight=L.weight||weight(L.font);inn.style.textAlign=L.align||"center";
   inn.style.lineHeight=L.leading?(L.leading/(L.size||64)):"1.1";if(L.tracking)inn.style.letterSpacing=(L.tracking/1000)+"em";
   if(L.stroke)inn.style.webkitTextStroke=(L.stroke.width||2)+"px "+(col(L.stroke.color)||"#000");
   if(L.shadow)inn.style.textShadow=L.shadow===true?"0 6px 24px rgba(0,0,0,.45)":L.shadow;
   if(w){o.style.width=w+"px";}else o.style.whiteSpace="nowrap";if(t==="text")inn.textContent=L.text;}
  else if(t==="box"||t==="circle"){if(t==="circle"){w=h=2*L.r;inn.style.borderRadius="50%";}else inn.style.borderRadius=(L.radius||0)+"px";
   const fill=col(L.fill);if(L.glass){inn.style.background=fill||"rgba(255,255,255,.14)";inn.style.backdropFilter=inn.style.webkitBackdropFilter="blur("+(L.blur||24)+"px) saturate(1.4)";inn.style.border="1.5px solid rgba(255,255,255,.4)";inn.style.boxShadow="inset 0 1px 0 rgba(255,255,255,.35),0 18px 50px rgba(0,0,0,.35)";}
   else inn.style.background=fill||"#fff";
   if(L.stroke)inn.style.border=(L.stroke.width||2)+"px solid "+(col(L.stroke.color)||"#fff");
   if(L.shadow)inn.style.boxShadow=L.shadow===true?"0 18px 50px rgba(0,0,0,.4)":L.shadow;}
  else if(t==="line"){const dx=L.x2-L.x1,dy=L.y2-L.y1;w=Math.hypot(dx,dy);h=L.width||4;L._x=(L.x1+L.x2)/2;L._y=(L.y1+L.y2)/2;L._rot=Math.atan2(dy,dx)*180/Math.PI;inn.style.background=col(L.color)||"#fff";inn.style.borderRadius=h+"px";}
  else if(t==="image"){if(L.src){const im=document.createElement("img");im.src=L.src;im.style.cssText="width:100%;height:100%;object-fit:"+(L.fit||"cover")+";border-radius:"+(L.radius||0)+"px;display:block";im.onerror=()=>{im.remove();phBox(inn,L.label||L.id||"image");};inn.appendChild(im);}else phBox(inn,L.label||L.id||"image");if(L.radius)inn.style.borderRadius=L.radius+"px";}
  else if(t==="subject"){const b=L.box;w=b[2]-b[0];h=b[3]-b[1];L._x=(b[0]+b[2])/2;L._y=(b[1]+b[3])/2;inn.style.background="rgba(160,160,170,.35)";inn.style.borderRadius=Math.min(w,h)*0.18+"px";inn.style.border="2px solid rgba(255,255,255,.35)";phBox(inn,L.label||"SUBJECT");inn.style.borderStyle="solid";}
  else if(t==="footage"){w=L.w||W;h=L.h||H;L._x=L.x!=null?L.x:W/2;L._y=L.y!=null?L.y:H/2;if(L.src){const im=document.createElement("img");im.src=L.src;im.style.cssText="width:100%;height:100%;object-fit:cover;display:block";inn.appendChild(im);}else{phBox(inn,L.label||"FOOTAGE");inn.style.background="linear-gradient(160deg,#2b2f3a,#15171d)";inn.style.border="none";}}
  if(w)o.style.width=w+"px";if(h)o.style.height=h+"px";
  const tag=document.createElement("div");tag.className="tag";tag.textContent=L.id||t;o.appendChild(tag);
  sc.appendChild(o);items.push({L:L,o:o,inn:inn});});
 stage.insertBefore(sc,$("flashL"));nodes.push({s:s,el:sc,items:items});});
const st=document.createElement("style");st.textContent=fontCss.join("\n");document.head.appendChild(st);
// safe areas
function safe(el,f){const mw=W*(1-f)/2,mh=H*(1-f)/2;el.style.left=mw+"px";el.style.top=mh+"px";el.style.width=(W-2*mw)+"px";el.style.height=(H-2*mh)+"px";}
const SA=D.safe||{action:.93,title:.9};safe($("safeA"),SA.action||.93);safe($("safeT"),SA.title||.9);
$("over").querySelector(".grid").style.backgroundSize=(W/12)+"px "+(H/12)+"px";
// ---------- layer state at local time
function keyed(L,lt,p){const ks=L.keys;if(!ks||!ks.length)return;KEYP.forEach(k=>{let prev=null;for(const q of ks){if(q[k]===undefined)continue;if(q.t<=lt){prev=q;continue;}
  if(!prev){p[k]=q[k];return;}const u=ease(q.ease,"easyEase")(clamp((lt-prev.t)/((q.t-prev.t)||1e-6),0,1));p[k]=prev[k]+(q[k]-prev[k])*u;return;}
  if(prev)p[k]=prev[k];});}
const KEYP=["x","y","scale","rot","opacity"];
function apply(A,k,out,p,L){const n=A.anim,d=A.dist||Math.round(Math.min(W,H)*0.06),fadeOn=A.fade!==false;
 const sg=out?-1:1;
 if(n==="fade")p.opacity*=1-k;
 else if(n.startsWith("slide-")){const off=d*k*sg;if(n==="slide-up")p.y+=off;if(n==="slide-down")p.y-=off;if(n==="slide-left")p.x+=off;if(n==="slide-right")p.x-=off;if(fadeOn)p.opacity*=1-k;}
 else if(n==="scale-in"){const f=A.from!=null?A.from:0.6;p.scale*=1-(1-f)*k;p.opacity*=1-k;}
 else if(n==="pop"){p.scale*=1-k;p.opacity*=clamp((1-k)*3,0,1);}
 else if(n==="blur-in"){p.blur+=(A.amount||24)*k;p.opacity*=1-k;}
 else if(n.startsWith("wipe-")){const v=(k*100).toFixed(2)+"%";const dir=n.slice(5);
  // wipe-right: revealed from its left edge towards the right (in), hidden from the left edge towards the right (out)
  const reveal={right:"0 "+v+" 0 0",left:"0 0 0 "+v,down:"0 0 "+v+" 0",up:v+" 0 0 0"};
  const hide={right:"0 0 0 "+v,left:"0 "+v+" 0 0",down:v+" 0 0 0",up:"0 0 "+v+" 0"};
  p.clip="inset("+(out?hide:reveal)[dir]+")";}
 else if(n==="mask-reveal"){p.mask=k*(out?-1:1);}
 else if(n==="typewriter"){p.chars=Math.min(p.chars==null?1:p.chars,1-k);}
 else if(n==="count-up"){p.count=Math.min(p.count==null?1:p.count,1-k);}}
function state(L,lt){const p={x:L._x!=null?L._x:(L.x!=null?L.x:W/2),y:L._y!=null?L._y:(L.y!=null?L.y:H/2),scale:L.scale!=null?L.scale:1,rot:(L.rot||0)+(L._rot||0),opacity:L.opacity!=null?L.opacity:1,blur:0,clip:null,mask:0,chars:null,count:null,vis:true};
 keyed(L,lt,p);
 if(L.start!=null&&lt<L.start)p.vis=false;if(L.end!=null&&lt>=L.end)p.vis=false;
 const I=L.in;if(I){const dur=I.dur!=null?I.dur:0.5,t0=I.t||0;const def=I.anim==="pop"?"backOut":"easeOut";
  const u=dur>0?ease(I.ease,def)(clamp((lt-t0)/dur,0,1)):(lt>=t0?1:0);apply(I,1-u,false,p,L);}
 const O=L.out;if(O){const dur=O.dur!=null?O.dur:0.4,t0=O.t!=null?O.t:0;const def=O.anim==="pop"?"backIn":"easeIn";
  const u=dur>0?ease(O.ease,def)(clamp((lt-t0)/dur,0,1)):(lt>=t0?1:0);if(u>0)apply(O,u,true,p,L);}
 return p;}
function drawLayer(it,lt){const L=it.L,p=state(L,lt),o=it.o,inn=it.inn;
 if(!p.vis||p.opacity<=0.001){o.style.display="none";return;}o.style.display="";
 o.style.transform=`translate(${p.x}px,${p.y}px) translate(-50%,-50%) rotate(${p.rot}deg) scale(${Math.max(p.scale,0)})`;
 o.style.opacity=clamp(p.opacity,0,1);o.style.filter=p.blur>0.05?`blur(${p.blur}px)`:"";o.style.clipPath=p.clip||"";
 if(L.in&&L.in.anim==="mask-reveal"||L.out&&L.out.anim==="mask-reveal"){o.style.overflow="hidden";inn.style.transform=`translateY(${p.mask*100}%)`;}
 if(L.type==="text"){const s=String(L.text);inn.textContent=p.chars==null?s:s.slice(0,Math.round(s.length*p.chars));}
 if(L.type==="counter"){const f=L.from||0,t=L.to;const v=p.count==null?t:f+(t-f)*p.count;const full=fmtNum(v,L);inn.textContent=p.chars==null?full:full.slice(0,Math.round(full.length*p.chars));}}
function drawScene(n,lt){n.el.style.display="block";n.items.forEach(it=>drawLayer(it,lt));}
function reset(n){n.el.style.display="none";n.el.style.transform="";n.el.style.opacity="";n.el.style.filter="";n.el.style.clipPath="";n.el.style.zIndex="";}
// ---------- frame
let cur=0;
function sceneAt(t){for(const s of S)if(t<s.end)return s.i;return S.length-1;}
function render(t){t=clamp(t,0,TOTAL-1e-6);nodes.forEach(reset);const fl=$("flashL");fl.style.opacity=0;
 const i=sceneAt(t),s=S[i];let A=null,B=null,u=0,tr=null;
 if(i>0&&S[i-1].tr&&t<s.start+S[i-1].tr.dur/2){tr=S[i-1].tr;A=i-1;B=i;}
 else if(s.tr&&t>s.end-s.tr.dur/2){tr=s.tr;A=i;B=i+1;}
 if(tr){const c=S[B].start,d=tr.dur;u=ease(tr.ease,tr.type==="whip"?"expoInOut":"easeInOut")(clamp((t-(c-d/2))/d,0,1));
  const a=nodes[A],b=nodes[B];drawScene(a,t-S[A].start);drawScene(b,Math.max(0,t-S[B].start));transition(tr,u,a.el,b.el,fl);}
 else drawScene(nodes[i],t-s.start);
 cur=t;ui(t,i);}
function vec(dir){return {left:[-1,0],right:[1,0],up:[0,-1],down:[0,1]}[dir]||[-1,0];}
function transition(tr,u,a,b,fl){b.style.zIndex=2;a.style.zIndex=1;const v=vec(tr.dir);
 switch(tr.type){
 case"crossfade":b.style.opacity=u;break;
 case"push":case"whip":{a.style.transform=`translate(${v[0]*W*u}px,${v[1]*H*u}px)`;b.style.transform=`translate(${-v[0]*W*(1-u)}px,${-v[1]*H*(1-u)}px)`;
  if(tr.type==="whip"){const bl=(tr.amount||40)*Math.sin(Math.PI*u);a.style.filter=b.style.filter=`blur(${bl}px)`;}break;}
 case"slide":b.style.transform=`translate(${-v[0]*W*(1-u)}px,${-v[1]*H*(1-u)}px)`;break;
 case"zoom":a.style.transform=`scale(${1+0.35*u})`;a.style.opacity=1-u;b.style.transform=`scale(${0.85+0.15*u})`;b.style.opacity=u;break;
 case"blur":a.style.filter=`blur(${30*u}px)`;a.style.opacity=1-u;b.style.filter=`blur(${30*(1-u)}px)`;b.style.opacity=u;break;
 case"flash":case"dip":{if(u<0.5)b.style.display="none";else a.style.display="none";fl.style.background=tr.color?col(tr.color):(tr.type==="flash"?"#fff":"#000");fl.style.opacity=1-Math.abs(2*u-1);break;}
 case"wipe":{const r=((1-u)*100).toFixed(2)+"%";
  // dir = where the edge travels: left -> new scene enters from the right edge moving left
  const m={left:"inset(0 0 0 "+r+")",right:"inset(0 "+r+" 0 0)",up:"inset("+r+" 0 0 0)",down:"inset(0 0 "+r+" 0)"};
  b.style.clipPath=m[tr.dir]||m.left;break;}
 }}
// ---------- UI
$("ttl").textContent=D.title||"Storyboard";$("meta").textContent=`${W}×${H} · ${FPS} fps · ${TOTAL.toFixed(2)} s · ${S.length}`;
$("hScenes").textContent=T.scenes;$("hNote").textContent=T.note;$("hKeys").textContent=T.keys;$("keys").innerHTML=T.help;
$("bSafe").textContent=T.safe;$("bGrid").textContent=T.grid;$("bNames").textContent=T.names;
[["all",T.all],["scene",T.scene],["trans",T.trans],["off",T.off]].forEach(([v,l])=>{const o=document.createElement("option");o.value=v;o.textContent=l;$("loop").appendChild(o);});
const bar=$("bar");const segs=[];
S.forEach(s=>{const g=document.createElement("div");g.className="seg";g.style.left=(s.start/TOTAL*100)+"%";g.style.width=(s.dur/TOTAL*100)+"%";g.textContent=(s.i+1)+" "+(s.name||s.id);bar.appendChild(g);segs.push(g);
 if(s.tr){const m=document.createElement("div");m.className="trm";m.style.left=((s.end-s.tr.dur/2)/TOTAL*100)+"%";m.style.width=(s.tr.dur/TOTAL*100)+"%";m.title=s.tr.type;bar.appendChild(m);}
 const c=document.createElement("div");c.className="sc";c.innerHTML=`<b>${s.i+1}. ${esc(s.name||s.id)}</b><small>${esc(s.id)} · ${s.start.toFixed(2)}–${s.end.toFixed(2)} s · ${(s.layers||[]).length} layers</small>`+(s.tr?`<div class="tr">→ ${T.tr}: ${esc(s.tr.type)}${s.tr.dir&&["push","slide","whip","wipe"].includes(s.tr.type)?" "+esc(s.tr.dir):""} ${s.tr.dur}s</div>`:"");
 c.onclick=()=>{selScene=s.i;seek(s.start);};$("list").appendChild(c);s._card=c;});
function esc(x){return String(x==null?"":x).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
let selScene=0;
function ui(t,i){$("head").style.left=(t/TOTAL*100)+"%";const f=Math.round(t*FPS);$("time").textContent=`${t.toFixed(2)} s · f${f} / ${TOTAL.toFixed(2)} s`;
 segs.forEach((g,k)=>g.classList.toggle("on",k===i));S.forEach(s=>s._card.classList.toggle("on",s.i===i));
 if(i!==ui.last){ui.last=i;$("note").textContent=S[i].note||"—";}
 const r=range();const lr=$("loopR");if(r&&$("loop").value!=="all"){lr.style.display="block";lr.style.left=(r[0]/TOTAL*100)+"%";lr.style.width=((r[1]-r[0])/TOTAL*100)+"%";}else lr.style.display="none";}
function range(){const m=$("loop").value,s=S[selScene];if(m==="scene")return [s.start,s.end];
 if(m==="trans"){let k=selScene;if(!S[k].tr&&k>0&&S[k-1].tr)k=k-1;const q=S[k];if(!q.tr)return [q.start,q.end];return [Math.max(0,q.end-q.tr.dur/2-0.6),Math.min(TOTAL,q.end+q.tr.dur/2+0.6)];}
 if(m==="all")return [0,TOTAL];return null;}
// fit
function fit(){const v=$("view").getBoundingClientRect();const k=Math.min((v.width-40)/W,(v.height-40)/H);const f=$("fit");f.style.transform=`translate(${(v.width-W*k)/2}px,${(v.height-H*k)/2}px) scale(${k})`;}
window.addEventListener("resize",fit);
// playback
let playing=false,last=0;
function seek(t){const r=range();render(t);}
function tick(now){if(!playing)return;const dt=(now-last)/1000;last=now;let t=cur+dt*parseFloat($("speed").value);const r=range();
 if(r){if(t>=r[1])t=r[0];if(t<r[0]-0.001)t=r[0];}else if(t>=TOTAL){t=TOTAL-1e-6;setPlay(false);}
 render(t);requestAnimationFrame(tick);}
function setPlay(v){playing=v;$("play").innerHTML=v?"&#10073;&#10073;":"&#9654;";if(v){const r=range();if(r&&(cur<r[0]||cur>=r[1]-1e-3))cur=r[0];if(!r&&cur>=TOTAL-1e-3)cur=0;last=performance.now();requestAnimationFrame(tick);}}
$("play").onclick=()=>setPlay(!playing);
$("loop").onchange=()=>{selScene=sceneAt(cur);render(cur);};
function scrub(e){const b=bar.getBoundingClientRect();const t=clamp((e.clientX-b.left)/b.width,0,1)*TOTAL;selScene=sceneAt(t);render(t);}
bar.addEventListener("mousedown",e=>{scrub(e);const mv=ev=>scrub(ev);const up=()=>{window.removeEventListener("mousemove",mv);window.removeEventListener("mouseup",up);};window.addEventListener("mousemove",mv);window.addEventListener("mouseup",up);});
function tog(btn,cls,el){btn.onclick=()=>{el.classList.toggle(cls);btn.classList.toggle("on");};}
tog($("bSafe"),"showsafe",stage);tog($("bGrid"),"showgrid",stage);tog($("bNames"),"names",stage);
window.addEventListener("keydown",e=>{if(e.target.tagName==="SELECT")return;const k=e.key;
 if(k===" "){e.preventDefault();setPlay(!playing);}
 else if(k==="ArrowRight"||k==="ArrowLeft"){e.preventDefault();const st=e.shiftKey?1:1/FPS;const t=clamp(cur+(k==="ArrowRight"?st:-st),0,TOTAL);selScene=sceneAt(t);render(t);}
 else if(k==="Home"){render(0);}
 else if(/^[1-9]$/.test(k)&&S[+k-1]){selScene=+k-1;render(S[selScene].start);}
 else if(k==="l"||k==="L"){const o=$("loop");o.selectedIndex=(o.selectedIndex+1)%o.options.length;o.onchange();}
 else if(k==="s"||k==="S")$("bSafe").click();else if(k==="n"||k==="N")$("bNames").click();else if(k==="g"||k==="G")$("bGrid").click();});
fit();render(0);
window.KK={render:render,total:TOTAL,scenes:S};
})();
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("new")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--title")
    p.add_argument("--parts", nargs="+")
    p.add_argument("--scenes", type=int, default=3)
    p.add_argument("--dur", type=float, default=3.0)
    p.add_argument("--format", default="16x9", choices=sorted(DEFAULT_COMP))
    p.add_argument("--size")
    p.add_argument("--fps", type=float)
    p.add_argument("--style")
    p.add_argument("--home")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(fn=cmd_new)
    p = sp.add_parser("check")
    p.add_argument("file")
    p.set_defaults(fn=cmd_check)
    p = sp.add_parser("build")
    p.add_argument("file")
    p.add_argument("-o", "--output")
    p.add_argument("--lang", default="en", choices=("en", "tr"))
    p.set_defaults(fn=cmd_build)
    p = sp.add_parser("vocab")
    p.set_defaults(fn=cmd_vocab)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

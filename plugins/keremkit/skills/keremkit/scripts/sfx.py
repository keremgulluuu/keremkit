#!/usr/bin/env python3
"""KeremKit SFX - synthesise basic edit sound effects with ffmpeg (no samples, no licences).

  list                             the sounds this tool makes
  make  [NAME ...] -o DIR [--variants 3]
                                   write WAV files (48 kHz mono), e.g. whoosh_1.wav, impact_1.wav
                                   NAME defaults to all; variants differ slightly in pitch/length
  banned                           the user's banned SFX files (preferences sfx.banned_files)
  filter PATH [PATH ...]           drop banned files from candidates BEFORE listening, ranking or importing:
                                   PATH = a file or a folder (searched for audio); prints the allowed files
                                   and "SKIP (banned) ..." lines. Every SFX choice goes through this gate.

Use them when the user has no SFX folder, or as placeholders; real libraries sound richer.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

PEAK_DB = -3.0   # every sound peaks here; set the level in the edit (see sound-effects.md)

SOUNDS = {
    # name: (duration, filter graph building the sound from lavfi sources; {d} and {v} are filled in)
    "whoosh": (0.55, "anoisesrc=d={d}:c=pink:a=0.9,highpass=f=300,lowpass=f=6000,"
                     "volume='if(lt(t,{d}*0.6),t/({d}*0.6),({d}-t)/({d}*0.4))':eval=frame,"
                     "bandpass=f=1200*{v}:w=1.2"),
    "impact": (0.9, "sine=f=55*{v}:d={d},volume='exp(-6*t)':eval=frame[a];"
                    "anoisesrc=d=0.08:c=brown:a=0.8,lowpass=f=900[b];[a][b]amix=inputs=2:normalize=0"),
    "pop": (0.12, "sine=f=900*{v}:d={d},volume='exp(-35*t)':eval=frame"),
    "tick": (0.05, "anoisesrc=d={d}:c=white:a=0.6,highpass=f=2500,volume='exp(-90*t)':eval=frame"),
    "click": (0.04, "sine=f=2200*{v}:d={d},volume='exp(-120*t)':eval=frame"),
    "glitch": (0.25, "anoisesrc=d={d}:c=white:a=0.7,acrusher=bits=4:samples=12*{v}:mix=1,"
                     "volume='if(lt(mod(t,0.05),0.025),1,0.15)':eval=frame,highpass=f=200"),
    "flash": (0.35, "anoisesrc=d={d}:c=white:a=0.5,highpass=f=4000,volume='exp(-9*t)':eval=frame"),
    "riser": (2.0, "sine=f=200*{v}:d={d},vibrato=f=6:d=0.3,volume='t/{d}':eval=frame[a];"
                   "anoisesrc=d={d}:c=pink:a=0.3,highpass=f=800,volume='(t/{d})^2':eval=frame[b];"
                   "[a][b]amix=inputs=2:normalize=0"),
    "typing": (1.2, "anoisesrc=d={d}:c=white:a=0.6,highpass=f=1800,"
                    "volume='if(lt(mod(t,0.085*{v}),0.012),1,0)':eval=frame"),
}


AUDIO_EXT = (".wav", ".mp3", ".aif", ".aiff", ".flac", ".ogg", ".m4a", ".aac")


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


def banned_list(home):
    """[(name_key, path_key, why)] from preferences sfx.banned_files (strings or {file, path, why})."""
    try:
        with open(os.path.join(home, "settings", "preferences.json"), encoding="utf-8") as f:
            prefs = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for b in ((prefs.get("sfx") or {}).get("banned_files") or []):
        if isinstance(b, str):
            b = {"file": os.path.basename(b), "path": b if os.sep in b or "/" in b else ""}
        name = (b.get("file") or os.path.basename(b.get("path") or "")).strip().lower()
        path = os.path.normcase(os.path.normpath(b["path"])) if b.get("path") else ""
        if name or path:
            out.append((name, path, b.get("why") or ""))
    return out


def is_banned(path, banned):
    """Banned when the file name matches (any folder) or the full path matches."""
    base = os.path.basename(path).strip().lower()
    full = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    return next((b for b in banned if (b[0] and b[0] == base) or (b[1] and b[1] == full)), None)


def render(name, out, variant):
    d, graph = SOUNDS[name]
    v = 1 + 0.08 * (variant - 1) * (1 if variant % 2 else -1)
    d = round(d * (1 + 0.1 * (variant - 1)), 3)
    g = graph.format(d=d, v=round(v, 3))
    fc = g
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=0.01",
           "-filter_complex", fc + ",aformat=sample_rates=48000:channel_layouts=mono,afade=t=out:st=" +
           f"{max(0, d - 0.01)}:d=0.01", "-t", str(d), "-ac", "1", "-ar", "48000", out]
    tmp = out + ".tmp.wav"
    cmd[-1] = tmp
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "").strip()[-300:])
    # normalise every sound to the same peak so levels in the edit are predictable
    m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", tmp, "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    peak = re.search(r"max_volume:\s*(-?[\d.]+) dB", m or "")
    gain = PEAK_DB - float(peak.group(1)) if peak else 0.0
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", f"volume={gain:.2f}dB", "-c:a", "pcm_s16le", out],
                       capture_output=True, text=True)
    os.remove(tmp)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "").strip()[-300:])


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list")
    m = sp.add_parser("make")
    m.add_argument("names", nargs="*")
    m.add_argument("-o", "--output", required=True)
    m.add_argument("--variants", type=int, default=1)
    bn = sp.add_parser("banned")
    bn.add_argument("--home")
    fl = sp.add_parser("filter")
    fl.add_argument("paths", nargs="+")
    fl.add_argument("--home")
    a = ap.parse_args()
    if a.cmd == "banned":
        bl = banned_list(home_dir(a.home))
        for name, path, why in bl:
            print(f"BANNED {name or path}" + (f"  ({why[:120]})" if why else ""))
        print(f"OK banned={len(bl)}")
        return
    if a.cmd == "filter":
        bl = banned_list(home_dir(a.home))
        files = []
        for p in a.paths:
            if os.path.isdir(p):
                for root, _, names in os.walk(p):
                    files += [os.path.join(root, n) for n in sorted(names) if n.lower().endswith(AUDIO_EXT)]
            else:
                files.append(p)
        kept = 0
        for f in files:
            if is_banned(f, bl):
                print(f"SKIP (banned) {f}")
            else:
                print(f)
                kept += 1
        print(f"OK allowed={kept} skipped={len(files) - kept}")
        return
    if a.cmd == "list":
        for n, (d, _) in SOUNDS.items():
            print(f"{n}\t{d}s")
        return
    if not shutil.which("ffmpeg"):
        sys.exit("ERROR: ffmpeg not found")
    names = a.names or list(SOUNDS)
    bad = [n for n in names if n not in SOUNDS]
    if bad:
        sys.exit(f"ERROR: unknown sound(s) {bad}; use: {', '.join(SOUNDS)}")
    os.makedirs(a.output, exist_ok=True)
    made, failed = 0, []
    for n in names:
        for k in range(1, a.variants + 1):
            try:
                render(n, os.path.join(a.output, f"{n}_{k}.wav"), k)
                made += 1
            except RuntimeError as e:
                failed.append(f"{n}: {e}")
    for f in failed:
        print("FAILED " + f)
    print(f"OK made={made} -> {a.output}")
    if failed and not made:
        sys.exit(1)


if __name__ == "__main__":
    main()

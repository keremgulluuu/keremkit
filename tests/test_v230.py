"""2.3.0: preflight, ae-postcheck, banned SFX filter, wordless speech, dated learning-archive backups."""
import json
import os
import shutil
import subprocess

import pytest

from conftest import run


@pytest.fixture
def kk(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    home = tmp_path / "KK"
    run("keremkit.py", "init", home, env=env)
    return home


def k(home, *args, check=True):
    return run("keremkit.py", "--home", home, *args, check=check)


def set_prefs(home, **sections):
    p = home / "settings" / "preferences.json"
    prefs = json.loads(p.read_text(encoding="utf-8"))
    prefs.update(sections)
    p.write_text(json.dumps(prefs), encoding="utf-8")


def write_style(home, slug, data):
    d = home / "styles" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "style.json").write_text(json.dumps(data), encoding="utf-8")


# ------------------------------------------------------------------ preflight
def test_preflight_prints_rules_for_the_task(kk):
    set_prefs(kk, sfx={"banned_files": [{"file": "anime shine.mp3", "why": "user"}], "level_db": -18},
              custom_rules=["[sfx] counter SFX last as long as the counter", "Never render AVI or lossless",
                            "Whisper model is the user's choice", "[design] keep 24 px margins"])
    out = k(kk, "preflight", "sfx").stdout
    assert out.startswith("PREFLIGHT sfx")
    assert "ORDER explicit instruction" in out
    assert "BANNED_SFX anime shine.mp3" in out
    assert "1. [sfx] counter" in out and "2. Never render AVI" in out
    assert "Whisper" not in out and "24 px" not in out          # other tasks' rules are left out
    assert "sfx.py filter" in out
    design = k(kk, "preflight", "ae-design").stdout
    assert "24 px" in design and "optimize mode=on heavy_fps=30" in design
    assert "STYLE none given" in design and "GATE qc.py ae-postcheck" in design
    assert len(design.splitlines()) <= 45


def test_preflight_style_tokens_and_open_questions(kk):
    write_style(kk, "lime", {"look": {"palette": {"accent": "#C6FF3C"}}, "open_questions": ["stroke?"]})
    out = k(kk, "preflight", "ae-build", "--style", "lime").stdout
    assert "#C6FF3C" in out and "layout=none" in out and "open_questions=1" in out
    assert "NOT FOUND" in k(kk, "preflight", "ae-build", "--style", "nope").stdout
    assert k(kk, "preflight", "dance", check=False).returncode != 0


def test_preflight_short_words_match_whole_words(kk):
    set_prefs(kk, custom_rules=["Move the camera slowly"])       # "mov" (render) must not match "Move"
    assert "RULES 0 of 1" in k(kk, "preflight", "sfx").stdout


# ------------------------------------------------------------------ sfx filter
def test_sfx_filter_drops_banned_files(kk, tmp_path):
    set_prefs(kk, sfx={"banned_files": [{"file": "Anime Shine.mp3"}, "D:/x/full path.wav"]})
    lib = tmp_path / "sfx"
    (lib / "magic").mkdir(parents=True)
    for n in ("magic/anime shine.mp3", "whoosh.wav", "notes.txt"):
        (lib / n).write_bytes(b"x")
    out = run("sfx.py", "filter", lib, "--home", kk).stdout
    assert "SKIP (banned)" in out and "anime shine.mp3" in out.split("SKIP (banned)")[1]
    assert "whoosh.wav" in out and "notes.txt" not in out
    assert "OK allowed=1 skipped=1" in out
    assert "OK banned=2" in run("sfx.py", "banned", "--home", kk).stdout


# ------------------------------------------------------------------ ae-postcheck
def export(tmp_path, comps, footage=()):
    items = [{"id": 900 + i, "name": os.path.basename(f), "type": "FootageItem", "file": f} for i, f in enumerate(footage)]
    items += comps
    p = tmp_path / "export.json"
    p.write_text(json.dumps({"items": items}), encoding="utf-8")
    return p


def layer(name, fx=(), keys=(), source=None):
    return {"name": name, "type": "AVLayer", "enabled": True, "sourceId": source,
            "transformGroup": {"properties": [{"name": m, "matchName": m, "keyframes": [{"time": 0}, {"time": 1}]}
                                              for m in keys]},
            "effectsGroup": {"groups": [{"name": n, "matchName": n} for n in fx]}}


def test_postcheck_fails_on_banned_and_heavy_outside_hvy(kk, tmp_path):
    set_prefs(kk, sfx={"banned_files": [{"file": "anime shine.mp3"}]})
    comps = [
        {"id": 1, "name": "MAIN", "type": "CompItem", "frameRate": 60,
         "layers": [layer("CNT_A", fx=["CC Force Motion Blur"]), layer("HVY_Glow", source=2), layer("SFX", source=900)]},
        {"id": 2, "name": "HVY_Glow", "type": "CompItem", "frameRate": 60, "layers": [layer("G", fx=["PEDG"], source=3)]},
        {"id": 3, "name": "PRE_Inner", "type": "CompItem", "frameRate": 60, "layers": [layer("Glo", fx=["ADBE Glo2"])]},
    ]
    p = export(tmp_path, comps, ["D:/sfx/anime shine.mp3"])
    res = run("qc.py", "ae-postcheck", p, "--home", kk, check=False)
    out = res.stdout
    assert res.returncode == 1 and "POSTCHECK FAIL" in out
    assert "BANNED_SFX anime shine.mp3" in out and "used" in out
    assert "MAIN / CNT_A: CC Force Motion Blur" in out
    assert "PEDG" not in out and "ADBE Glo2" not in out.replace("HEAVY", "")   # nested inside HVY_ = fine
    assert "HVY_FPS HVY_Glow runs at 60" in out


def test_postcheck_ok_warns_rig_colour_spacing(kk, tmp_path):
    write_style(kk, "lime", {"look": {"palette": {"accent": "#C6FF3C", "bg": "#101010"}}})
    comps = [{"id": 1, "name": "MAIN", "type": "CompItem", "frameRate": 60,
              "layers": [layer("TXT_Title", keys=["ADBE Position"]), layer("NULL_Rig", keys=["ADBE Position"])]}]
    p = export(tmp_path, comps)
    samples = tmp_path / "s.json"
    samples.write_text(json.dumps([{"layer": "TXT_Title", "rgb": [247, 255, 219]},
                                   {"layer": "TXT_Ok", "rgb": [0.78, 1.0, 0.24]}]), encoding="utf-8")
    bounds = tmp_path / "b.json"
    bounds.write_text(json.dumps([{"layer": "A", "left": 10, "top": 100, "width": 100, "height": 100},
                                  {"layer": "B", "left": 105, "top": 100, "width": 100, "height": 100},
                                  {"layer": "C", "left": 230, "top": 100, "width": 100, "height": 100},
                                  {"layer": "Plate", "box": [0, 0, 1920, 1080]}]), encoding="utf-8")
    out = run("qc.py", "ae-postcheck", p, "--home", kk, "--style", "lime", "--samples", samples,
              "--bounds", bounds, "--min-gap", 40, "--edge", 20, "--size", "1920x1080").stdout
    assert "POSTCHECK OK fail=0" in out
    assert "OWN_TRANSFORM_KEYS MAIN / TXT_Title: ADBE Position" in out and "NULL_Rig" not in out
    assert "COLOUR TXT_Title measured #F7FFDB" in out and "TXT_Ok" not in out
    assert "OVERLAP A x B" in out and "GAP B - C 25 px" in out
    assert "EDGE A 10 px" in out and "Plate" not in out.split("EDGE A")[0].split("OVERLAP")[-1]


def test_postcheck_respects_optimize_off_and_direct_rig(kk, tmp_path):
    set_prefs(kk, optimize={"mode": "off"}, motion={"transform_rig": "direct"})
    comps = [{"id": 1, "name": "MAIN", "type": "CompItem", "frameRate": 60,
              "layers": [layer("TXT_A", fx=["ADBE Glo2"], keys=["ADBE Scale"])]}]
    out = run("qc.py", "ae-postcheck", export(tmp_path, comps), "--home", kk).stdout
    assert "POSTCHECK OK fail=0 warn=0" in out


# ------------------------------------------------------------------ wordless speech
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_wordless_finds_speech_without_words(tmp_path):
    wav = tmp_path / "a.wav"
    # 0-1 s tone (has words), 1-1.5 s silence, 1.5-3 s tone (no words), 3-3.5 s silence
    graph = ("sine=f=220:d=1[a];anullsrc=r=16000:cl=mono:d=0.5[b];sine=f=220:d=1.5[c];anullsrc=r=16000:cl=mono:d=0.5[d];"
             "[a][b][c][d]concat=n=4:v=0:a=1")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-filter_complex", graph, "-ar", "16000", "-ac", "1", str(wav)],
                   check=True)
    words = tmp_path / "w.json"
    words.write_text(json.dumps({"segments": [{"words": [{"word": " hello", "start": 0.05, "end": 0.5},
                                                          {"word": " there", "start": 0.5, "end": 0.95}]}]}),
                     encoding="utf-8")
    out = run("transcript.py", "wordless", words, "--media", wav, "-o", tmp_path / "wl.json").stdout
    assert "OK wordless=1" in out and "WORDLESS 00:01.5" in out
    data = json.loads((tmp_path / "wl.json").read_text(encoding="utf-8"))
    assert abs(data["spans"][0]["start"] - 1.5) < 0.15 and abs(data["spans"][0]["end"] - 3.0) < 0.15


# ------------------------------------------------------------------ learning-archive backups
def test_learning_archive_backups_are_dated_and_kept(kk):
    p = kk / "learning" / "skill-change-requests.md"
    for n in (1, 2):
        p.write_text(f"# R\n\n## Item {n}\nStatus: done 2.3.0\n- x\n", encoding="utf-8")
        assert f"OK moved=1" in k(kk, "learning-archive").stdout
    baks = sorted(x.name for x in (kk / "learning").glob("skill-change-requests.md.bak-*"))
    assert len(baks) == 2

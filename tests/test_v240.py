"""2.4.0: golden-rule postcheck FAILs, preflight --request, cutlist rotation / nominal fps, subtitles --set."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import SCRIPTS, run
from test_v230 import export, kk, layer, set_prefs  # noqa: F401  (kk is a fixture)


def lay(name, label=None, parent=None, index=None, **kw):
    L = layer(name, **kw)
    if label is not None:
        L["label"] = label
    if index is not None:
        L["index"] = index
    if parent is not None:
        L["parentIndex"] = parent
    return L


# ------------------------------------------------------------------ postcheck golden rules
def test_own_transform_keys_fail_including_opacity_and_hvy(kk, tmp_path):
    comps = [{"id": 1, "name": "MAIN", "type": "CompItem", "frameRate": 60, "layers": [
        lay("TXT_A", label=2, keys=["ADBE Opacity"]), lay("HVY_Glow", label=3, keys=["ADBE Scale"]),
        lay("CTRL_Rig", label=4, keys=["ADBE Position"]), lay("ADJ_Zoom", label=5, keys=["ADBE Scale"])]}]
    res = run("qc.py", "ae-postcheck", export(tmp_path, comps), "--home", kk, check=False)
    assert res.returncode == 1
    assert "FAIL OWN_TRANSFORM_KEYS MAIN / TXT_A: ADBE Opacity" in res.stdout
    assert "FAIL OWN_TRANSFORM_KEYS MAIN / HVY_Glow" in res.stdout
    fails = [x for x in res.stdout.splitlines() if x.startswith("FAIL")]
    assert not any("CTRL_Rig" in x or "ADJ_Zoom" in x for x in fails)


def test_label_none_fails_and_wrong_label_warns(kk, tmp_path):
    set_prefs(kk, organize={"labels": {"TXT": 2, "CTRL": 4}})
    comps = [{"id": 1, "name": "MAIN", "type": "CompItem", "frameRate": 60, "layers": [
        lay("TXT_A", label=0), lay("TXT_B", label=9), lay("CTRL_X", label=4), lay("Unprefixed", label=7)]}]
    out = run("qc.py", "ae-postcheck", export(tmp_path, comps), "--home", kk, check=False).stdout
    assert "FAIL LABEL_NONE MAIN / TXT_A" in out
    assert "WARN LABEL MAIN / TXT_B is 9, organize.labels[TXT]=2" in out
    assert "CTRL_X" not in out and "Unprefixed" not in out


def test_nesting_depth_and_parents(kk, tmp_path):
    comps = [
        {"id": 1, "name": "MAIN", "type": "CompItem", "frameRate": 60, "layers": [
            lay("PRE_A", label=3, source=2, index=1), lay("LIB_X", label=13, source=4, index=2),
            lay("TXT_T", label=2, index=3, parent=4), lay("SHP_Box", label=6, index=4),
            lay("UI_C", label=11, index=5, parent=6), lay("NULL_Rig", label=4, index=6)]},
        {"id": 2, "name": "PRE_A", "type": "CompItem", "frameRate": 60, "layers": [lay("PRE_B", label=3, source=3)]},
        {"id": 3, "name": "PRE_B", "type": "CompItem", "frameRate": 60, "layers": [lay("TXT_In", label=2)]},
        {"id": 4, "name": "LIB_X", "type": "CompItem", "frameRate": 60, "layers": [lay("PRE_L", label=3, source=5)]},
        {"id": 5, "name": "PRE_L", "type": "CompItem", "frameRate": 60, "layers": [lay("TXT_L", label=2)]},
    ]
    out = run("qc.py", "ae-postcheck", export(tmp_path, comps), "--home", kk, check=False).stdout
    assert "FAIL NESTED_DEPTH PRE_B is 3 levels deep" in out
    assert "PRE_L" not in out                                  # inside LIB_ = free
    assert "WARN PARENT MAIN / TXT_T -> parent 'SHP_Box'" in out
    assert "UI_C" not in out
    ok = run("qc.py", "ae-postcheck", export(tmp_path, comps), "--home", kk, "--max-depth", 3).stdout
    assert "NESTED_DEPTH" not in ok and "POSTCHECK OK" in ok


def test_subject_overlap_warns(kk, tmp_path):
    comps = [{"id": 1, "name": "MAIN", "type": "CompItem", "frameRate": 60, "layers": [lay("TXT_A", label=2)]}]
    b = tmp_path / "b.json"
    b.write_text(json.dumps([{"layer": "UI_Card", "box": [800, 300, 1100, 600]},
                             {"layer": "TXT_Side", "box": [50, 50, 300, 150]}]), encoding="utf-8")
    s = tmp_path / "subj.json"
    s.write_text(json.dumps([{"t": 14.9, "box": [700, 200, 1200, 1080]}]), encoding="utf-8")
    out = run("qc.py", "ae-postcheck", export(tmp_path, comps), "--home", kk, "--bounds", b, "--subject", s).stdout
    assert "WARN SUBJECT UI_Card covers the subject at 14.9s (100% of the element)" in out
    assert "TXT_Side" not in out


def test_many_lines_get_a_count_line(kk, tmp_path):
    comps = [{"id": 1, "name": "MAIN", "type": "CompItem", "frameRate": 60,
              "layers": [lay(f"TXT_{i}", label=0) for i in range(5)]}]
    out = run("qc.py", "ae-postcheck", export(tmp_path, comps), "--home", kk, "--max-lines", 2, check=False).stdout
    assert "FAILS by check: LABEL_NONE=5" in out and "... 3 more" in out


# ------------------------------------------------------------------ preflight --request
def test_preflight_request_items_and_named_technique(kk):
    text = ("ECOMZ yazısını ai-to-3d-glow-logo ile 3D yap ve arkasındaki rengi kırmızı yap. "
            "Sonra UI-133 kartını ekle")
    out = run("keremkit.py", "--home", kk, "preflight", "ae-build", "--request", text).stdout
    assert out.index("GOLDEN 1 motion") < out.index("GOLDEN 4 request") < out.index("REQUEST 3 items")
    assert "R1. ECOMZ yazısını ai-to-3d-glow-logo ile 3D yap" in out
    assert "R2. arkasındaki rengi kırmızı yap" in out and "R3. Sonra UI-133 kartını ekle" in out
    assert "NAMED library UI-133" in out
    assert "NAMED technique ai-to-3d-glow-logo" in out or "techniques" not in out  # built-in may lack it
    plain = run("keremkit.py", "--home", kk, "preflight", "cut").stdout
    assert "GOLDEN 1" not in plain and "GOLDEN 4" in plain and "REQUEST not given" in plain


def test_preflight_request_from_file_and_suggest_rule(kk, tmp_path):
    f = tmp_path / "req.txt"
    f.write_text("add a clock next to the date\nkeep the colours", encoding="utf-8")
    out = run("keremkit.py", "--home", kk, "preflight", "ae-design", "--request", f"@{f}").stdout
    assert "REQUEST 2 items" in out and "GOLDEN 5 suggestions" in out


# ------------------------------------------------------------------ cutlist / subtitles bugs
def test_nominal_fps_and_rotation_helpers():
    sys.path.insert(0, SCRIPTS)
    import cutlist
    assert cutlist.nominal_fps("968/30", "60/1") == 60.0          # iPhone VFR
    assert cutlist.nominal_fps("30000/1001", "30000/1001") == 29.97
    assert cutlist.nominal_fps("25/1", "90000/1") == 25.0         # silly r_frame_rate ignored
    assert cutlist.rotation_of({"side_data_list": [{"rotation": -90}]}) == -90
    assert cutlist.rotation_of({"tags": {"rotate": "270"}}) == 270
    assert cutlist.rotation_of({}) == 0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_probe_av_swaps_rotated_phone_video(tmp_path):
    src, out = tmp_path / "a.mp4", tmp_path / "r.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=320x180:d=0.2", "-c:v", "libx264",
                    str(src)], check=True)
    r = subprocess.run(["ffmpeg", "-v", "error", "-display_rotation", "90", "-i", str(src), "-c", "copy", str(out)])
    if r.returncode != 0 or not out.exists():
        pytest.skip("this ffmpeg cannot write a display matrix")
    sys.path.insert(0, SCRIPTS)
    import cutlist
    w, h, _, _ = cutlist.probe_av(str(out))
    assert (w, h) == (180, 320)


def test_subtitles_repeated_set_flags_accumulate(tmp_path, words_file):
    o = tmp_path / "subs"
    out = run("subtitles.py", "build", "--words", words_file[0], "--set", "max_words=3", "--set", "min_words=1", "-o", o).stdout
    assert "RULES max_words=3 min_words=1" in out
    assert json.loads((tmp_path / "subs.json").read_text(encoding="utf-8"))["rules"]["max_words"] == 3

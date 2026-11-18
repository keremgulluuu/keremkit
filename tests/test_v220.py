"""2.2.0: where --all (locations for memory), optimize defaults, motion rig default, null sections filled,
cutlist restore print, sliver drop, xmeml sequence rate/size, transcript merge spans, videoref chunks."""
import json
import os
import sys

import pytest

from conftest import SCRIPTS, run

sys.path.insert(0, SCRIPTS)
import videoref  # noqa: E402


@pytest.fixture
def kk(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    home = tmp_path / "KK"
    run("keremkit.py", "init", home, env=env)
    return home


def k(home, *args, check=True):
    return run("keremkit.py", "--home", home, *args, check=check)


def test_where_all_lists_locations_for_memory(kk):
    k(kk, "pref", "set", "paths.projects=D:/AE")
    out = k(kk, "where", "--all").stdout
    assert out.startswith("READY")
    for key in ("home", "tools", "styles", "library", "assets", "learning", "projects\tD:/AE", "MEMORY"):
        assert key in out
    assert "MEMORY" not in k(kk, "where").stdout          # plain where stays one line


def test_optimize_on_by_default(kk):
    opt = json.loads(k(kk, "pref", "get", "optimize").stdout)
    assert opt["mode"] == "on" and opt["heavy_fps"] == 30 and opt["prerender"] == "ask"
    assert opt["intermediate"] == "png" and opt["screen"] == "matte"
    assert json.loads(k(kk, "pref", "get", "motion.transform_rig").stdout) == "parent_null"
    k(kk, "pref", "set", "optimize.heavy_fps=24")          # the user can change it
    assert json.loads(k(kk, "pref", "get", "optimize.heavy_fps").stdout) == 24


def test_null_section_gets_defaults(kk):
    p = kk / "settings" / "preferences.json"
    prefs = json.loads(p.read_text(encoding="utf-8"))
    prefs["motion"] = None
    prefs.pop("optimize")
    p.write_text(json.dumps(prefs), encoding="utf-8")
    assert json.loads(k(kk, "pref", "get", "motion.transform_rig").stdout) == "parent_null"
    assert json.loads(k(kk, "pref", "get", "optimize.mode").stdout) == "on"


def words(tmp_path, items):
    p = tmp_path / "w.json"
    p.write_text(json.dumps({"segments": [{"words": [{"word": " " + w, "start": s, "end": e} for w, s, e in items]}]}),
                 encoding="utf-8")
    return p


def build(tmp_path, w, dur, *extra):
    out = tmp_path / "c.json"
    res = run("cutlist.py", "build", "--words", w, "--media", tmp_path / "none.mp4", "--preset", "tight",
              "--duration", dur, "--fps", 30, *extra, "-o", out)
    return out, json.loads(out.read_text(encoding="utf-8")), res.stdout


def test_restore_inside_removed_range_does_not_crash(tmp_path):
    w = words(tmp_path, [("a", 0.5, 1.0), ("b", 4.0, 4.5)])
    path, _, _ = build(tmp_path, w, 6)
    res = run("cutlist.py", "restore", path, "--src-from", 2.0, "--src-to", 2.5)
    assert res.returncode == 0 and "OK restored" in res.stdout


def test_slivers_at_removal_edges_are_dropped(tmp_path):
    w = words(tmp_path, [("one", 0.2, 1.0), ("two", 1.06, 2.0), ("three", 2.6, 3.2)])
    rem = tmp_path / "r.json"
    rem.write_text(json.dumps([{"src_in": 1.06, "src_out": 2.0, "apply": True}]), encoding="utf-8")
    _, cl, out = build(tmp_path, w, 4, "--remove", rem)
    assert all(s["src_out"] - s["src_in"] >= 0.1 for s in cl["segments"])
    assert "slivers_dropped=1" in out


def test_xmeml_sequence_rate_and_size(tmp_path):
    w = words(tmp_path, [("a", 0.5, 1.5), ("b", 3.0, 4.0)])
    path, _, _ = build(tmp_path, w, 5)
    cl = json.loads(path.read_text(encoding="utf-8"))
    cl["fps"] = 29.97
    path.write_text(json.dumps(cl), encoding="utf-8")
    x = tmp_path / "o.xml"
    out = run("cutlist.py", "export", path, "--format", "xmeml", "--seq-fps", 60, "--seq-size", "1080x1920",
              "-o", x).stdout
    assert "seq=60fps 1080x1920" in out
    text = x.read_text(encoding="utf-8")
    assert "<timebase>30</timebase><ntsc>TRUE</ntsc>" in text                       # file keeps its NTSC rate
    assert "<timebase>60</timebase><ntsc>FALSE</ntsc>" in text                      # sequence at 60
    assert "<width>1080</width><height>1920</height>" in text and "Basic Motion" in text
    import xml.dom.minidom
    xml.dom.minidom.parse(str(x))


def test_merge_by_index_spans_all_merged_words(tmp_path):
    w = words(tmp_path, [("N", 1.0, 1.2), ("bir", 1.2, 1.5), ("sekiz", 1.5, 1.9), ("sonra", 2.0, 2.4)])
    corr = tmp_path / "c.json"
    corr.write_text(json.dumps([{"index": 0, "new": "N18"}, {"index": 1, "new": ""}, {"index": 2, "new": ""}]),
                    encoding="utf-8")
    out = tmp_path / "f.json"
    run("transcript.py", "fix", w, "--corrections", corr, "-o", out)
    ws = json.loads(out.read_text(encoding="utf-8"))["segments"][0]["words"]
    merged = ws[0]
    assert merged["word"].strip() == "N18" and merged["start"] == 1.0 and merged["end"] == 1.9
    assert [x["word"].strip() for x in ws] == ["N18", "sonra"]


def test_videoref_extracts_in_chunks(tmp_path, monkeypatch):
    calls = []

    def fake(path, picks, tw, th, tmp):
        calls.append(list(picks))
        return {f: f"{tmp}/{f}.jpg" for f in picks}

    monkeypatch.setattr(videoref, "extract_chunk", fake)
    picks = list(range(0, 300, 3))                       # 100 frames
    got = videoref.extract_thumbs("v.mp4", picks, 30, 160, 90, str(tmp_path))
    assert len(got) == 100 and len(calls) == 3 and max(len(c) for c in calls) <= videoref.CHUNK


def test_learning_archive_keeps_template_and_prose(kk):
    p = kk / "learning" / "skill-change-requests.md"
    p.write_text("# Skill change requests\n\nFormat:\n\n```\n## <short title> (YYYY-MM-DD)\nStatus: open\n```\n\n"
                 "The maintainer sets `Status: done X.Y.Z` when it ships.\n\n"
                 "## Fixed thing (2026-11-01)\nStatus: done 2.2.0\n- x\n\n## Open thing (2026-11-02)\nStatus: open\n- y\n",
                 encoding="utf-8")
    out = k(kk, "learning-archive").stdout
    assert "moved=1 open=1" in out
    text = p.read_text(encoding="utf-8")
    assert "## <short title>" in text and "sets `Status: done X.Y.Z`" in text and "Open thing" in text
    assert "Fixed thing" not in text

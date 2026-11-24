"""2.5.0: storyboard.py (new / check / build / vocab), design.preview, preflight STORYBOARD line."""
import json
import os

from conftest import run
from test_v230 import kk, set_prefs  # noqa: F401  (kk is a fixture)


def scenes(**over):
    d = {"kind": "keremkit-storyboard", "version": 1, "title": "T",
         "comp": {"w": 1080, "h": 1920, "fps": 30},
         "tokens": {"colors": {"bg": "#000000", "accent": "#ffc800"}, "fonts": {"titles": "Montserrat-Bold"}},
         "scenes": [
             {"id": "S1", "name": "Hook", "dur": 2, "bg": "bg", "layers": [
                 {"id": "TXT_A", "type": "text", "text": "Hi </script>", "x": 540, "y": 400, "color": "accent",
                  "font": "titles", "in": {"anim": "slide-up", "t": 0.1, "dur": 0.5, "ease": "expoOut"}}],
              "transition": {"type": "push", "dir": "left", "dur": 0.4}},
             {"id": "S2", "name": "Count", "dur": 3, "layers": [
                 {"id": "CNT_U", "type": "counter", "from": 0, "to": 25000, "x": 540, "y": 900,
                  "in": {"anim": "count-up", "t": 0, "dur": 1.5, "ease": [0.16, 1, 0.3, 1]}},
                 {"id": "SUBJ", "type": "subject", "box": [200, 800, 880, 1920]}]}]}
    d.update(over)
    return d


def write(tmp_path, d, name="scenes.json"):
    p = tmp_path / name
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def test_check_ok_and_summary(tmp_path):
    res = run("storyboard.py", "check", write(tmp_path, scenes()))
    assert "OK errors=0 warnings=0 scenes=2 layers=3 transitions=1 duration=5.00s" in res.stdout


def test_check_catches_vocabulary_and_timing(tmp_path):
    d = scenes()
    d["scenes"][0]["layers"][0]["in"]["anim"] = "slidee"
    d["scenes"][0]["layers"][0]["out"] = {"anim": "fade", "t": 1.9, "dur": 0.5}
    d["scenes"][0]["transition"] = {"type": "push", "dir": "sideways", "dur": 2.5}
    d["scenes"][1]["layers"][0]["in"]["ease"] = "bouncy"
    d["scenes"][1]["layers"].append({"id": "BOX", "type": "box", "w": 10, "in": {"anim": "count-up"}})
    res = run("storyboard.py", "check", write(tmp_path, d), check=False)
    assert res.returncode == 1
    out = res.stdout
    assert "ERR S1/TXT_A.in: unknown anim 'slidee'" in out
    assert "WARN S1/TXT_A.out: ends at 2.40s" in out
    assert "ERR S1.transition.dur: 2.5s is longer" in out
    assert "ERR S1.transition.dir" in out
    assert "ERR S2/CNT_U.in.ease: unknown 'bouncy'" in out
    assert "ERR S2/BOX: type box needs 'h'" in out
    assert "ERR S2/BOX.in: count-up is for counter layers" in out


def test_build_writes_selfcontained_html(tmp_path):
    p = write(tmp_path, scenes())
    res = run("storyboard.py", "build", p, "--lang", "tr")
    html = (tmp_path / "scenes.html").read_text(encoding="utf-8")
    assert "OK ->" in res.stdout
    assert '<html lang="tr">' in html and "__DATA__" not in html
    assert "Hi <\\/script>" in html          # embedded JSON cannot close the script tag
    assert "http://" not in html and "https://" not in html.replace("https?:", "")   # offline
    data = html.split('id="kk-data">', 1)[1].split("</script>", 1)[0]
    assert json.loads(data.replace("<\\/", "</"))["scenes"][1]["id"] == "S2"


def test_build_refuses_on_error(tmp_path):
    d = scenes()
    d["scenes"][0]["dur"] = 0
    res = run("storyboard.py", "build", write(tmp_path, d), check=False)
    assert res.returncode == 1 and "nothing written" in res.stdout
    assert not (tmp_path / "scenes.html").exists()


def test_new_takes_style_tokens(kk, tmp_path):
    sd = os.path.join(kk, "styles", "demo")
    os.makedirs(sd)
    with open(os.path.join(sd, "style.json"), "w", encoding="utf-8") as f:
        json.dump({"look": {"palette": {"accent": [1, 0.5, 0]}, "fonts": [{"use": "titles", "font": "Inter-Bold"}]},
                   "layout": {"base_unit": 8}}, f)
    out = tmp_path / "sb" / "scenes.json"
    res = run("storyboard.py", "new", "-o", out, "--home", kk, "--style", "demo", "--format", "9x16",
              "--parts", "Hook: soru", "Kapanis")
    assert "scenes=2 comp=1080x1920@30" in res.stdout
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["tokens"]["colors"]["accent"] == "#ff8000"
    assert d["tokens"]["fonts"]["titles"] == "Inter-Bold"
    assert d["tokens"]["layout"] == {"base_unit": 8}
    assert d["scenes"][0]["layers"][0]["text"] == "soru" and "transition" in d["scenes"][0]
    assert "transition" not in d["scenes"][1]
    assert run("storyboard.py", "check", out).returncode == 0
    again = run("storyboard.py", "new", "-o", out, "--home", kk, check=False)
    assert again.returncode != 0 and "exists" in again.stderr


def test_vocab_lists_everything():
    out = run("storyboard.py", "vocab").stdout
    for word in ("LAYERS", "ANIMS", "TRANSITIONS", "EASES", "KEYS", "mask-reveal", "whip", "easyEase"):
        assert word in out


def test_preflight_storyboard_line(kk):
    out = run("keremkit.py", "--home", kk, "preflight", "ae-design").stdout
    assert "STORYBOARD design.preview=None" in out and "ask once" in out
    set_prefs(kk, design={"plan": "big", "preview": "off"})
    out = run("keremkit.py", "--home", kk, "preflight", "ae-design").stdout
    assert "STORYBOARD" not in out
    assert "STORYBOARD" not in run("keremkit.py", "--home", kk, "preflight", "cut").stdout

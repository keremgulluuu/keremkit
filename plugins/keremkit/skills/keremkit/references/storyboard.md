# Storyboard preview - show it before building it

Before a design with several scenes or transitions is built in After Effects, the user can see it as a small HTML player: the scenes, their timing, what moves and how the scenes join. Claude writes only a short `scenes.json`; `storyboard.py build` turns it into the player. Claude never opens the HTML or takes screenshots of it - the user looks.

Why: building blind in AE costs many batches and a wrong idea is found only at the end. A scene list costs a few hundred tokens, fixes the idea, and becomes the build plan.

Preference `design.preview` (null = never asked):
- `ask` - offer it once per design ("Önce sahneleri tarayıcıda göstereyim mi? (düşük maliyet)").
- `always` - make it after every plan, before any AE call.
- `off` - never.
Ask once, after the first `design-plan.md` plan with 2+ scenes or a transition: "Before building, I can show the scenes and transitions as a simple preview in your browser (low cost, not the final look). Always / Ask each time / Never?" -> `always` / `ask` / `off`. A user asking for a preview gets one whatever the preference says.

## 1. Where

`<project folder>/_keremkit/storyboard/scenes.json` (+ `scenes.html`). No project yet: `<paths.projects>/<name>/_keremkit/storyboard/`. Versions: `scenes_v2.json` when the user asks for a different idea; small changes edit the same file.

## 2. Write the scene list

1. `storyboard.py new -o <dir>/scenes.json --parts "Hook: ..." "Counter: ..." --format 9x16 --style SLUG` - comp size / fps, palette, fonts and layout tokens come from the style and preferences; one scene per plan part.
2. Fill it from the approved plan (`design-plan.md`) and the style. `storyboard.py vocab` prints every allowed value in 5 lines; use only those - the player and the AE build both know them.
3. `storyboard.py build <dir>/scenes.json --lang tr` (the user's language: `en` / `tr`). `build` runs `check` first and writes nothing on `ERR`.
4. Tell the user the HTML path in one line and how to answer ("sahne 2 daha uzun", "geçiş 1 flash olsun"). Wait for the answer; change the JSON, build again.

Edits are made with small JSON edits, never by rewriting the file.

## 3. The format

```json
{"kind": "keremkit-storyboard", "version": 1, "title": "...",
 "comp": {"w": 1080, "h": 1920, "fps": 30},
 "tokens": {"colors": {"bg": "#0e0f14", "accent": "#ffc800"}, "fonts": {"titles": "Montserrat-ExtraBold"}, "layout": {}},
 "scenes": [
  {"id": "S1", "name": "Hook", "dur": 2.5, "bg": "bg", "note": "what happens, in the user's words",
   "layers": [
    {"id": "TXT_Hook", "type": "text", "text": "...", "x": 540, "y": 420, "size": 110, "font": "titles", "color": "accent",
     "in": {"anim": "mask-reveal", "t": 0.15, "dur": 0.6, "ease": "expoOut"},
     "out": {"anim": "fade", "t": 2.1, "dur": 0.3},
     "keys": [{"t": 0, "y": 420}, {"t": 2.5, "y": 400, "ease": "linear"}]},
    {"id": "SUBJ", "type": "subject", "box": [240, 760, 840, 1920]},
    {"id": "FTG_Cam", "type": "footage", "label": "Camera"}],
   "transition": {"type": "push", "dir": "left", "dur": 0.5, "ease": "expoInOut"}}]}
```

- **Times** are seconds inside the scene. Scenes play one after another; a transition is **centred on the cut** (half its length at the end of one scene, half at the start of the next), the way an AE transition over the cut is usually placed.
- **Positions** are the layer centre in comp pixels, like an AE anchor at the centre. `layers[0]` is the top layer (AE layer 1).
- **Layer ids** are the AE layer names the build will use (`standards.md` prefixes: `TXT_ UI_ BG_ IMG_ ...`).
- **Colours / fonts** name a token (`"accent"`, `"titles"`) or give a value (`#hex`, a PostScript name). The player loads installed fonts by PostScript name; a missing font falls back to a system font - say so if it matters.
- **subject** (`design-plan.md` 0c box) and **footage** are grey stand-ins for the person / video; `image` without `src` is a labelled placeholder; `src` can be a local file (relative to the JSON).
- **Counter:** `from`, `to`, `decimals`, `sep` (thousands), `prefix`, `suffix`, animated with `count-up`.
- `in` / `out`: `anim`, `t`, `dur`, `ease`, plus `dist` (slides, px), `from` (scale-in), `amount` (blur), `fade: false` (slide without fade).
- `keys`: free movement of `x y scale rot opacity`, each key eased in from the previous one. In AE these keys go on the layer's rig (`CTRL_` null / `ADJ_` / Transform effect), never on the layer's own transform.

## 4. What the preview is not

An approximation: glass is a CSS blur, glows, 3D, particles, motion blur and library items with effects are not drawn (use a `box` / `image` placeholder with the library id as `label`). It is for timing, layout, order and the feel of transitions. Say this in the first message about it, once.

## 5. From preview to build

The approved `scenes.json` is the plan (`design-plan.md` §5): scene lengths and order, layer names, positions, in/out times, transition types and lengths are built as written. A change the build needs (a value that looks wrong in AE) is told to the user in one line, and the JSON is updated so the two stay the same. `qc.py ae-postcheck` still runs at the end.

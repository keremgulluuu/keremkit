# Quality control

Before a final render (and on "check everything"): `qc.mode` decides - `auto` (always run), `ask` (offer once per render, default), `off`.

## In After Effects (numbers only, one or two batches)

| Check | Operation | Issue when |
|---|---|---|
| Missing fonts | `font.list_missing` | anything listed |
| Offline footage | `footage.list_missing` | anything listed |
| Expression errors | `project.find_layers` + `layer.info summary` on suspects | error text present |
| Safe areas | `layer.bounds` for TXT_/SUB_/UI_/ICN_ layers at their mid time | outside title-safe |
| Gaps / overlaps | `comp.info` of the main comp | holes between clips, layers past the comp end |
| Text spelling | read text layer contents (`project.find_layers type: TextLayer`, contents from `layer.info summary`) | typos, wrong names (use the glossary) |
| Work area | `comp.info` | work area shorter than the edit |
| Names | layer/comp names vs `_keremkit/names.tsv` (`keremkit.py map name`) | the same thing under two names, or a name outside `standards.md` |
| Motion blur | switches of animated layers vs `motion.blur` (`motion-blur.md` §5) | off while the preference is `always`; layer switch in an Advanced 3D comp |
| Optimization | `HVY_` comps, `PLT_` layers, draft leftovers (`optimization.md` §9) | wrong heavy fps, Preserve frame rate off, collapsed `HVY_` layer, frame blending on; plate missing/stale/wrong alpha, `HVY_` and `PLT_` both visible; Draft 3D, effect switches off or proxies left on |
| Motion rig | animated layers' own Transform keys vs `motion.transform_rig` | element keys on its own Position/Scale/Rotation/Opacity while the rig is `parent_null` |

## AE postcheck - the gate before "done" (every AE build, unasked)

`ok:true` from a batch only says the ops ran. Before an AE build is called done:

1. `ae_project_export_json(outPath=<project>/_keremkit/export.json)`, then
   `qc.py ae-postcheck <export.json> --comp <main comp> [--style SLUG] [--samples s.json] [--bounds b.json --min-gap PX --edge PX --size WxH]`.
2. Checks: **FAIL** a banned SFX file in the project; **FAIL** a heavy effect (glows, CC Force Motion Blur, RSMB, CC Glass, Displacement, Fractal Noise, Particular, Element...) in a comp that is not inside an `HVY_` comp while `optimize.mode` is on; WARN an `HVY_` comp not at `optimize.heavy_fps`; WARN keys on an element's own transform while `motion.transform_rig` is `parent_null`; WARN a sampled colour far from the style palette (CIE dE > 12); WARN overlaps, gaps below the minimum, elements too close to the frame edge.
3. Colour and spacing need two small files from ONE batch: `comp.sample` at the rest frame of each `TXT_`/`UI_` layer -> `[{"layer","rgb"}]`; `layer.bounds` -> `[{"layer","left","top","width","height"}]`. Sample after the whole effect chain (fill -> toner -> contrast -> glow): the measured colour is what the viewer sees.
4. Any FAIL: fix it (or ask, when the fix changes the look) and run it again. "Done" only with no FAIL; WARN lines go to the user in the review checklist below.

## On the rendered file

`qc.py check <render>` -> one line per issue with its time: `BLACK`, `FROZEN`, `SILENCE` (long), `LOUDNESS` (off target), `TRUE_PEAK` (clipping risk), then a verdict line.

Intended black (fade to black at the end) and intended silence are fine - judge by position (start/end) and tell the user only real problems.

## Report

```
Kontrol: 2 sorun
- 00:41 - "SUB_Captions" title-safe dışına taşıyor (alt kenar)
- Ses -17.2 LUFS (hedef -14) -> normalize edeyim mi?
```

Fix what is mechanical (loudness, safe-area offsets) after one confirmation; spelling and content fixes are shown and asked.

## Review checklist (after every bulk update - always)

A bulk update = one job that added or changed several elements, clips or keys. Claude cannot judge the result by eye, so the user gets exactly where to look and what to look for:

```
Kontrol etmen gerekenler:
1. SCN_Main 52:00-54:15 - tedarik çizgileri: ışık noktaları çizginin üstünde mi, çıkış 54:15'te bitiyor mu?
2. SCN_Main 01:10:12 - iPhone ekranı: köşeler çerçeveye oturuyor mu, kenarda boşluk var mı?
3. PRE_Card_03 00:00-00:20 - giriş: diğer kartlarla aynı hızda mı?
```

- One line per check: comp or sequence name + time (with frames, `mm:ss` or `mm:ss:ff`) or range + the element + the concrete question.
- Every changed element gets at least one line; risky spots (new rigs, matched timing, things measured by numbers only) first.
- Put the same list into the session report and the project's `_keremkit/log.md` line (`project-map.md`).

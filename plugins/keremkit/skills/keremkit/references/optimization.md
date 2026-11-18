# After Effects optimization - fast previews, fast renders, nothing lost

On by default. Preferences (the user can change any of them; `keremkit.py pref set optimize.mode=off` turns all of this off):

| Key | Default | Values |
|---|---|---|
| `optimize.mode` | `on` | `on` / `off` |
| `optimize.heavy_fps` | `30` | frame rate of heavy precomps. 30 divides 60 evenly (every frame shown exactly twice); 24 in a 60 comp repeats 3-2-3-2 and judders on slow, smooth moves |
| `optimize.prerender` | `ask` | `ask` = render heavy plates only after the user's yes; `off` = keep heavy parts live |
| `optimize.intermediate` | `png` | `png` (PNG sequence, RGB+Alpha) / `prores4444` (alpha, big .mov) / `h264` (no alpha, plates without transparency only) |
| `optimize.screen` | `matte` | `matte` (screen matte pass + corner pin) / `green` (green-screen render, then key) |
| `optimize.setup_checked` | null | date the one-time AE settings checklist (§8) was given |

This file is mechanism, not taste: which element, move or look the edit has is the style's job. The style's frame rate, render format and the user's render rules always win; when a rule here would change how something looks, say so and ask.

A small mistake here can spoil a whole project (a stale plate, a wrong alpha, a frame-rate slip). Every step below has its check; never skip one.

## 1. Find what is heavy (before building, and when a preview is slow)

Heavy = any of these, measured, not guessed:
- 3D: Advanced 3D comps, GLB/OBJ models, extruded text/shapes, environment lights, many 3D layers with shadows.
- Heavy effects: glows (Glow, third-party glows), Gaussian/Camera Lens Blur on large areas, Displacement Map, Turbulent Displace, CC Glass, Fractal Noise, particle effects, Echo, Pixel Motion Blur, CC Force Motion Blur with many samples, Keylight, Lumetri stacks.
- Big textures: images larger than about 2x the size they are shown at, 4K+ footage, many large PNG layers.
- Dense animation: dozens of animated layers in one precomp, text animators on long texts, expressions with `valueAtTime` loops, `sampleImage`, or that read other comps.

How to find it cheaply: the precomp list from the project map or `digest.py`; effect names from `digest.py --deep`. The user can open the Composition Profiler (per-layer render time) - ask them for the top 3 lines when a comp is slow and nothing above explains it.

## 2. Heavy parts in their own lower-frame-rate precomp

1. Put each heavy part in a precomp named `HVY_<Name>` (`standards.md`), frame rate `optimize.heavy_fps`, size = the part's bounds + overscan (§6), not the full frame. Duration = what is used + about 0.5 s handles at each end (room to re-time).
2. Keep everything simple outside: footage, cuts, text, simple 2D moves stay in the main comp at its own rate (for example 60).
3. Two ways to use the `HVY_` comp in the 60 fps comp:
   - **Live (default while building):** the `HVY_` comp's Composition Settings → Advanced → "Preserve frame rate when nested or in render queue" on (`comp.set_props {preserveNestedFrameRate: true}`, then read it back - `ae-ops.md`: unknown keys return ok silently). AE then renders only 30 of the 60 frames of that part, in previews too.
   - **Plate (fastest, §3):** render the `HVY_` comp once, use the file.
4. Checks:
   - Collapse Transformations on the `HVY_` layer turns Preserve frame rate off silently. Never collapse an `HVY_` layer; if it must be collapsed, it is not an `HVY_` comp.
   - Frame Blending off on `HVY_` and plate layers (it would blend neighbouring frames into ghosts).
   - Time-stretch or time-remap of an `HVY_` layer at a non-integer speed breaks the even 2:1 cadence: re-time inside the `HVY_` comp instead.
   - Motion inside `HVY_` comps then moves in 30 fps steps. Fast moves inside them get motion blur there (§5) so the steps do not show.

## 3. Pre-render plates (only with the user's yes)

`optimize.prerender: ask` means: when the build is done (or a heavy part is finished and will not change), offer ONE question listing every plate: name, duration, frame count, format, estimated size, folder, ★ recommendation. The user's yes covers that list only. `off` = never offer. A render the user did not approve is never started (the user's render rules).

Plate render, step by step:
1. **Disk first:** free space on the target drive vs the estimate (PNG RGBA at 1080x1920 ≈ 3-5 MB per frame; ProRes 4444 ≈ 1.5-3 MB per frame). Not enough → say so, do not start.
2. **Folder:** `<project folder>/_plates/<HVY_name>_v###/` (a new version folder per render; never overwrite a plate in use).
3. **Settings:** Render Settings Best quality, Full resolution, frame rate = `optimize.heavy_fps` ("Use this frame rate", `ae-ops.md`), motion blur and effects "Current settings" on, work area = the `HVY_` comp's full duration. Output module: PNG sequence RGB+Alpha (`png`), Apple ProRes 4444 with alpha (`prores4444`), or H.264 high bitrate (`h264`, only plates with no transparency). Never AVI, never a lossless/uncompressed codec.
4. **Check the files:** frame count = duration × heavy fps (ffprobe or count the PNGs), first and last frame not empty (`ffmpeg` signalstats / alpha not all 0), no frames missing in the sequence numbering.
5. **Import:** interpret footage frame rate = heavy fps (AE imports image sequences at its default sequence rate, often 30 - set it explicitly anyway). Alpha: PNG → Straight; ProRes 4444 → as the output module wrote it (default Premultiplied with black). A wrong alpha interpretation gives dark or bright fringes, worst under glows.
6. **Swap, reversibly:** add the plate as `PLT_<Name>` directly above the `HVY_` layer, same in point and same transform, then switch the `HVY_` layer's video off (never delete it, never "Import & Replace Usage"). The user can go back by toggling two eyes.
7. **Match check:** `comp.sample` the same pixels at 3 times on the plate and on the live `HVY_` layer (switch them one at a time) - colour and position must match within a few levels. A gamma or colour shift means a colour-management mismatch: same project working space for the render, 8 bpc unless the project is 16/32.
8. **Log it:** `_keremkit/log.md` + map: plate path, source `HVY_` comp, render date, frame rate. Changing anything inside an `HVY_` comp later makes its plate stale: say so at once, and offer a re-render (new `_v###`).

## 4. 3D elements: build and render the 3D first, animate the plate in the final comp

The rule: what needs real 3D (rotation in depth, perspective, reflections) happens in the `HVY_` comp and is rendered as a plate; every 2D move (slide in/out, scale, position, 2D rotation, opacity, motion blur) is added to the plate afterwards in the final comp, where it costs almost nothing.

Example, phone mockup:
1. `HVY_Phone_Turn`: the phone model with the 3D move only, for example a left-to-right turn. Camera and lights fixed. Render with alpha.
2. Final comp: `PLT_Phone_Turn`, parented to `NULL_Phone`; slide in/out, scale, overshoot and motion blur keyed on the null (the user's motion rig, `standards.md`).
3. The screen content:
   - **Static during the 3D move** → put the screen design inside the `HVY_` comp; the plate already holds it.
   - **Changes later, is long, or is heavy itself** → `optimize.screen`:
     - `matte` (default, cleanest): render a second pass from the same `HVY_` comp, `HVY_Phone_Turn_Matte`: the screen plane pure white, everything else black, same camera, same frames. In the final comp the screen design precomp sits above the phone plate, uses the matte pass as a luma track matte, and is fitted with Corner Pin (below). No keying: no spill, no chewed edges, exact anti-aliased screen edges.
     - `green`: the screen plane is pure green (#00FF00, no reflections on it) in the render; key it in the final comp (Keylight), then choke 1 px and despill. Use it only when a matte pass cannot be made (for example the user gives a finished render).
   - **Corner Pin when the phone turns:** in the `HVY_` comp, 4 nulls at the screen corners take `toComp()` of the screen layer's corners; convert them to keyframes (`comp.sample` at every heavy-fps frame + `keyframe.apply`). The Corner Pin on the screen design reads those keys. The keys must step at the plate's frame rate (`posterizeTime(heavy_fps)` in the Corner Pin expression, or hold keys), otherwise the 60 fps pin slides against the 30 fps phone between frames.
   - **Glass on top:** reflections or the glass highlight over the screen as a third pass (screen layer hidden, reflection only), above the design in Screen or Add mode.
4. Static holds: when the 3D object stands still, render ONE frame (PNG) and hold it instead of rendering the 3D every frame.
5. Loops (turntables, idle spins, shines): render one cycle, then loop the plate (time remap + `loopOut("cycle")`, integer frame count per cycle).
6. Render plates at the largest size they are shown at: if the final comp scales a plate to 140 %, render the `HVY_` comp that much bigger, or the plate goes soft.

## 5. Motion blur and optimization

Mechanism and values: `motion-blur.md`. For speed:
- **After, not inside:** blur the final 2D move on the plate (layer switch + comp switch in the final comp) - cheap, because the plate is one flat layer. Do not add CC Force Motion Blur or Pixel Motion Blur on top of a 3D comp to get a 2D slide blurred.
- **Inside the `HVY_` comp** only for motion that exists only there (the 3D turn itself): comp motion blur in Classic 3D with Samples Per Frame as low as looks clean; in Advanced 3D layer blur is unsupported - render the plate without it, then blur the plate (CC Force Motion Blur on the plate layer, or a user plug-in from the user's own kit notes).
- Blur at 30 fps with shutter angle 180 streaks over 1/60 s - the same streak a 60 fps comp at 360 gives. That streak also hides the 30 fps steps.
- On the rig: the move on `NULL_`/`CTRL_` parents blurs the child (the child's switch must be on). A Transform effect used as the rig has its own shutter: "Use Composition's Shutter Angle" off, set its angle.
- Only layers that move fast enough to show a streak get the switch; slow drifts do not (cost, no visible gain).
- Text that must stay readable: lower angle (`motion-blur.md` table).

## 6. Glows, sparkles and 3D logos

- **Glow on what needs it only:** apply the glow to a small precomp of the glowing element (or an adjustment layer trimmed to the frames it is needed), never to a full-frame comp for the whole edit.
- **Separate glow pass:** for heavy glows, render element and glow as one plate, or the glow alone over black and add it back in Add/Screen mode. A static glow is rendered once.
- **Animate only what changes:** a glow whose intensity or radius pulses stays live (or is rendered as a loop); the parts that do not change are rendered.
- **Overscan:** a glow or blur reaches past the element's edge; the precomp gets padding (glow radius + 10 %) so the glow is not cut off at the comp edge.
- **Sparkles and shines:** particle sparkles, CC Light Sweep and shine passes are rendered once per cycle and looped; many sparkles = one plate, not many live layers.
- **3D logos:** the extrusion, bevel and reflections are rendered as a plate (turntable or intro move); the logo's hold is a single frame; the logo's 2D entrance and exit run on the plate in the final comp. Reflections need an environment light, which scripts cannot set (`ae-ops.md`): ask the user once.
- Effects without Multi-Frame Rendering support show a yellow warning in Effect Controls and slow the whole render: tell the user which; plate them.

## 7. General rules (every build while `optimize.mode` is on)

- **Comp size = delivery size** (never a 4K comp for a 1080 delivery). Precomps only as big as their content plus overscan.
- **Bit depth 8 bpc** unless the style or a look needs 16/32 (banding in gradients, HDR work): 16 bpc is about twice the memory, 32 bpc much slower.
- **Big stills:** scale images larger than about 2x their on-screen size down with ffmpeg before import (keep the original next to it). Vectors (.ai, .svg): Continuous Rasterize only when scaled above 100 %.
- **Trim everything to where it is visible:** adjustment layers, effect layers, overlays and layers fully covered by others end where they stop being visible (layer in/out), instead of running the whole edit at opacity 0 or hidden underneath. A layer not needed at all is switched off, not set to opacity 0.
- **Expressions:** heavy ones (loops over `valueAtTime`, `sampleImage`, reading other comps, wiggles linked across many layers) get `posterizeTime()` at the needed rate, or are baked to keys (`comp.sample` + `keyframe.apply`) once final.
- **Effects:** GPU-accelerated effects first where they give the same look (Gaussian Blur, Fast Box Blur, Lumetri). Heavy effects at the end of the stack after crops and masks, so they process fewer pixels. Masks with large feather and Motion Tile with big output only where needed.
- **Duplicates share one source:** many copies of the same element = one precomp used many times (AE caches it), not many separate copies of its layers.
- **Footage:** 4K or long-GOP footage that previews slowly → the user can make proxies (Create Proxy) - offer it; proxies off for the final render (QC).
- **Viewer:** before big batches, set the viewer to a small comp (`standards.md` → After Effects speed).
- **What is never changed for speed:** final render quality (Best, Full), motion blur in the final render, layer quality, resolution or effect switches left in draft. If preview speed tricks are used while building (Draft 3D, effect switch off, quarter resolution), they are logged and undone before the final render (QC).

## 8. One-time AE settings checklist (the user sets these; scripts cannot)

The first time an AE build runs while `optimize.setup_checked` is null, give the user this list once, then `pref set optimize.setup_checked=<date>`:
1. Edit → Preferences → Memory & Performance: Multi-Frame Rendering on; RAM reserved for other apps as low as the machine allows.
2. Preferences → Media & Disk Cache: disk cache on the fastest SSD, as large as possible (50-100+ GB), not on the system drive if another SSD exists. "Empty Disk Cache" when it fills or previews show stale frames.
3. File → Project Settings → Video Rendering and Effects: Mercury GPU Acceleration (CUDA on NVIDIA cards).
4. Preferences → Previews: Cache Frames When Idle on.
5. Keep the GPU driver current (Studio driver on NVIDIA).
6. Preview with Adaptive Resolution / Fast Previews and region of interest while working; Draft 3D in Advanced 3D comps (it can crash with GLB models on some versions - turn it off if AE hangs).

## 9. QC before the final render (`qc.md` → Optimization)

- Every `HVY_` comp: frame rate = `optimize.heavy_fps`, Preserve frame rate on, its layer not collapsed, frame blending off.
- Every `PLT_` layer: its plate exists on disk, frame count right, alpha interpretation right, newer than the last change to its `HVY_` comp (log), its `HVY_` layer switched off (not deleted) - never both visible.
- Nothing left in draft: Draft 3D off for the final, effect switches back on, proxies off, layer quality Best.
- Screen designs on turning 3D objects: corner pin posterized to the plate's rate.

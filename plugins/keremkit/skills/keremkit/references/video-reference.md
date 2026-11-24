# Learning from a reference video

The user gives a finished video and wants its style, rhythm or a recreation in After Effects. Claude cannot watch video; it reads frames as images, which are expensive. So code measures first and Claude looks only where it matters.

## 1. Package the video

`videoref.py <video> -o _keremkit/ref_<name>` (ffmpeg + standard library, a few seconds for a short reel) writes:
- `README.md`: shots with start/end/duration (cuts found from frame differences), motion windows inside each shot, main colours per shot, audio loudness and onsets (and how many land on cuts), the list of sheets with their token cost;
- `sheets/00_overview.jpg`: one frame per shot;
- `sheets/shotNN*.jpg`: start/middle/end of each shot and the frames where something moves (up to 12 per motion window), each stamped with its time;
- `data.json`: the same plus the frame-by-frame motion curve.

Also transcribe the video with Whisper (`transcript.md`) when it has speech: words + timing explain most cut points and caption styles.

Tuning: `--cut` (default 28) lower finds softer cuts/dissolves; `--move` (default 2.5) lower catches subtler motion; `--max-motion-frames` raises density for fast animations.

## 2. Read it economically

1. Read `README.md` (text).
2. Open `00_overview.jpg` once.
3. Open shot sheets only for the shots the question is about. A 15 s reel is typically ~9k tokens for all sheets; most questions need two or three.
4. Never open the original video frames one by one.

## 3. Turn it into reusable knowledge

- **Rhythm**: shot durations and the cut/onset alignment -> the style's `editing.rules` (`edit-plan.md`) and SFX rules (`sound-effects.md`).
- **Look**: colours from the README, type and layout from the sheets -> tokens (`design-import.md`) and the style's `look`.
- **Motion**: a motion window's frame count and the positions across its frames give duration and easing (fast start + long settle = ease-out). Match them to techniques (`techniques.py list`) or build library items.
- Confirm with the user in a compact list before building, as with any design import.

## 4. Limits - tell the user up front

- Real footage (people, places) cannot be recreated; the user supplies their own or generates replacements.
- Plugins and presets used in the original are unknown - effects are rebuilt with built-in tools. A font that cannot be identified or installed is reported as missing (§5), never silently replaced.

## 5. Clone mode - "make it exactly like this"

When the user asks for a one-to-one copy of a reference (a clone, "birebir", "aynısı"), the steps above are not enough. Clone mode:

1. **From scratch, from measurements.** No remembered element, no library item, no technique preset is applied as the element. Every element is designed from zero from what the reference shows: size, position, corner radius, stroke, colour (sampled, not guessed), gradient stops, shadow / glow size and opacity, blur.
2. **Frame to frame.** For each element, take the frames of its motion window at the reference frame rate (`videoref.py ... --max-motion-frames` high enough for every frame) and measure per frame: box, position, scale, opacity, blur, colour. Turn the series into keyframes and easing (`ae-ops.md` for the ops). A ready pop / fade / bounce is never a substitute for a measured curve.
3. **Exact font.** Crop the reference glyphs at full resolution and compare candidates glyph by glyph (shapes of a, g, R, numerals, terminals, width). Use the exact family and weight; when it is not installed, download it (`assets.md`) or tell the user it is missing. Also measure tracking, leading, fill, gradient, stroke, shadow / glow.
4. **Compare after every step.** Render the same time from the clone and put it side by side with the reference frame (and a difference image: `ffmpeg ... -filter_complex "[0][1]blend=all_mode=difference"`). Fix what differs before the next element. Before delivery, every scene is checked at the same times side by side; the session report lists the times compared.
5. Say in one line what could not be matched (footage, unknown plugin, missing font) instead of approximating it silently.
- Recreating someone else's video one-to-one for publishing can infringe their rights; learning the style and applying it to the user's own content is the intended use.

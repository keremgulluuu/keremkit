---
name: keremkit
description: KeremKit - editing kit for Claude in After Effects and Premiere Pro. Remembered preferences, whole edits from a named edit style (learned from projects with a full checklist), design plans that reuse a library first, audio-based silence cutting with retake removal, transcript correction, edit plans on word indices, techniques (J/L cuts, jump-cut zoom, audio clean-up, formats, QC), Whisper/CrisperWhisper subtitles, SFX, a design library with previews, free stock elements with licences (photos, video, textures, vectors and .ai sources, icons, logos, 3D, Lottie, fonts, sound), copying a look from references, .ffx presets, Premiere XML/MOGRT/MCP builds, video downloads (YouTube, TikTok, Instagram) with a Premiere-safe mode and repair, and token budgeting with cost estimates. Use it for ANY After Effects or Premiere work, footage or element downloads, in any language, even when the kit is not named.
license: MIT
compatibility: After Effects MCP (ae_do / ae_catalog / ae_context; tested with @kumoproductions/mcp-aftereffects); optional Premiere MCP (premiere-pro-mcp); shell access to the user's computer; Python 3.9+, ffmpeg; Whisper for subtitles; yt-dlp is installed by the kit.
---

# KeremKit

Makes Claude edit in After Effects and Premiere Pro like a disciplined editor who remembers everything (preferences, named styles, a design library, past problems) while spending as few tokens as possible.

## Language

- Reply in the language the user writes in (`language.reply` can override). Translate the English question templates naturally; never mix languages in one message.
- Keep replies short: what was done, 1-3 lines.
- **Every question explains itself:** what was found (file/comp/time), why it is asked, the options and what each does, your pick marked ★. Never a bare yes/no (`references/preferences.md`).
- **State only what was checked on the user's machine.** Never suggest backups, recovery, sync or version history that were not verified there.
- Library, category and style names: English `name` + local `names` (`language.library`, from the user's language).

## The KeremKit home folder

Folders: settings/ (preferences.json, null = never asked), library/ (CATALOG.tsv - search it, never read it whole), styles/, assets/, learning/, tools/, extensions/, models/ (`references/setup.md` §1).

- Find it with `python <this skill's folder>/scripts/keremkit.py where`; then use `<home>/tools/` ("tools/x.py" below). `NOT_SET_UP` or first request: `references/setup.md`.
- **Remember the locations:** with persistent memory, save the output of `keremkit.py where --all` once as ONE memory "KeremKit locations"; update that memory when a location changes, never add a second. Later sessions confirm it with a plain `where`.
- **Tools version:** once per session run `keremkit.py version` (this skill is `KeremKit 2.5.0`). If it differs, say so in one line; update the tools only when the user asks.
- **Tools:** keremkit.py, transcript.py, cutlist.py, subtitles.py, editplan.py, audio.py, sfx.py, qc.py, techniques.py, tokens.py, presets.py, videoref.py, previews.py, storyboard.py, assets.py, digest.py, prproj.py, download.py, prbatch.py. They are plain Python (standard library) plus ffmpeg; on Windows the command may be `py`.

## No edit templates - the user's styles decide

The kit gives nobody an edit template. Every creative or taste rule (timings, SFX placement, animations, transitions, looks, text sync, framing) belongs to the style the user names (ask which if unclear), or to `custom_rules` when the user says it is for every edit. The references describe mechanisms, not taste.

## The skill is read-only - the kit grows in the home folder

Never edit, repackage or re-version this skill or `KeremKit/tools/`. Techniques → `techniques.py add`; new tools → `extensions/<id>/`; rules → `custom_rules` / `pref set`; solved problems → `learning/known-issues.md`; designs → the library. A real bug or missing mechanism in the skill (never a taste rule) → `learning/skill-change-requests.md` (format: `references/token-budget.md` §5), plus one line to the user.

## Gates: preflight first, postcheck last

- **Preflight:** the first tool call of every build, edit or SFX job is `keremkit.py preflight <task> [--style SLUG] --request "<the user's words>"` (tasks: ae-design, ae-build, sfx, edit, cut, subtitles, premiere, download, library). Its output - golden rules, the request as numbered items, named functions resolved to ids, banned files, custom_rules, prefs, style tokens, the gate - is the checklist; it beats memory.
- **Request first:** no edit before the request is split into items. A named function / technique / library item = exactly that one, its steps verbatim; nothing outside the request; an unclear word -> that function's own definition, else ask. The final reply lists each item done / not done.
- **Order when instructions meet:** explicit instruction in this request > the user's hand fixes > the named style > library defaults > Claude's choice. A real conflict with no instruction is asked, never resolved silently.
- **Postcheck:** an AE build is done only when `qc.py ae-postcheck` shows no FAIL: keys on an element's own transform, a layer without a colour label, precomp-in-precomp, heavy effects outside `HVY_`, banned SFX (`references/qc.md`). SFX files are chosen only from `sfx.py filter` output.
- **Cloning a reference** = from scratch, measured frame to frame, exact font (`references/video-reference.md` §5).

## Preferences - remember everything, ask once

- Before anything that depends on a choice, read it with `keremkit.py pref get <key>`. Never assume a value.
- `null` = never asked: ask once, when first needed (`references/preferences.md`), and save at once.
- A lasting preference said in passing is saved and confirmed in one line.
- Style settings override global ones.

## Token rules (always on)

1. **Estimate first.** Before every operation, say the expected cost in one line: `Tahmini token: az / orta / çok` (in the user's language), with a total for a multi-step plan. Classes and typical costs: `references/token-budget.md`.
2. **No screenshots by default.** Verify with numbers (`references/verification.md`); previews and contact sheets are for the user.
3. **AE / Premiere the cheap way** (`references/token-budget.md` §2-3): AE ops in one `batch.run` (names: grep `ae-ops.md`); Premiere over ~5 calls → `prbatch.py`, writes one at a time.
4. **Preview before building:** a multi-scene design is shown as a storyboard first (`references/storyboard.md`, `design.preview`).
5. **Heavy work runs locally** (Whisper, transcript.py, cutlist.py, subtitles.py, ffmpeg). Read their short results, never media or raw JSON.
6. **Search, don't read:** `keremkit.py find <words>` before designing, downloading or analysing; one reference at a time; resume from the project map (`references/project-map.md`).
6b. **One feedback round = one session;** generated ops go to a file, never inline (`references/token-budget.md` §4).
7. **Same method failed twice → stop** and report: what, error, likely cause, proposal.
8. **Bulk change:** try it on one item, then apply to all.

## After every task (always)

1. Append to `learning/token-notes.md`: what was expensive, what saved tokens, and proposals. Write it plainly and completely, without asking; mistakes included.
2. Write the session report `learning/sessions/<date>-<topic>.md` (done, files, decisions, open items, how to continue). Give the user its path in one line.
3. A new problem solved → one entry in `learning/known-issues.md`.
4. Project work → update its map and log (`references/project-map.md`). A bulk update → give the user the review checklist: comp + time + what to look at (`references/qc.md`).

Formats: `references/token-budget.md` section 5.

## Safety: checkpoints, saves, stop rules

- **Checkpoints:** before anything hard to undo, save a numbered copy `<Project>_v###.aep`, at most one per task. Small edits need none.
- **Never reduce or rebuild in the user's own file.** `project.reduce` runs only on a `keremkit.py save-prep` copy. Premiere work runs on a `safe-copy` of the .prproj.
- **Saves are proven on disk:** `keremkit.py stat` / `save-check`. `saved:true` alone is not proof. Create folders first.
- **Stop rule:** an answer that contradicts the expected state (no file after a save, wrong `project.file`, undo that changed nothing, a recovery lock) stops all host calls. Rescue-save to `library/_work/`, `stat` the user's files, report in 2-3 lines and ask.

## Naming

ASCII `PREFIX_PascalName[_01]` inside AE (comps `SCN_ PRE_ LIB_`, layers `TXT_ UI_ BG_ CTRL_ NULL_ ADJ_ ...`; `references/standards.md`). One thing, one name in a project: `keremkit.py map name`. Premiere names follow `premiere.project_naming` / `sequence_naming`.

## What to read when

| Situation | Read |
|---|---|
| First use, `NOT_SET_UP`; a preference is null or stated | `references/setup.md`; `references/preferences.md` |
| Cost estimates, token notes, session reports | `references/token-budget.md` |
| A named edit style, new style, learning one | `references/edit-styles.md` |
| Speech: transcribe, fix words, retakes, wordless speech; cut silences | `references/transcript.md`, then `references/cutting.md` |
| Voice-led edit with many shots | `references/edit-plan.md` |
| A reference video to learn from or clone | `references/video-reference.md` |
| Subtitles; sound effects; audio clean-up, music | `references/subtitles.md`; `references/sound-effects.md`; `references/audio.md` |
| Free elements (photo, video, vector/.ai, icon, logo, 3D, Lottie, font, sound) | `references/assets.md` |
| A design with several parts; copying a look | `references/design-plan.md`; `references/design-import.md` |
| Scene / transition preview before building | `references/storyboard.md` |
| Effect presets (.ffx); techniques, "what can you do with ...?" | `references/presets.md`; `references/techniques.md` |
| More formats (9:16, 1:1...); chapters, titles, export | `references/formats.md`; `references/publish.md` |
| AE postcheck, before the final render | `references/qc.md` |
| Layer order, names, colour labels, precomping | `references/organize.md` |
| Resuming a project, brand kit, canonical names | `references/project-map.md` |
| AE op parameters, Advanced 3D pitfalls; motion blur | `references/ae-ops.md`; `references/motion-blur.md` |
| AE speed: heavy parts, plates, slow renders | `references/optimization.md` |
| Premiere Pro (XML, MCP, MOGRT, .prproj) | `references/premiere.md` |
| Downloading a video, Premiere fix, 4K + repair | `references/downloads.md` |
| Saving to the library / a pack; placing a saved item | `references/library-save.md`, `references/library-pack.md`; `references/library-use.md` |
| Previews; the user asks to look / screenshot | `references/previews.md`; `references/verification.md` |
| Project structure, safe areas, motion, render | `references/standards.md` |
| Something failed | `references/troubleshooting.md` |

## Always-on habits

- A design with several parts starts with a numbered plan and layout tokens (`references/design-plan.md`).
- Offer once to save a reusable element. After an edit, ask once whether to save what was learned.
- Tidy layers after an edit (`organize.md`) unless `organize.mode` is off.
- **AE builds are optimized** while `optimize.mode` is on: heavy parts in `HVY_` precomps at `optimize.heavy_fps`, plates only after the user's yes (`references/optimization.md`). Moves go on a null / ADJ_ / Transform effect (`motion.transform_rig`). Library colours are remapped, never overlaid (`references/library-use.md`).
- **Project map** `_keremkit/` next to the project (`keremkit.py map`): log, map, canonical names, brand kit. Read it by search first when resuming; new elements reuse its brand kit.
- Something broken on the user's machine → `keremkit.py doctor`. First library use in a session → `previews.py scan --brief`.

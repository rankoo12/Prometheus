# CLAUDE.md — Prometheus

Automated Rocket League clip auto-editor. **Design source of truth: [rl-editor-spec-v1.md](rl-editor-spec-v1.md).** Read it before non-trivial work; flag and ask before deviating from it.

## How we work (non-negotiable)
- **SDD** — design the seams and contracts before implementation; prove the risky parts in isolation. Confirm contracts before scaffolding broadly.
- **SOLID** — Single Responsibility + Open/Closed especially: new event types or styles are added as data or as new `Source`/`Handler` subclasses, never by editing existing stages.
- **Iterate before code**, and give honest critical evaluation over agreement — flag bad ideas directly.
- **Keep docs current** — after a decision or a phase, fold it back into this file, the spec, and the README so the project state is always clear. Spec changes go via PR.
- **Commits and PRs carry no Claude attribution.**

## Architecture — three stages that never bleed (spec §3)

```
SOURCES  → Event[]            detect events (CV / Whisper)
HANDLERS → EditInstruction[]  turn events into edit instructions (read the Profile)
RENDERER → final .mp4         assemble + run FFmpeg
```

- Backend (Python) owns detection, Whisper, FFmpeg, music. Frontend (Electron + TS) owns all UI.
- Transport: **stdio JSON-RPC 2.0**, newline-delimited JSON. stdout is RPC-only; all logs go to stderr.
- **Profile** is the styling contract: a validated JSON document in `contracts/` (the JSON Schema is the single cross-language source of truth). Style is data, never hardcoded.

## Layout

```
contracts/   Profile JSON Schema + default document
backend/     models, sources, handlers, render, music, api (rpc + commands), detection, probe.py, tests
frontend/    Electron + TS: main (+ python-bridge), preload, renderer, shared
```

## Commands

Backend (from repo root):
```
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python -m pytest backend\tests
```
Frontend (from `frontend/`): `npm install`, then `npm run build`, then `npm start`.

## Environment notes (Windows)
- Requires **ffmpeg/ffprobe** on PATH, or set `PROMETHEUS_FFPROBE` to the `ffprobe.exe` path.
- If `electron .` crashes with `Cannot read properties of undefined (reading 'handle')`, the shell has `ELECTRON_RUN_AS_NODE=1` set (some VS Code terminals do) — launch from a clean terminal or clear that variable.

## Status
- **Phase 0 — complete.** Shared contracts (`Event`, `EditInstruction`, `Profile`) + a `probe()` stdio round-trip, verified through the Electron UI on a real 1080×1920/60 clip.
- **Phase 1 — boost detection (the go/no-go risk gate).** Complete (validated). The HUD is a
  BakkesMod-style boost panel (bottom-left of the gameplay area), so the gauge region +
  digit templates are tuned to that, not the spec's placeholder coords. Pipeline: crop →
  Otsu binary → segment (drop edge dial-arc, size/merged-digit filters) → per-digit
  template match → value series → median smooth + physical drop-rate despike → upward-jump
  detection + animation-aware debounce → +12/+100 by result or rise size (a big pad grabbed while boosting may peak below 100, but the large
  rise still classifies it big). Digit recognition is
  **multi-exemplar 1-NN** over a bank of real glyphs (`detection/templates/<digit>_*.png`)
  on canonical grayscale fingerprints. The overlay *animates* the number up over several
  frames, so a whole climb-then-settle is collapsed into one pickup at its peak. Bank is ~171
  glyphs from 2 labeled clips; timelines validated against user ground truth (big +100 / small
  +12 correct; the 5/6 misreads that caused false +12s removed; near-full grabs like 96->100
  are below the rise threshold by design, review-absorbed). Tools: `boost_timeline` (text),
  `verify_pickups` (montage), `preview_overlay` (burns markers onto the clip). Diagnostic
  tooling is in the session scratchpad. See spec §6.1.
- **Phase 2 — boost overlays (SFX dropped, no sound files).** Complete (validated, PR #5).
  `BoostHandler` → ASS `+12`/`+100` pop above the gauge (Profile-driven position/color/animation)
  → `ass_builder` → `Renderer` (FFmpeg burns the overlay) → end-to-end render, validated on a real
  clip (+12/+100 appear above the gauge with pop+fade). No audio/SFX. **Carry-forward gaps** (to
  fold in before/with the Settings UI): the Profile has no `boost.text.size` yet (handler defaults
  to 72px), and `font_file` is a placeholder (Arial fallback at render — bundle a real font).
  All style is Profile data, so position/color/size/font/animation become editable in **Phase 6
  (Settings UI)** — the visual editor the user wants. See spec §7.1.
- **Phase 3 — goal detection + effects.** Detection complete & validated (9/9 on labelled clips);
  effect handler (flash) next; slowmo deferred to its own slice. Pipeline: `GoalSource` reads the
  two scoreboard digits by **shape-matching a small exemplar bank** (`detection/score_templates/`,
  0–4 so far) — robust to the score box's *semi-transparent background bleed* that defeats naive
  pixel-diffing → a goal = a confirmed score **increment** (debounced; replay None-gaps skipped).
  Ownership is by **position, not colour**: the user's team is always the LEFT box (colour varies —
  blue/orange/gray club) → `side` = `your_team` (left) / `opponent` (right). `GoalScorer` then tags
  each team goal `scorer` = `you` / `teammate` via the **"&lt;NAME&gt; SCORED!" banner** (PRIMARY —
  matches the user's fixed name, one template not OCR; appears at the goal so it survives short
  clips) + the **"GOAL +100" popup** (BACKUP, name-independent, appears ~2-3s late). Banks live in
  `detection/scorer_templates/{name,popup}/`. Tools: `goal_timeline` (text), `goal_preview` (burns
  YOU/ASSIST/OPP markers). Detection method pivoted from the spec's scene-change idea to scoreboard
  reading (semantically stronger, no false fires on cuts/saves). See spec §6.2. Carry-forward: digit
  bank needs scores ≥5; multi-user name input is future work.
  **Goal effect (flash slice — done):** `GoalHandler` → white **flash** (full-frame ASS box) +
  **"GOAL!"** text pop, Profile-styled (`goal.scope=your_goals` → only the user's own goals fire
  it; assists/opponent get nothing). `ass_builder` refactored to **per-event inline styling**
  (boost/goal/captions each carry their own look; payload `type:"flash"` draws the box) — boost
  output unchanged. Tool: `render_goal`. **Slowmo (done):** GoalHandler emits a `RETIME_SEGMENT`
  per celebrated goal (`goal.slowmo`); the `Renderer` splits/retimes the clip (setpts/atempo +
  concat), **re-times every overlay onto the output timeline** (`render/retime.py` — pure
  `remap_time`, since slowing a span shifts all later timestamps), burns them, and forces CFR
  (the slowed span is VFR). See spec §7.2. **Phase 3 complete** (detection + scorer + flash/GOAL!
  + slowmo, all validated).
- **Phase 4 — captions.** Complete & validated. `CaptionSource` runs **faster-whisper** (`base.en`,
  CPU int8; `detection/caption_config.py`) → `CAPTION_WORD` events (word-level timings).
  `CaptionHandler` groups words into lines of `words_per_chunk`, **breaking on pauses > 1s** so a
  line never spans a silence. `ass_builder` renders a lower-third **`\k` karaoke** line (each word
  flips `base_color`→`active_color` as spoken; Primary=active/Secondary=base) with optional pop-in.
  Tool: `render_captions`. Validated end-to-end (word-by-word highlight, e.g. "**Nice** shot" on the
  goal). `faster-whisper` added to requirements; `captions.size` added to the Profile. See spec
  §6.3/§7.3. GPU (CUDA) decode/transcribe is a later perf option.

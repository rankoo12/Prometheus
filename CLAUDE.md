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
- **Phase 1 — boost detection (the go/no-go risk gate).** In progress. The HUD is a
  BakkesMod-style boost panel (bottom-left of the gameplay area), so the gauge region +
  digit templates are tuned to that, not the spec's placeholder coords. Pipeline: crop →
  Otsu binary → segment (drop edge dial-arc, size/merged-digit filters) → per-digit
  template match → value series → median smooth + physical drop-rate despike → upward-jump
  detection + animation-aware debounce → +12/+100 by result. Digit recognition is
  **multi-exemplar 1-NN** over a bank of real glyphs (`detection/templates/<digit>_*.png`)
  on canonical grayscale fingerprints. The overlay *animates* the number up over several
  frames, so a whole climb-then-settle is collapsed into one pickup at its peak. Bank is ~171
  glyphs from 2 labeled clips; timelines validated against user ground truth (big +100 / small
  +12 correct; the 5/6 misreads that caused false +12s removed; near-full grabs like 96->100
  are below the rise threshold by design, review-absorbed). Tools: `boost_timeline` (text),
  `verify_pickups` (montage), `preview_overlay` (burns markers onto the clip). Diagnostic
  tooling is in the session scratchpad. See spec §6.1.

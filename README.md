# Prometheus — RL Clip Auto-Editor

Automated Rocket League clip editor. Detects gameplay events (boost pickups, goals),
overlays styled effects + SFX + karaoke captions, and exports a near-finished short for
final polish in CapCut.

The full design lives in [rl-editor-spec-v1.md](rl-editor-spec-v1.md) — **that is the
source of truth.** This README only covers how to run what exists today.

## Architecture (the core seam)

Three stages that never bleed into each other (spec §3):

```
SOURCES  ──► Event[]            detect events (CV / Whisper)
HANDLERS ──► EditInstruction[]  turn events into edit instructions (read the Profile)
RENDERER ──► final .mp4         assemble + run FFmpeg
```

- **Backend** (Python) owns the heavy work: CV detection, Whisper, FFmpeg, music fetch.
- **Frontend** (Electron + TypeScript) owns the UI and talks to the backend over
  **stdio JSON-RPC**.
- The **Profile** (`contracts/profile.*.json`) is the styling contract between them.
  All stylistic values live there, never in code.

## Status — Phase 0 (skeleton)

Implemented:
- Shared contracts: `Event`, `EditInstruction`, `Profile` (`backend/models/`).
- stdio JSON-RPC transport with one working round-trip: `probe(clip_path)`.

Exit criterion: Electron calls Python over stdio JSON-RPC and gets a clip's
duration/width/height/fps back via `probe()`.

## Prerequisites

- Python 3.11+
- Node.js 20+
- **ffmpeg / ffprobe** on `PATH` (or set `PROMETHEUS_FFPROBE` to the ffprobe binary).

## Setup

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python -m pytest backend\tests
```

Frontend:

```powershell
cd frontend
npm install
npm run build
npm start
```

`npm start` launches the Electron shell; pick a clip and it round-trips through the
Python backend via `probe()`.

## Layout

```
contracts/   cross-language Profile contract (JSON Schema + default document)
backend/     Python: models, sources, handlers, render, api (JSON-RPC)
frontend/    Electron + TypeScript app shell
```

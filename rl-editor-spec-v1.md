# RL Clip Auto-Editor — Master SDD Specification (v1)

**Project codename:** Prometheus
**Author:** Ran (with Claude)
**Status:** Draft v1 — build bible for implementation in Visual Studio
**Last updated:** 2026-06-29

---

## 0. Purpose of this document

This is the master Software Design Document (SDD) for an automated Rocket League clip editor. It is written to be carried into Visual Studio and used as the reference Claude (and you) build against. It defines scope, architecture, module boundaries, interfaces/contracts, the configuration model, and a risk-first phased roadmap.

It follows two guiding rules throughout:
- **SOLID** — especially Single Responsibility (each module does one thing) and Open/Closed (new event types and styles are added as data or new handlers, never by editing existing code).
- **SDD** — design the seams and contracts before writing implementation, so the risky parts can be proven in isolation.

---

## 1. Product overview

### 1.1 What it does

The tool ingests raw Rocket League clips (full ~30s captures), lets the user trim them, automatically detects gameplay events from the video, overlays styled effects + sound effects keyed to those events, optionally adds karaoke-style captions and a music track, stamps a Twitch thumbnail/badge template, and exports a near-finished short. The user then takes the export into CapCut for final polish.

**The tool's job is to kill the tedious detection-and-placement grind. CapCut remains the finishing room.**

### 1.2 What it explicitly does NOT do

- It does **not** replace CapCut. Final creative polish stays manual.
- It does **not** detect ball touches, assists, or demos. These have no reliable on-screen indicator in gameplay footage; detecting them from pixels alone is research-grade and unreliable. **Scope is limited to boost pickups and goals**, which are reliably detectable.
- It does **not** parse replay files. (Considered and rejected — see §1.3.)
- It does **not** pick or license music. It can fetch audio the user points it at; sourcing/licensing is the user's responsibility.

### 1.3 Key rejected decision: replays

Replay parsing (carball/rattletrap) would yield perfect event data for every event type. It was rejected because it requires saving and syncing `.replay` files to each clip, which complicates the capture workflow the user wants to keep simple. **Consequence:** detection is video-based, which constrains scope to boost + goals. This is an accepted trade.

> **Architectural note:** Because the design isolates event *sources* behind an interface (§3), replay parsing can be added later as an alternative source without touching handlers or rendering. The door is left open even though it's not built.

---

## 2. Scope (v1)

| Capability | In v1 | Notes |
|---|---|---|
| Import full clips | ✅ | ~30s captures, 1080×1920/60fps |
| In-app trim (in/out points) | ✅ | Per clip, before processing |
| Boost pickup detection | ✅ | Video CV — the risky core |
| Goal detection | ✅ | Video CV — easier than boost |
| Boost "+12/+100" text + pop animation | ✅ | ASS overlay, configurable |
| Boost SFX | ✅ | Event→SFX mapping |
| Goal effects + SFX | ✅ | Event→SFX mapping |
| Karaoke captions (EN) | ✅ | Whisper word-timing + ASS |
| Twitch thumbnail/badge template | ✅ | Static overlay from profile |
| Attach music track | ✅ | User-supplied or fetched file |
| Music fetch (yt-dlp) | ✅ (neutral) | User responsible for sourcing/licensing |
| Export for CapCut | ✅ | Full 1080×1920/60fps |
| Settings UI (profile editor) | ✅ | Colors, placement, SFX map, caption style, animation |
| Ball touch / assist / demo detection | ❌ | No reliable video signal |
| Replay parsing | ❌ | Workflow cost; door left open |
| Auto song selection / trend detection | ❌ | Manual, by design |

---

## 3. Architecture

### 3.1 The core seam

The entire design rests on one principle: **separate detecting events from acting on events from rendering.** These three stages never bleed into each other.

```
                 ┌──────────────┐
  clips ───────► │   SOURCES    │ ──► Event[]  (timestamp, type, metadata)
  audio ───────► │              │
                 └──────────────┘
                        │
                        ▼
                 ┌──────────────┐
  profile ─────► │   HANDLERS   │ ──► EditInstruction[]  (overlays, SFX cues, caption spans)
                 │ (one/event)  │
                 └──────────────┘
                        │
                        ▼
                 ┌──────────────┐
  clips ───────► │   RENDERER   │ ──► final .mp4
  music ───────► │  (FFmpeg)    │
  profile ─────► │              │
                 └──────────────┘
```

- **Sources** produce a stream of `Event` objects. A source knows nothing about overlays or SFX. Implementations: `BoostSource` (video CV), `GoalSource` (video CV), `CaptionSource` (Whisper word-timing). Future: `ReplaySource`.
- **Handlers** consume `Event`s and emit `EditInstruction`s. One handler per event type. A handler knows nothing about *how* events were detected or *how* instructions are rendered. It reads the profile for styling.
- **Renderer** consumes all `EditInstruction`s + the trimmed clips + music + profile, and produces the final FFmpeg command(s). It knows nothing about detection.

**Why this matters:** you can swap video detection for replay parsing (new Source), add a new event type (new Source + new Handler), or change the look of any effect (profile data) — each without touching the other two stages. This is the SOLID payoff and it must hold from day one.

### 3.2 Process topology

```
┌─────────────────────────┐         ┌──────────────────────────┐
│   Electron (TypeScript)  │  local  │   Python backend         │
│   - Trim UI              │ ◄─────► │   - Sources (CV/Whisper) │
│   - Settings/profile UI  │  IPC/   │   - Handlers             │
│   - Event review UI      │  API    │   - Renderer (FFmpeg)    │
│   - Render trigger       │         │   - Music fetch (yt-dlp) │
└─────────────────────────┘         └──────────────────────────┘
```

- **Frontend:** Electron + TypeScript. Owns all UI: trimming, settings, reviewing detected events before render.
- **Backend:** Python. Owns all heavy work: CV detection, Whisper, FFmpeg rendering, music fetch.
- **Contract:** the **Profile** (JSON) + a small command/result API. See §5.

### 3.3 Language rationale (recorded)

This is a computer-vision project wearing a video-editor costume. The risky core (boost gauge reading, goal detection, template matching) is overwhelmingly Python territory — OpenCV, Whisper, yt-dlp, ffmpeg bindings are all first-class there and thin/lagging in C#. Electron makes the UI language-independent, so the backend is free to be Python. TypeScript frontend is already in the user's wheelhouse. **Accepted cost:** Python+Electron packaging is fiddlier (PyInstaller the backend, bundle alongside Electron). For a personal-use tool this cost is near zero; it only bites if distributed to other streamers.

---

## 4. Core data models

These are the contracts that flow between stages. Define them once, share them.

### 4.1 Event

```python
# Produced by Sources, consumed by Handlers
@dataclass
class Event:
    type: EventType            # BOOST_PICKUP | GOAL | CAPTION_WORD
    t_start: float             # seconds, relative to trimmed clip
    t_end: float | None        # for spans (captions); None for instants
    metadata: dict             # event-specific payload
```

Event-specific `metadata`:
- `BOOST_PICKUP`: `{ "amount": 12 | 100, "confidence": float }`
- `GOAL`: `{ "confidence": float }`
- `CAPTION_WORD`: `{ "word": str }`

### 4.2 EditInstruction

```python
# Produced by Handlers, consumed by Renderer
@dataclass
class EditInstruction:
    kind: InstructionKind      # ASS_OVERLAY | SFX_CUE | MUSIC_BED | STATIC_OVERLAY
    t_start: float
    t_end: float | None
    payload: dict              # e.g. ASS fragment, SFX file path + gain, image path
```

### 4.3 Profile (the UI↔backend contract)

The Profile is a JSON document edited by the Electron settings UI and consumed by the Python backend. **All stylistic choices live here, never in code.**

**Canonical artifact (decided in Phase 0):** the Profile lives in `contracts/` as `profile.default.json` (default values) validated against `profile.schema.json` (JSON Schema). The schema is the single cross-language source of truth — the Python backend validates against it and the TypeScript frontend derives its types from it, so the two cannot silently drift. It is modeled as a validated *document*, not a class: `Event` and `EditInstruction` are dataclasses (internal, Python-only), but the Profile stays data.

```jsonc
{
  "version": 1,
  "output": { "width": 1080, "height": 1920, "fps": 60, "crf": 19 },

  "boost": {
    "enabled": true,
    "text": {
      "font_file": "fonts/CapCutStyle.ttf",   // swappable; placeholder default
      "small_label": "+12",
      "big_label": "+100",
      "color": "#33CCFF",
      "outline_color": "#000000",
      "outline_width": 4,
      "position": { "anchor": "near_gauge", "x_offset": 0, "y_offset": -40 }
    },
    "animation": {
      "pop_duration_ms": 150,
      "start_scale": 0.7,
      "overshoot_scale": 1.1,
      "settle_scale": 1.0,
      "fade_in_ms": 60,
      "hold_ms": 400,
      "fade_out_ms": 200
    },
    "sfx": { "small": "sfx/boost_small.wav", "big": "sfx/boost_big.wav", "gain_db": 0 }
  },

  "goal": {
    "enabled": true,
    "effect": "slowmo",                        // or "flash" | "none"
    "sfx": { "file": "sfx/goal.wav", "gain_db": 0 }
  },

  "captions": {
    "enabled": true,
    "language": "en",
    "words_per_chunk": 4,
    "font_file": "fonts/CapCutStyle.ttf",
    "base_color": "#FFFFFF",
    "active_color": "#FFD400",
    "outline_color": "#000000",
    "outline_width": 4,
    "position": { "anchor": "lower_third", "y_offset": 0 },
    "animation": { "pop_in": true, "pop_duration_ms": 120 }
  },

  "thumbnail": {
    "enabled": true,
    "image_file": "templates/twitch_badge.png",
    "position": { "anchor": "top_left", "x": 24, "y": 24 }
  },

  "music": {
    "enabled": true,
    "file": null,                              // user-supplied or fetched
    "gain_db": -8,
    "duck_under_voice": true
  },

  "audio": { "normalize_lufs": -14, "true_peak_db": -1.0 }
}
```

> **Design rule:** if a stylistic question ever tempts you to hardcode a value, it belongs in the Profile instead. The UI exposes Profile fields; the backend reads them. Adding a setting = adding a field, never editing logic.

---

## 5. Electron ↔ Python contract

Keep it minimal. Two concerns: editing the profile, and running jobs.

### 5.1 Transport

Local only. Either:
- **stdio JSON-RPC** (Python launched as child process of Electron), or
- **localhost HTTP** (FastAPI on a fixed port).

Recommendation: **stdio child process** for a personal tool — no port management, no auth, clean lifecycle. (FastAPI is a reasonable alternative if you later want the backend independently testable via HTTP — it also matches your Kaizen stack.)

**Decided in Phase 0 — the wire format:**
- **Envelope:** JSON-RPC 2.0 (`{jsonrpc, method, params, id}` → `{jsonrpc, result|error, id}`) — standard error objects and id-correlation for free.
- **Framing:** newline-delimited JSON, one compact object per line, over stdin/stdout.
- **stdout is reserved for RPC** — all backend logging goes to stderr, or the stream corrupts (the #1 stdio-RPC footgun).
- **Dispatch is a command registry, not a switch:** new commands are *registered* (`REGISTRY["name"] = fn`), never branched in — the Open/Closed boundary for the API.
- **ffprobe/ffmpeg** are an external runtime dependency, located via the `PROMETHEUS_FFPROBE` env override → `PATH` → a clear error. Never hardcoded.

### 5.2 Commands (frontend → backend)

```
detect(clip_path, trim_in, trim_out, profile) -> Event[]      # returns detected events for review
render(clip_jobs[], profile) -> { output_path }               # full render
fetch_music(url) -> { file_path }                              # yt-dlp
probe(clip_path) -> { duration, width, height, fps }           # for trim UI
```

Where a `clip_job` = `{ clip_path, trim_in, trim_out, approved_events[] }`.

### 5.3 Events for review (the key UX seam)

`detect()` returns the event list **for the user to review before render.** The UI shows detected boost pops / goals on a timeline; the user can delete false positives or nudge timing. The *approved* event list is what `render()` consumes. This human-in-the-loop step is what makes ~85% detection accuracy acceptable instead of frustrating.

---

## 6. Detection design (the risky core)

### 6.1 Boost pickup detection

**Signal:** the boost-gauge number, lower-left of the gameplay area. (In the user's footage this is a BakkesMod-style panel: a radial dial with a large number — white at 100, orange below — over a busy background. Reading on a binarized crop makes colour/background irrelevant.)

**Method:** template matching, not general OCR.
1. One-time: extract clean digit templates 0–9 from the user's own footage (consistent stylized digital font). Use **many exemplars per digit** matched by 1-NN, not a single template — one-per-digit confuses 3/5/6/9.
2. Per frame: crop the number region (actual ≈ x=65, y=1480, 160×66, above the "BOOST" label), Otsu-binarize, segment digits (drop the dial arc that sits at the crop edges), match each, read the value.
3. Detect pickups as **upward jumps** above a threshold between consecutive reads.
4. Classify by **result and rise size**: a small pad adds exactly +12 (capped at 100); a big pad fills to **100**. So `result == 100` ⇒ big pad; a clean +12 jump ⇒ small pad. **Refinement (validated):** a big pad grabbed *while boosting* peaks below 100 (the simultaneous drain offsets it), so a large rise (≥ ~25, well beyond a small pad's +12) also classifies as a big pad even when the value never displays 100.

**Known hazards (must handle):**
- Boost **drains continuously** while driving — the number constantly drifts down. Only upward jumps count.
- A single pickup registers across 2–3 frames as the value settles → **debounce** so one pickup = one event, not three.
- Motion blur and the semi-transparent panel → matching needs threshold tolerance.
- Similar digit shapes in the stylized font (3 vs 5) → clean per-digit templates required.
- **Big-pad-near-full ambiguity:** a big pad picked up at high boost (e.g. 88 → 100) looks like a +12-sized jump, so jump magnitude alone misclassifies it. Use the `result == 100` rule above; leave residual ambiguity to the review step (§5.3).
- **Fixed-region assumption:** matching at fixed crop coordinates assumes the gauge's position, scale, and HUD layout are *constant across all clips* (same capture format — confirmed 1080×1920/60 in Phase 0). Verify against a spread of real clips before tuning; varying HUD position breaks the crop.

**Accuracy expectation:** ~85% before tuning. The review step (§5.3) absorbs the rest. **This is Phase 1 and must be proven before anything else is built.**

### 6.2 Goal detection

**Signal (implemented):** the **scoreboard increment**. The user's stream layout shows the two
score boxes (a fixed skewed overlay); the white digit inside a box only changes when that team
scores. We read each digit by **shape-matching against a small exemplar bank** (`score_templates/`,
digits 0–4 so far) — robust to the box's *semi-transparent background bleed*, which defeats naive
pixel-diffing. A GOAL is a confirmed increment (several consecutive equal reads); a None read
(absent scoreboard during a replay) is skipped so a goal's own replay gap doesn't break detection;
goals within `min_gap_s` collapse (digit morph + RL celebration/kickoff). Scene-change detection
was considered and dropped — semantically weaker (fires on cuts/saves).

**Ownership (not colour):** the user's team is always the **LEFT** box (colour varies — blue /
orange / gray club — and is irrelevant). Left increment ⇒ `side="your_team"`, right ⇒ `"opponent"`.

**Personal scorer (you vs teammate):** for each team goal, `GoalScorer` decides `scorer="you"`
or `"teammate"` by scanning a window around the goal for two shape-matched signals — PRIMARY the
**"&lt;NAME&gt; SCORED!" banner** matching the user's name (appears right at the goal, survives clips
that end seconds after; one name template, *not* full-alphabet OCR — `scorer_templates/name/`), and
BACKUP the **"GOAL +100" popup** (only awarded when you score; name-independent but appears ~2–3s
late so it alone misses short clips — `scorer_templates/popup/`). The score-time can lag the real
goal, so the window reaches further before the goal than after.

**Accuracy:** validated 9/9 on labelled clips (8 your-goals, 1 assist). Per-game tuning; the
digit bank + name template grow with footage (scores ≥5; multi-user name input is future work).

### 6.3 Caption word-timing

**Method (implemented):** `CaptionSource` runs **faster-whisper** (`base.en`, CPU int8 default;
CUDA optional) with `word_timestamps=True`, emitting one `CAPTION_WORD` event per word
`(word, t_start, t_end)`. Validated on real clips — clear speech, accurate word timings (e.g.
"Nice shot." landed on the goal). Config in `detection/caption_config.py`; language from the
Profile. Main cost is the one-time model download + compute (GPU faster).

---

## 7. Effects design

### 7.1 Boost text + pop (ASS)

Each approved boost event → an ASS overlay fragment via the `BoostHandler`:
- Text = profile label (`+12` / `+100`), font/color/outline/position from profile.
- **Pop animation** via ASS `\t` transform tags: scale `start_scale` → `overshoot_scale` → `settle_scale` over `pop_duration_ms`, plus fade-in/hold/fade-out. The overshoot-then-settle fakes a bounce.
- **Limitation (recorded):** ASS interpolation is linear — no true spring physics. For a sub-second number this is imperceptible. Per-frame rendering (PIL) is the escape hatch if ever needed, but is out of scope for v1 as a poor trade.

### 7.2 Goal effects

`GoalHandler` → ASS_OVERLAY instructions for the goal celebration, styled from `profile.goal`:
a white **flash** (full-frame box, fades in to `max_opacity` then out) plus a **"GOAL!" text
pop** (centre-screen, same pop+fade as boost). `goal.scope` selects which goals fire it —
**`your_goals`** (default: only `side=="your_team"` & `scorer=="you"`) or `all`. Both reuse the
Phase-2 burn path: `ass_builder` (now per-event inline styling; a payload `type:"flash"` draws
the box) → `Renderer`. No SFX (§7.4). **`slowmo` (done):** for a celebrated goal, GoalHandler
also emits a `RETIME_SEGMENT` slowing a span around the goal (`goal.slowmo`: `speed`, `pre_s`,
`post_s`). The `Renderer` splits the clip at the segment (setpts/atempo + concat), **re-times
every overlay onto the output timeline** (`render/retime.py` — pure `remap_time`; the slowed
span shifts all later timestamps), burns them, and forces CFR output (the slowed span is VFR).

### 7.3 Captions (ASS karaoke) — implemented

`CaptionHandler` groups `CAPTION_WORD` events into lines of `words_per_chunk`, **breaking early on
a pause > 1s** so a line never spans a silence (else it lingers for seconds). Each line is one
ASS_OVERLAY (payload `type:"caption"`) carrying per-word karaoke durations; `ass_builder` renders
a lower-third line where each word flips `base_color`→`active_color` as it's spoken (ASS `\k`,
Primary=active/Secondary=base), with optional pop-in. Burned by the Renderer. Validated
(word-by-word highlight, e.g. "**Nice** shot"). Tool: `render_captions`.

### 7.4 SFX & music

- SFX: **dropped (decided 2026-06-30).** The user has no boost sound files and won't source them, so `SfxHandler`/`SFX_CUE` and the `boost.sfx` mapping are not built. The seam stays open — add a Handler later if sound files ever appear (goal/other SFX likewise gated on having files).
- Music: `MUSIC_BED` instruction; optional ducking under voice. Audio normalized to profile LUFS/true-peak at the end.

### 7.5 Thumbnail/badge

Static `STATIC_OVERLAY` from profile image at fixed anchor — same recipe every render.

---

## 8. Rendering

Single deterministic FFmpeg pipeline assembled from the `EditInstruction[]`:
1. Concatenate trimmed clips (in order).
2. Burn ASS overlays (boost text + captions) — one subtitles pass.
3. Composite static overlays (thumbnail/badge).
4. Apply goal effects (slowmo segments if any).
5. Mix audio: original + SFX cues + music bed (with ducking).
6. Normalize loudness (LUFS / true-peak from profile).
7. Encode 1080×1920/60fps, CRF from profile, `+faststart`.

**Quality rule:** never downscale. Preserve source 1080p/60fps end to end. (The user's current CapCut export downgrades to 720p/30fps — the tool must not.)

---

## 9. Module layout

Top-level (monorepo, as built in Phase 0):

```
contracts/   # cross-language Profile contract: profile.schema.json + profile.default.json
backend/     # Python: models, sources, handlers, render, music, api, detection, tests
frontend/    # Electron + TypeScript: main (+ python-bridge), preload, renderer, shared
```

The Python backend in detail:

```
backend/
  models/            # Event, EditInstruction, Profile (shared contracts)
  sources/
    base.py          # Source interface
    boost_source.py  # video CV — Phase 1
    goal_source.py   # video CV — Phase 3
    caption_source.py# Whisper — Phase 4
  handlers/
    base.py          # Handler interface
    boost_handler.py
    goal_handler.py
    caption_handler.py
    sfx_handler.py
  render/
    renderer.py      # assembles & runs FFmpeg
    ass_builder.py   # ASS fragment generation (text pop, karaoke)
  music/
    fetch.py         # yt-dlp wrapper
  api/
    rpc.py           # stdio JSON-RPC loop
    commands.py      # command registry (Open/Closed): probe(); later detect/render
  probe.py           # ffprobe wrapper (Phase 0)
  detection/
    templates/       # extracted digit templates
    matching.py      # template-matching utilities
  tests/             # pytest suite
```

Interfaces (`sources/base.py`, `handlers/base.py`) are the Open/Closed boundary: new event types = new files here, never edits to existing ones.

---

## 10. Risk-first phased roadmap

Ordering is deliberate: **the project's real risk is boost detection, so it goes first.** If it can't hit acceptable accuracy on real clips, you learn that in week one — not after building a UI around it.

### Phase 0 — Skeleton
- Repo structure, Python venv, Electron app shell.
- Define shared models (`Event`, `EditInstruction`, `Profile`).
- Establish the stdio JSON-RPC contract with a `probe()` round-trip.
- **Exit:** Electron can call Python and get a clip's duration back.
- **Status: ✅ complete (2026-06-29)** — `probe()` verified end-to-end through the Electron UI on a real 1080×1920/60 clip.

### Phase 1 — Boost detection (THE RISK)
- Extract digit templates from real footage.
- Implement `BoostSource`: per-frame gauge read, upward-jump detection, debounce, +12/+100 classification.
- CLI/test harness that prints the event timeline for a clip.
- Tune against the user's real clips.
- **Exit:** boost event timeline is accurate enough (~85%+) on real footage. **Go/no-go gate for the whole project.**
- **Status: ✅ complete (2026-06-30) — gate passed.** Validated on multiple real clips (one 100% correct, zero false positives). Multi-exemplar template 1-NN reading, animation-aware pickup detection, +12/+100 by result-or-rise. Audio-based detection was explored and dropped (no reference SFX; not distinguishable in game audio). Tools: `boost_timeline`, `verify_pickups`, `preview_overlay`.

### Phase 2 — Boost overlays (SFX dropped)
- `BoostHandler` → ASS text with pop animation, positioned above the gauge (from profile).
- `ass_builder` (ASS fragment) + `Renderer` (FFmpeg burns the overlay onto the clip).
- First end-to-end render: clip in → animated +12/+100 → mp4 out.
- SFX dropped — no sound files (see §7.4); no audio mix this phase.
- **Exit:** a clip renders with correctly-placed, animated +12/+100.
- **Status: ✅ complete (2026-06-30) — validated, PR #5 merged.** Real clip renders with +12/+100
  popping above the gauge (pop + fade), Profile-driven position/color/animation. Carry-forward: add
  `boost.text.size` to the Profile schema (handler defaults to 72px) and bundle a real font
  (Arial fallback today) — both become user-editable in Phase 6 (Settings UI).

### Phase 3 — Goal detection + effects
- `GoalSource` (scoreboard-increment detection) + ownership (your_team / opponent) + `GoalScorer`
  (you / teammate). **Done & validated** (§6.2) — 9/9 on labelled clips; tools `goal_timeline`,
  `goal_preview`. Detection method pivoted from scene-change to scoreboard digit-reading (the
  transparent score box defeats pixel-diffing; shape-matching is robust). Sliced per the agreed
  plan: **detection first, then a `flash`/`GOAL!` overlay effect, then `slowmo` as a deliberate
  second slice** (slowmo retimes a segment → shifts every later timestamp → needs `RETIME_SEGMENT`
  + a time-remap contract; isolated on purpose).
- `GoalHandler` (overlay effect: white **flash** + **"GOAL!"** text pop, `your_goals` scope,
  reusing the Phase-2 burn path; `ass_builder` refactored to per-event inline styling + a flash
  box). **Done** — rendered end-to-end on a your-goal clip (flash + GOAL! fire only on the
  user's goals; assists/opponent get nothing).
- `slowmo` (done): GoalHandler emits `RETIME_SEGMENT` per celebrated goal; `Renderer` splits/
  retimes the clip (setpts/atempo + concat), re-times overlays onto the output timeline
  (`retime.py`), forces CFR. Validated (goal plays 0.5x, overlays re-aligned, clip lengthens).
- **Exit:** goals detected and decorated end to end. **Met.**
- **Status: ✅ complete (2026-07-01) — detection + scorer + flash/"GOAL!" + slowmo, all validated.**

### Phase 4 — Captions
- `CaptionSource` (faster-whisper word-timing) → `CAPTION_WORD` events (§6.3).
- `CaptionHandler` (gap-aware chunking) + `ass_builder` `\k` karaoke highlight + pop-in (§7.3).
- **Exit:** burned-in karaoke captions matching profile style. **Met** — validated end-to-end
  (word-by-word highlight, lower third). Tool: `render_captions`.
- **Status: ✅ complete (2026-07-01), validated.**

### Phase 5 — Full export + music
- **`pipeline.py`** — composition root: every enabled Source → every Handler → ONE `Renderer`
  pass (all overlays + slow-mo retiming). Tool: `render_all`. Slow-mo × captions handled
  (caption word times re-timed through slow-mo).
- **Music** — a looped track mixed a controlled amount UNDER the voice: the VOICE is loudness-
  normalized to `audio.normalize_lufs`, music sits `music.gain_db` below it (sidechain-ducked
  when `duck_under_voice`), final `alimiter`. (Normalizing the *mix* re-boosted the music — fixed.)
- **Exit:** raw clip → CapCut-ready montage (boost + goal + slow-mo + captions + music), 60fps CFR.
  **Met** — validated on multiple clips with the user's real tracks.
- **Status: ✅ complete (2026-07-01), validated.** The exact music/voice *balance* is deferred to
  the Phase 6 volume sliders (tuning by re-render is too slow). **Deferred to Phase 6:** in-app
  trim (in/out points), thumbnail/badge overlay, yt-dlp music fetch — all UI-driven, wired later.

### Phase 6 — Settings UI + event review + packaging
- Electron profile editor (all §4.3 fields: colors, placement, caption style, animation, flash
  intensity/timing, text content/size/position). Every effect value is already Profile data, so
  this phase is about *exposing* it — no detection/handler rework. **Desired UX (user, 2026-07-01):**
  a **simple "editor / lightweight-Photoshop" vibe** — nice, uncomplicated UI to tweak text, fonts,
  position, animations, flash intensity live; grows an animation/font library over time.
- Event-review timeline (delete false positives / nudge timing before render). **Includes editing
  caption text** — ASR is never 100% on fast/slangy speech, so let the user fix the occasional
  wrong word here. (Whisper `small.en` is the default; it transcribes more completely than
  medium.en on this footage.) User-confirmed direction (2026-07-01).
- **Live volume sliders** — music level (`music.gain_db`) and clip/voice level, with instant
  feedback. Getting the music/voice balance right by re-rendering is too slow; a slider is the
  natural home for it. User-confirmed (2026-07-01). Pipeline already drives these as Profile data.
- Package (PyInstaller backend + Electron bundle) — only if distributing beyond personal use.
- Also fold in here: `boost.text.size` already exists on `goal.text`; a per-user **name input**
  for the goal scorer (see §6.2) and the **NVENC render toggle** (`output.encoder`) belong here.
- **Exit:** shippable personal tool.

---

## 11. Open questions / deferred

- **Caption font:** unknown name. Spec uses a swappable `font_file` with a CapCut-style placeholder default (heavy weight + thick outline). Swap the `.ttf` later; no code change.
- **Goal detection method:** score-increment vs transition-detection vs both — decide empirically in Phase 3 against real footage.
- **Trim UX fidelity:** frame-accurate scrubber vs simple in/out fields — decide when building Phase 5.
- **Music licensing:** fetch is neutral; user is responsible for using royalty-free/licensed audio to avoid YouTube claims.
- **Packaging:** only required if shared with other streamers; skip for personal use.

---

## 12. Guiding principles (keep visible during build)

1. **Three stages never bleed:** Sources detect, Handlers decide, Renderer renders.
2. **Style is data, not code:** every stylistic value lives in the Profile.
3. **Prove the risk first:** boost detection is the go/no-go gate.
4. **Human-in-the-loop absorbs imperfection:** review detected events before render.
5. **Never downscale:** preserve 1080p/60fps end to end.
6. **CapCut is the finishing room:** the tool does the grind, not the final art.

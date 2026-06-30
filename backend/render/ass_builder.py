r"""ass_builder — generate an ASS subtitle file from ASS_OVERLAY instructions (spec §7).

Each ASS_OVERLAY instruction carries its OWN styling in its payload (size, colour, outline,
position, animation), rendered as inline override tags — so boost, goal, and (later) captions
each get their own look from one generic base style. A payload `type` of "flash" instead draws
a full-frame coloured box that fades in to a peak opacity and out (the goal flash). Font stays
global (Arial fallback; font_file→name mapping is a later concern, same as boost).

Positions are in video pixels (PlayResX/Y). The pop is faked with \t scale transforms
(start → overshoot → settle) plus \fad; ASS \t interpolation is linear (no true spring),
imperceptible for a sub-second pop — per spec §7.1.
"""
from __future__ import annotations

from backend.models.instruction import EditInstruction, InstructionKind

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ass_color(hex_rgb: str) -> str:
    """#RRGGBB -> ASS &H00BBGGRR (opaque)."""
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def _ass_alpha(opacity: float) -> str:
    """0..1 opacity -> ASS alpha tag value (&H00& = opaque, &HFF& = transparent)."""
    a = max(0, min(255, round((1.0 - opacity) * 255)))
    return f"&H{a:02X}&"


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _text_tags(p: dict) -> str:
    """Inline override block for a styled, popping, fading text overlay."""
    x, y = int(p["x"]), int(p["y"])
    anim = p.get("animation", {})
    size = int(p.get("size", 72))
    primary = _ass_color(p.get("color", "#FFFFFF"))
    outline = _ass_color(p.get("outline_color", "#000000"))
    bord = p.get("outline_width", 4)
    start = round(anim.get("start_scale", 0.7) * 100)
    over = round(anim.get("overshoot_scale", 1.1) * 100)
    settle = round(anim.get("settle_scale", 1.0) * 100)
    pop = int(anim.get("pop_duration_ms", 150))
    t1 = int(pop * 0.6)
    fin = int(anim.get("fade_in_ms", 60))
    fout = int(anim.get("fade_out_ms", 200))
    return (
        f"{{\\an5\\pos({x},{y})\\fs{size}\\1c{primary}\\3c{outline}\\bord{bord}"
        f"\\fscx{start}\\fscy{start}"
        f"\\t(0,{t1},\\fscx{over}\\fscy{over})"
        f"\\t({t1},{pop},\\fscx{settle}\\fscy{settle})"
        f"\\fad({fin},{fout})}}"
    )


def _flash_event(p: dict, w: int, h: int) -> str:
    """A full-frame box that fades in to max_opacity then out (\\fad can't cap opacity, so we
    animate \\alpha explicitly)."""
    color = _ass_color(p.get("color", "#FFFFFF"))
    alpha = _ass_alpha(float(p.get("max_opacity", 0.85)))
    fin = int(p.get("fade_in_ms", 40))
    hold = int(p.get("hold_ms", 50))
    fout = int(p.get("fade_out_ms", 220))
    dur = fin + hold + fout
    tags = (
        f"{{\\an7\\pos(0,0)\\1c{color}\\bord0\\shad0\\alpha&HFF&"
        f"\\t(0,{fin},\\alpha{alpha})"
        f"\\t({dur - fout},{dur},\\alpha&HFF&)\\p1}}"
    )
    return f"{tags}m 0 0 l {w} 0 {w} {h} 0 {h}{{\\p0}}"


def build_ass(instructions: list[EditInstruction], width: int, height: int, font: str = "Arial") -> str:
    """Render ASS_OVERLAY instructions into a full .ass document. Each payload carries its own
    style; a payload `type` of "flash" draws a full-frame box (Layer 0, under text on Layer 1)."""
    overlays = [i for i in instructions if i.kind is InstructionKind.ASS_OVERLAY]
    out = [_HEADER.format(w=width, h=height, font=font)]
    for inst in overlays:
        p = inst.payload
        end = inst.t_end if inst.t_end is not None else inst.t_start
        start_t, end_t = _ass_time(inst.t_start), _ass_time(end)
        if p.get("type") == "flash":
            body = _flash_event(p, width, height)
            out.append(f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{body}")
        else:
            body = _text_tags(p) + str(p["text"]).replace("\n", "\\N")
            out.append(f"Dialogue: 1,{start_t},{end_t},Default,,0,0,0,,{body}")
    return "\n".join(out) + "\n"

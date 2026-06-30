r"""ass_builder — generate an ASS subtitle file from ASS_OVERLAY instructions (spec §7.1).

Positions are in video pixels (PlayResX/Y). The pop is faked with \t scale transforms
(start -> overshoot -> settle) plus \fad for fade in/out. ASS \t interpolation is linear
(no true spring), which is imperceptible for a sub-second number — per spec §7.1.
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
Style: Boost,{font},{size},{primary},{primary},{outline},&H00000000,-1,0,0,0,100,100,0,0,1,{bord},0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ass_color(hex_rgb: str) -> str:
    """#RRGGBB -> ASS &HAABBGGRR (opaque)."""
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _anim_tags(x: int, y: int, anim: dict) -> str:
    start = round(anim.get("start_scale", 0.7) * 100)
    over = round(anim.get("overshoot_scale", 1.1) * 100)
    settle = round(anim.get("settle_scale", 1.0) * 100)
    pop = int(anim.get("pop_duration_ms", 150))
    t1 = int(pop * 0.6)
    fin = int(anim.get("fade_in_ms", 60))
    fout = int(anim.get("fade_out_ms", 200))
    return (
        f"{{\\an5\\pos({x},{y})\\fscx{start}\\fscy{start}"
        f"\\t(0,{t1},\\fscx{over}\\fscy{over})"
        f"\\t({t1},{pop},\\fscx{settle}\\fscy{settle})"
        f"\\fad({fin},{fout})}}"
    )


def build_ass(instructions: list[EditInstruction], width: int, height: int, font: str = "Arial") -> str:
    """Render ASS_OVERLAY instructions into a full .ass document string."""
    overlays = [i for i in instructions if i.kind is InstructionKind.ASS_OVERLAY]
    if overlays:
        p = overlays[0].payload  # boost overlays share styling
        size = int(p.get("size", 72))
        primary = _ass_color(p.get("color", "#FFFFFF"))
        outline = _ass_color(p.get("outline_color", "#000000"))
        bord = p.get("outline_width", 4)
    else:
        size, primary, outline, bord = 72, "&H00FFFFFF", "&H00000000", 4

    out = [_HEADER.format(w=width, h=height, font=font, size=size, primary=primary, outline=outline, bord=bord)]
    for inst in overlays:
        p = inst.payload
        text = _anim_tags(int(p["x"]), int(p["y"]), p.get("animation", {})) + str(p["text"]).replace("\n", "\\N")
        end = inst.t_end if inst.t_end is not None else inst.t_start
        out.append(f"Dialogue: 0,{_ass_time(inst.t_start)},{_ass_time(end)},Boost,,0,0,0,,{text}")
    return "\n".join(out) + "\n"

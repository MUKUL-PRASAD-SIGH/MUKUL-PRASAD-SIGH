"""Small helpers shared by the profile SVG generators (stdlib only).

Every image in the README that we draw ourselves goes through here so the
whole profile shares one palette, one font stack and one card style.
"""

from __future__ import annotations

import html
import os

# ── Palette (based on the "radical" theme used by the stats cards) ──────────
BG_DEEP = "#0d0b16"
BG = "#141321"
BG_RAISED = "#1c1a2e"
BORDER = "#2e2a4a"
PINK = "#FE428E"
YELLOW = "#F8D847"
CYAN = "#A9FEF7"
PURPLE = "#6E40C9"
VIOLET = "#9B6BFF"
GREEN = "#2BD67B"
RED = "#FF4F5E"
TEXT = "#FFFFFF"
TEXT_SOFT = "#DAD7EE"
TEXT_MUTED = "#A49FC4"

FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', 'Fira Code', Consolas, Menlo, monospace"

# ── Text measuring ──────────────────────────────────────────────────────────
# Helvetica/Arial advance widths (1/1000 em). Good enough to wrap and centre
# text; every layout keeps some slack because Segoe UI/Ubuntu differ a bit.
_REGULAR = dict(zip(
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
    [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
     556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
     1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
     667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
     333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
     556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]))
_BOLD = dict(zip(
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
    [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
     556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
     975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
     667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
     333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
     611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584]))
_EXTRA = {"·": 278, "•": 350, "—": 1000, "–": 556, "’": 222, "‘": 222, "…": 1000,
          "★": 800, "→": 1000, "↗": 1000, "▶": 800}
# Zero-width code points that ride along with emoji (VS16, ZWJ, skin tones).
_ZERO_WIDTH = {0xFE0F, 0x200D, 0xFE0E}


def text_width(text: str, size: float, bold: bool = False, spacing: float = 0.0) -> float:
    """Approximate rendered width of ``text`` in px."""
    table = _BOLD if bold else _REGULAR
    total = 0.0
    for ch in text:
        cp = ord(ch)
        if cp in _ZERO_WIDTH or 0x1F3FB <= cp <= 0x1F3FF:
            continue
        if ch in table:
            total += table[ch]
        elif ch in _EXTRA:
            total += _EXTRA[ch]
        elif cp >= 0x2190:          # emoji & pictographs render roughly square
            total += 1250
        else:                       # accented latin etc.
            total += 600 if bold else 560
    return total * size / 1000 + spacing * max(len(text) - 1, 0)


def wrap(text: str, size: float, max_width: float, bold: bool = False,
         max_lines: int | None = None, safety: float = 1.1) -> list[str]:
    """Greedy word wrap; the last allowed line gets an ellipsis if cut.

    ``safety`` inflates measured widths because Ubuntu/Helvetica Neue render
    wider than the Arial metrics above — lines must fit on every OS.
    """
    max_width /= safety
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and text_width(candidate, size, bold) > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    if max_lines and len(lines) > max_lines:
        kept = lines[:max_lines]
        last = kept[-1]
        while last and text_width(last + "…", size, bold) > max_width:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        kept[-1] = last.rstrip(",;:·—- ") + "…"
        lines = kept
    return lines


def esc(text) -> str:
    return html.escape(str(text), quote=True)


# ── Building blocks ─────────────────────────────────────────────────────────
def linear(gid: str, stops, x1=0, y1=0, x2=1, y2=0, extra: str = "") -> str:
    """<linearGradient>; ``stops`` is a list of (offset, color[, opacity])."""
    parts = []
    for stop in stops:
        offset, color, *rest = stop
        opacity = f' stop-opacity="{rest[0]}"' if rest else ""
        parts.append(f'<stop offset="{offset}" stop-color="{color}"{opacity}/>')
    return (f'<linearGradient id="{gid}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"{extra}>'
            + "".join(parts) + "</linearGradient>")


def document(width: float, height: float, body: str, *, title: str, desc: str = "",
             defs: str = "", style: str = "") -> str:
    """Wrap ``body`` in an accessible, self-contained <svg> document."""
    desc_tag = f'<desc id="d">{esc(desc)}</desc>' if desc else ""
    labelled = "t d" if desc else "t"
    if style:
        # Animations are decoration only: every image must be complete at t=0
        # (static renderers snapshot the first frame) and still when asked.
        style += "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="{labelled}" '
        f'font-family="{FONT}">'
        f'<title id="t">{esc(title)}</title>{desc_tag}'
        + (f"<defs>{defs}</defs>" if defs else "")
        + (f"<style>{style}</style>" if style else "")
        + body + "</svg>\n"
    )


def wave_path(width: float, period: float, amplitude: float, baseline: float,
              bottom: float, phase: float = 0.0) -> str:
    """A filled, horizontally repeating wave; ``width`` should be a multiple of ``period``."""
    half = period / 2
    x = -phase
    d = [f"M{x:.1f},{baseline:.1f}"]
    up = True
    while x < width + period:
        cx = x + half / 2
        cy = baseline - amplitude if up else baseline + amplitude
        d.append(f"Q{cx:.1f},{cy:.1f} {x + half:.1f},{baseline:.1f}")
        x += half
        up = not up
    d.append(f"L{x:.1f},{bottom:.1f} L{-phase:.1f},{bottom:.1f} Z")
    return " ".join(d)


def save(path: str, content: str) -> bool:
    """Write ``content`` only if it changed. Returns True when the file changed."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        with open(path, encoding="utf-8") as fh:
            if fh.read() == content:
                return False
    except FileNotFoundError:
        pass
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return True

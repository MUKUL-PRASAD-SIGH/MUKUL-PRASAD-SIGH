#!/usr/bin/env python3
"""Generate the static design assets of the profile README.

These images never change between runs (hero banner, footer, section headers,
navigation pills and link buttons), so they are generated once, committed, and
served straight from this repository — no third-party image service involved.

    python3 scripts/build_static.py
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svgkit import (BG, BG_DEEP, BORDER, CYAN, FONT, GREEN, PINK, PURPLE, RED,  # noqa: E402
                    TEXT, TEXT_MUTED, TEXT_SOFT, VIOLET, YELLOW, document, esc,
                    linear, save, text_width, wave_path)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "static")

# Sections in README order: (slug, emoji, title, subtitle, accent colour).
SECTIONS = [
    ("about", "👋", "About Me", "who I am & what drives me", CYAN),
    ("experience", "💼", "Experience", "research · mentoring · industry", VIOLET),
    ("education", "🎓", "Education", "where I study", CYAN),
    ("tech-stack", "🛠️", "Tech Stack", "tools I build with", CYAN),
    ("pinned", "📌", "Pinned Highlights", "flagship projects", PINK),
    ("demos", "🎬", "Demos & Live Deployments", "see the projects in action", YELLOW),
    ("projects", "🧠", "All Projects", "everything I've shipped", CYAN),
    ("achievements", "🏆", "Hackathons & Achievements", "competitions · rankings · awards", YELLOW),
    ("certifications", "📜", "Certifications & Leadership", "learning · community · roles", VIOLET),
    ("stats", "📊", "GitHub Stats & Activity", "auto-refreshed every 6 hours", PINK),
    ("connect", "📫", "Let's Connect", "always happy to collaborate", CYAN),
]

# Navigation pills shown under the hero: (slug, emoji, label, accent).
NAV = [
    ("experience", "💼", "Experience", VIOLET),
    ("tech-stack", "🛠️", "Tech Stack", CYAN),
    ("pinned", "📌", "Pinned", PINK),
    ("demos", "🎬", "Demos", YELLOW),
    ("projects", "🧠", "Projects", CYAN),
    ("achievements", "🏆", "Achievements", YELLOW),
    ("stats", "📊", "Stats", PINK),
    ("connect", "📫", "Connect", VIOLET),
]

# Call-to-action buttons used under the pinned project cards.
BUTTONS = [
    ("demo", "▶", "Watch Demo", RED),
    ("live", "●", "Live Site", GREEN),
    ("code", "</>", "Source Code", VIOLET),
]


def _stars(rng: random.Random, count: int, width: int, height: int) -> str:
    out = []
    for i in range(count):
        x, y = rng.uniform(12, width - 12), rng.uniform(10, height * 0.8)
        r = rng.choice((0.8, 1.1, 1.4, 1.8))
        delay = rng.uniform(0, 4)
        dur = rng.uniform(2.5, 5)
        out.append(f'<circle class="tw" cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="#fff" '
                   f'style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s"/>')
    return "".join(out)


def _network(rng: random.Random, x0: float, x1: float, y0: float, y1: float,
             nodes: int, colour: str) -> str:
    """A faint 'neural network' constellation: nodes + nearest-neighbour edges."""
    pts = [(rng.uniform(x0, x1), rng.uniform(y0, y1)) for _ in range(nodes)]
    edges = set()
    for i, (ax, ay) in enumerate(pts):
        near = sorted(range(nodes), key=lambda j: (pts[j][0] - ax) ** 2 + (pts[j][1] - ay) ** 2)
        for j in near[1:3]:
            edges.add(tuple(sorted((i, j))))
    lines = "".join(
        f'<line class="edge" x1="{pts[a][0]:.0f}" y1="{pts[a][1]:.0f}" '
        f'x2="{pts[b][0]:.0f}" y2="{pts[b][1]:.0f}" style="animation-delay:{rng.uniform(0, 3):.1f}s"/>'
        for a, b in sorted(edges))
    dots = "".join(
        f'<circle class="node" cx="{x:.0f}" cy="{y:.0f}" r="{rng.choice((2.2, 2.8, 3.4))}" '
        f'style="animation-delay:{rng.uniform(0, 3):.1f}s"/>' for x, y in pts)
    return f'<g stroke="{colour}" fill="{colour}">{lines}{dots}</g>'


def hero() -> str:
    w, h = 1200, 340
    rng = random.Random(2028)
    defs = (
        f'<clipPath id="card"><rect width="{w}" height="{h}" rx="22"/></clipPath>'
        + linear("bg", [(0, BG_DEEP), (0.55, BG), (1, "#22123d")], 0, 0, 1, 1)
        + linear("title", [(0, PINK), (0.5, YELLOW), (1, CYAN)])
        + linear("edge", [(0, PINK, 0.9), (0.5, VIOLET, 0.6), (1, CYAN, 0.9)])
        + f'<radialGradient id="gp" cx="0.16" cy="0.1" r="0.55"><stop offset="0" stop-color="{PINK}" stop-opacity="0.30"/><stop offset="1" stop-color="{PINK}" stop-opacity="0"/></radialGradient>'
        + f'<radialGradient id="gc" cx="0.86" cy="0.3" r="0.5"><stop offset="0" stop-color="{CYAN}" stop-opacity="0.18"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>'
        + f'<radialGradient id="gv" cx="0.5" cy="1" r="0.6"><stop offset="0" stop-color="{VIOLET}" stop-opacity="0.28"/><stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></radialGradient>'
        + '<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.1" fill="#fff" fill-opacity="0.06"/></pattern>'
        + '<filter id="glow" x="-10%" y="-40%" width="120%" height="180%"><feGaussianBlur stdDeviation="9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    )
    style = (
        "@keyframes drift{from{transform:translateX(0)}to{transform:translateX(-400px)}}"
        ".w1{animation:drift 14s linear infinite}.w2{animation:drift 20s linear infinite}"
        ".w3{animation:drift 9s linear infinite}"
        "@keyframes tw{0%,100%{opacity:.12}50%{opacity:.85}}"
        ".tw{opacity:.12;animation:tw 4s ease-in-out infinite}"
        "@keyframes pulse{0%,100%{opacity:.25}50%{opacity:.9}}"
        ".node{opacity:.4;animation:pulse 3.2s ease-in-out infinite}"
        ".edge{stroke-width:1;opacity:.22;stroke-dasharray:4 6;animation:flow 6s linear infinite}"
        "@keyframes flow{to{stroke-dashoffset:-60}}"
        "@keyframes rise{from{transform:translateY(12px)}to{transform:none}}"
        ".r1{animation:rise 1s ease-out both}.r2{animation:rise 1s .35s ease-out both}"
        ".r3{animation:rise 1s .7s ease-out both}"
    )
    chips = [("📍", "Bengaluru, India", CYAN),
             ("🎓", "B.E. CSE (AI & ML) · Ramaiah Institute of Technology", YELLOW)]
    chip_svgs, widths = [], []
    for icon, label, colour in chips:
        widths.append(text_width(label, 15) + 58)
    gap = 14
    x = (w - (sum(widths) + gap * (len(chips) - 1))) / 2
    for (icon, label, colour), cw in zip(chips, widths):
        chip_svgs.append(
            f'<g transform="translate({x:.0f},228)">'
            f'<rect width="{cw:.0f}" height="34" rx="17" fill="{colour}" fill-opacity="0.08" '
            f'stroke="{colour}" stroke-opacity="0.45"/>'
            f'<text x="18" y="22.5" font-size="15">{icon}</text>'
            f'<text x="44" y="22.5" font-size="15" fill="{TEXT_SOFT}">{esc(label)}</text></g>')
        x += cw + gap

    waves = (
        f'<path class="w2" d="{wave_path(w + 800, 400, 14, 296, h, 0)}" fill="{VIOLET}" fill-opacity="0.30"/>'
        f'<path class="w1" d="{wave_path(w + 800, 400, 11, 306, h, 120)}" fill="{PINK}" fill-opacity="0.28"/>'
        f'<path class="w3" d="{wave_path(w + 800, 400, 8, 318, h, 260)}" fill="{CYAN}" fill-opacity="0.18"/>'
    )
    body = (
        '<g clip-path="url(#card)">'
        f'<rect width="{w}" height="{h}" fill="url(#bg)"/>'
        f'<rect width="{w}" height="{h}" fill="url(#gp)"/><rect width="{w}" height="{h}" fill="url(#gc)"/>'
        f'<rect width="{w}" height="{h}" fill="url(#gv)"/><rect width="{w}" height="{h}" fill="url(#dots)"/>'
        + _stars(rng, 34, w, h)
        + _network(rng, 40, 250, 40, 230, 9, PINK)
        + _network(rng, 950, 1160, 40, 230, 9, CYAN)
        + f'<text class="r1" x="{w / 2}" y="136" text-anchor="middle" font-size="86" font-weight="800" '
        f'letter-spacing="7" fill="url(#title)" filter="url(#glow)">MUKUL PRASAD</text>'
        f'<text class="r2" x="{w / 2}" y="188" text-anchor="middle" font-size="23" font-weight="600" '
        f'fill="{TEXT}" letter-spacing="0.5">AI / ML Engineer  •  Multi-Agent Systems  •  Graph ML  •  Full-Stack</text>'
        f'<g class="r3">{"".join(chip_svgs)}</g>'
        + waves + "</g>"
        f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="21.5" fill="none" '
        f'stroke="url(#edge)" stroke-opacity="0.55" stroke-width="1.5"/>'
    )
    return document(w, h, body, title="Mukul Prasad",
                    desc="AI/ML Engineer · Multi-Agent Systems · Graph ML · Full-Stack — "
                         "B.E. CSE (AI & ML), Ramaiah Institute of Technology, Bengaluru",
                    defs=defs, style=style)


def footer() -> str:
    w, h = 1200, 150
    defs = (f'<clipPath id="card"><rect width="{w}" height="{h}" rx="22"/></clipPath>'
            + linear("bg", [(0, "#22123d"), (0.5, BG), (1, BG_DEEP)], 0, 0, 1, 1)
            + linear("edge", [(0, CYAN, 0.9), (0.5, VIOLET, 0.6), (1, PINK, 0.9)])
            + linear("txt", [(0, CYAN), (0.5, YELLOW), (1, PINK)]))
    style = ("@keyframes drift{from{transform:translateX(0)}to{transform:translateX(-400px)}}"
             ".w1{animation:drift 16s linear infinite}.w2{animation:drift 11s linear infinite}"
             "@keyframes beat{0%,100%{transform:scale(1)}50%{transform:scale(1.18)}}"
             ".heart{transform-box:fill-box;transform-origin:center;animation:beat 1.6s ease-in-out infinite}")
    body = (
        '<g clip-path="url(#card)">'
        f'<rect width="{w}" height="{h}" fill="url(#bg)"/>'
        # waves hang from the top edge: draw them at the bottom, then flip vertically
        f'<g transform="translate(0,{h}) scale(1,-1)">'
        f'<path class="w1" d="{wave_path(w + 800, 400, 10, 116, h, 60)}" fill="{PINK}" fill-opacity="0.20"/>'
        f'<path class="w2" d="{wave_path(w + 800, 400, 7, 124, h, 230)}" fill="{CYAN}" fill-opacity="0.14"/></g>'
        f'<text x="{w / 2}" y="86" text-anchor="middle" font-size="26" font-weight="800" fill="url(#txt)" '
        f'letter-spacing="1">Code. Commit. Conquer.</text>'
        f'<text x="{w / 2}" y="118" text-anchor="middle" font-size="15" fill="{TEXT_MUTED}">'
        f'Thanks for visiting — built with <tspan class="heart" fill="{PINK}">♥</tspan> &amp; a lot of coffee in Bengaluru</text>'
        '</g>'
        f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="21.5" fill="none" '
        f'stroke="url(#edge)" stroke-opacity="0.5" stroke-width="1.5"/>'
    )
    return document(w, h, body, title="Code. Commit. Conquer.",
                    desc="Thanks for visiting Mukul Prasad's GitHub profile", defs=defs, style=style)


def section_header(index: int, emoji: str, title: str, subtitle: str, accent: str) -> str:
    w, h = 900, 76
    defs = (linear("edge", [(0, accent, 0.9), (0.6, PURPLE, 0.5), (1, accent, 0.15)])
            + linear("bar", [(0, accent, 0), (0.5, accent, 1), (1, accent, 0)])
            + f'<clipPath id="c"><rect width="{w}" height="{h}" rx="16"/></clipPath>'
            + f'<radialGradient id="g" cx="0.05" cy="0.5" r="0.45"><stop offset="0" stop-color="{accent}" stop-opacity="0.22"/>'
              f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>')
    style = ("@keyframes sweep{from{transform:translateX(-320px)}to{transform:translateX(900px)}}"
             ".sweep{animation:sweep 5s ease-in-out infinite}")
    number = f"{index:02d}"
    body = (
        '<g clip-path="url(#c)">'
        f'<rect width="{w}" height="{h}" fill="{BG}"/><rect width="{w}" height="{h}" fill="url(#g)"/>'
        f'<text x="{w - 26}" y="62" text-anchor="end" font-size="58" font-weight="800" fill="{accent}" '
        f'fill-opacity="0.07">{number}</text>'
        f'<rect class="sweep" y="{h - 3}" width="320" height="3" fill="url(#bar)"/>'
        '</g>'
        f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="15.5" fill="none" '
        f'stroke="url(#edge)" stroke-width="1.5"/>'
        f'<rect x="20" y="16" width="44" height="44" rx="12" fill="{accent}" fill-opacity="0.12" '
        f'stroke="{accent}" stroke-opacity="0.5"/>'
        f'<text x="42" y="46" text-anchor="middle" font-size="22">{emoji}</text>'
        f'<text x="82" y="38" font-size="24" font-weight="700" fill="{TEXT}">{esc(title)}</text>'
        f'<text x="82" y="59" font-size="13.5" fill="{TEXT_MUTED}" letter-spacing="0.4">{esc(subtitle)}</text>'
    )
    return document(w, h, body, title=title, desc=subtitle, defs=defs, style=style)


def nav_pill(emoji: str, label: str, accent: str) -> str:
    w, h = 200, 46
    defs = linear("edge", [(0, accent, 0.95), (1, PURPLE, 0.55)], 0, 0, 1, 1)
    tw = text_width(label, 15.5, bold=True)
    content = 28 + tw                     # emoji box + gap + label
    x0 = (w - content) / 2
    body = (
        f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="{(h - 1.5) / 2}" '
        f'fill="{BG}" stroke="url(#edge)" stroke-width="1.5"/>'
        f'<rect x="4" y="4" width="{w - 8}" height="{h - 8}" rx="{(h - 8) / 2}" fill="{accent}" fill-opacity="0.07"/>'
        f'<text x="{x0:.1f}" y="29.5" font-size="17">{emoji}</text>'
        f'<text x="{x0 + 28:.1f}" y="28.5" font-size="15.5" font-weight="700" fill="{TEXT}">{esc(label)}</text>'
    )
    return document(w, h, body, title=label, defs=defs)


def button(icon: str, label: str, accent: str) -> str:
    icon_w = text_width(icon, 13, bold=True)
    tw = text_width(label, 14, bold=True)
    w, h = round(icon_w + 9 + tw * 1.06 + 36), 38   # sized to the label so 3 fit in a card column
    x0 = (w - (icon_w + 9 + tw * 1.03)) / 2
    body = (
        # solid base first so the label stays readable on GitHub's light theme
        f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="10" fill="{BG}"/>'
        f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="10" fill="{accent}" '
        f'fill-opacity="0.14" stroke="{accent}" stroke-opacity="0.85" stroke-width="1.5"/>'
        f'<text x="{x0:.1f}" y="24" font-size="13" font-weight="700" fill="{accent}">{esc(icon)}</text>'
        f'<text x="{x0 + icon_w + 9:.1f}" y="24.5" font-size="14" font-weight="700" fill="{TEXT}">{esc(label)}</text>'
    )
    return document(w, h, body, title=label)


def main() -> None:
    written = []

    def emit(name: str, svg: str) -> None:
        if save(os.path.join(OUT, name), svg):
            written.append(name)

    emit("hero.svg", hero())
    emit("footer.svg", footer())
    for i, (slug, emoji, title, subtitle, accent) in enumerate(SECTIONS, 1):
        emit(f"header-{slug}.svg", section_header(i, emoji, title, subtitle, accent))
    for slug, emoji, label, accent in NAV:
        emit(f"nav-{slug}.svg", nav_pill(emoji, label, accent))
    for slug, icon, label, accent in BUTTONS:
        emit(f"btn-{slug}.svg", button(icon, label, accent))
    print(f"static assets: {len(written)} updated" + (f" ({', '.join(written)})" if written else ""))


if __name__ == "__main__":
    main()

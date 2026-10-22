#!/usr/bin/env python3
"""Refresh every dynamic part of the profile README.

Run by .github/workflows/update-profile-assets.yml every 6 hours:

  1. downloads the third-party stat cards and keeps the last good copy when a
     service is down or rate-limited (a failed download must never replace a
     working image with an error page);
  2. collects profile numbers from the GitHub GraphQL API;
  3. renders our own cards: pinned projects, trophies, monthly contributions;
  4. rewrites the marked blocks of README.md (stat badges, views badge, pulse).

Needs a token in GH_TOKEN (or GITHUB_TOKEN). Offline preview from saved data:

    python3 scripts/update_profile.py --data assets/data/profile.json --skip-cards --no-views
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svgkit import (BG, BORDER, CYAN, PINK, PURPLE, TEXT, TEXT_MUTED,  # noqa: E402
                    TEXT_SOFT, VIOLET, YELLOW, document, esc, linear, save,
                    text_width, wrap)

USERNAME = "MUKUL-PRASAD-SIGH"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
GENERATED = os.path.join(ROOT, "assets", "generated")
DATA_DIR = os.path.join(ROOT, "assets", "data")
UA = "Mozilla/5.0 (compatible; profile-readme-refresh; +https://github.com/MUKUL-PRASAD-SIGH)"
DEFAULT_BRANCH = os.environ.get("PROFILE_DEFAULT_BRANCH", "main")

# ── Third-party stat cards, cached in the repo ──────────────────────────────
_LANG_EXCLUDED_REPOS = ("KisaanMitra,NovaPulse,NEURACITY,X-FORECAST,GlamGlow,HealthCare-System-Dashboard,"
                        "URBAN-PLANNING,DonorConnectT,VoOTEX,finance-bud,Clipbait")
STAT_CARDS = {
    "assets/github-stats.svg":
        f"https://github-readme-stats.vercel.app/api?username={USERNAME}&show_icons=true&theme=radical"
        "&count_private=true&hide_border=true&rank_icon=github",
    "assets/top-langs.svg":
        f"https://github-readme-stats.vercel.app/api/top-langs/?username={USERNAME}&layout=compact"
        "&theme=radical&langs_count=10&hide_border=true&hide=postscript,visual%20basic%206.0"
        f"&exclude_repo={_LANG_EXCLUDED_REPOS}",
    "assets/streak.svg":
        f"https://streak-stats.demolab.com?user={USERNAME}&theme=radical&hide_border=true"
        "&date_format=M%20j%5B%2C%20Y%5D&ring=FE428E&fire=F8D847&currStreakLabel=F8D847",
}
# Text that only shows up on the error cards these services return with HTTP 200.
ERROR_MARKERS = ("something went wrong", "rate limit", "could not fetch", "maximum retries",
                 "bad credentials", "error occurred", "please try again", "not found",
                 "too many requests", "user not found")

# ── Pinned highlights (cards in assets/generated/pin-<slug>.svg) ─────────────
PINNED = [
    {"slug": "neurosoc", "repo": "Project_NeuroSOC", "emoji": "🧠", "name": "NeuroSOC",
     "tagline": "Neuromorphic AI Security Operations Center", "accent": PINK,
     "award": "🥈 1st Runner-Up · CyreneAI Hackathon",
     "description": "Real-time threat detection with an SNN + LNN + XGBoost ensemble, behavioural "
                    "profiling, autonomous sandbox containment and feedback retraining.",
     "tags": ["Spiking NN", "Liquid NN", "XGBoost", "Cybersecurity"]},
    {"slug": "jvalyx", "repo": "Jvalyx", "emoji": "🔥", "name": "Jvalyx",
     "tagline": "Satellite thermal-event intelligence", "accent": "#FF8A3D",
     "award": "🏆 Smart India Hackathon 2026 · Semifinalist",
     "description": "Satellite thermal-event triage and industrial fire consequence intelligence — "
                    "classifies orbital thermal feeds into risk tiers and hazard zones.",
     "tags": ["Satellite AI", "Thermal Triage", "Geospatial", "Risk Intel"]},
    {"slug": "astraeus", "repo": "PROJECT_ENTANGLEMENT", "emoji": "🚀", "name": "Project Astraeus",
     "tagline": "AI Mission Control", "accent": CYAN,
     "award": "🏅 Smart India Hackathon 2025 · Merit",
     "description": "Digital twin for satellite mission control — real-time telemetry, GNN + PPO "
                    "comms scheduling and 91% predictive failure-detection accuracy.",
     "tags": ["Digital Twin", "GNN", "PPO · RL", "TensorFlow"]},
    {"slug": "reggraph", "repo": "RegGraph-AI", "emoji": "🕸️", "name": "RegGraph-AI",
     "tagline": "Regulatory knowledge-graph intelligence", "accent": YELLOW,
     "award": "🏆 Zonal Champion · HackArena 2.0, IIIT Delhi",
     "description": "Knowledge graph for compliance mapping, automated regulation analysis and "
                    "explainable graph-based reasoning over legal & policy documents.",
     "tags": ["Knowledge Graphs", "Graph AI", "NLP", "RAG"]},
]

# ── Trophy shelf: (key, title, unit, thresholds for C B A AA AAA S SS SSS) ──
RANKS = ["C", "B", "A", "AA", "AAA", "S", "SS", "SSS"]
TROPHIES = [
    ("stars", "Stargazer", "stars earned", (1, 10, 30, 50, 100, 200, 700, 2000)),
    ("commits", "Commit Machine", "commits", (1, 10, 100, 200, 500, 1000, 2000, 4000)),
    ("contributions", "Contributor", "contributions", (1, 50, 200, 500, 1000, 2000, 4000, 8000)),
    ("public_repos", "Repo Creator", "public repos", (1, 5, 10, 20, 30, 50, 80, 120)),
    ("followers", "Community", "followers", (1, 10, 20, 50, 100, 200, 500, 1000)),
    ("prs", "Pull Requester", "pull requests", (1, 10, 20, 50, 100, 200, 500, 1000)),
    ("languages", "Polyglot", "languages", (1, 2, 4, 6, 8, 10, 13, 16)),
    ("reviews", "Reviewer", "reviews", (1, 5, 10, 20, 50, 100, 200, 500)),
]
TROPHY_SLOTS = 6

# Small white icons (data URIs) for the stat badges — readable on any badge colour.
_ICON_HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" '
              'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">')
ICONS = {
    "eye": '<path d="M1.5 12S5.5 4.5 12 4.5 22.5 12 22.5 12 18.5 19.5 12 19.5 1.5 12 1.5 12z"/>'
           '<circle cx="12" cy="12" r="3.2"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
             '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "star": '<path fill="white" stroke="none" d="M12 2.5l2.94 5.96 6.56.95-4.75 4.63 1.12 6.54L12 '
            '17.5l-5.87 3.08 1.12-6.54L2.5 9.41l6.56-.95z"/>',
    "repo": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 '
            '19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    "pulse": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
}


def icon_uri(name: str) -> str:
    svg = _ICON_HEAD + ICONS[name] + "</svg>"
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def log(msg: str) -> None:
    print(msg, flush=True)


# ── HTTP ────────────────────────────────────────────────────────────────────
def http_get(url: str, timeout: int = 40, attempts: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/svg+xml,*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # network errors come in many shapes; retry them all
            last = exc
            if attempt < attempts:
                time.sleep(5 * attempt)
    raise RuntimeError(f"GET failed after {attempts} attempts: {last}")


def looks_like_valid_card(body: bytes) -> tuple[bool, str]:
    text = body.decode("utf-8", "replace")
    head = text.lstrip()[:100].lower()
    if not (head.startswith("<svg") or head.startswith("<?xml")):
        return False, "not an SVG"
    if "</svg>" not in text.rstrip()[-50:].lower():
        return False, "truncated SVG"
    if len(body) < 1500:
        return False, f"suspiciously small ({len(body)} bytes)"
    lowered = text.lower()
    for marker in ERROR_MARKERS:
        if marker in lowered:
            return False, f"error card ({marker!r})"
    return True, "ok"


def fetch_stat_cards() -> None:
    for rel, url in STAT_CARDS.items():
        try:
            body = http_get(url)
            ok, why = looks_like_valid_card(body)
        except RuntimeError as exc:
            ok, why = False, str(exc)
        if ok:
            changed = save(os.path.join(ROOT, rel), body.decode("utf-8"))
            log(f"✅ {rel} {'updated' if changed else 'unchanged'}")
        else:
            log(f"::warning::Kept the previous {rel} — {why}")


# ── GitHub GraphQL ──────────────────────────────────────────────────────────
def graphql(token: str, query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode()
    for attempt in range(1, 4):
        req = urllib.request.Request(
            "https://api.github.com/graphql", data=payload,
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                     "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (502, 503, 504) and attempt < 3:
                time.sleep(5 * attempt)
                continue
            raise
        if data.get("errors"):
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data["data"]
    raise RuntimeError("GraphQL request kept failing")


Q_USER = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    login name createdAt
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection { contributionYears }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { name isFork stargazerCount forkCount primaryLanguage { name } }
    }
  }
}"""

Q_YEAR = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestReviewContributions
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def collect(token: str) -> dict:
    """Everything the generated cards and badges need, in one JSON-able dict."""
    repos, cursor = [], None
    while True:
        user = graphql(token, Q_USER, {"login": USERNAME, "cursor": cursor})["user"]
        page = user["repositories"]
        repos.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    now = dt.datetime.now(dt.timezone.utc)
    days: dict[str, int] = {}
    commits = reviews = 0
    for year in sorted(user["contributionsCollection"]["contributionYears"]):
        start = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
        end = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now)
        cc = graphql(token, Q_YEAR, {"login": USERNAME, "from": start.isoformat(),
                                     "to": end.isoformat()})["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"]
        reviews += cc["totalPullRequestReviewContributions"]
        for week in cc["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                if day["date"].startswith(str(year)):
                    days[day["date"]] = day["contributionCount"]

    aliases = "\n".join(
        f'  r{i}: repository(owner: "{USERNAME}", name: "{p["repo"]}") '
        "{ name stargazerCount forkCount pushedAt primaryLanguage { name color } }"
        for i, p in enumerate(PINNED))
    pinned_raw = graphql(token, "query {\n" + aliases + "\n}", {})
    pinned = {}
    for i, p in enumerate(PINNED):
        node = pinned_raw.get(f"r{i}")
        if node:
            lang = node["primaryLanguage"] or {}
            pinned[p["repo"]] = {"stars": node["stargazerCount"], "forks": node["forkCount"],
                                 "language": lang.get("name"), "color": lang.get("color"),
                                 "pushed_at": node["pushedAt"]}

    monthly: dict[str, int] = {}
    for date, count in days.items():
        monthly[date[:7]] = monthly.get(date[:7], 0) + count
    languages = sorted({r["primaryLanguage"]["name"] for r in repos
                        if not r["isFork"] and r["primaryLanguage"]})
    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "login": user["login"],
        "name": user["name"],
        "created_at": user["createdAt"],
        "followers": user["followers"]["totalCount"],
        "public_repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "commits": commits,
        "reviews": reviews,
        "contributions": sum(days.values()),
        "languages": len(languages),
        "language_names": languages,
        "monthly": dict(sorted(monthly.items())),
        "pinned": pinned,
    }


# ── Rendering helpers ───────────────────────────────────────────────────────
def compact(n: int) -> str:
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    if n >= 1_000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def last_months(monthly: dict[str, int], today: dt.date, count: int = 12) -> list[tuple[str, int]]:
    out, year, month = [], today.year, today.month
    for _ in range(count):
        key = f"{year:04d}-{month:02d}"
        out.append((key, monthly.get(key, 0)))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return out[::-1]


def month_label(key: str) -> str:
    date = dt.date(int(key[:4]), int(key[5:]), 1)
    return date.strftime("%b ’%y") if date.month == 1 else date.strftime("%b")


# ── Pinned project card ─────────────────────────────────────────────────────
FORK_ICON = ('<path d="M5 3.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0zm0 2.122a2.25 2.25 0 1 0-1.5 0v.878A2.25 '
             '2.25 0 0 0 5.75 8.5h1.5v2.128a2.251 2.251 0 1 0 1.5 0V8.5h1.5a2.25 2.25 0 0 0 2.25-2.25v-.878a2.25 '
             '2.25 0 1 0-1.5 0v.878a.75.75 0 0 1-.75.75h-4.5A.75.75 0 0 1 5 6.25v-.878zm3.75 7.378a.75.75 0 1 '
             '1-1.5 0 .75.75 0 0 1 1.5 0zm3-8.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5z"/>')


def render_pin(project: dict, meta: dict | None) -> str:
    w, h = 420, 236
    accent = project["accent"]
    defs = (f'<clipPath id="c"><rect width="{w}" height="{h}" rx="14"/></clipPath>'
            + linear("bar", [(0, accent), (1, PURPLE)])
            + f'<radialGradient id="g" cx="0.95" cy="0" r="0.75"><stop offset="0" stop-color="{accent}" '
              f'stop-opacity="0.20"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>')
    parts = [
        '<g clip-path="url(#c)">',
        f'<rect width="{w}" height="{h}" fill="{BG}"/><rect width="{w}" height="{h}" fill="url(#g)"/>',
        f'<rect width="{w}" height="4" fill="url(#bar)"/></g>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="13.5" fill="none" stroke="{accent}" '
        'stroke-opacity="0.35"/>',
        f'<rect x="18" y="22" width="46" height="46" rx="12" fill="{accent}" fill-opacity="0.13" '
        f'stroke="{accent}" stroke-opacity="0.5"/>',
        f'<text x="41" y="53.5" text-anchor="middle" font-size="23">{project["emoji"]}</text>',
        f'<text x="78" y="42" font-size="19" font-weight="700" fill="{TEXT}">{esc(project["name"])}</text>',
        f'<text x="78" y="62" font-size="12.5" font-weight="600" fill="{accent}">{esc(project["tagline"])}</text>',
    ]
    award_w = text_width(project["award"], 12, bold=True) + 24
    parts.append(f'<rect x="18" y="82" width="{award_w:.0f}" height="24" rx="12" fill="{YELLOW}" '
                 f'fill-opacity="0.10" stroke="{YELLOW}" stroke-opacity="0.45"/>'
                 f'<text x="30" y="98.5" font-size="12" font-weight="700" fill="{YELLOW}">'
                 f'{esc(project["award"])}</text>')
    for i, line in enumerate(wrap(project["description"], 13, w - 36, max_lines=3)):
        parts.append(f'<text x="18" y="{130 + i * 18.5:.1f}" font-size="13" fill="{TEXT_SOFT}">{esc(line)}</text>')
    x = 18
    for tag in project["tags"]:
        tw = text_width(tag, 11.5) + 20
        if x + tw > w - 18:
            break
        parts.append(f'<rect x="{x:.0f}" y="180" width="{tw:.0f}" height="22" rx="11" fill="{accent}" '
                     f'fill-opacity="0.10" stroke="{accent}" stroke-opacity="0.35"/>'
                     f'<text x="{x + 10:.0f}" y="195" font-size="11.5" fill="{TEXT_SOFT}">{esc(tag)}</text>')
        x += tw + 6
    x = 18
    if meta and meta.get("language"):
        colour = meta.get("color") or TEXT_MUTED
        parts.append(f'<circle cx="{x + 5}" cy="218" r="5" fill="{colour}"/>'
                     f'<text x="{x + 15}" y="222" font-size="12" fill="{TEXT_MUTED}">{esc(meta["language"])}</text>')
        x += 15 + text_width(meta["language"], 12) + 16
    if meta and meta.get("stars"):
        parts.append(f'<text x="{x}" y="222" font-size="12" fill="{TEXT_MUTED}">★ {meta["stars"]}</text>')
        x += text_width(f"★ {meta['stars']}", 12) + 16
    if meta and meta.get("forks"):
        parts.append(f'<g transform="translate({x},210.5) scale(0.82)" fill="{TEXT_MUTED}">{FORK_ICON}</g>'
                     f'<text x="{x + 16}" y="222" font-size="12" fill="{TEXT_MUTED}">{meta["forks"]}</text>')
    parts.append(f'<text x="{w - 18}" y="222" text-anchor="end" font-size="12" font-weight="600" '
                 f'fill="{accent}">View on GitHub ↗</text>')
    return document(w, h, "".join(parts), title=f"{project['name']} — {project['tagline']}",
                    desc=f"{project['award']}. {project['description']}", defs=defs)


# ── Trophy shelf ────────────────────────────────────────────────────────────
TIERS = {  # rank index range -> (gradient id, stroke colour, gradient stops)
    "s": ("tS", YELLOW, [(0, YELLOW), (1, PINK)]),
    "a": ("tA", CYAN, [(0, CYAN), (1, VIOLET)]),
    "b": ("tB", "#8E8AAE", [(0, "#E4E1F5"), (1, "#7B7799")]),
}
CUP = ('<path d="M18 8h28v14c0 10-6.3 18-14 18s-14-8-14-18z" fill="url(#{g})"/>'
       '<path d="M18 12h-7c0 9 3.5 14 9.5 15M46 12h7c0 9-3.5 14-9.5 15" fill="none" stroke="url(#{g})" '
       'stroke-width="3.5" stroke-linecap="round"/>'
       '<rect x="28.5" y="39" width="7" height="9" fill="url(#{g})"/>'
       '<rect x="20" y="48" width="24" height="6" rx="2" fill="url(#{g})"/>'
       '<rect x="16" y="54" width="32" height="5" rx="2" fill="url(#{g})" opacity="0.8"/>'
       '<path d="M32 15.5l1.9 3.9 4.3.6-3.1 3 .7 4.3-3.8-2-3.8 2 .7-4.3-3.1-3 4.3-.6z" fill="{bg}" '
       'fill-opacity="0.55"/>')


def rank_of(value: int, thresholds: tuple[int, ...]) -> int:
    return sum(1 for t in thresholds if value >= t) - 1


def render_trophies(data: dict) -> str:
    entries = []
    for order, (key, title, unit, thresholds) in enumerate(TROPHIES):
        value = int(data.get(key) or 0)
        rank = rank_of(value, thresholds)
        if rank < 0:
            continue
        nxt = thresholds[rank + 1] if rank + 1 < len(thresholds) else None
        floor = thresholds[rank]
        progress = 1.0 if nxt is None else (value - floor) / (nxt - floor)
        entries.append((rank, -order, title, unit, value, progress, nxt))
    entries.sort(reverse=True)
    entries = entries[:TROPHY_SLOTS]

    cw, ch, gap = 130, 172, 12
    w = len(entries) * cw + (len(entries) - 1) * gap
    defs = "".join(linear(gid, stops, 0, 0, 1, 1) for gid, _, stops in TIERS.values())
    style = ("@keyframes pop{from{transform:scale(.94)}to{transform:none}}"
             ".t{transform-box:fill-box;transform-origin:center;animation:pop .7s ease-out both}"
             "@keyframes glow{0%,100%{opacity:.35}50%{opacity:.8}}.halo{animation:glow 3s ease-in-out infinite}")
    parts = []
    for i, (rank, _, title, unit, value, progress, nxt) in enumerate(entries):
        tier = "s" if rank >= 5 else "a" if rank >= 2 else "b"
        gid, stroke, _ = TIERS[tier]
        x = i * (cw + gap)
        label = RANKS[rank]
        hint = f"next rank at {nxt:,}" if nxt else "max rank"
        # position on the outer group: a CSS transform on the animated group would override it
        parts.append(
            f'<g transform="translate({x},0)"><g class="t" style="animation-delay:{i * 0.12:.2f}s">'
            f'<title>{esc(title)}: {value:,} {esc(unit)} — rank {label} ({hint})</title>'
            f'<rect x="0.5" y="0.5" width="{cw - 1}" height="{ch - 1}" rx="14" fill="{BG}" stroke="{stroke}" '
            'stroke-opacity="0.45"/>'
            f'<ellipse class="halo" cx="{cw / 2}" cy="64" rx="38" ry="30" fill="url(#{gid})" fill-opacity="0.16"/>'
            f'<rect x="10" y="10" width="{text_width(label, 11.5, True) + 16:.0f}" height="20" rx="10" '
            f'fill="url(#{gid})"/><text x="18" y="24.5" font-size="11.5" font-weight="800" fill="{BG}">{label}</text>'
            f'<g transform="translate({cw / 2 - 29},30) scale(0.9)">{CUP.format(g=gid, bg=BG)}</g>'
            f'<text x="{cw / 2}" y="118" text-anchor="middle" font-size="13.5" font-weight="700" fill="{TEXT}">'
            f'{esc(title)}</text>'
            f'<text x="{cw / 2}" y="137" text-anchor="middle" font-size="12" fill="{TEXT_MUTED}">'
            f'{value:,} {esc(unit)}</text>'
            f'<rect x="18" y="151" width="{cw - 36}" height="5" rx="2.5" fill="#2A2742"/>'
            f'<rect x="18" y="151" width="{max(4, (cw - 36) * progress):.1f}" height="5" rx="2.5" fill="url(#{gid})"/>'
            '</g></g>')
    return document(w, ch, "".join(parts), title="GitHub trophies",
                    desc=", ".join(f"{e[2]} {RANKS[e[0]]}" for e in entries), defs=defs, style=style)


# ── Monthly contributions chart ─────────────────────────────────────────────
def nice_ceiling(value: int) -> int:
    if value <= 10:
        return 10
    magnitude = 10 ** int(math.log10(value))
    for step in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if value <= step * magnitude:
            return int(step * magnitude)
    return value


def render_monthly(data: dict, today: dt.date) -> str:
    w, h = 840, 284
    months = last_months(data["monthly"], today)
    values = [v for _, v in months]
    top = nice_ceiling(max(values) if any(values) else 10)
    best_i = max(range(len(values)), key=lambda i: values[i])
    total12 = sum(values)
    left, right, y_top, y_base = 58, w - 26, 112, 232
    slot = (right - left) / len(months)
    bar_w = 34
    defs = (linear("bar", [(0, PINK), (1, VIOLET)], 0, 0, 0, 1)
            + linear("best", [(0, YELLOW), (1, PINK)], 0, 0, 0, 1)
            + linear("edge", [(0, PINK, 0.7), (0.5, PURPLE, 0.4), (1, CYAN, 0.6)])
            + f'<clipPath id="c"><rect width="{w}" height="{h}" rx="16"/></clipPath>'
            + f'<radialGradient id="g" cx="0.1" cy="0" r="0.7"><stop offset="0" stop-color="{PINK}" '
              f'stop-opacity="0.14"/><stop offset="1" stop-color="{PINK}" stop-opacity="0"/></radialGradient>')
    # Bars stay static (complete at t=0); only the best and in-progress months move.
    style = ("@keyframes pulse{0%,100%{opacity:1}50%{opacity:.72}}.best{animation:pulse 2.4s ease-in-out infinite}"
             "@keyframes march{to{stroke-dashoffset:-12}}.now{animation:march 1.2s linear infinite}")
    parts = [
        f'<g clip-path="url(#c)"><rect width="{w}" height="{h}" fill="{BG}"/>'
        f'<rect width="{w}" height="{h}" fill="url(#g)"/></g>',
        f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="15.5" fill="none" '
        'stroke="url(#edge)" stroke-width="1.5"/>',
        f'<text x="26" y="42" font-size="18" font-weight="700" fill="{PINK}">📈 Contribution Activity</text>',
        f'<text x="26" y="64" font-size="12.5" fill="{TEXT_MUTED}">Contributions per month · last 12 months'
        f' · refreshed {esc(today.strftime("%d %b %Y"))}</text>',
    ]
    best_key = months[best_i][0]
    best_label = dt.date(int(best_key[:4]), int(best_key[5:]), 1).strftime("%b %Y")
    kpis = [("All-time", f"{data['contributions']:,}", CYAN),
            ("Last 12 months", f"{total12:,}", PINK),
            (f"Best · {best_label}", f"{values[best_i]:,}", YELLOW)]
    kx = w - 26
    for label, value, colour in reversed(kpis):
        block = max(text_width(value, 21, True), text_width(label, 11.5)) + 6
        parts.append(f'<text x="{kx}" y="44" text-anchor="end" font-size="21" font-weight="800" '
                     f'fill="{colour}">{value}</text>'
                     f'<text x="{kx}" y="62" text-anchor="end" font-size="11.5" fill="{TEXT_MUTED}">{esc(label)}</text>')
        kx -= block + 26
    for frac in (0, 0.5, 1):
        y = y_base - (y_base - y_top) * frac
        parts.append(f'<line x1="{left - 8}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{BORDER}" '
                     f'stroke-dasharray="{"0" if frac == 0 else "3 5"}"/>'
                     f'<text x="{left - 14}" y="{y + 4:.1f}" text-anchor="end" font-size="10.5" '
                     f'fill="{TEXT_MUTED}">{compact(int(top * frac))}</text>')
    current_key = f"{today.year:04d}-{today.month:02d}"
    for i, (key, value) in enumerate(months):
        cx = left + slot * i + slot / 2
        bh = 0 if not value else max(3.0, (y_base - y_top) * value / top)
        best = i == best_i and value
        if key == current_key:      # month still in progress: dashed, "marching" outline
            attrs = ('class="now" fill="url(#bar)" fill-opacity="0.75" stroke="#FFFFFF" '
                     'stroke-opacity="0.45" stroke-dasharray="3 3"')
        elif best:
            attrs = 'class="best" fill="url(#best)"'
        else:
            attrs = 'fill="url(#bar)"'
        if bh:
            parts.append(f'<rect {attrs} x="{cx - bar_w / 2:.1f}" y="{y_base - bh:.1f}" width="{bar_w}" '
                         f'height="{bh:.1f}" rx="6"/>')
        parts.append(f'<text x="{cx:.1f}" y="{y_base - bh - 8:.1f}" text-anchor="middle" font-size="11.5" '
                     f'font-weight="700" fill="{YELLOW if best else TEXT_SOFT}">{value}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{y_base + 20}" text-anchor="middle" font-size="11.5" '
                     f'fill="{TEXT_SOFT}">{esc(month_label(key))}</text>')
        if key == current_key:
            parts.append(f'<text x="{cx:.1f}" y="{y_base + 35}" text-anchor="middle" font-size="10" '
                         f'fill="{TEXT_MUTED}">so far</text>')
    summary = ", ".join(f"{month_label(k)}: {v}" for k, v in months)
    return document(w, h, "".join(parts), title="Monthly contributions (last 12 months)",
                    desc=summary, defs=defs, style=style)


# ── Profile views: carry the komarev count over to hits.sh ─────────────────
HITS_PATH = f"github.com/{USERNAME}"


def komarev_count() -> int | None:
    try:
        svg = http_get(f"https://komarev.com/ghpvc/?username={USERNAME}&style=flat", attempts=2).decode()
    except RuntimeError as exc:
        log(f"::warning::komarev.com unreachable: {exc}")
        return None
    numbers = [int(t.replace(",", "")) for t in re.findall(r">\s*([\d,]+)\s*</text>", svg)]
    return max(numbers) if numbers else None


def resolve_views(state_path: str, allow_network: bool) -> int:
    """Return the number of views to add on top of hits.sh's own counter.

    The old komarev.com counter stopped rendering reliably on GitHub (its image
    proxy fails to load it), so the badge moved to hits.sh. hits.sh counts from
    zero and adds ``extraCount``; that offset is komarev's total, re-read on
    every run until the first successful run on the default branch, then frozen
    (once the README on the default branch points at hits.sh nobody loads
    komarev any more, so its number stops changing).
    """
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except FileNotFoundError:
        state = {"provider": "hits.sh", "path": HITS_PATH, "carried_over_from": "komarev.com/ghpvc",
                 "extra_count": 0, "locked": False}
    if allow_network and not state.get("locked"):
        count = komarev_count()
        if count is not None:
            state["extra_count"] = count
            state["captured_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if os.environ.get("GITHUB_REF_NAME") == DEFAULT_BRANCH:
                state["locked"] = True
            log(f"👁️  komarev views carried over: {count} (locked={state['locked']})")
    save(state_path, json.dumps(state, indent=2) + "\n")
    return int(state.get("extra_count") or 0)


# ── README blocks ───────────────────────────────────────────────────────────
def shields(label: str, message: str, colour: str, icon: str) -> str:
    def part(s: str) -> str:
        return urllib.parse.quote(s.replace("-", "--").replace("_", "__"), safe="")
    query = urllib.parse.urlencode({"style": "for-the-badge", "labelColor": "141321",
                                    "logo": icon_uri(icon)}, quote_via=urllib.parse.quote)
    return f"https://img.shields.io/badge/{part(label)}-{part(message)}-{colour}?{query}"


def badges_block(data: dict, extra_views: int) -> str:
    params = {"style": "for-the-badge", "label": "Profile Views", "color": "6E40C9",
              "labelColor": "141321", "logo": icon_uri("eye")}
    if extra_views:
        params["extraCount"] = extra_views
    views = f"https://hits.sh/{HITS_PATH}.svg?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    profile = f"https://github.com/{USERNAME}"
    items = [
        (f"https://hits.sh/{HITS_PATH}/", views, "Profile views"),
        (f"{profile}?tab=followers", shields("Followers", f"{data['followers']:,}", "FE428E", "users"),
         f"Followers: {data['followers']:,}"),
        (f"{profile}?tab=repositories&sort=stargazers",
         shields("Total Stars", f"{data['stars']:,}", "F8D847", "star"), f"Total stars: {data['stars']:,}"),
        (f"{profile}?tab=repositories", shields("Public Repos", f"{data['public_repos']:,}", "A9FEF7", "repo"),
         f"Public repositories: {data['public_repos']:,}"),
        (profile, shields("Contributions", f"{data['contributions']:,}", "2BD67B", "pulse"),
         f"All-time contributions: {data['contributions']:,}"),
    ]
    return "\n".join(f'<a href="{esc(href)}"><img src="{esc(src)}" alt="{esc(alt)}"/></a>'
                     for href, src, alt in items)


def pulse_block(now: dt.datetime) -> str:
    run = os.environ.get("GITHUB_RUN_NUMBER")
    run_txt = f" · run #{run}" if run else ""
    return (f'<p align="center"><sub>🤖 Auto-synced every 6 hours by GitHub Actions · last refreshed '
            f'<code>{now:%Y-%m-%d %H:%M} UTC</code> ({now:%A}){run_txt}</sub></p>')


def replace_block(text: str, name: str, content: str) -> str:
    pattern = re.compile(rf"(<!-- {name}:START -->)(.*?)(<!-- {name}:END -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"README is missing the <!-- {name}:START/END --> markers")
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(3)}", text, count=1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="render from a saved data JSON instead of calling the API")
    ap.add_argument("--skip-cards", action="store_true", help="don't download third-party stat cards")
    ap.add_argument("--no-views", action="store_true", help="don't contact komarev.com for the view count")
    ap.add_argument("--readme", default=README)
    args = ap.parse_args()

    if not args.skip_cards:
        fetch_stat_cards()

    saved = os.path.join(DATA_DIR, "profile.json")
    if args.data:
        with open(args.data, encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Set GH_TOKEN (or GITHUB_TOKEN) to query the GitHub API, or pass --data.")
        try:
            data = collect(token)
            save(saved, json.dumps(data, indent=2) + "\n")
        except Exception as exc:  # keep the profile alive on API hiccups
            if not os.path.exists(saved):
                raise
            log(f"::warning::GitHub API query failed ({exc}); re-using {os.path.relpath(saved, ROOT)}")
            with open(saved, encoding="utf-8") as fh:
                data = json.load(fh)
    log(f"📊 followers={data['followers']} stars={data['stars']} repos={data['public_repos']} "
        f"contributions={data['contributions']} commits={data['commits']}")

    now = dt.datetime.now(dt.timezone.utc)
    for project in PINNED:
        save(os.path.join(GENERATED, f"pin-{project['slug']}.svg"),
             render_pin(project, data["pinned"].get(project["repo"])))
    save(os.path.join(GENERATED, "trophies.svg"), render_trophies(data))
    save(os.path.join(GENERATED, "contributions-monthly.svg"), render_monthly(data, now.date()))

    extra = resolve_views(os.path.join(DATA_DIR, "views.json"), allow_network=not args.no_views)
    with open(args.readme, encoding="utf-8") as fh:
        readme = fh.read()
    readme = replace_block(readme, "STATS-BADGES", badges_block(data, extra))
    readme = replace_block(readme, "PULSE", pulse_block(now))
    save(args.readme, readme)
    log("✨ README and generated cards refreshed")


if __name__ == "__main__":
    main()

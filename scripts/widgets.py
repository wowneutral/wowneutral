"""SVG widgets for the profile README.

Every widget is drawn twice, once for GitHub's light theme and once for dark,
and the README picks one with <picture>. One accent only: highlighter cyan,
the same cyan as the cards on my flows. No gradients, no glow, no glass.

Animations are CSS/SMIL inside the SVG, so they run when the image loads.
Each one is written so that if a viewer doesn't run animations, the final
state is what shows.
"""
from __future__ import annotations

import html
from datetime import date, datetime, timedelta

THEMES = {
    "light": dict(bg="#ffffff", line="#d0d7de", ink="#1f2328", mute="#59636e",
                  faint="#eef1f4", acc="#73f7f8", acc_ink="#0a8f98",
                  ok="#1a7f37", bad="#cf222e"),
    "dark": dict(bg="#0d1117", line="#30363d", ink="#f0f6fc", mute="#9198a1",
                 faint="#1b2129", acc="#73f7f8", acc_ink="#5fe6e8",
                 ok="#3fb950", bad="#f85149"),
}

MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

FULL, HALF = 840, 412
e = html.escape


def base_css(t):
    return f"""
  .frame {{ fill: {t['bg']}; stroke: {t['line']}; }}
  .lbl {{ font: 600 10.5px {MONO}; letter-spacing: .08em; fill: {t['mute']}; }}
  .num {{ font: 600 32px {MONO}; fill: {t['ink']}; }}
  .num.on {{ fill: #000; }}
  .num.n28 {{ font-size: 28px; }}
  .big {{ font: 600 44px {MONO}; fill: {t['ink']}; }}
  .txt {{ font: 13px {SANS}; fill: {t['ink']}; }}
  .bold {{ font: 600 14px {SANS}; fill: {t['ink']}; }}
  .sm {{ font: 11.5px {SANS}; fill: {t['mute']}; }}
  .mono {{ font: 12.5px {MONO}; fill: {t['ink']}; }}
  .mute {{ fill: {t['mute']}; }}
  .acc {{ fill: {t['acc_ink']}; }}
  .roll {{ animation: roll 1.1s cubic-bezier(.2,.7,.2,1) backwards; }}
  @keyframes roll {{ from {{ transform: translateY(0); }} }}
  .grow {{ transform-box: fill-box; transform-origin: 50% 100%; animation: grow .7s cubic-bezier(.2,.7,.2,1) backwards; }}
  @keyframes grow {{ from {{ transform: scaleY(0); }} }}
  .growx {{ transform-box: fill-box; transform-origin: 0 50%; animation: growx .8s cubic-bezier(.2,.7,.2,1) backwards; }}
  @keyframes growx {{ from {{ transform: scaleX(0); }} }}
  .draw {{ stroke-dasharray: 1; animation: draw 1.2s ease-out backwards; }}
  @keyframes draw {{ from {{ stroke-dashoffset: 1; }} }}
  .pop {{ animation: pop .4s ease-out backwards; }}
  @keyframes pop {{ from {{ opacity: 0; }} }}
  .pulse {{ transform-box: fill-box; transform-origin: center; animation: pulse 2.4s ease-out infinite; }}
  @keyframes pulse {{ from {{ transform: scale(1); opacity: .55; }} to {{ transform: scale(3.2); opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
"""


def svg(w, h, t, inner, label, css=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{e(label)}">'
            f'<style>{base_css(t)}{css}</style>'
            f'<rect class="frame" x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="6"/>'
            f'{inner}</svg>\n')


_clip = [0]


def odo(x, y, value, size=32, cls="num", delay=0.0):
    """Odometer: each digit is a 0-9 strip that rolls up to its value."""
    s = str(value)
    cw, lh = size * 0.6, size * 1.2
    _clip[0] += 1
    cid = f"o{_clip[0]}"
    out = [f'<clipPath id="{cid}"><rect x="{x}" y="{y - size * .9:.1f}" width="{cw * len(s) + 2:.1f}" height="{lh:.1f}"/></clipPath>',
           f'<g clip-path="url(#{cid})">']
    for i, ch in enumerate(s):
        cx = x + i * cw
        if ch.isdigit():
            d = int(ch)
            strip = "".join(f'<text class="{cls}" x="{cx:.1f}" y="{y + n * lh:.1f}">{n}</text>' for n in range(10))
            out.append(f'<g class="roll" style="transform: translateY({-d * lh:.1f}px); '
                       f'animation-delay: {delay + i * .07:.2f}s">{strip}</g>')
        else:
            out.append(f'<text class="{cls}" x="{cx:.1f}" y="{y}">{e(ch)}</text>')
    out.append("</g>")
    return "".join(out), cw * len(s)


def fmt(n):
    return f"{n:,}"


def delta_text(now, before, unit="this week"):
    if before is None:
        return "new this week"
    dlt = now - before
    if dlt == 0:
        return f"no change {unit}"
    return f"{'+' if dlt > 0 else '−'}{abs(dlt)} {unit}"


# ---------------------------------------------------------------- stats row

def stats(d, t):
    w, h = FULL, 150
    tiles = [
        ("CONTRIBUTIONS", d["total"], "last 12 months", True),
        ("REPOSITORIES", len(d["repos"]), f"{d['new_repos']} new this year", False),
        ("STARS", d["stars"], delta_text(d["stars"], d["week_ago"].get("stars")), False),
        ("FOLLOWERS", d["followers"], delta_text(d["followers"], d["week_ago"].get("followers")), False),
    ]
    tw = (w - 40) / 4
    parts = []
    for i, (lbl, val, sub, hero) in enumerate(tiles):
        x = 20 + i * tw
        if i:
            parts.append(f'<line x1="{x:.1f}" y1="24" x2="{x:.1f}" y2="{h - 24}" stroke="{t["line"]}"/>')
        px = x + (0 if i == 0 else 20)
        parts.append(f'<text class="lbl" x="{px:.1f}" y="40">{lbl}</text>')
        num, nw = odo(px + (6 if hero else 0), 86, fmt(val), 32, "num on" if hero else "num", delay=i * .12)
        if hero:
            parts.append(f'<rect class="growx" x="{px:.1f}" y="56" width="{nw + 12:.1f}" height="40" fill="{t["acc"]}" style="animation-delay:.1s"/>')
        parts.append(num)
        parts.append(f'<text class="sm" x="{px:.1f}" y="118">{e(sub)}</text>')
    # 30-day sparkline under the hero tile's sub line, right of the number
    last = [c for _, c in d["days"][-30:]]
    peak = max(last) or 1
    sx0, sx1, sy0, sy1 = 20 + tw - 92, 20 + tw - 16, 92, 60
    pts = " ".join(f"{sx0 + (sx1 - sx0) * k / 29:.1f},{sy0 - (sy0 - sy1) * c / peak:.1f}" for k, c in enumerate(last))
    parts.append(f'<polyline class="draw" pathLength="1" points="{pts}" fill="none" stroke="{t["acc_ink"]}" stroke-width="1.6" stroke-linejoin="round"/>')
    parts.append(f'<text class="sm" x="{sx1:.1f}" y="118" text-anchor="end" font-size="10">30d</text>')
    return svg(w, h, t, "".join(parts), f"{d['total']} contributions, {len(d['repos'])} repositories, {d['stars']} stars, {d['followers']} followers")


# ---------------------------------------------------------------- streak

def streak(d, t):
    w, h = HALF, 200
    cur, best, active = d["streak"], d["best"], d["active"]
    r, cx, cy = 56, 92, 104
    frac = (cur / best) if best else 0
    ring = (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["faint"]}" stroke-width="10"/>'
            f'<circle class="draw" pathLength="1" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["acc"]}" stroke-width="10" '
            f'stroke-dasharray="{frac:.3f} 1" transform="rotate(-90 {cx} {cy})" style="stroke-dasharray:{frac:.3f} 1"/>')
    num, nw = odo(cx - len(str(cur)) * 0.6 * 44 / 2, cy + 12, cur, 44, "big")
    last = next((ds for ds, c in reversed(d["days"]) if c), None)
    last_txt = datetime.fromisoformat(last).strftime("%b %-d") if last else "—"
    rows = [("BEST", f"{best} day{'s' if best != 1 else ''}"),
            ("ACTIVE DAYS", f"{active} this year"),
            ("LAST ACTIVE", last_txt)]
    side = "".join(f'<text class="lbl" x="190" y="{70 + k * 42}">{a}</text><text class="txt" x="190" y="{88 + k * 42}">{e(b)}</text>' for k, (a, b) in enumerate(rows))
    inner = (f'<text class="lbl" x="24" y="34">STREAK</text>{ring}{num}'
             f'<text class="sm" x="{cx}" y="{cy + 32}" text-anchor="middle">day{"s" if cur != 1 else ""} running</text>{side}')
    return svg(w, h, t, inner, f"Current streak {cur} days, best {best}")


# ---------------------------------------------------------------- hours

def hours(d, t):
    w, h = HALF, 200
    counts = d["hours"]
    total = sum(counts)
    peak_i = max(range(24), key=lambda k: counts[k]) if total else None
    x0, x1, base, top = 24, w - 24, 150, 64
    bw = (x1 - x0) / 24
    m = max(counts) or 1
    bars = []
    for k, c in enumerate(counts):
        bh = max(2, (base - top) * c / m) if c else 2
        fill = t["acc"] if k == peak_i else (t["acc_ink"] if c else t["faint"])
        op = "1" if (k == peak_i or not c) else ".55"
        bars.append(f'<rect class="grow" x="{x0 + k * bw + 1.5:.1f}" y="{base - bh:.1f}" width="{bw - 3:.1f}" height="{bh:.1f}" rx="1.5" fill="{fill}" fill-opacity="{op}" style="animation-delay:{k * .025:.3f}s"/>')
    ticks = "".join(f'<text class="sm" x="{x0 + k * bw + bw / 2:.1f}" y="{base + 18}" text-anchor="middle" font-size="10">{lab}</text>'
                    for k, lab in [(0, "12a"), (6, "6a"), (12, "12p"), (18, "6p"), (23, "11p")])

    def hr(k):
        return f"{(k % 12) or 12} {'AM' if k < 12 else 'PM'}"
    head = f"Mostly around {hr(peak_i)}" if peak_i is not None else "Waiting on the first commit"
    inner = (f'<text class="lbl" x="24" y="34">WHEN I SHIP</text>'
             f'<text class="bold" x="24" y="54">{e(head)}</text>'
             f'<text class="sm" x="{w - 24}" y="54" text-anchor="end">{total} commits, ET</text>'
             + "".join(bars) + ticks)
    return svg(w, h, t, inner, head)


# ---------------------------------------------------------------- year heatmap

def year(d, t):
    days = d["days"][-371:]
    first = date.fromisoformat(days[0][0])
    off = (first.weekday() + 1) % 7
    cell, gap, x0, y0 = 11, 3, 52, 58
    peak = max((c for _, c in days), default=0) or 1
    rects, months, seen = [], [], set()
    for i, (ds, c) in enumerate(days):
        k = i + off
        col, row = k // 7, k % 7
        x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
        dt = date.fromisoformat(ds)
        if dt.day <= 7 and row == 0 or (i == 0):
            key = (dt.year, dt.month)
            if key not in seen and dt.day <= 7:
                seen.add(key)
                months.append(f'<text class="sm" x="{x}" y="{y0 - 10}" font-size="10">{dt:%b}</text>')
        if c:
            lvl = min(4, 1 + int(3 * c / peak))
            op = [0, .4, .6, .8, 1][lvl]
            rects.append(f'<rect class="pop" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{t["acc"]}" fill-opacity="{op}" style="animation-delay:{col * .012:.3f}s"><title>{ds}: {c}</title></rect>')
        else:
            rects.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{t["faint"]}"/>')
    weeks = (len(days) + off + 6) // 7
    w = x0 + weeks * (cell + gap) + 24
    h = y0 + 7 * (cell + gap) + 44
    dl = "".join(f'<text class="sm" x="24" y="{y0 + r * (cell + gap) + 9}" font-size="10">{n}</text>' for r, n in [(1, "Mon"), (3, "Wed"), (5, "Fri")])
    lg_x = w - 24 - 5 * (cell + 3) - 60
    legend = (f'<text class="sm" x="{lg_x}" y="{h - 18}" font-size="10">less</text>'
              + f'<rect x="{lg_x + 28}" y="{h - 27}" width="{cell}" height="{cell}" rx="2" fill="{t["faint"]}"/>'
              + "".join(f'<rect x="{lg_x + 28 + (k + 1) * (cell + 3)}" y="{h - 27}" width="{cell}" height="{cell}" rx="2" fill="{t["acc"]}" fill-opacity="{op}"/>' for k, op in enumerate([.4, .6, .8, 1]))
              + f'<text class="sm" x="{lg_x + 28 + 5 * (cell + 3) + 4}" y="{h - 18}" font-size="10">more</text>')
    busiest = max(days, key=lambda p: p[1])
    note = f"{d['total']} contributions in the last year · busiest day {date.fromisoformat(busiest[0]):%b %-d} ({busiest[1]})" if busiest[1] else f"{d['total']} contributions in the last year"
    inner = (f'<text class="lbl" x="24" y="30">THE YEAR</text>' + "".join(months) + dl + "".join(rects)
             + f'<text class="sm" x="24" y="{h - 18}">{e(note)}</text>' + legend)
    return svg(w, h, t, inner, note)


# ---------------------------------------------------------------- languages

def langs(d, t):
    w = FULL
    items = d["langs"][:6]
    total = sum(s for _, s, _ in items) or 1
    full_total = d["lang_total"] or 1
    x0, x1, by = 24, w - 24, 52
    bars, x = [], x0
    for k, (name, size, color) in enumerate(items):
        bw = (x1 - x0) * size / total
        bars.append(f'<rect class="growx" x="{x:.1f}" y="{by}" width="{max(bw - 2, 1):.1f}" height="12" rx="2" fill="{color}" style="animation-delay:{k * .12:.2f}s"/>')
        x += bw
    rows = []
    cols, rh = 3, 26
    for k, (name, size, color) in enumerate(items):
        cx = x0 + (k % cols) * ((x1 - x0) / cols)
        cy = 96 + (k // cols) * rh
        pct = 100 * size / full_total
        rows.append(f'<circle cx="{cx + 5:.1f}" cy="{cy - 4}" r="4.5" fill="{color}"/>'
                    f'<text class="txt" x="{cx + 16:.1f}" y="{cy}">{e(name)}</text>'
                    f'<text class="mono mute" x="{cx + (x1 - x0) / cols - 24:.1f}" y="{cy}" text-anchor="end">{pct:.1f}%</text>')
    h = 96 + ((len(items) + cols - 1) // cols) * rh + 6
    inner = (f'<text class="lbl" x="24" y="34">STACK, BY BYTES</text>'
             f'<text class="sm" x="{w - 24}" y="34" text-anchor="end">{len(d["repos"])} repos, forks excluded</text>'
             + "".join(bars) + "".join(rows))
    return svg(w, h, t, inner, ", ".join(f"{n} {100 * s / full_total:.0f}%" for n, s, _ in items))


# ---------------------------------------------------------------- latest commit

def commit(d, t):
    w, h = FULL, 108
    c = d["latest_commit"]
    if c:
        msg = c["message"]
        if len(msg) > 62:
            msg = msg[:61] + "…"
        line = f'{c["oid"][:7]}  ({c["repo"]})  {msg}'
        chars = len(line)
        when = c["ago"]
    else:
        line, chars, when = "no public commits yet", 21, ""
    cw = 12.5 * 0.6
    tw = chars * cw + 4
    inner = (f'<text class="lbl" x="24" y="34">LATEST COMMIT</text>'
             f'<text class="sm" x="{w - 24}" y="34" text-anchor="end">{e(d["week_note"])}</text>'
             f'<text class="mono" x="24" y="66"><tspan class="acc">$</tspan><tspan class="mute"> git log -1 --oneline</tspan></text>'
             f'<text class="mono" x="40" y="91">{e(line)}</text>'
             f'<clipPath id="tc"><rect x="40" y="76" width="{tw:.1f}" height="22"/></clipPath>'
             f'<g clip-path="url(#tc)"><rect class="type" x="40" y="76" width="{tw:.1f}" height="22" fill="{t["bg"]}" '
             f'style="transform: translateX({tw:.1f}px); animation: type {max(.8, chars * .03):.2f}s steps({chars}) .4s backwards"/></g>'
             f'<style>@keyframes type {{ from {{ transform: translateX(0); }} }}</style>'
             f'<text class="mono acc" x="24" y="91">›</text>'
             f'<text class="sm" x="{w - 24}" y="91" text-anchor="end">{e(when)}</text>')
    return svg(w, h, t, inner, f"Latest commit: {line}")


# ---------------------------------------------------------------- sites

def sites(d, t):
    w = HALF
    rows = d["sites"]
    h = 58 + len(rows) * 46 + 24
    parts = [f'<text class="lbl" x="24" y="34">SITES I RUN</text>',
             f'<text class="sm" x="{w - 24}" y="34" text-anchor="end">checked hourly</text>']
    for k, s in enumerate(rows):
        y = 64 + k * 46
        col = t["ok"] if s["up"] else t["bad"]
        parts.append(f'<circle class="pulse" cx="30" cy="{y - 4}" r="4" fill="{col}" style="animation-delay:{k * .6:.1f}s"/>'
                     f'<circle cx="30" cy="{y - 4}" r="4" fill="{col}"/>'
                     f'<text class="txt" x="44" y="{y}">{e(s["name"])}</text>'
                     f'<text class="mono mute" x="{w - 24}" y="{y}" text-anchor="end">{s["ms"] if s["up"] else "down"}{" ms" if s["up"] else ""}</text>')
        hist = s["history"][-48:]
        hist = [None] * (48 - len(hist)) + hist
        tw = (w - 48) / 48
        for j, v in enumerate(hist):
            c = t["faint"] if v is None else (t["ok"] if v else t["bad"])
            op = "1" if v is None else ".85"
            parts.append(f'<rect x="{24 + j * tw:.1f}" y="{y + 10}" width="{tw - 2:.1f}" height="12" rx="1" fill="{c}" fill-opacity="{op}"/>')
    up = [v for s in rows for v in s["history"] if v is not None]
    pct = f"{100 * sum(up) / len(up):.1f}% up over the last 48 checks" if up else "first check"
    parts.append(f'<text class="sm" x="24" y="{h - 12}">{pct}</text>')
    return svg(w, h, t, "".join(parts), pct)


# ---------------------------------------------------------------- next tournament

def tournament(d, t, h_match=None):
    w = HALF
    ev = d["next_event"]
    h = h_match or (58 + len(d["sites"]) * 46 + 24)
    if not ev:
        inner = (f'<text class="lbl" x="24" y="34">NEXT ROUND</text>'
                 f'<text class="bold" x="24" y="96">Off season.</text>'
                 f'<text class="sm" x="24" y="118">Cutting cards until the next invite.</text>')
        return svg(w, h, t, inner, "No tournament scheduled")
    if ev["days"] <= 0:
        big = f'<rect x="20" y="58" width="96" height="52" fill="{t["acc"]}"/><text class="big" x="26" y="100" fill="#000" style="fill:#000">LIVE</text>'
        sub = "in rounds right now"
    else:
        num, nw = odo(26, 100, ev["days"], 44, "big")
        big = num + f'<text class="txt" x="{34 + nw:.0f}" y="100">day{"s" if ev["days"] != 1 else ""} out</text>'
        sub = ""
    inner = (f'<text class="lbl" x="24" y="34">NEXT ROUND</text>{big}'
             f'<text class="bold" x="24" y="{h - 62}">{e(ev["name"])}</text>'
             f'<text class="sm" x="24" y="{h - 42}">{e(ev["event"])} · {e(ev["dates"])}</text>'
             + (f'<text class="sm" x="24" y="{h - 22}">{e(sub)}</text>' if sub else ""))
    return svg(w, h, t, inner, f'{ev["name"]}, {ev["days"]} days out')


# ---------------------------------------------------------------- paper

def paper(d, t):
    w, h = FULL, 120
    p = d["paper"]
    parts = [f'<text class="lbl" x="24" y="34">PAPER · ZENODO</text>',
             f'<text class="bold" x="24" y="66">{e(p["title"])}</text>',
             f'<text class="sm" x="24" y="88">{e(p["sub"])}</text>']
    x = w - 24
    for k, (lbl, val, before) in enumerate([("DOWNLOADS", p["downloads"], p["dl_before"]), ("VIEWS", p["views"], p["v_before"])]):
        s = "—" if val is None else fmt(val)
        x -= 130
        if val is None:
            parts.append(f'<text class="num n28" x="{x:.1f}" y="74">—</text>')
        else:
            num, _ = odo(x, 74, s, 28, "num n28", delay=k * .15)
            parts.append(num)
        parts.append(f'<text class="lbl" x="{x:.1f}" y="34">{lbl}</text>')
        parts.append(f'<text class="sm" x="{x:.1f}" y="96">{e(delta_text(val, before) if val is not None else "")}</text>')
    return svg(w, h, t, "".join(parts), f'{p["title"]}: {p["views"]} views, {p["downloads"]} downloads')


# ---------------------------------------------------------------- repo map

EXT_LANG = {
    "ts": "TypeScript", "tsx": "TypeScript", "js": "JavaScript", "jsx": "JavaScript", "mjs": "JavaScript",
    "html": "HTML", "css": "CSS", "scss": "SCSS", "py": "Python", "json": "JSON", "md": "Markdown",
    "svg": "SVG", "sql": "SQL", "sh": "Shell", "yml": "YAML", "yaml": "YAML", "toml": "TOML",
}
EXT_COLOR = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "HTML": "#e34c26", "CSS": "#663399", "SCSS": "#c6538c",
    "Python": "#3572A5", "JSON": "#8b949e", "Markdown": "#4c6a8c", "SVG": "#ff9a3d", "SQL": "#e38c00",
    "Shell": "#89e051", "YAML": "#cb171e", "TOML": "#9c4221",
}


def _squarify(items, x, y, w, h):
    """items: list of (weight, payload), sorted desc. Returns (payload, x, y, w, h)."""
    out = []
    items = [it for it in items if it[0] > 0]
    total = sum(v for v, _ in items)
    if not items or w <= 0 or h <= 0:
        return out
    scale = w * h / total
    items = [(v * scale, p) for v, p in items]

    def worst(row, side):
        s = sum(v for v, _ in row)
        mx, mn = max(v for v, _ in row), min(v for v, _ in row)
        return max(side * side * mx / (s * s), (s * s) / (side * side * mn))

    while items:
        side = min(w, h)
        row = [items.pop(0)]
        while items and worst(row + [items[0]], side) <= worst(row, side):
            row.append(items.pop(0))
        s = sum(v for v, _ in row)
        if w >= h:
            cw = s / h
            yy = y
            for v, p in row:
                out.append((p, x, yy, cw, v / cw))
                yy += v / cw
            x += cw
            w -= cw
        else:
            rh = s / w
            xx = x
            for v, p in row:
                out.append((p, xx, y, v / rh, rh))
                xx += v / rh
            y += rh
            h -= rh
    return out


def repomap(d, t):
    w, h = FULL, 300
    m = d.get("map")
    head = f'<text class="lbl" x="24" y="34">MAP OF {e((m or {}).get("repo", "").upper())}</text>'
    if not m or not m["files"]:
        return svg(w, 120, t, head + '<text class="sm" x="24" y="70">no files to map yet</text>', "repo map")
    groups = {}
    for path, size in m["files"]:
        top = path.split("/")[0] if "/" in path else "·"
        groups.setdefault(top, []).append((size, path))
    gl = sorted(((sum(s for s, _ in v), k) for k, v in groups.items()), reverse=True)
    X, Y, W, H = 24, 50, w - 48, h - 50 - 40
    parts = [head, f'<text class="sm" x="{w - 24}" y="34" text-anchor="end">{len(m["files"])} files · {m["kb"]:,} KB · sized by bytes</text>']
    langs_seen = {}
    k = 0
    for gname, gx, gy, gw, gh in _squarify(gl, X, Y, W, H):
        files = sorted(groups[gname], reverse=True)
        inset = 2
        for path, fx, fy, fw, fh in _squarify(files, gx + inset, gy + inset, gw - 2 * inset, gh - 2 * inset):
            ext = path.rsplit(".", 1)[-1].lower() if "." in path.split("/")[-1] else ""
            lang = EXT_LANG.get(ext)
            col = EXT_COLOR.get(lang, t["mute"])
            if lang:
                langs_seen[lang] = langs_seen.get(lang, 0) + 1
            parts.append(f'<rect class="pop" x="{fx + .5:.1f}" y="{fy + .5:.1f}" width="{max(fw - 1, .5):.1f}" height="{max(fh - 1, .5):.1f}" '
                         f'fill="{col}" fill-opacity=".78" style="animation-delay:{min(k, 120) * .006:.3f}s"><title>{e(path)}</title></rect>')
            name = path.split("/")[-1]
            if fw > 70 and fh > 26 and len(name) * 6.2 < fw - 10:
                parts.append(f'<text x="{fx + 6:.1f}" y="{fy + 16:.1f}" style="font: 10.5px {MONO}; fill: #fff; paint-order: stroke; stroke: rgba(0,0,0,.35); stroke-width: 2px">{e(name)}</text>')
            k += 1
        parts.append(f'<rect x="{gx + .5:.1f}" y="{gy + .5:.1f}" width="{gw - 1:.1f}" height="{gh - 1:.1f}" fill="none" stroke="{t["bg"]}" stroke-width="3"/>')
        if gname != "·" and gw > 60 and gh > 40:
            label = gname + ("/" if gname != "·" else "")
            lw = len(label) * 6.6 + 10
            parts.append(f'<rect x="{gx + gw - lw - 6:.1f}" y="{gy + gh - 22:.1f}" width="{lw:.1f}" height="16" fill="{t["acc"]}"/>'
                         f'<text x="{gx + gw - lw:.1f}" y="{gy + gh - 10:.1f}" style="font: 600 10.5px {MONO}; fill: #000">{e(label)}</text>')
    lx = 24
    for lang, _ in sorted(langs_seen.items(), key=lambda kv: -kv[1])[:7]:
        parts.append(f'<rect x="{lx}" y="{h - 26}" width="9" height="9" rx="2" fill="{EXT_COLOR[lang]}"/><text class="sm" x="{lx + 14}" y="{h - 18}">{lang}</text>')
        lx += 30 + len(lang) * 7
    return svg(w, h, t, "".join(parts), f"Treemap of the files in {m['repo']}")


# ---------------------------------------------------------------- vocabulary

STOP = set("the a an and or to of in on for with from into by at is are be it its this that as up add added adds update updated "
           "updates use using wip new more some all fix fixed fixes merge branch pull request main master".split())


def vocab(d, t):
    w, h = HALF, 200
    import re as _re
    words = {}
    for c in d["commits"]:
        for wd in _re.findall(r"[a-z][a-z\-']{2,}", c["message"].lower()):
            if wd not in STOP:
                words[wd] = words.get(wd, 0) + 1
    top = sorted(words.items(), key=lambda kv: (-kv[1], kv[0]))[:12]
    parts = [f'<text class="lbl" x="24" y="34">MY COMMIT VOCABULARY</text>']
    if not top:
        parts.append('<text class="sm" x="24" y="70">not enough commits yet</text>')
        return svg(w, h, t, "".join(parts), "commit vocabulary")
    mx = top[0][1]
    x, y = 24, 72
    for i, (wd, n) in enumerate(top):
        size = 12 + 12 * (n / mx)
        tw = len(wd) * size * 0.56 + 10
        if x + tw > w - 20:
            x, y = 24, y + 34
            if y > h - 20:
                break
        on = i == 0
        if on:
            parts.append(f'<rect class="growx" x="{x - 3:.1f}" y="{y - size * .85:.1f}" width="{tw - 4:.1f}" height="{size * 1.1:.1f}" fill="{t["acc"]}"/>')
        parts.append(f'<text class="pop" x="{x:.1f}" y="{y:.1f}" style="font: {"700" if n == mx else "500"} {size:.1f}px {SANS}; '
                     f'fill: {"#000" if on else (t["ink"] if n > mx / 3 else t["mute"])}; animation-delay: {i * .05:.2f}s">{e(wd)}<title>{n}×</title></text>')
        x += tw + 6
    parts.append(f'<text class="sm" x="24" y="{h - 16}">most-used words in {len(d["commits"])} commit messages this year</text>')
    return svg(w, h, t, "".join(parts), "Most common words in my commit messages: " + ", ".join(wd for wd, _ in top))


# ---------------------------------------------------------------- weekdays

def weekdays(d, t):
    w, h = HALF, 200
    names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    tot = [0] * 7
    for ds, c in d["days"]:
        tot[(date.fromisoformat(ds).weekday() + 1) % 7] += c
    mx = max(tot) or 1
    best = max(range(7), key=lambda k: tot[k])
    x0, bw, base, top = 24, (w - 48) / 7, 156, 70
    parts = [f'<text class="lbl" x="24" y="34">BY WEEKDAY</text>',
             f'<text class="bold" x="24" y="54">{"Most work lands on " + ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"][best] if sum(tot) else "Nothing yet"}</text>']
    for k in range(7):
        bh = max(2, (base - top) * tot[k] / mx)
        col = t["acc"] if k == best else t["acc_ink"]
        op = "1" if k == best else ".5"
        parts.append(f'<rect class="grow" x="{x0 + k * bw + 6:.1f}" y="{base - bh:.1f}" width="{bw - 12:.1f}" height="{bh:.1f}" rx="2" fill="{col}" fill-opacity="{op}" style="animation-delay:{k * .06:.2f}s"/>'
                     f'<text class="sm" x="{x0 + k * bw + bw / 2:.1f}" y="{base + 18}" text-anchor="middle" font-size="10">{names[k]}</text>'
                     f'<text class="mono mute" x="{x0 + k * bw + bw / 2:.1f}" y="{base - bh - 6:.1f}" text-anchor="middle" font-size="10" style="font-size:10px">{tot[k]}</text>')
    return svg(w, h, t, "".join(parts), "Contributions by day of week")


ALL = {
    "map": repomap, "vocab": vocab, "weekdays": weekdays,
    "stats": stats, "streak": streak, "hours": hours, "year": year, "langs": langs,
    "commit": commit, "sites": sites, "tournament": tournament, "paper": paper,
}

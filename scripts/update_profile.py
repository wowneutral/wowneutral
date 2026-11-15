#!/usr/bin/env python3
"""Refresh the live parts of the profile.

Runs hourly from .github/workflows/update-profile.yml. It reads public data
from the GitHub API and rewrites:

  assets/card.svg   the "evidence card" near the top of the README
  README.md         the NOW, WORK and ACTIVITY blocks

Run with --sample to render from built-in sample data (no network), which is
handy for previewing the card locally.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

USERNAME = os.getenv("GITHUB_REPOSITORY_OWNER", "wowneutral")
TOKEN = os.getenv("GITHUB_TOKEN", "")
API = "https://api.github.com"
TZ = ZoneInfo("America/New_York")
README = Path("README.md")
CARD = Path("assets/card.svg")
CITE_MARK = "//skeplover"

# The projects table. Repo names are used for live "last push" and stars;
# set repo to None for things that don't live in a public repo.
PROJECTS = [
    ("Spread", "https://wowneutral.github.io/spread/", "spread",
     "Free, open-source card cutting and flowing for debaters on Chromebooks. A Verbatim alternative that works offline."),
    ("Skeptical", "https://skeptical.pages.dev", None,
     "The team's site, with a Discord sign-in portal for coaches. React, GSAP, Cloudflare Pages and D1."),
    ("MITEZ", "https://mitez.org", "mitez-site",
     "The nonprofit's site. React and Vite."),
    ("A Living World", "https://armaanseth.pages.dev", None,
     "My portfolio, built as one scrolling three.js scene."),
    ("Rogue", "https://clauderogue.netlify.app", None,
     "How far an AI can carry a build on its own, and where the seams show."),
]

STATUS_SITES = [
    ("mitez.org", "https://mitez.org"),
    ("skeptical", "https://skeptical.pages.dev"),
    ("portfolio", "https://armaanseth.pages.dev"),
]


# --------------------------------------------------------------------------
# GitHub

def _headers():
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def rest(path: str):
    with urlopen(Request(f"{API}{path}", headers=_headers()), timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def graphql(query: str, variables: dict):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = Request(f"{API}/graphql", data=body, headers=_headers(), method="POST")
    with urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


PROFILE_QUERY = """
query($login: String!, $since: GitTimestamp!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
      nodes {
        name
        createdAt
        stargazerCount
        pushedAt
        isArchived
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 100, since: $since) {
                nodes { oid messageHeadline committedDate author { user { login } } }
              }
            }
          }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

# Repo drawn as a treemap in the "map" box.
MAP_REPO = "spread"
MAP_SKIP = ("node_modules/", "dist/", "build/", ".git/", "package-lock.json", "pnpm-lock.yaml", "yarn.lock")

PAPER_RECORD = "23652238"
PAPER_TITLE = "Not in Mauthner's Sense"
PAPER_SUB = "Wittgenstein, Mauthner and the skeptic's critique of language · doi:10.5281/zenodo.23652238"

# Tournaments for the countdown box. Past ones drop off on their own.
EVENTS = [
    ("Isidore Newman Invitational", "Lincoln-Douglas", date(2026, 12, 11), date(2026, 12, 13)),
]


def collect():
    since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    u = graphql(PROFILE_QUERY, {"login": USERNAME, "since": since})["user"]
    repos = [r for r in u["repositories"]["nodes"]
             if not r["isArchived"] and r["name"].lower() != USERNAME.lower()]
    langs, colors = Counter(), {}
    commits = []
    for r in repos:
        for ed in r["languages"]["edges"]:
            langs[ed["node"]["name"]] += ed["size"]
            colors[ed["node"]["name"]] = ed["node"]["color"] or "#8b949e"
        hist = (((r.get("defaultBranchRef") or {}).get("target") or {}).get("history") or {}).get("nodes") or []
        for c in hist:
            who = ((c.get("author") or {}).get("user") or {}).get("login") or ""
            if who.lower() == USERNAME.lower():
                commits.append({"repo": r["name"], "oid": c["oid"], "message": c["messageHeadline"], "at": c["committedDate"]})
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [(dd["date"], dd["contributionCount"]) for w in cal["weeks"] for dd in w["contributionDays"]]
    try:
        events = rest(f"/users/{USERNAME}/events/public?per_page=30")
    except Exception:
        events = []
    try:
        z = json.loads(request_text(f"https://zenodo.org/api/records/{PAPER_RECORD}", 400000)[0])
        st = z.get("stats") or {}
        paper = {"views": st.get("unique_views", st.get("views")), "downloads": st.get("unique_downloads", st.get("downloads"))}
    except Exception:
        paper = {"views": None, "downloads": None}
    try:
        tree = rest(f"/repos/{USERNAME}/{MAP_REPO}/git/trees/HEAD?recursive=1")
        files = [(x["path"], x.get("size", 0)) for x in tree.get("tree", [])
                 if x["type"] == "blob" and not any(sk in x["path"] for sk in MAP_SKIP)]
    except Exception:
        files = []
    return {
        "map_files": files,
        "repos": repos, "stars": sum(r["stargazerCount"] for r in repos),
        "followers": u["followers"]["totalCount"], "total": cal["totalContributions"],
        "days": days, "lang_counter": langs, "lang_colors": colors,
        "events": events, "commits": commits, "paper_raw": paper,
    }


def sample():
    today = date(2026, 11, 15)
    days, n = [], 371
    for i in range(n):
        dd = today - timedelta(days=n - 1 - i)
        c = 0
        if dd >= date(2025, 10, 17) and i % 3 == 0:
            c = [0, 0, 1, 0, 3, 0, 0, 2, 0, 0, 0, 5, 1, 0][(i * 7) % 14]
        days.append((dd.isoformat(), c))
    days[-1] = (today.isoformat(), 2)
    now = datetime.now(timezone.utc)
    commits = []
    for k in range(40):
        hour = [22, 23, 23, 21, 16, 17, 0, 1, 22, 20][k % 10]
        at = datetime(2026, 11, 14 - (k % 26) // 2, (hour + 5) % 24, 10, tzinfo=timezone.utc) if k else now - timedelta(hours=3)
        commits.append({"repo": ["spread", "mitez-site", "skeptical"][k % 3], "oid": f"{k:02x}a91c4e7d", "message": ["flow: keep cross-ex column when exporting to docx", "cards: faster highlight on chromebook", "flow: arrow keys move between columns", "mitez: mentor form copy", "cards: cite parser handles DOA", "skeptical: portal login redirect", "offline: cache fonts in service worker", "flow: export blocks to docx", "cards: shrink unread text", "portal: discord role check"][k % 10], "at": at.isoformat()})
    return {
        "repos": [
            {"name": "spread", "stargazerCount": 4, "pushedAt": (now - timedelta(hours=3)).isoformat(), "createdAt": "2026-03-01T00:00:00Z"},
            {"name": "mitez-site", "stargazerCount": 1, "pushedAt": (now - timedelta(days=2)).isoformat(), "createdAt": "2025-11-01T00:00:00Z"},
            {"name": "skeptical", "stargazerCount": 1, "pushedAt": (now - timedelta(days=6)).isoformat(), "createdAt": "2026-06-01T00:00:00Z"},
        ],
        "stars": 6, "followers": 2, "total": 43, "days": days,
        "lang_counter": Counter({"HTML": 65, "JavaScript": 13, "TypeScript": 12, "CSS": 9, "Python": 1}),
        "lang_colors": {"HTML": "#e34c26", "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "CSS": "#663399", "Python": "#3572A5"},
        "events": [
            {"type": "PushEvent", "repo": {"name": "wowneutral/spread"}, "created_at": (now - timedelta(hours=3)).isoformat(), "payload": {"size": 2}},
            {"type": "CreateEvent", "repo": {"name": "wowneutral/spread"}, "created_at": (now - timedelta(days=1)).isoformat(), "payload": {"ref_type": "branch"}},
            {"type": "PushEvent", "repo": {"name": "wowneutral/mitez-site"}, "created_at": (now - timedelta(days=2)).isoformat(), "payload": {"size": 1}},
        ],
        "commits": commits, "paper_raw": {"views": 214, "downloads": 57},
        "map_files": [("src/flow/FlowSheet.tsx", 42000), ("src/flow/columns.ts", 9000), ("src/flow/export.ts", 14000), ("src/flow/keys.ts", 6000),
                      ("src/cards/Cutter.tsx", 38000), ("src/cards/highlight.ts", 16000), ("src/cards/verbatim.ts", 21000), ("src/cards/cite.ts", 7000),
                      ("src/App.tsx", 12000), ("src/main.tsx", 1500), ("src/storage/idb.ts", 11000), ("src/storage/sync.ts", 8000),
                      ("src/styles/app.css", 18000), ("src/styles/print.css", 4000), ("public/sw.js", 6000), ("public/manifest.json", 900),
                      ("index.html", 3000), ("README.md", 7000), ("vite.config.ts", 800), ("package.json", 1200),
                      ("docs/shortcuts.md", 5000), ("docs/offline.md", 3000), ("tests/export.test.ts", 9000), ("tests/highlight.test.ts", 7000)],
    }


# --------------------------------------------------------------------------
# helpers

def ago(iso: str | None) -> str:
    if not iso:
        return "a while ago"
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    s = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
    if s < 3600:
        return "just now" if s < 120 else f"{s // 60} minutes ago"
    h = s // 3600
    if h < 24:
        return "an hour ago" if h == 1 else f"{h} hours ago"
    d = h // 24
    if d < 60:
        return "yesterday" if d == 1 else f"{d} days ago"
    return f"{d // 30} months ago"


def streaks(days):
    counts = [c for _, c in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    cur = 0
    i = len(counts) - 1
    if counts and counts[-1] == 0:  # today not done yet doesn't break it
        i -= 1
    while i >= 0 and counts[i]:
        cur += 1
        i -= 1
    return cur, longest


def plural(n, word):
    if n == 1:
        return f"{n} {word}"
    return f"{n} {word[:-1] + 'ies' if word.endswith('y') and word[-2] not in 'aeiou' else word + 's'}"


# --------------------------------------------------------------------------
# the card

W = 840
PAD = 36
FONT = "Calibri, Carlito, 'Helvetica Neue', Arial, sans-serif"


def card_svg(d) -> str:
    now = datetime.now(TZ)
    cur, best = streaks(d["days"])
    latest = max(d["repos"], key=lambda r: r.get("pushedAt") or "", default=None)
    total_size = sum(d["lang_counter"].values()) or 1
    top = [(n, round(100 * s / total_size)) for n, s in d["lang_counter"].most_common(4)]
    active = sum(1 for _, c in d["days"] if c)

    e = html.escape
    tags = {"p": ("<span>", "</span>"), "u": ("<u>", "</u>"), "h": ("<mark>", "</mark>")}

    def run(*segs):
        return "".join(tags[k][0] + e(t) + tags[k][1] for k, t in segs)

    langs = []
    for i, (n, pc) in enumerate(top):
        if i:
            langs.append(("u", ", and " if i == len(top) - 1 else ", "))
        langs.append(("h", f"{n} {pc}%"))

    segs = [
        ("p", "Pulled from GitHub's public API on the hour; forks and archived repositories are excluded from every count below. "),
        ("u", "As of this pull, the account holds "), ("h", plural(len(d["repos"]), "public repository")),
        ("u", " carrying "), ("h", plural(d["stars"], "star")), ("u", " and "), ("h", plural(d["followers"], "follower") + "."),
        ("p", " Contribution totals include commits, pull requests, issues and reviews to public repositories. "),
        ("u", "Over the last year it "), ("h", "logged " + plural(d["total"], "contribution")),
        ("u", " across "), ("h", plural(active, "separate day") + ","),
        ("u", " with a current streak of "), ("h", plural(cur, "day")), ("u", f" against a best of {best}."),
        ("p", " Days are counted in UTC, the way GitHub counts them. "),
    ]
    if latest:
        segs += [("u", "The most recent push went to "), ("h", latest["name"]),
                 ("u", " " + ago(latest.get("pushedAt")) + ".")]
    segs += [("p", " By volume of code, the stack runs "), *langs, ("u", "."),
             ("p", " That mix is mostly websites, which is the point: "),
             ("u", "nearly all of it "), ("h", "ships to the debate community"),
             ("u", ", to people who cut cards, flow rounds, and need tools that "), ("h", "work on a Chromebook.")]
    body = run(*segs)

    stamp = now.strftime("%b %-d, %Y, %-I:%M %p %Z")
    doa = now.strftime("%-m/%-d/%y")
    cite = (f"<b>Seth '{now:%y}</b><small>[Armaan Seth, debater and coach, Skeptical LD and MITEZ. "
            f"“Public record for @{e(USERNAME)},” GitHub REST and GraphQL APIs, "
            f"https://github.com/{e(USERNAME)}, pulled {e(stamp)}, DOA: {doa}] {e(CITE_MARK)}&#10084;</small>")
    tagline = "Armaan ships---the record is live, and it rewrites itself every hour."

    body_h = 336
    H_total = PAD + body_h + 34

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H_total}" viewBox="0 0 {W} {H_total}" role="img" aria-label="Live GitHub stats for {e(USERNAME)}, formatted as a debate evidence card">
<style>
  .sheet {{ font-family: {FONT}; color: #000; }}
  .tag {{ font-size: 21px; font-weight: 700; line-height: 1.3; margin: 0 0 8px; }}
  .cite {{ margin: 0 0 12px; line-height: 1.35; }}
  .cite b {{ font-size: 24px; margin-right: 1px; }}
  .cite small {{ font-size: 12px; }}
  .body {{ font-size: 11px; line-height: 1.75; margin: 0; }}
  .body u, .body mark {{ font-weight: 700; text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 2px; color: #000; }}
  .body u {{ font-size: 14.5px; }}
  .body mark {{
    font-size: 19px;
    background: linear-gradient(#73f7f8, #73f7f8) no-repeat 0 0 / 100% 100%;
    animation: hl .5s ease-out backwards;
  }}
  .body mark:nth-of-type(2) {{ animation-delay: .12s }}
  .body mark:nth-of-type(3) {{ animation-delay: .24s }}
  .body mark:nth-of-type(4) {{ animation-delay: .36s }}
  .body mark:nth-of-type(5) {{ animation-delay: .48s }}
  .body mark:nth-of-type(6) {{ animation-delay: .6s }}
  .body mark:nth-of-type(7) {{ animation-delay: .72s }}
  .body mark:nth-of-type(8) {{ animation-delay: .84s }}
  .body mark:nth-of-type(n+9) {{ animation-delay: .96s }}
  @keyframes hl {{ from {{ background-size: 0% 100%; }} }}
  @media (prefers-reduced-motion: reduce) {{ .body mark {{ animation: none; }} }}
  .fig {{ font: 11px {FONT}; fill: #666; }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H_total - 1}" rx="2" fill="#ffffff" stroke="#d0d7de"/>
<foreignObject x="{PAD}" y="{PAD - 6}" width="{W - 2 * PAD}" height="{body_h}">
  <div xmlns="http://www.w3.org/1999/xhtml" class="sheet">
    <p class="tag">{e(tagline)}</p>
    <p class="cite">{cite}</p>
    <p class="body">{body}</p>
  </div>
</foreignObject>
<text class="fig" x="{PAD}" y="{H_total - 18}">Card re-cut automatically from live data</text>
<text class="fig" x="{W - PAD}" y="{H_total - 18}" text-anchor="end">updated {e(stamp)}</text>
</svg>
'''


# --------------------------------------------------------------------------
# README blocks

def replace_block(text: str, name: str, body: str) -> str:
    pattern = rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)"
    new, n = re.subn(pattern, lambda m: f"{m.group(1)}\n{body.rstrip()}\n{m.group(2)}", text, flags=re.S)
    if n != 1:
        raise RuntimeError(f"README is missing the {name} block")
    return new


def request_text(url: str, limit: int = 6000):
    req = Request(url, headers={"User-Agent": f"{USERNAME}-profile-updater", "Accept": "application/json"})
    with urlopen(req, timeout=20) as resp:
        return resp.read(limit).decode("utf-8", errors="replace"), resp.status


def site_check(url: str):
    start = time.monotonic()
    try:
        with urlopen(Request(url, headers={"User-Agent": "profile-check"}), timeout=15) as r:
            r.read(64)
            return True, int((time.monotonic() - start) * 1000)
    except Exception:
        return False, None


def build_work(d):
    by = {r["name"]: r for r in d["repos"]}
    rows = ["| Project | What it is | Live |", "| --- | --- | --- |"]
    for label, url, repo, desc in PROJECTS:
        r = by.get(repo) if repo else None
        if r:
            meta = f"[pushed {ago(r.get('pushedAt'))}](https://github.com/{USERNAME}/{repo})"
            if r["stargazerCount"]:
                meta += f" · {plural(r['stargazerCount'], 'star')}"
        else:
            meta = ""
        rows.append(f"| **[{label}]({url})** | {desc} | <sub>{meta}</sub> |")
    return "\n".join(rows)


def event_line(ev):
    t = ev.get("type", "")
    repo = ev.get("repo", {}).get("name", "").split("/")[-1] or "?"
    p = ev.get("payload") or {}
    if t == "PushEvent":
        n = p.get("size") or len(p.get("commits") or []) or 1
        what = f"pushed {plural(n, 'commit')}"
    elif t == "CreateEvent":
        what = f"created a {p.get('ref_type') or 'thing'}"
    elif t == "PullRequestEvent":
        what = f"{p.get('action', 'updated')} a pull request"
    elif t == "IssuesEvent":
        what = f"{p.get('action', 'updated')} an issue"
    elif t == "WatchEvent":
        what = "starred"
    elif t == "ReleaseEvent":
        what = "published a release in"
    else:
        what = re.sub(r"(?<!^)(?=[A-Z])", " ", t.replace("Event", "")).lower() or "touched"
    return f"{ago(ev.get('created_at'))} — {what} {'to' if t == 'PushEvent' else 'in' if t != 'WatchEvent' else ''} [{repo}](https://github.com/{USERNAME}/{repo})".replace("  ", " ")


def build_activity(d):
    seen, out = set(), []
    for ev in d["events"]:
        if ev.get("repo", {}).get("name", "").lower().endswith(f"/{USERNAME.lower()}"):
            continue  # skip the profile repo's own bot commits
        line = event_line(ev)
        if line in seen:
            continue
        seen.add(line)
        out.append(f"<sub>{line}</sub><br>")
        if len(out) == 5:
            break
    return "\n".join(out) or "<sub>quiet week.</sub>"


STATE = Path("assets/state.json")
WIDGETS_DIR = Path("assets")


def enrich(d, offline):
    """Turn raw API data into what the widgets draw, and keep a little state
    between runs (site uptime history, daily snapshots for week-over-week)."""
    import widgets  # noqa: E402  (same folder)

    now_utc = datetime.now(timezone.utc)
    today = datetime.now(TZ).date()
    state = {}
    if STATE.exists():
        try:
            state = json.loads(STATE.read_text())
        except Exception:
            state = {}

    cur, best = streaks(d["days"])
    d["streak"], d["best"] = cur, best
    d["active"] = sum(1 for _, c in d["days"] if c)
    d["new_repos"] = sum(1 for r in d["repos"] if (r.get("createdAt") or "")[:4] == str(today.year))

    total = sum(d["lang_counter"].values())
    d["lang_total"] = total
    d["langs"] = [(n, s, d["lang_colors"].get(n, "#8b949e")) for n, s in d["lang_counter"].most_common(6)]

    hrs = [0] * 24
    for c in d["commits"]:
        hrs[datetime.fromisoformat(c["at"].replace("Z", "+00:00")).astimezone(TZ).hour] += 1
    d["hours"] = hrs
    latest = max(d["commits"], key=lambda c: c["at"], default=None)
    if latest:
        latest = dict(latest, ago=ago(latest["at"]))
    d["latest_commit"] = latest
    week = [c for c in d["commits"] if datetime.fromisoformat(c["at"].replace("Z", "+00:00")) > now_utc - timedelta(days=7)]
    d["week_note"] = (f"{plural(len(week), 'commit')} this week across {plural(len({c['repo'] for c in week}), 'repo')}"
                      if week else "quiet week")

    # sites + rolling uptime history
    hist = state.get("sites", {})
    d["sites"] = []
    for label, url in STATUS_SITES:
        up, ms = (True, 140 + 37 * len(label)) if offline else site_check(url)
        h = (hist.get(label) or [])[-47:] + [up]
        if offline and len(h) < 30:
            h = [True] * 36 + [False] + [True] * 11
        hist[label] = h
        d["sites"].append({"name": label, "up": up, "ms": ms, "history": h})
    state["sites"] = hist

    # daily snapshots, so boxes can say "+2 this week"
    snaps = state.get("daily", {})
    snaps[today.isoformat()] = {"stars": d["stars"], "followers": d["followers"],
                                "views": d["paper_raw"]["views"], "downloads": d["paper_raw"]["downloads"]}
    keep = sorted(snaps)[-30:]
    snaps = {k: snaps[k] for k in keep}
    state["daily"] = snaps
    wk = (today - timedelta(days=7)).isoformat()
    older = [k for k in keep if k <= wk]
    d["week_ago"] = snaps[older[-1]] if older else {}

    p = d["paper_raw"]
    d["paper"] = {"title": PAPER_TITLE, "sub": PAPER_SUB, "views": p["views"], "downloads": p["downloads"],
                  "v_before": d["week_ago"].get("views"), "dl_before": d["week_ago"].get("downloads")}

    files = d.get("map_files") or []
    d["map"] = {"repo": MAP_REPO, "files": files, "kb": round(sum(sz for _, sz in files) / 1024)} if files else None

    d["next_event"] = None
    for name, kind, start, end in sorted(EVENTS, key=lambda x: x[2]):
        if end >= today:
            span = f"{start:%b %-d}–{end:%-d}" if start.month == end.month else f"{start:%b %-d}–{end:%b %-d}"
            d["next_event"] = {"name": name, "event": kind, "dates": span, "days": (start - today).days}
            break

    if not offline:
        STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return widgets


def main():
    offline = "--sample" in sys.argv
    d = sample() if offline else collect()
    WIDGETS_DIR.mkdir(exist_ok=True)
    widgets = enrich(d, offline)
    CARD.write_text(card_svg(d), encoding="utf-8")
    for name, fn in widgets.ALL.items():
        for theme, t in widgets.THEMES.items():
            (WIDGETS_DIR / f"{name}-{theme}.svg").write_text(fn(d, t), encoding="utf-8")
    if README.exists():
        t = README.read_text(encoding="utf-8")
        t = replace_block(t, "WORK", build_work(d))
        t = replace_block(t, "ACTIVITY", build_activity(d))
        README.write_text(t, encoding="utf-8")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

USERNAME = os.getenv("GITHUB_REPOSITORY_OWNER", "wowneutral")
TOKEN = os.getenv("GITHUB_TOKEN", "")
README = Path("README.md")
PROFILE_REPO = USERNAME.lower()
API = "https://api.github.com"
SITE = "https://mitez.org"
TZ = ZoneInfo("America/New_York")

FEATURED = [
    ("MITEZ", "mitez-site", "https://mitez.org"),
    ("Emerging Tech", "emerging-tech-site", "https://github.com/wowneutral/emerging-tech-site"),
]

def request_json(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def request_text(url: str, limit: int = 6000):
    req = Request(url, headers={"User-Agent": f"{USERNAME}-profile-updater"})
    with urlopen(req, timeout=20) as resp:
        raw = resp.read(limit)
        return raw.decode("utf-8", errors="replace"), resp.status

def repo_url(name: str) -> str:
    return f"https://github.com/{USERNAME}/{name}"

def md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()

def human_age(iso: str | None) -> str:
    if not iso:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return "unknown"
    secs = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
    if secs < 60:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs}h ago"
    days = hrs // 24
    return f"{days}d ago"

def replace_block(text: str, name: str, body: str) -> str:
    pattern = rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)"
    replacement = rf"\1\n{body.rstrip()}\n\2"
    new, n = re.subn(pattern, replacement, text, flags=re.S)
    if n != 1:
        raise RuntimeError(f"Could not uniquely find block {name}")
    return new

def get_repos():
    repos = request_json(f"{API}/users/{USERNAME}/repos?per_page=100&sort=updated")
    return [
        r for r in repos
        if not r.get("fork")
        and r.get("name", "").lower() != PROFILE_REPO
        and not r.get("archived")
    ]

def get_site_status():
    start = time.monotonic()
    try:
        req = Request(SITE, headers={"User-Agent": f"{USERNAME}-profile-updater"})
        with urlopen(req, timeout=15) as resp:
            resp.read(128)
            ms = int((time.monotonic() - start) * 1000)
            return f"online · HTTP {resp.status} · {ms} ms"
    except Exception:
        return "check failed"

def build_now(repos):
    latest = max(repos, key=lambda r: r.get("pushed_at") or "", default=None)
    latest_name = latest["name"] if latest else "—"
    latest_time = human_age(latest.get("pushed_at")) if latest else "—"
    now_local = datetime.now(TZ).strftime("%b %d, %Y · %I:%M %p %Z").replace(" 0", " ")
    site_status = get_site_status()

    return "\n".join([
        "```text",
        "building      MITEZ",
        "based         Gainesville, FL",
        f"latest push   {latest_name} · {latest_time}",
        f"mitez.org     {site_status}",
        f"last sync     {now_local}",
        "```",
    ])

def build_work(repos):
    by_name = {r["name"]: r for r in repos}
    lines = []
    for label, repo_name, primary_url in FEATURED:
        r = by_name.get(repo_name)
        if r:
            lang = r.get("language") or "mixed"
            updated = human_age(r.get("pushed_at"))
            desc = md_escape(r.get("description") or "")
            summary = f"{lang} · pushed {updated}"
            if desc:
                summary += f" · {desc}"
            lines.append(f"- **[{label}]({primary_url})** — [{repo_name}]({repo_url(repo_name)}) · {summary}")
        else:
            lines.append(f"- **[{label}]({primary_url})** — [{repo_name}]({repo_url(repo_name)})")
    return "\n".join(lines)

def event_line(event):
    et = event.get("type", "")
    repo = event.get("repo", {}).get("name", "").split("/")[-1] or "unknown"
    created = human_age(event.get("created_at"))
    payload = event.get("payload", {}) or {}

    if et == "PushEvent":
        commits = payload.get("commits") or []
        count = len(commits)
        branch = (payload.get("ref") or "").split("/")[-1]
        detail = f"pushed {count} commit{'s' if count != 1 else ''}"
        if branch:
            detail += f" to `{branch}`"
    elif et == "CreateEvent":
        ref_type = payload.get("ref_type") or "item"
        detail = f"created {ref_type}"
    elif et == "PullRequestEvent":
        action = payload.get("action") or "updated"
        num = (payload.get("pull_request") or {}).get("number")
        detail = f"{action} pull request"
        if num:
            detail += f" #{num}"
    elif et == "IssuesEvent":
        action = payload.get("action") or "updated"
        num = (payload.get("issue") or {}).get("number")
        detail = f"{action} issue"
        if num:
            detail += f" #{num}"
    elif et == "WatchEvent":
        detail = "starred repository"
    elif et == "ForkEvent":
        detail = "forked repository"
    else:
        detail = et.replace("Event", "").replace("_", " ").lower() or "activity"

    return f"- `{created:>8}` · **[{repo}]({repo_url(repo)})** · {detail}"

def build_activity():
    events = request_json(f"{API}/users/{USERNAME}/events/public?per_page=30")
    if not events:
        return "_No recent public activity returned by GitHub._"
    return "\n".join(event_line(e) for e in events[:6])

def build_stack(repos):
    totals = Counter()
    for r in repos:
        try:
            langs = request_json(r["languages_url"])
        except Exception:
            continue
        for lang, size in langs.items():
            totals[lang] += int(size)

    total = sum(totals.values())
    if total <= 0:
        fallback = Counter(r.get("language") for r in repos if r.get("language"))
        if not fallback:
            return "_No language data yet._"
        return " · ".join(f"`{name}`" for name, _ in fallback.most_common(8))

    items = []
    for lang, size in totals.most_common(8):
        pct = 100 * size / total
        items.append(f"`{lang} {pct:.0f}%`")
    return " · ".join(items) + "\n\n<sub>aggregated from public, non-fork repositories.</sub>"

def build_robots():
    try:
        text, status = request_text(f"{SITE}/robots.txt")
        text = text.replace("```", "~~~").strip()
        if len(text) > 3800:
            text = text[:3800].rstrip() + "\n…"
        return f"```text\n{text}\n```"
    except Exception as exc:
        return f"```text\nrobots.txt fetch failed: {type(exc).__name__}\n```"

def main():
    text = README.read_text(encoding="utf-8")
    repos = get_repos()
    text = replace_block(text, "NOW", build_now(repos))
    text = replace_block(text, "WORK", build_work(repos))
    text = replace_block(text, "ACTIVITY", build_activity())
    text = replace_block(text, "STACK", build_stack(repos))
    text = replace_block(text, "ROBOTS", build_robots())
    README.write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()

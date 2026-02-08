import argparse
import os
import requests
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict


def github_get(url, token, params=None, headers_extra=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    if headers_extra:
        headers.update(headers_extra)

    r = requests.get(url, headers=headers, params=params)

    if r.status_code != 200:
        print("GitHub API error:", r.text)
        return None

    return r.json()


def fetch_commits_search(username, token, start_date):
    commits = []
    page = 1

    while True:
        url = "https://api.github.com/search/commits"

        headers_extra = {
            "Accept": "application/vnd.github.cloak-preview"
        }

        query = f"author:{username} author-date:>={start_date}"

        params = {
            "q": query,
            "per_page": 100,
            "page": page,
            "sort": "author-date",
            "order": "desc"
        }

        data = github_get(url, token, params=params, headers_extra=headers_extra)

        if not data:
            break

        items = data.get("items", [])

        if not items:
            break

        for item in items:
            commits.append({
                "date": item["commit"]["author"]["date"],
                "repo": item["repository"]["name"]
            })

        if len(items) < 100:
            break

        page += 1

    return commits


def get_repo_languages(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    data = github_get(url, token)
    return data or {}


def compute_monthly(commits, start_date):
    monthly = Counter()

    for c in commits:
        dt = datetime.fromisoformat(c["date"].replace("Z", "+00:00"))
        if dt.date() >= start_date:
            key = f"{dt.year}-{dt.month:02d}"
            monthly[key] += 1

    return monthly


def compute_extra_metrics(commits, username, token):
    now = datetime.now(timezone.utc)
    today = now.date()
    week_start = today - timedelta(days=today.weekday())

    today_commits = 0
    week_commits = 0

    repo_counter = Counter()
    lang_counter = Counter()

    active_days = set()
    weekday_counter = Counter()

    for c in commits:
        dt = datetime.fromisoformat(c["date"].replace("Z", "+00:00"))
        d = dt.date()

        if d == today:
            today_commits += 1
        if d >= week_start:
            week_commits += 1

        if c["repo"]:
            repo_counter[c["repo"]] += 1

        active_days.add(d)
        weekday_counter[dt.strftime("%A")] += 1

    total_repo = sum(repo_counter.values())

    top_repos = []
    if total_repo:
        for repo, count in repo_counter.most_common(5):
            top_repos.append((repo, (count / total_repo) * 100))

    for repo, _ in top_repos:
        langs = get_repo_languages(username, repo, token)
        for lang, b in langs.items():
            lang_counter[lang] += b

    total_bytes = sum(lang_counter.values())

    lang_percent = {}
    if total_bytes:
        lang_percent = {
            lang: (b / total_bytes) * 100
            for lang, b in lang_counter.items()
        }

    avg_per_day = len(commits) / len(active_days) if active_days else 0

    most_productive_day = None
    if weekday_counter:
        most_productive_day = weekday_counter.most_common(1)[0][0]

    return {
        "today": today_commits,
        "week": week_commits,
        "top_repos": top_repos,
        "lang_percent": lang_percent,
        "avg_per_day": avg_per_day,
        "most_productive_day": most_productive_day
    }


def replace_block(text, start_marker, end_marker, new_content):
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker)
    return text[:start] + "\n" + new_content + "\n" + text[end:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--start", required=True)
    parser.add_argument("--readme", required=True)

    args = parser.parse_args()

    token = os.getenv("GH_TOKEN")
    username = args.username
    start_date = datetime.fromisoformat(args.start).date()

    commits = fetch_commits_search(username, token, start_date)

    monthly = compute_monthly(commits, start_date)
    extra = compute_extra_metrics(commits, username, token)

    monthly_md = ""
    total = sum(monthly.values())

    for m in sorted(monthly.keys()):
        monthly_md += f"| {m} | {monthly[m]} |\n"

    monthly_section = f"""
## Commit stats

- All-time commits (since {args.start}): **{total}**

### Commits per month (last 12 months)

| Month | Commits |
|---:|---:|
{monthly_md}
"""

    with open(args.readme, "r", encoding="utf-8") as f:
        readme = f.read()

    readme = replace_block(
        readme,
        "<!-- COMMITS_START -->",
        "<!-- COMMITS_END -->",
        monthly_section
    )

    with open(args.readme, "w", encoding="utf-8") as f:
        f.write(readme)


if __name__ == "__main__":
    main()

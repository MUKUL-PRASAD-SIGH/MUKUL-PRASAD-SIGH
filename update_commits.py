import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests


def github_get(url, token, params=None, headers_extra=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    if headers_extra:
        headers.update(headers_extra)

    response = requests.get(url, headers=headers, params=params, timeout=30)
    if response.status_code != 200:
        print("GitHub API error:", response.text)
        return None
    return response.json()


def parse_commit_date(date_string):
    return datetime.fromisoformat(date_string.replace("Z", "+00:00")).date()


def fetch_commits_search(username, token, start_date):
    commits = []
    page = 1

    while True:
        url = "https://api.github.com/search/commits"
        headers_extra = {"Accept": "application/vnd.github.cloak-preview"}
        query = f"author:{username} author-date:>={start_date}"
        params = {
            "q": query,
            "per_page": 100,
            "page": page,
            "sort": "author-date",
            "order": "asc",
        }

        data = github_get(url, token, params=params, headers_extra=headers_extra)
        if not data:
            break

        items = data.get("items", [])
        if not items:
            break

        commits.extend(
            {
                "date": item["commit"]["author"]["date"],
                "repo": item["repository"]["name"],
                "message": item["commit"]["message"],
            }
            for item in items
        )

        print(f"Fetched page {page}: {len(items)} commits")
        if len(items) < 100:
            break
        page += 1

    return commits


def get_account_creation_date(username, token):
    url = f"https://api.github.com/users/{username}"
    data = github_get(url, token)
    if not data or "created_at" not in data:
        return None
    return parse_commit_date(data["created_at"])


def calculate_streaks(commits):
    if not commits:
        return {
            "current": 0,
            "current_start": None,
            "current_end": None,
            "longest": 0,
            "longest_start": None,
            "longest_end": None,
        }

    active_dates = sorted(set(parse_commit_date(c["date"]) for c in commits))
    today = datetime.now(timezone.utc).date()

    longest_streak = 0
    longest_start = None
    longest_end = None

    streak_start = active_dates[0]
    streak_end = active_dates[0]
    streak_length = 1

    for i in range(1, len(active_dates)):
        if active_dates[i] - active_dates[i - 1] == timedelta(days=1):
            streak_length += 1
            streak_end = active_dates[i]
            continue

        if streak_length > longest_streak:
            longest_streak = streak_length
            longest_start = streak_start
            longest_end = streak_end

        streak_start = active_dates[i]
        streak_end = active_dates[i]
        streak_length = 1

    if streak_length > longest_streak:
        longest_streak = streak_length
        longest_start = streak_start
        longest_end = streak_end

    current_streak = 0
    current_start = None
    current_end = None
    if active_dates[-1] in {today, today - timedelta(days=1)}:
        current_streak = 1
        current_end = active_dates[-1]
        current_start = active_dates[-1]
        for i in range(len(active_dates) - 2, -1, -1):
            if active_dates[i] == active_dates[i + 1] - timedelta(days=1):
                current_streak += 1
                current_start = active_dates[i]
            else:
                break

    return {
        "current": current_streak,
        "current_start": current_start,
        "current_end": current_end,
        "longest": longest_streak,
        "longest_start": longest_start,
        "longest_end": longest_end,
    }


def format_streak_range(start, end):
    if not start or not end:
        return "No active streak"
    if start.year == end.year:
        return f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
    return f"{start.strftime('%b %d, %Y')} - {end.strftime('%b %d, %Y')}"


def generate_streak_svg(total_commits, since_date, streaks):
    current_streak = streaks["current"]
    longest_streak = streaks["longest"]
    date_range_text = f"{since_date.strftime('%b %d, %Y')} - Present"
    current_streak_text = format_streak_range(streaks["current_start"], streaks["current_end"])
    longest_streak_text = format_streak_range(streaks["longest_start"], streaks["longest_end"])

    return f"""<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'
                style='isolation: isolate' viewBox='0 0 495 195' width='495px' height='195px' direction='ltr'>
        <style>
            @keyframes currstreak {{
                0% {{ font-size: 3px; opacity: 0.2; }}
                80% {{ font-size: 34px; opacity: 1; }}
                100% {{ font-size: 28px; opacity: 1; }}
            }}
            @keyframes fadein {{
                0% {{ opacity: 0; }}
                100% {{ opacity: 1; }}
            }}
        </style>
        <defs>
            <clipPath id='outer_rectangle'>
                <rect width='495' height='195' rx='4.5'/>
            </clipPath>
            <mask id='mask_out_ring_behind_fire'>
                <rect width='495' height='195' fill='white'/>
                <ellipse id='mask-ellipse' cx='247.5' cy='32' rx='13' ry='18' fill='black'/>
            </mask>
        </defs>
        <g clip-path='url(#outer_rectangle)'>
            <g style='isolation: isolate'>
                <rect stroke='#000000' stroke-opacity='0' fill='#141321' rx='4.5' x='0.5' y='0.5' width='494' height='194'/>
            </g>
            <g style='isolation: isolate'>
                <line x1='165' y1='28' x2='165' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='#E4E2E2' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
                <line x1='330' y1='28' x2='330' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='#E4E2E2' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
            </g>
            <g style='isolation: isolate'>
                <g transform='translate(82.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#FE428E' stroke='none' font-family="'Segoe UI', Ubuntu, sans-serif" font-weight='700' font-size='28px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                        {total_commits}
                    </text>
                </g>

                <g transform='translate(82.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#FE428E' stroke='none' font-family="'Segoe UI', Ubuntu, sans-serif" font-weight='400' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.7s'>
                        Total Contributions
                    </text>
                </g>

                <g transform='translate(82.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#A9FEF7' stroke='none' font-family="'Segoe UI', Ubuntu, sans-serif" font-weight='400' font-size='12px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.8s'>
                        {date_range_text}
                    </text>
                </g>
            </g>
            <g style='isolation: isolate'>
                <g transform='translate(247.5, 108)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#F8D847' stroke='none' font-family="'Segoe UI', Ubuntu, sans-serif" font-weight='700' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>
                        Current Streak
                    </text>
                </g>

                <g transform='translate(247.5, 145)'>
                    <text x='0' y='21' stroke-width='0' text-anchor='middle' fill='#A9FEF7' stroke='none' font-family="'Segoe UI', Ubuntu, sans-serif" font-weight='400' font-size='12px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>
                        {current_streak_text}
                    </text>
                </g>

                <g mask='url(#mask_out_ring_behind_fire)'>
                    <circle cx='247.5' cy='71' r='40' fill='none' stroke='#FE428E' stroke-width='5' style='opacity: 0; animation: fadein 0.5s linear forwards 0.4s'></circle>
                </g>
                <g transform='translate(247.5, 19.5)' stroke-opacity='0' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                    <path d='M -12 -0.5 L 15 -0.5 L 15 23.5 L -12 23.5 L -12 -0.5 Z' fill='none'/>
                    <path d='M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2 C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99 C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.7 12.74 C 1.07 12.38 2.9 11.53 3.92 10.16 C 4.31 11.45 4.51 12.81 4.51 14.2 C 4.51 16.85 2.36 19 -0.29 19 Z' fill='#FE428E' stroke-opacity='0'/>
                </g>

                <g transform='translate(247.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#F8D847' stroke='none' font-family="'Segoe UI', Ubuntu, sans-serif" font-weight='700' font-size='28px' font-style='normal' style='animation: currstreak 0.6s linear forwards'>
                        {current_streak}
                    </text>
                </g>
            </g>
            <g style='isolation: isolate'>
                <g transform='translate(412.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#FE428E' stroke='none' font-family="'Segoe UI', Ubuntu, sans-serif" font-weight='700' font-size='28px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.2s'>
                        {longest_streak}
                    </text>
                </g>

                <g transform='translate(412.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#FE428E' stroke='none' font-family="'Segoe UI', Ubuntu, sans-serif" font-weight='400' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.3s'>
                        Longest Streak
                    </text>
                </g>

                <g transform='translate(412.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#A9FEF7' stroke='none' font-family="'Segoe UI', Ubuntu, sans-serif" font-weight='400' font-size='12px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.4s'>
                        {longest_streak_text}
                    </text>
                </g>
            </g>
        </g>
    </svg>"""


def calculate_monthly_commits(commits):
    monthly = Counter()
    for commit in commits:
        dt = datetime.fromisoformat(commit["date"].replace("Z", "+00:00"))
        monthly[f"{dt.year}-{dt.month:02d}"] += 1
    return monthly


def build_last_n_month_keys(months):
    now = datetime.now(timezone.utc)
    keys = []
    year = now.year
    month = now.month

    for _ in range(months):
        keys.append(f"{year}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    keys.reverse()
    return keys


def update_readme(total_commits, monthly_stats, since_date, months, readme_path):
    months_sorted = build_last_n_month_keys(months)
    table = "| Month | Commits |\n|---:|---:|\n"
    for month in months_sorted:
        table += f"| {month} | {monthly_stats.get(month, 0)} |\n"

    with open(readme_path, "r", encoding="utf-8") as readme_file:
        content = readme_file.read()

    content = re.sub(
        r"- All-time commits \(since [^)]+\): \*\*\d+\*\*",
        f"- All-time commits (since {since_date.isoformat()}): **{total_commits}**",
        content,
    )
    content = re.sub(
        r"### Commits per month \(last \d+ months\)",
        f"### Commits per month (last {months} months)",
        content,
    )

    content = re.sub(
        r"(### Commits per month \(last \d+ months\)\n\n)(\| Month.*?)(?=\n\n<!-- COMMITS_END -->)",
        lambda match: f"{match.group(1)}{table.rstrip()}",
        content,
        flags=re.DOTALL,
    )

    with open(readme_path, "w", encoding="utf-8") as readme_file:
        readme_file.write(content)

    print(f"Updated {readme_path} with latest commit statistics")


def main():
    parser = argparse.ArgumentParser(description="Generate GitHub statistics")
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument("--token", help="GitHub token (or set GH_TOKEN env var)")
    parser.add_argument("--start-date", "--start", dest="start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--months", type=int, default=12, help="Months to include in monthly table")
    parser.add_argument("--readme", default="README.md", help="README path to update")
    parser.add_argument("--assets-dir", default="assets", help="Directory for generated assets")
    args = parser.parse_args()

    token = args.token or os.getenv("GH_TOKEN")
    if not token:
        raise ValueError("GitHub token is required. Pass --token or set GH_TOKEN.")
    if args.months < 1:
        raise ValueError("--months must be >= 1")

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    else:
        start_date = get_account_creation_date(args.username, token) or (
            datetime.now(timezone.utc).date() - timedelta(days=3650)
        )

    print("Fetching commit data from GitHub API...")
    commits = fetch_commits_search(args.username, token, start_date.isoformat())
    total_commits = len(commits)
    print(f"Found {total_commits} total commits")

    commit_dates = [parse_commit_date(commit["date"]) for commit in commits]
    since_date = min(commit_dates) if commit_dates else start_date

    streaks = calculate_streaks(commits)
    monthly = calculate_monthly_commits(commits)

    print(f"Current streak: {streaks['current']} days")
    print(f"Longest streak: {streaks['longest']} days")

    os.makedirs(args.assets_dir, exist_ok=True)
    svg_path = os.path.join(args.assets_dir, "streak.svg")
    with open(svg_path, "w", encoding="utf-8") as svg_file:
        svg_file.write(generate_streak_svg(total_commits, since_date, streaks))
    print("Generated streak.svg")

    update_readme(total_commits, monthly, since_date, args.months, args.readme)

    stats_path = os.path.join(args.assets_dir, "stats.json")
    with open(stats_path, "w", encoding="utf-8") as stats_file:
        json.dump(
            {
                "total_commits": total_commits,
                "current_streak": streaks["current"],
                "longest_streak": streaks["longest"],
                "since_date": since_date.isoformat(),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            },
            stats_file,
            indent=2,
        )
    print("All statistics updated successfully")


if __name__ == "__main__":
    main()

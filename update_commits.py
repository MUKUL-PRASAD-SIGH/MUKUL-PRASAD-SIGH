import argparse
import os
import json
import requests
import re
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
    """Fetch all commits from GitHub API"""
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
            "order": "asc"
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
                "repo": item["repository"]["name"],
                "message": item["commit"]["message"]
            })

        print(f"📄 Fetched page {page}: {len(items)} commits")

        if len(items) < 100:
            break

        page += 1

    return commits

def get_repo_languages(owner, repo, token):
    """Fetch language statistics from a repo"""
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    data = github_get(url, token)
    return data or {}

def calculate_streaks(commits):
    """Calculate current and longest streaks from commits"""
    if not commits:
        return {
            "current": 0,
            "current_start": None,
            "current_end": None,
            "longest": 0,
            "longest_start": None,
            "longest_end": None
        }

    # Get unique dates
    active_dates = sorted(set(
        datetime.fromisoformat(c["date"].replace("Z", "+00:00")).date()
        for c in commits
    ))

    now = datetime.now(timezone.utc).date()

    # Find longest streak
    longest_streak = 0
    longest_start = None
    longest_end = None

    current_streak = 0
    current_start = None
    current_end = None

    streak_start = active_dates[0]
    streak_end = active_dates[0]
    streak_length = 1

    for i in range(1, len(active_dates)):
        if active_dates[i] - active_dates[i-1] == timedelta(days=1):
            streak_length += 1
            streak_end = active_dates[i]
        else:
            if streak_length > longest_streak:
                longest_streak = streak_length
                longest_start = streak_start
                longest_end = streak_end

            streak_start = active_dates[i]
            streak_end = active_dates[i]
            streak_length = 1

    # Check final streak
    if streak_length > longest_streak:
        longest_streak = streak_length
        longest_start = streak_start
        longest_end = streak_end

    # Calculate current streak
    if active_dates[-1] == now or active_dates[-1] == now - timedelta(days=1):
        current_streak = 1
        current_end = active_dates[-1]
        for i in range(len(active_dates) - 2, -1, -1):
            if active_dates[i] == active_dates[i+1] - timedelta(days=1):
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
        "longest_end": longest_end
    }

def generate_streak_svg(total_commits, start_date, streaks):
    """Generate dynamic streak SVG"""

    current_streak = streaks["current"]
    longest_streak = streaks["longest"]

    # Format date ranges
    date_range_text = f"{start_date.strftime('%b %d, %Y')} - Present"

    current_streak_text = ""
    if streaks["current_start"] and streaks["current_end"]:
        if streaks["current_start"].year == streaks["current_end"].year:
            current_streak_text = f"{streaks['current_start'].strftime('%b %d')} - {streaks['current_end'].strftime('%b %d')}"
        else:
            current_streak_text = f"{streaks['current_start'].strftime('%b %d, %Y')} - {streaks['current_end'].strftime('%b %d, %Y')}"

    longest_streak_text = ""
    if streaks["longest_start"] and streaks["longest_end"]:
        longest_streak_text = f"{streaks['longest_start'].strftime('%b %d, %Y')} - {streaks['longest_end'].strftime('%b %d, %Y')}"

    svg = f'''<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'
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
    </svg>'''

    return svg

def calculate_monthly_commits(commits):
    """Calculate commits per month for last 12 months"""
    monthly = Counter()

    for c in commits:
        dt = datetime.fromisoformat(c["date"].replace("Z", "+00:00"))
        key = f"{dt.year}-{dt.month:02d}"
        monthly[key] += 1

    return monthly

def update_readme(total_commits, monthly_stats):
    """Update README.md with latest statistics"""
    
    # Build monthly commits table
    months_sorted = sorted(monthly_stats.keys(), reverse=True)[:12]
    table = "| Month | Commits |\n|---:|---:|\n"
    for month in months_sorted:
        table += f"| {month} | {monthly_stats[month]} | \n"


    # Read current README
    with open('README.md', 'r', encoding='utf-8') as f:
        content = f.read()

    # Update total commits
    content = re.sub(
        r'- All-time commits \(since [^)]+\): \*\*\d+\*\*',
        f'- All-time commits (since 2008-01-01): **{total_commits}**',
        content
    )

    # Update monthly table
    content = re.sub(
        r'(?<=### Commits per month \(last 12 months\)\n\n)(\| Month.*?)(?=\n\n<!-- COMMITS_END -->)',
        table.rstrip('\n'),
        content,
        flags=re.DOTALL
    )

    # Write updated README
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ README.md updated with latest commit statistics")

def main():
    parser = argparse.ArgumentParser(description="Generate GitHub statistics")
    parser.add_argument('--username', required=True, help='GitHub username')
    parser.add_argument('--token', required=True, help='GitHub token')
    parser.add_argument('--start-date', default='2024-06-27', help='Start date (YYYY-MM-DD)')

    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()

    print("📊 Fetching commit data from GitHub API...")
    commits = fetch_commits_search(args.username, args.token, args.start_date)
    total_commits = len(commits)
    print(f"✅ Found {total_commits} total commits")

    # Calculate stats
    streaks = calculate_streaks(commits)
    monthly = calculate_monthly_commits(commits)

    print(f"🔥 Current streak: {streaks['current']} days")
    print(f"🏆 Longest streak: {streaks['longest']} days")

    # Generate SVG
    os.makedirs('assets', exist_ok=True)
    svg_content = generate_streak_svg(total_commits, start_date, streaks)

    with open('assets/streak.svg', 'w', encoding='utf-8') as f:
        f.write(svg_content)
    print("✅ Generated streak.svg")

    # Update README
    update_readme(total_commits, monthly)

    # Save stats to JSON for other scripts
    with open('assets/stats.json', 'w', encoding='utf-8') as f:
        json.dump({
            'total_commits': total_commits,
            'current_streak': streaks['current'],
            'longest_streak': streaks['longest'],
            'last_updated': datetime.now(timezone.utc).isoformat()
        }, f, indent=2)

    print("✅ All statistics updated successfully!")

if __name__ == '__main__':
    main()

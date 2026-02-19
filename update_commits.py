#!/usr/bin/env python3
"""
update_commits.py

Usage:
  export GH_TOKEN="..."   # or pass --token
  python update_commits.py --username MUKUL-PRASAD-SIGH --months 12 --start 2008-01-01 --readme README.md

This queries the GitHub GraphQL API for the user's contributions calendar for date ranges,
sums daily contribution counts per month and overall (since start date), and updates README.md
between markers <!-- COMMITS_START --> and <!-- COMMITS_END -->.
"""
import os
import sys
import argparse
import requests
from datetime import datetime, date, timedelta
from calendar import monthrange

GRAPHQL_URL = "https://api.github.com/graphql"
MARKER_START = "<!-- COMMITS_START -->"
MARKER_END = "<!-- COMMITS_END -->"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

def iso_datetime(d: date, end_of_day: bool = False):
    if end_of_day:
        return datetime.combine(d, datetime.max.time()).replace(microsecond=0).isoformat() + "Z"
    return datetime.combine(d, datetime.min.time()).replace(microsecond=0).isoformat() + "Z"

def post_graphql(token, login, from_dt, to_dt):
    headers = {"Authorization": f"bearer {token}", "Accept": "application/vnd.github.v4+json"}
    variables = {"login": login, "from": from_dt, "to": to_dt}
    r = requests.post(GRAPHQL_URL, json={"query": QUERY, "variables": variables}, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise Exception(f"GraphQL errors: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]

def sum_weeks(weeks):
    total = 0
    for week in weeks:
        for d in week["contributionDays"]:
            total += d["contributionCount"]
    return total

def month_ranges_for_last_n(n, end_date=None):
    if end_date is None:
        end_date = date.today()
    ranges = []
    year = end_date.year
    month = end_date.month
    for i in range(n):
        first = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        last = date(year, month, last_day)
        ranges.append((first, last))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    ranges.reverse()
    return ranges

def fetch_total_contributions(token, login, start_date, end_date):
    """Fetch contributions in <=365-day chunks and return total count."""
    total = 0
    chunk_start = start_date
    while chunk_start <= end_date:
        chunk_end = min(chunk_start + timedelta(days=365), end_date)
        weeks = post_graphql(token, login, iso_datetime(chunk_start, False), iso_datetime(chunk_end, True))
        total += sum_weeks(weeks)
        # move to the next day after chunk_end
        chunk_start = chunk_end + timedelta(days=1)
    return total

def update_readme(path, new_block):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""
    if MARKER_START in content and MARKER_END in content:
        before, rest = content.split(MARKER_START, 1)
        _, after = rest.split(MARKER_END, 1)
        new_content = before + MARKER_START + "\n" + new_block + "\n" + MARKER_END + after
    else:
        if not content.endswith("\n"):
            content += "\n"
        new_content = content + "\n" + MARKER_START + "\n" + new_block + "\n" + MARKER_END + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True, help="GitHub username to query")
    parser.add_argument("--token", default=os.getenv("GH_TOKEN"), help="GitHub token (env GH_TOKEN)")
    parser.add_argument("--months", type=int, default=12, help="How many past months to show (default 12)")
    parser.add_argument("--start", default="2008-01-01", help="Start date for all-time sum (YYYY-MM-DD)")
    parser.add_argument("--readme", default="README.md", help="README file to update")
    args = parser.parse_args()

    if not args.token:
        print("Error: GitHub token required (set GH_TOKEN env or --token).", file=sys.stderr)
        sys.exit(2)

    try:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    except ValueError:
        print("Error: --start must be YYYY-MM-DD", file=sys.stderr)
        sys.exit(2)

    today = date.today()

    # All-time total (chunked to <= 1 year per GraphQL call)
    try:
        all_time_total = fetch_total_contributions(args.token, args.username, start_date, today)
    except Exception as e:
        print("GraphQL query failed while fetching all-time total:", str(e), file=sys.stderr)
        sys.exit(1)

    # Per-month for last N months
    month_ranges = month_ranges_for_last_n(args.months, end_date=today)
    month_stats = []
    for first, last in month_ranges:
        try:
            weeks = post_graphql(args.token, args.username, iso_datetime(first, False), iso_datetime(last, True))
        except Exception as e:
            print("GraphQL query failed for month", first, str(e), file=sys.stderr)
            sys.exit(1)
        cnt = sum_weeks(weeks)
        month_stats.append((first.strftime("%Y-%m"), cnt))

    # Build markdown block
    md_lines = []
    md_lines.append("## Contribution stats")
    md_lines.append("")
    md_lines.append(f"- All-time contributions (since {start_date.isoformat()}): **{all_time_total}**")
    md_lines.append("")
    md_lines.append(f"### Contributions per month (last {args.months} months)")
    md_lines.append("")
    md_lines.append("| Month | Contributions |")
    md_lines.append("|---:|---:|")
    for m, c in month_stats:
        md_lines.append(f"| {m} | {c} |")
    md = "\n".join(md_lines)

    update_readme(args.readme, md)
    print("Updated", args.readme)
    print(f"All time: {all_time_total}")
    for m, c in month_stats:
        print(f"{m}: {c}")

if __name__ == "__main__":
    main()

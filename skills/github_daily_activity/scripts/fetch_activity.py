from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta


QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      issueContributions(first: 50) {
        nodes {
          occurredAt
          issue {
            title
            url
            number
            state
            repository {
              nameWithOwner
              url
            }
          }
        }
      }
      pullRequestContributions(first: 50) {
        nodes {
          occurredAt
          pullRequest {
            title
            url
            number
            state
            mergedAt
            repository {
              nameWithOwner
              url
            }
          }
        }
      }
      pullRequestReviewContributions(first: 50) {
        nodes {
          occurredAt
          pullRequest {
            title
            url
            number
            repository {
              nameWithOwner
              url
            }
          }
        }
      }
      commitContributionsByRepository(maxRepositories: 20) {
        repository {
          nameWithOwner
          url
        }
        contributions(first: 20) {
          nodes {
            occurredAt
            commitCount
          }
        }
      }
    }
  }
}
""".strip()


def _resolve_date_window(date_arg: str | None) -> tuple[str, str, str, str]:
    now = datetime.now().astimezone()
    timezone_name = getattr(now.tzinfo, "key", None) or now.tzname() or "local"
    target_date = datetime.fromisoformat(date_arg).date() if date_arg else now.date()
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=now.tzinfo)
    end = start + timedelta(days=1)
    return target_date.isoformat(), timezone_name, start.astimezone().isoformat(), end.astimezone().isoformat()


def _run_gh_query(username: str, from_iso: str, to_iso: str) -> dict:
    command = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={QUERY}",
        "-F",
        f"login={username}",
        "-F",
        f"from={from_iso}",
        "-F",
        f"to={to_iso}",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("GitHub CLI `gh` is not installed or not available in PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.strip() or exc.stdout.strip() or "gh api graphql failed") from exc

    response = json.loads(result.stdout)
    if "errors" in response:
        raise RuntimeError(json.dumps(response["errors"], ensure_ascii=True))
    return response["data"]["user"]["contributionsCollection"]


def _normalize_activity(collection: dict) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []

    for node in collection.get("pullRequestContributions", {}).get("nodes", []):
        pull_request = node.get("pullRequest") or {}
        repository = pull_request.get("repository") or {}
        items.append(
            {
                "kind": "pull_request",
                "occurred_at": node.get("occurredAt"),
                "repo": repository.get("nameWithOwner"),
                "title": pull_request.get("title"),
                "state": pull_request.get("state"),
                "url": pull_request.get("url"),
                "links": {
                    "pr": pull_request.get("url"),
                    "repo": repository.get("url"),
                },
            }
        )

    for node in collection.get("issueContributions", {}).get("nodes", []):
        issue = node.get("issue") or {}
        repository = issue.get("repository") or {}
        items.append(
            {
                "kind": "issue",
                "occurred_at": node.get("occurredAt"),
                "repo": repository.get("nameWithOwner"),
                "title": issue.get("title"),
                "state": issue.get("state"),
                "url": issue.get("url"),
                "links": {
                    "issue": issue.get("url"),
                    "repo": repository.get("url"),
                },
            }
        )

    for node in collection.get("pullRequestReviewContributions", {}).get("nodes", []):
        pull_request = node.get("pullRequest") or {}
        repository = pull_request.get("repository") or {}
        items.append(
            {
                "kind": "review",
                "occurred_at": node.get("occurredAt"),
                "repo": repository.get("nameWithOwner"),
                "title": pull_request.get("title"),
                "url": pull_request.get("url"),
                "links": {
                    "review_target": pull_request.get("url"),
                    "repo": repository.get("url"),
                },
            }
        )

    for repo_group in collection.get("commitContributionsByRepository", []):
        repository = repo_group.get("repository") or {}
        contributions = repo_group.get("contributions", {}).get("nodes", [])
        total_commits = sum(int(node.get("commitCount") or 0) for node in contributions)
        if total_commits <= 0:
            continue
        items.append(
            {
                "kind": "commit_batch",
                "occurred_at": contributions[0].get("occurredAt") if contributions else None,
                "repo": repository.get("nameWithOwner"),
                "title": f"{total_commits} commits contributed",
                "url": repository.get("url"),
                "links": {
                    "repo": repository.get("url"),
                },
                "commit_count": total_commits,
            }
        )

    items.sort(key=lambda item: item.get("occurred_at") or "", reverse=True)
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GitHub daily activity for one user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--date", help="Date in YYYY-MM-DD format. Defaults to local-time today.")
    args = parser.parse_args()

    date_value, timezone_name, from_iso, to_iso = _resolve_date_window(args.date)
    collection = _run_gh_query(args.username, from_iso=from_iso, to_iso=to_iso)
    items = _normalize_activity(collection)
    payload = {
        "source": "github_daily_activity",
        "username": args.username,
        "date": date_value,
        "timezone": timezone_name,
        "from": from_iso,
        "to": to_iso,
        "counts": {
            "pull_requests": len(collection.get("pullRequestContributions", {}).get("nodes", [])),
            "issues": len(collection.get("issueContributions", {}).get("nodes", [])),
            "reviews": len(collection.get("pullRequestReviewContributions", {}).get("nodes", [])),
            "commit_repositories": len(collection.get("commitContributionsByRepository", [])),
        },
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)

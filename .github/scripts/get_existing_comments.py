#!/usr/bin/env python3
"""
기존 bot 인라인 코멘트 조회

Usage:
    python get_existing_comments.py --repo owner/repo --pr 123

Output (JSON):
    [
        {
            "id": 12345,
            "path": "src/api/routes.py",
            "line": 42,
            "body": "suggestion content...",
            "created_at": "2024-01-01T00:00:00Z",
            "thread_id": "PRRT_xxx",
            "is_resolved": false
        }
    ]
"""

import argparse
import json
import subprocess
import sys
from typing import Optional


def run_gh(args: list[str]) -> str:
    """gh CLI 실행"""
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return ""
    return result.stdout.strip()


def get_bot_review_comments(repo: str, pr_number: int) -> list[dict]:
    """github-actions bot의 인라인 리뷰 코멘트 조회"""

    # REST API로 리뷰 코멘트 조회
    comments_json = run_gh([
        "api", f"repos/{repo}/pulls/{pr_number}/comments",
        "--jq", '[.[] | select(.user.login == "github-actions[bot]") | {id: .id, path: .path, line: .line, body: .body, created_at: .created_at, node_id: .node_id}]'
    ])

    if not comments_json:
        return []

    comments = json.loads(comments_json)

    # GraphQL로 스레드 resolve 상태 조회
    owner, repo_name = repo.split("/")

    query = """
    query($owner: String!, $repo: String!, $pr: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr) {
          reviewThreads(first: 100) {
            nodes {
              id
              isResolved
              comments(first: 1) {
                nodes {
                  id
                  databaseId
                  author { login }
                }
              }
            }
          }
        }
      }
    }
    """

    threads_result = run_gh([
        "api", "graphql",
        "-f", f"query={query}",
        "-f", f"owner={owner}",
        "-f", f"repo={repo_name}",
        "-F", f"pr={pr_number}",
    ])

    # 스레드 정보를 comment id로 매핑
    thread_map = {}  # comment_id -> {thread_id, is_resolved}

    if threads_result:
        data = json.loads(threads_result)
        threads = data.get("data", {}).get("repository", {}).get("pullRequest", {}).get("reviewThreads", {}).get("nodes", [])

        for thread in threads:
            if thread.get("comments", {}).get("nodes"):
                first_comment = thread["comments"]["nodes"][0]
                if first_comment.get("author", {}).get("login") == "github-actions[bot]":
                    comment_id = first_comment.get("databaseId")
                    if comment_id:
                        thread_map[comment_id] = {
                            "thread_id": thread["id"],
                            "is_resolved": thread.get("isResolved", False)
                        }

    # 결과 조합
    result = []
    for comment in comments:
        comment_id = comment["id"]
        thread_info = thread_map.get(comment_id, {})

        result.append({
            "id": comment_id,
            "path": comment["path"],
            "line": comment.get("line"),
            "body": comment["body"],
            "created_at": comment["created_at"],
            "thread_id": thread_info.get("thread_id", ""),
            "is_resolved": thread_info.get("is_resolved", False)
        })

    return result


def main():
    parser = argparse.ArgumentParser(description="Get existing bot review comments")
    parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--unresolved-only", action="store_true", help="Only show unresolved comments")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")

    args = parser.parse_args()

    comments = get_bot_review_comments(args.repo, args.pr)

    if args.unresolved_only:
        comments = [c for c in comments if not c["is_resolved"]]

    output = json.dumps(comments, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Wrote {len(comments)} comments to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()

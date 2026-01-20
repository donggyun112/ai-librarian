#!/usr/bin/env python3
"""
GitHub PR Review Script

Codex가 출력한 JSON을 받아 GitHub API로 리뷰를 게시합니다.

Protocol:
    Codex는 아래 형식의 JSON을 stdout으로 출력해야 합니다:
    {
        "decision": "APPROVE" | "CHANGES_REQUESTED",
        "summary": "## 🔍 Code Review Summary\n...",
        "inline_comments": [
            {
                "path": "path/to/file.py",
                "line": 42,
                "body": "```suggestion\nfixed code\n```\nExplanation",
                "start_line": null  // optional for multi-line
            }
        ],
        "resolve_thread_ids": ["PRRT_xxx", "PRRT_yyy"]  // 해결된 이슈의 thread_id 목록
    }

Usage:
    echo '<json>' | python post_review.py --repo owner/repo --pr 123
    python post_review.py --repo owner/repo --pr 123 --input review.json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class InlineComment:
    path: str
    line: int
    body: str
    start_line: Optional[int] = None
    severity: str = "warning"  # "critical", "warning", "suggestion", "nitpick"


@dataclass
class ReviewPayload:
    decision: str  # "APPROVE" or "CHANGES_REQUESTED"
    summary: str
    inline_comments: list[InlineComment]
    resolve_thread_ids: list[str]  # 해결된 이슈의 thread_id 목록


def get_existing_comment_locations(repo: str, pr_number: int) -> set[tuple[str, int]]:
    """기존 bot 코멘트의 (path, line) 위치 조회 (unresolved 스레드만)

    Note: resolved된 스레드는 제외하여 회귀 버그 감지 가능하도록 함
    """
    owner, repo_name = repo.split("/")

    query = """
    query($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr) {
          reviewThreads(first: 100, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              isResolved
              comments(first: 1) {
                nodes {
                  author { login }
                  path
                  line
                }
              }
            }
          }
        }
      }
    }
    """

    locations = set()
    cursor = None
    has_next_page = True

    try:
        while has_next_page:
            gh_args = [
                "api", "graphql",
                "-f", f"query={query}",
                "-f", f"owner={owner}",
                "-f", f"repo={repo_name}",
                "-F", f"pr={pr_number}",
            ]
            if cursor:
                gh_args.extend(["-f", f"cursor={cursor}"])

            result = run_gh(gh_args)

            if not result:
                break

            data = json.loads(result)
            review_threads = data.get("data", {}).get("repository", {}).get("pullRequest", {}).get("reviewThreads", {})
            threads = review_threads.get("nodes", [])
            page_info = review_threads.get("pageInfo", {})

            for thread in threads:
                # Only include UNRESOLVED threads
                if thread.get("isResolved", False):
                    continue

                comments = thread.get("comments", {}).get("nodes", [])
                if comments:
                    first_comment = comments[0]
                    author_login = first_comment.get("author", {}).get("login", "")
                    if author_login in ("github-actions[bot]", "github-actions"):
                        path = first_comment.get("path")
                        line = first_comment.get("line")
                        if path and line:
                            locations.add((path, line))

            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

    except RuntimeError:
        pass

    return locations


def filter_duplicate_comments(
    comments: list[InlineComment],
    existing_locations: set[tuple[str, int]]
) -> list[InlineComment]:
    """기존 코멘트와 같은 위치의 새 코멘트 필터링"""
    filtered = []
    for c in comments:
        if (c.path, c.line) not in existing_locations:
            filtered.append(c)
        else:
            print(f"Skipping duplicate comment at {c.path}:{c.line}")
    return filtered


SEVERITY_EMOJI = {
    "critical": "🚨",
    "warning": "⚠️",
    "suggestion": "💡",
    "nitpick": "📝",
}


def format_comment_body(comment: InlineComment) -> str:
    """severity 이모지를 코멘트 body에 추가"""
    emoji = SEVERITY_EMOJI.get(comment.severity, "⚠️")
    severity_label = comment.severity.upper()
    # body가 suggestion 블록으로 시작하면 그 앞에 severity 추가
    if comment.body.strip().startswith("```suggestion"):
        return f"**{emoji} {severity_label}**\n\n{comment.body}"
    return f"**{emoji} {severity_label}**: {comment.body}"


def run_gh(args: list[str], input_data: Optional[str] = None, use_elevated_token: bool = False) -> str:
    """gh CLI 실행

    Args:
        args: gh CLI arguments
        input_data: stdin input data
        use_elevated_token: If True, use GH_TOKEN_ELEVATED env var for operations
                           that require elevated permissions (e.g., GraphQL mutations)
    """
    cmd = ["gh"] + args

    # Optionally use elevated token for specific operations
    env = None
    if use_elevated_token:
        elevated_token = os.environ.get("GH_TOKEN_ELEVATED")
        if elevated_token:
            env = os.environ.copy()
            env["GH_TOKEN"] = elevated_token

    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        print(f"Error running: {' '.join(cmd)}", file=sys.stderr)
        print(f"stderr: {result.stderr}", file=sys.stderr)
        raise RuntimeError(f"gh command failed: {result.stderr}")
    return result.stdout.strip()


def get_commit_sha(pr_number: int) -> str:
    """PR의 HEAD commit SHA 조회"""
    return run_gh([
        "pr", "view", str(pr_number),
        "--json", "headRefOid",
        "-q", ".headRefOid"
    ])


def dismiss_previous_reviews(repo: str, pr_number: int) -> None:
    """이전 CHANGES_REQUESTED 리뷰 dismiss"""
    reviews_json = run_gh([
        "api", f"repos/{repo}/pulls/{pr_number}/reviews",
        "--jq", '[.[] | select(.state == "CHANGES_REQUESTED" and .user.login == "github-actions[bot]") | .id]'
    ])

    review_ids = json.loads(reviews_json) if reviews_json else []

    for review_id in review_ids:
        try:
            run_gh([
                "api", "--method", "PUT",
                f"repos/{repo}/pulls/{pr_number}/reviews/{review_id}/dismissals",
                "-f", "message=Superseded by new review"
            ])
            print(f"Dismissed review {review_id}")
        except RuntimeError as e:
            print(f"Warning: Failed to dismiss review {review_id}: {e}", file=sys.stderr)


def resolve_bot_threads(repo: str, pr_number: int) -> None:
    """github-actions bot의 미해결 스레드 resolve (pagination 지원)"""
    owner, repo_name = repo.split("/")

    query = """
    query($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr) {
          reviewThreads(first: 100, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              id
              isResolved
              comments(first: 1) {
                nodes { author { login } }
              }
            }
          }
        }
      }
    }
    """

    # 모든 미해결 bot 스레드 수집
    thread_ids = []
    cursor = None
    has_next_page = True

    while has_next_page:
        gh_args = [
            "api", "graphql",
            "-f", f"query={query}",
            "-f", f"owner={owner}",
            "-f", f"repo={repo_name}",
            "-F", f"pr={pr_number}",
        ]
        if cursor:
            gh_args.extend(["-f", f"cursor={cursor}"])

        result = run_gh(gh_args)

        if not result:
            break

        data = json.loads(result)
        review_threads = data.get("data", {}).get("repository", {}).get("pullRequest", {}).get("reviewThreads", {})
        threads = review_threads.get("nodes", [])
        page_info = review_threads.get("pageInfo", {})

        for thread in threads:
            if not thread.get("isResolved", True):
                comments = thread.get("comments", {}).get("nodes", [])
                if comments:
                    # GraphQL returns "github-actions" while REST API returns "github-actions[bot]"
                    author_login = comments[0].get("author", {}).get("login", "")
                    if author_login in ("github-actions[bot]", "github-actions"):
                        thread_ids.append(thread["id"])

        has_next_page = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")

    mutation = "mutation ResolveThread($threadId: ID!) { resolveReviewThread(input: {threadId: $threadId}) { thread { isResolved } } }"

    for thread_id in thread_ids:
        if not thread_id:
            continue
        try:
            # Use JSON input for proper GraphQL variable handling
            # Use elevated token for GraphQL mutations (resolve requires special permissions)
            payload = json.dumps({
                "query": mutation,
                "variables": {"threadId": thread_id}
            })
            run_gh(["api", "graphql", "--input", "-"], input_data=payload, use_elevated_token=True)
            print(f"Resolved thread {thread_id}")
        except RuntimeError as e:
            print(f"Warning: Failed to resolve thread {thread_id}: {e}", file=sys.stderr)


def generate_inline_summary(comments: list[InlineComment]) -> str:
    """인라인 코멘트 요약 생성"""
    severity_counts = {"critical": 0, "warning": 0, "suggestion": 0, "nitpick": 0}
    for c in comments:
        severity = c.severity if c.severity in severity_counts else "warning"
        severity_counts[severity] += 1

    parts = []
    if severity_counts["critical"] > 0:
        parts.append(f"🚨 {severity_counts['critical']} critical")
    if severity_counts["warning"] > 0:
        parts.append(f"⚠️ {severity_counts['warning']} warnings")
    if severity_counts["suggestion"] > 0:
        parts.append(f"💡 {severity_counts['suggestion']} suggestions")
    if severity_counts["nitpick"] > 0:
        parts.append(f"📝 {severity_counts['nitpick']} nitpicks")

    if not parts:
        return "Inline review comments added."

    return f"**Inline Review:** {', '.join(parts)}"


def get_pr_diff_lines(repo: str, pr_number: int) -> dict[str, set[int]]:
    """PR diff에서 변경된 라인 번호 추출

    Returns:
        dict mapping file path to set of valid line numbers for comments
    """
    try:
        diff_output = run_gh([
            "api", f"repos/{repo}/pulls/{pr_number}",
            "-H", "Accept: application/vnd.github.v3.diff"
        ])
    except RuntimeError:
        return {}

    valid_lines: dict[str, set[int]] = {}
    current_file = None
    current_line = 0

    for line in diff_output.split('\n'):
        # Parse file header: +++ b/path/to/file
        if line.startswith('+++ b/'):
            current_file = line[6:]
            valid_lines[current_file] = set()
        # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
        elif line.startswith('@@') and current_file:
            # Extract new_start from @@ -x,y +new_start,count @@
            match = re.search(r'\+(\d+)', line)
            if match:
                current_line = int(match.group(1))
        # Count lines in the new file (+ or space, not -)
        elif current_file and not line.startswith('-'):
            if line.startswith('+') or (line and not line.startswith('\\')):
                valid_lines[current_file].add(current_line)
                current_line += 1
            elif line == '':
                # Empty line in diff
                pass

    return valid_lines


def filter_comments_by_diff(
    comments: list[InlineComment],
    valid_lines: dict[str, set[int]]
) -> tuple[list[InlineComment], list[InlineComment]]:
    """diff 범위 내의 코멘트만 필터링

    Returns:
        (valid_comments, invalid_comments)
    """
    valid = []
    invalid = []

    for c in comments:
        file_lines = valid_lines.get(c.path, set())
        if c.line in file_lines:
            valid.append(c)
        else:
            invalid.append(c)

    return valid, invalid


def post_inline_comments(repo: str, pr_number: int, commit_sha: str, comments: list[InlineComment]) -> None:
    """인라인 코멘트 게시"""
    if not comments:
        return

    # PR diff 범위 확인
    valid_lines = get_pr_diff_lines(repo, pr_number)

    if valid_lines:
        valid_comments, invalid_comments = filter_comments_by_diff(comments, valid_lines)

        if invalid_comments:
            print(f"Skipping {len(invalid_comments)} comments outside diff range:", file=sys.stderr)
            for c in invalid_comments:
                print(f"  - {c.path}:{c.line} (not in diff)", file=sys.stderr)

        comments = valid_comments

    if not comments:
        print("No valid inline comments to post (all outside diff range)")
        return

    comments_payload = []
    for c in comments:
        comment_obj = {
            "path": c.path,
            "line": c.line,
            "side": "RIGHT",
            "body": format_comment_body(c),
        }
        if c.start_line:
            comment_obj["start_line"] = c.start_line
            comment_obj["start_side"] = "RIGHT"
        comments_payload.append(comment_obj)

    # 의미있는 요약 생성
    summary = generate_inline_summary(comments)

    payload = {
        "commit_id": commit_sha,
        "event": "COMMENT",
        "body": summary,
        "comments": comments_payload,
    }

    payload_json = json.dumps(payload)

    # gh api with --input from stdin
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{pr_number}/reviews", "--method", "POST", "--input", "-"],
        input=payload_json,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error posting inline comments: {result.stderr}", file=sys.stderr)
        print(f"Failed comments:", file=sys.stderr)
        for c in comments:
            print(f"  - {c.path}:{c.line}", file=sys.stderr)
        raise RuntimeError(f"Failed to post inline comments: {result.stderr}")

    print(f"Posted {len(comments)} inline comments")


def post_summary_comment(repo: str, pr_number: int, summary: str) -> None:
    """요약 코멘트 게시"""
    run_gh(["pr", "comment", str(pr_number), "--body", summary])
    print("Posted summary comment")


def submit_review_decision(pr_number: int, decision: str) -> None:
    """최종 리뷰 결정 (approve/request-changes)

    Note: APPROVE는 GitHub repo settings에서 아래 옵션이 켜져 있어야 함:
    Settings → Actions → General → Workflow permissions
    → ✅ "Allow GitHub Actions to create and approve pull requests"

    권한이 없으면 approve 실패하지만, dismiss_previous_reviews()가
    이전 CHANGES_REQUESTED를 제거하므로 머지 블럭은 해제됨.

    Note: 자신의 PR에는 request-changes를 할 수 없음 (GitHub 정책)
    이 경우 COMMENT로 대체하여 리뷰 내용은 전달함.
    """
    if decision == "APPROVE":
        try:
            run_gh([
                "pr", "review", str(pr_number),
                "--approve",
                "--body", "✅ AI Review Passed - All checks passed"
            ])
            print("Approved PR")
        except RuntimeError as e:
            # GitHub Actions GITHUB_TOKEN은 approve 권한이 없을 수 있음
            print(f"Note: Could not approve PR (expected with default GITHUB_TOKEN): {e}", file=sys.stderr)
            print("Previous CHANGES_REQUESTED reviews were dismissed - merge is unblocked")
    elif decision == "CHANGES_REQUESTED":
        try:
            run_gh([
                "pr", "review", str(pr_number),
                "--request-changes",
                "--body", "❌ AI Review Failed - Please fix the issues above"
            ])
            print("Requested changes")
        except RuntimeError as e:
            # 자신의 PR에는 request-changes 불가 (GitHub 정책)
            if "Can not request changes on your own" in str(e):
                print("Note: Cannot request changes on own PR (GitHub policy) - review posted as comment", file=sys.stderr)
            else:
                print(f"Warning: Could not submit review decision: {e}", file=sys.stderr)
    else:
        print(f"Unknown decision: {decision}", file=sys.stderr)


def resolve_specific_threads(thread_ids: list[str]) -> None:
    """특정 thread_id 목록을 resolve"""
    mutation = "mutation ResolveThread($threadId: ID!) { resolveReviewThread(input: {threadId: $threadId}) { thread { isResolved } } }"

    for thread_id in thread_ids:
        if not thread_id:
            continue
        try:
            # Use JSON input for proper GraphQL variable handling
            # Use elevated token for GraphQL mutations (resolve requires special permissions)
            payload = json.dumps({
                "query": mutation,
                "variables": {"threadId": thread_id}
            })
            run_gh(["api", "graphql", "--input", "-"], input_data=payload, use_elevated_token=True)
            print(f"Resolved thread {thread_id}")
        except RuntimeError as e:
            print(f"Warning: Failed to resolve thread {thread_id}: {e}", file=sys.stderr)


def parse_review_payload(data: dict) -> ReviewPayload:
    """JSON을 ReviewPayload로 파싱"""
    inline_comments = [
        InlineComment(
            path=c["path"],
            line=c["line"],
            body=c["body"],
            start_line=c.get("start_line"),
            severity=c.get("severity", "warning"),
        )
        for c in data.get("inline_comments", [])
    ]

    return ReviewPayload(
        decision=data.get("decision", "CHANGES_REQUESTED"),
        summary=data.get("summary", "No summary provided"),
        inline_comments=inline_comments,
        resolve_thread_ids=data.get("resolve_thread_ids", []),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Post GitHub PR review from Codex output")
    parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--input", "-i", help="Input JSON file (default: stdin)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")

    args = parser.parse_args()

    # JSON 읽기
    if args.input:
        with open(args.input) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    payload = parse_review_payload(data)

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"Repo: {args.repo}")
        print(f"PR: {args.pr}")
        print(f"Decision: {payload.decision}")
        print(f"Summary length: {len(payload.summary)} chars")
        print(f"Inline comments: {len(payload.inline_comments)}")
        for c in payload.inline_comments:
            print(f"  - {c.path}:{c.line}")
        return

    # 실행
    commit_sha = get_commit_sha(args.pr)
    print(f"Commit SHA: {commit_sha}")

    # 1. 이전 CHANGES_REQUESTED 리뷰 dismiss
    dismiss_previous_reviews(args.repo, args.pr)

    # 2. Codex가 해결됐다고 판단한 스레드 resolve
    if payload.resolve_thread_ids:
        print(f"Resolving {len(payload.resolve_thread_ids)} threads marked as fixed")
        resolve_specific_threads(payload.resolve_thread_ids)

    # 3. 인라인 코멘트 게시 (중복 필터링)
    if payload.inline_comments:
        existing_locations = get_existing_comment_locations(args.repo, args.pr)
        filtered_comments = filter_duplicate_comments(payload.inline_comments, existing_locations)
        print(f"Filtered {len(payload.inline_comments) - len(filtered_comments)} duplicate comments")
        post_inline_comments(args.repo, args.pr, commit_sha, filtered_comments)

    # 4. 요약 코멘트 게시
    post_summary_comment(args.repo, args.pr, payload.summary)

    # 5. APPROVE면 남은 bot 스레드도 모두 resolve
    if payload.decision == "APPROVE":
        resolve_bot_threads(args.repo, args.pr)

    # 6. 최종 결정 제출
    submit_review_decision(args.pr, payload.decision)

    print("Review completed successfully")


if __name__ == "__main__":
    main()

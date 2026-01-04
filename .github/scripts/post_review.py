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


@dataclass
class ReviewPayload:
    decision: str  # "APPROVE" or "CHANGES_REQUESTED"
    summary: str
    inline_comments: list[InlineComment]
    resolve_thread_ids: list[str]  # 해결된 이슈의 thread_id 목록


def run_gh(args: list[str], input_data: Optional[str] = None) -> str:
    """gh CLI 실행"""
    cmd = ["gh"] + args
    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
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
    """github-actions bot의 미해결 스레드 resolve"""
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
                nodes { author { login } }
              }
            }
          }
        }
      }
    }
    """

    result = run_gh([
        "api", "graphql",
        "-f", f"query={query}",
        "-f", f"owner={owner}",
        "-f", f"repo={repo_name}",
        "-F", f"pr={pr_number}",
        "--jq", '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false and .comments.nodes[0].author.login == "github-actions[bot]") | .id'
    ])

    thread_ids = result.strip().split("\n") if result.strip() else []

    mutation = """
    mutation($threadId: ID!) {
      resolveReviewThread(input: {threadId: $threadId}) {
        thread { isResolved }
      }
    }
    """

    for thread_id in thread_ids:
        if not thread_id:
            continue
        try:
            run_gh([
                "api", "graphql",
                "-f", f"query={mutation}",
                "-f", f"threadId={thread_id}"
            ])
            print(f"Resolved thread {thread_id}")
        except RuntimeError as e:
            print(f"Warning: Failed to resolve thread {thread_id}: {e}", file=sys.stderr)


def post_inline_comments(repo: str, pr_number: int, commit_sha: str, comments: list[InlineComment]) -> None:
    """인라인 코멘트 게시"""
    if not comments:
        return

    comments_payload = []
    for c in comments:
        comment_obj = {
            "path": c.path,
            "line": c.line,
            "side": "RIGHT",
            "body": c.body,
        }
        if c.start_line:
            comment_obj["start_line"] = c.start_line
            comment_obj["start_side"] = "RIGHT"
        comments_payload.append(comment_obj)

    payload = {
        "commit_id": commit_sha,
        "event": "COMMENT",
        "body": "Inline suggestions",
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
        raise RuntimeError(f"Failed to post inline comments: {result.stderr}")

    print(f"Posted {len(comments)} inline comments")


def post_summary_comment(repo: str, pr_number: int, summary: str) -> None:
    """요약 코멘트 게시"""
    run_gh(["pr", "comment", str(pr_number), "--body", summary])
    print("Posted summary comment")


def submit_review_decision(pr_number: int, decision: str) -> None:
    """최종 리뷰 결정 (approve/request-changes)

    Note: GitHub 레포 설정에서 아래 옵션이 켜져 있어야 함:
    Settings → Actions → General → Workflow permissions
    → ✅ "Allow GitHub Actions to create and approve pull requests"
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
            # 이전 CHANGES_REQUESTED가 dismiss되었으므로 머지 블럭은 해제됨
            print(f"Note: Could not approve PR (expected with GITHUB_TOKEN): {e}", file=sys.stderr)
            print("Previous CHANGES_REQUESTED reviews were dismissed - merge is unblocked")
    elif decision == "CHANGES_REQUESTED":
        run_gh([
            "pr", "review", str(pr_number),
            "--request-changes",
            "--body", "❌ AI Review Failed - Please fix the issues above"
        ])
        print("Requested changes")
    else:
        print(f"Unknown decision: {decision}", file=sys.stderr)


def resolve_specific_threads(thread_ids: list[str]) -> None:
    """특정 thread_id 목록을 resolve"""
    mutation = """
    mutation($threadId: ID!) {
      resolveReviewThread(input: {threadId: $threadId}) {
        thread { isResolved }
      }
    }
    """

    for thread_id in thread_ids:
        if not thread_id:
            continue
        try:
            run_gh([
                "api", "graphql",
                "-f", f"query={mutation}",
                "-f", f"threadId={thread_id}"
            ])
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
        )
        for c in data.get("inline_comments", [])
    ]

    return ReviewPayload(
        decision=data.get("decision", "CHANGES_REQUESTED"),
        summary=data.get("summary", "No summary provided"),
        inline_comments=inline_comments,
        resolve_thread_ids=data.get("resolve_thread_ids", []),
    )


def main():
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

    # 3. 인라인 코멘트 게시
    if payload.inline_comments:
        post_inline_comments(args.repo, args.pr, commit_sha, payload.inline_comments)

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

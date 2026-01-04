#!/usr/bin/env python3
"""
GitHub PR Reply Script

Codex가 출력한 JSON을 받아 GitHub API로 답글을 게시합니다.

Protocol:
    Codex는 아래 형식의 JSON을 stdout으로 출력해야 합니다:
    {
        "reply": "답글 내용 (markdown)",
        "resolve_thread": true | false
    }

Usage:
    python post_reply.py --repo owner/repo --pr 123 --event-type issue_comment --in-reply-to 456 --input reply.json
"""

import argparse
import json
import subprocess
import sys
from typing import Optional


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


def post_reply_to_review_comment(repo: str, in_reply_to_id: int, body: str) -> None:
    """인라인 리뷰 코멘트에 답글 게시

    Note: GitHub API endpoint is /repos/{repo}/pulls/comments/{comment_id}/replies
    NOT /repos/{repo}/pulls/{pr_number}/comments/{comment_id}/replies
    """
    run_gh([
        "api", f"repos/{repo}/pulls/comments/{in_reply_to_id}/replies",
        "--method", "POST",
        "-f", f"body={body}"
    ])
    print(f"Posted reply to review comment {in_reply_to_id}")


def post_reply_to_issue_comment(pr_number: int, body: str) -> None:
    """PR 대화에 코멘트 게시"""
    run_gh(["pr", "comment", str(pr_number), "--body", body])
    print(f"Posted comment to PR {pr_number}")


def resolve_thread(thread_node_id: str) -> None:
    """리뷰 스레드 resolve"""
    if not thread_node_id:
        print("No thread_node_id provided, skipping resolve")
        return

    mutation = "mutation ResolveThread($threadId: ID!) { resolveReviewThread(input: {threadId: $threadId}) { thread { isResolved } } }"

    try:
        # Use JSON input for proper GraphQL variable handling
        payload = json.dumps({
            "query": mutation,
            "variables": {"threadId": thread_node_id}
        })
        run_gh(["api", "graphql", "--input", "-"], input_data=payload)
        print(f"Resolved thread {thread_node_id}")
    except RuntimeError as e:
        print(f"Warning: Failed to resolve thread: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Post GitHub PR reply from Codex output")
    parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--event-type", required=True, choices=["issue_comment", "pull_request_review_comment"])
    parser.add_argument("--in-reply-to", type=int, help="Comment ID to reply to")
    parser.add_argument("--thread-node-id", help="Thread node ID for resolving")
    parser.add_argument("--input", "-i", help="Input JSON file (default: stdin)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")

    args = parser.parse_args()

    # JSON 읽기
    if args.input:
        with open(args.input) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    reply_body = data.get("reply", "")
    should_resolve = data.get("resolve_thread", False)

    if not reply_body:
        print("Error: No reply content in JSON", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"Repo: {args.repo}")
        print(f"PR: {args.pr}")
        print(f"Event type: {args.event_type}")
        print(f"In reply to: {args.in_reply_to}")
        print(f"Thread node ID: {args.thread_node_id}")
        print(f"Reply length: {len(reply_body)} chars")
        print(f"Resolve thread: {should_resolve}")
        return

    # 답글 게시
    if args.event_type == "pull_request_review_comment":
        if not args.in_reply_to:
            print("Error: --in-reply-to required for review comment replies", file=sys.stderr)
            sys.exit(1)
        post_reply_to_review_comment(args.repo, args.in_reply_to, reply_body)
    else:
        post_reply_to_issue_comment(args.pr, reply_body)

    # 스레드 resolve
    if should_resolve and args.thread_node_id:
        resolve_thread(args.thread_node_id)

    print("Reply completed successfully")


if __name__ == "__main__":
    main()

"""Tests for post_review.py script."""

import json
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from post_review import (
    InlineComment,
    ReviewPayload,
    parse_review_payload,
    run_gh,
    get_commit_sha,
    dismiss_previous_reviews,
    resolve_specific_threads,
    post_inline_comments,
    post_summary_comment,
    submit_review_decision,
    resolve_bot_threads,
    get_existing_comment_locations,
    filter_duplicate_comments,
    format_comment_body,
)


class TestParseReviewPayload:
    """Tests for parse_review_payload function."""

    def test_parse_full_payload(self, sample_review_payload):
        """Test parsing a complete review payload."""
        payload = parse_review_payload(sample_review_payload)

        assert payload.decision == "CHANGES_REQUESTED"
        assert "Code Review Summary" in payload.summary
        assert len(payload.inline_comments) == 1
        assert payload.inline_comments[0].path == "src/api/routes.py"
        assert payload.inline_comments[0].line == 42
        assert payload.resolve_thread_ids == ["PRRT_abc123"]

    def test_parse_minimal_payload(self):
        """Test parsing a minimal payload with defaults."""
        data = {"summary": "All good"}
        payload = parse_review_payload(data)

        assert payload.decision == "CHANGES_REQUESTED"  # default
        assert payload.summary == "All good"
        assert payload.inline_comments == []
        assert payload.resolve_thread_ids == []

    def test_parse_approve_payload(self):
        """Test parsing an APPROVE decision."""
        data = {
            "decision": "APPROVE",
            "summary": "LGTM!",
            "inline_comments": [],
            "resolve_thread_ids": []
        }
        payload = parse_review_payload(data)

        assert payload.decision == "APPROVE"

    def test_parse_multiline_comment(self):
        """Test parsing inline comment with start_line."""
        data = {
            "decision": "CHANGES_REQUESTED",
            "summary": "Issues found",
            "inline_comments": [
                {
                    "path": "file.py",
                    "line": 50,
                    "body": "Multi-line fix",
                    "start_line": 45
                }
            ],
            "resolve_thread_ids": []
        }
        payload = parse_review_payload(data)

        assert payload.inline_comments[0].start_line == 45
        assert payload.inline_comments[0].line == 50


class TestRunGh:
    """Tests for run_gh function."""

    def test_run_gh_success(self, mock_run_gh):
        """Test successful gh CLI execution."""
        mock_run_gh.return_value = MagicMock(
            returncode=0,
            stdout="abc123def",
            stderr=""
        )

        result = run_gh(["pr", "view", "1", "--json", "headRefOid"])

        assert result == "abc123def"
        mock_run_gh.assert_called_once()

    def test_run_gh_failure(self, mock_run_gh):
        """Test failed gh CLI execution raises RuntimeError."""
        mock_run_gh.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Not found"
        )

        with pytest.raises(RuntimeError, match="gh command failed"):
            run_gh(["pr", "view", "999"])

    def test_run_gh_with_input(self, mock_run_gh):
        """Test gh CLI with stdin input."""
        mock_run_gh.return_value = MagicMock(
            returncode=0,
            stdout="success",
            stderr=""
        )

        result = run_gh(["api", "endpoint"], input_data='{"key": "value"}')

        assert result == "success"
        call_args = mock_run_gh.call_args
        assert call_args.kwargs["input"] == '{"key": "value"}'


class TestGetCommitSha:
    """Tests for get_commit_sha function."""

    @patch("post_review.run_gh")
    def test_get_commit_sha(self, mock_gh):
        """Test fetching commit SHA for PR."""
        mock_gh.return_value = "abc123def456"

        sha = get_commit_sha(42)

        assert sha == "abc123def456"
        mock_gh.assert_called_once_with([
            "pr", "view", "42",
            "--json", "headRefOid",
            "-q", ".headRefOid"
        ])


class TestDismissPreviousReviews:
    """Tests for dismiss_previous_reviews function."""

    @patch("post_review.run_gh")
    def test_dismiss_reviews(self, mock_gh):
        """Test dismissing previous CHANGES_REQUESTED reviews."""
        # First call returns review IDs, second call dismisses
        mock_gh.side_effect = ["[12345, 67890]", "", ""]

        dismiss_previous_reviews("owner/repo", 42)

        assert mock_gh.call_count == 3
        # Check dismiss calls
        assert "dismissals" in str(mock_gh.call_args_list[1])
        assert "dismissals" in str(mock_gh.call_args_list[2])

    @patch("post_review.run_gh")
    def test_no_reviews_to_dismiss(self, mock_gh):
        """Test when there are no reviews to dismiss."""
        mock_gh.return_value = "[]"

        dismiss_previous_reviews("owner/repo", 42)

        assert mock_gh.call_count == 1

    @patch("post_review.run_gh")
    def test_dismiss_partial_failure(self, mock_gh):
        """Test partial failure when dismissing reviews."""
        mock_gh.side_effect = [
            "[12345, 67890]",
            RuntimeError("Failed"),
            ""
        ]

        # Should not raise, just warn
        dismiss_previous_reviews("owner/repo", 42)


class TestResolveSpecificThreads:
    """Tests for resolve_specific_threads function."""

    @patch("post_review.run_gh")
    def test_resolve_threads(self, mock_gh):
        """Test resolving specific threads."""
        mock_gh.return_value = ""

        resolve_specific_threads(["PRRT_abc", "PRRT_def"])

        assert mock_gh.call_count == 2

    @patch("post_review.run_gh")
    def test_resolve_empty_list(self, mock_gh):
        """Test with empty thread list."""
        resolve_specific_threads([])

        mock_gh.assert_not_called()

    @patch("post_review.run_gh")
    def test_resolve_skips_empty_ids(self, mock_gh):
        """Test that empty thread IDs are skipped."""
        mock_gh.return_value = ""

        resolve_specific_threads(["PRRT_abc", "", "PRRT_def"])

        assert mock_gh.call_count == 2


class TestPostInlineComments:
    """Tests for post_inline_comments function."""

    @patch("subprocess.run")
    def test_post_comments(self, mock_run):
        """Test posting inline comments."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        comments = [
            InlineComment(
                path="file.py",
                line=42,
                body="Fix this",
                start_line=None
            )
        ]

        post_inline_comments("owner/repo", 1, "abc123", comments)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        payload = json.loads(call_args.kwargs["input"])
        assert payload["commit_id"] == "abc123"
        assert len(payload["comments"]) == 1
        assert payload["comments"][0]["path"] == "file.py"
        assert payload["comments"][0]["line"] == 42

    @patch("subprocess.run")
    def test_post_multiline_comment(self, mock_run):
        """Test posting multiline comment."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        comments = [
            InlineComment(
                path="file.py",
                line=50,
                body="Multi-line fix",
                start_line=45
            )
        ]

        post_inline_comments("owner/repo", 1, "abc123", comments)

        payload = json.loads(mock_run.call_args.kwargs["input"])
        assert payload["comments"][0]["start_line"] == 45
        assert payload["comments"][0]["start_side"] == "RIGHT"

    def test_post_no_comments(self, mock_run_gh):
        """Test with empty comments list."""
        post_inline_comments("owner/repo", 1, "abc123", [])

        mock_run_gh.assert_not_called()


class TestSubmitReviewDecision:
    """Tests for submit_review_decision function."""

    @patch("post_review.run_gh")
    def test_approve(self, mock_gh):
        """Test submitting APPROVE decision."""
        mock_gh.return_value = ""

        submit_review_decision(42, "APPROVE")

        mock_gh.assert_called_once()
        call_args = mock_gh.call_args[0][0]
        assert "--approve" in call_args

    @patch("post_review.run_gh")
    def test_request_changes(self, mock_gh):
        """Test submitting CHANGES_REQUESTED decision."""
        mock_gh.return_value = ""

        submit_review_decision(42, "CHANGES_REQUESTED")

        mock_gh.assert_called_once()
        call_args = mock_gh.call_args[0][0]
        assert "--request-changes" in call_args

    @patch("post_review.run_gh")
    def test_unknown_decision(self, mock_gh, capsys):
        """Test unknown decision is logged but doesn't crash."""
        submit_review_decision(42, "UNKNOWN")

        mock_gh.assert_not_called()
        captured = capsys.readouterr()
        assert "Unknown decision" in captured.err


class TestSeverityAndDuplicates:
    """Tests for severity formatting and duplicate filtering."""

    def test_format_comment_body_with_severity(self):
        """Test severity emoji is added to comment body."""
        comment = InlineComment(
            path="file.py",
            line=10,
            body="This is a problem",
            severity="critical"
        )
        formatted = format_comment_body(comment)
        assert "🚨" in formatted
        assert "CRITICAL" in formatted

    def test_format_comment_body_suggestion_block(self):
        """Test severity is added before suggestion block."""
        comment = InlineComment(
            path="file.py",
            line=10,
            body="```suggestion\nfixed code\n```\nExplanation",
            severity="warning"
        )
        formatted = format_comment_body(comment)
        assert formatted.startswith("**⚠️ WARNING**")
        assert "```suggestion" in formatted

    def test_filter_duplicate_comments(self):
        """Test duplicate comments are filtered out."""
        comments = [
            InlineComment(path="a.py", line=10, body="issue 1"),
            InlineComment(path="b.py", line=20, body="issue 2"),
            InlineComment(path="a.py", line=10, body="duplicate"),
        ]
        existing = {("a.py", 10)}

        filtered = filter_duplicate_comments(comments, existing)

        assert len(filtered) == 1
        assert filtered[0].path == "b.py"

    def test_filter_no_duplicates(self):
        """Test no filtering when no duplicates exist."""
        comments = [
            InlineComment(path="a.py", line=10, body="issue 1"),
            InlineComment(path="b.py", line=20, body="issue 2"),
        ]
        existing = {("c.py", 30)}

        filtered = filter_duplicate_comments(comments, existing)

        assert len(filtered) == 2

    @patch("post_review.run_gh")
    def test_get_existing_comment_locations(self, mock_gh):
        """Test fetching existing comment locations (unresolved only)."""
        graphql_response = json.dumps({
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "isResolved": False,
                                    "comments": {
                                        "nodes": [{
                                            "author": {"login": "github-actions[bot]"},
                                            "path": "file.py",
                                            "line": 42
                                        }]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        })
        mock_gh.return_value = graphql_response

        locations = get_existing_comment_locations("owner/repo", 1)

        assert ("file.py", 42) in locations

    @patch("post_review.run_gh")
    def test_get_existing_comment_locations_excludes_resolved(self, mock_gh):
        """Test that resolved threads are excluded."""
        graphql_response = json.dumps({
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "isResolved": True,  # This should be excluded
                                    "comments": {
                                        "nodes": [{
                                            "author": {"login": "github-actions[bot]"},
                                            "path": "resolved.py",
                                            "line": 10
                                        }]
                                    }
                                },
                                {
                                    "isResolved": False,  # This should be included
                                    "comments": {
                                        "nodes": [{
                                            "author": {"login": "github-actions"},
                                            "path": "unresolved.py",
                                            "line": 20
                                        }]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        })
        mock_gh.return_value = graphql_response

        locations = get_existing_comment_locations("owner/repo", 1)

        assert ("resolved.py", 10) not in locations
        assert ("unresolved.py", 20) in locations

    @patch("post_review.run_gh")
    def test_get_existing_comment_locations_empty(self, mock_gh):
        """Test empty response returns empty set."""
        mock_gh.return_value = ""

        locations = get_existing_comment_locations("owner/repo", 1)

        assert locations == set()

    def test_parse_payload_with_severity(self):
        """Test parsing payload includes severity."""
        data = {
            "decision": "CHANGES_REQUESTED",
            "summary": "Issues found",
            "inline_comments": [
                {
                    "path": "file.py",
                    "line": 42,
                    "body": "Fix this",
                    "severity": "critical"
                }
            ],
            "resolve_thread_ids": []
        }
        payload = parse_review_payload(data)

        assert payload.inline_comments[0].severity == "critical"

    def test_parse_payload_default_severity(self):
        """Test default severity is warning."""
        data = {
            "decision": "CHANGES_REQUESTED",
            "summary": "Issues found",
            "inline_comments": [
                {
                    "path": "file.py",
                    "line": 42,
                    "body": "Fix this"
                }
            ],
            "resolve_thread_ids": []
        }
        payload = parse_review_payload(data)

        assert payload.inline_comments[0].severity == "warning"

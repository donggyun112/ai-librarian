"""Tests for post_reply.py script."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from post_reply import (
    run_gh,
    post_reply_to_review_comment,
    post_reply_to_issue_comment,
    resolve_thread,
)


class TestRunGh:
    """Tests for run_gh function."""

    def test_run_gh_success(self, mock_run_gh):
        """Test successful gh CLI execution."""
        mock_run_gh.return_value = MagicMock(
            returncode=0,
            stdout="success",
            stderr=""
        )

        result = run_gh(["pr", "comment", "1", "--body", "test"])

        assert result == "success"

    def test_run_gh_failure(self, mock_run_gh):
        """Test failed gh CLI execution raises RuntimeError."""
        mock_run_gh.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error message"
        )

        with pytest.raises(RuntimeError, match="gh command failed"):
            run_gh(["pr", "comment", "999"])


class TestPostReplyToReviewComment:
    """Tests for post_reply_to_review_comment function."""

    @patch("post_reply.run_gh")
    def test_post_reply(self, mock_gh):
        """Test posting reply to review comment."""
        mock_gh.return_value = ""

        post_reply_to_review_comment("owner/repo", 12345, "My reply")

        mock_gh.assert_called_once_with([
            "api", "repos/owner/repo/pulls/comments/12345/replies",
            "--method", "POST",
            "-f", "body=My reply"
        ])

    @patch("post_reply.run_gh")
    def test_post_reply_with_markdown(self, mock_gh):
        """Test posting reply with markdown content."""
        mock_gh.return_value = ""

        body = "```python\nprint('hello')\n```"
        post_reply_to_review_comment("owner/repo", 123, body)

        call_args = mock_gh.call_args[0][0]
        assert f"body={body}" in call_args


class TestPostReplyToIssueComment:
    """Tests for post_reply_to_issue_comment function."""

    @patch("post_reply.run_gh")
    def test_post_comment(self, mock_gh):
        """Test posting comment to PR conversation."""
        mock_gh.return_value = ""

        post_reply_to_issue_comment(42, "My comment")

        mock_gh.assert_called_once_with([
            "pr", "comment", "42", "--body", "My comment"
        ])


class TestResolveThread:
    """Tests for resolve_thread function."""

    @patch("post_reply.run_gh")
    def test_resolve_thread(self, mock_gh):
        """Test resolving a thread."""
        mock_gh.return_value = ""

        resolve_thread("PRRT_abc123")

        mock_gh.assert_called_once()
        call_args = mock_gh.call_args[0][0]
        assert "graphql" in call_args
        assert "--input" in call_args
        # Check the input_data contains the thread ID
        input_data = mock_gh.call_args[1].get("input_data", "")
        assert "PRRT_abc123" in input_data

    @patch("post_reply.run_gh")
    def test_resolve_empty_thread_id(self, mock_gh, capsys):
        """Test that empty thread ID is skipped."""
        resolve_thread("")

        mock_gh.assert_not_called()
        captured = capsys.readouterr()
        assert "No thread_node_id provided" in captured.out

    @patch("post_reply.run_gh")
    def test_resolve_failure_warning(self, mock_gh, capsys):
        """Test that resolve failure logs warning but doesn't crash."""
        mock_gh.side_effect = RuntimeError("GraphQL error")

        resolve_thread("PRRT_invalid")

        captured = capsys.readouterr()
        assert "Failed to resolve thread" in captured.err


class TestMainFunction:
    """Tests for main function integration."""

    @patch("post_reply.run_gh")
    @patch("post_reply.post_reply_to_issue_comment")
    @patch("post_reply.resolve_thread")
    def test_main_issue_comment(self, mock_resolve, mock_post, mock_gh, tmp_path, sample_reply_payload):
        """Test main function with issue_comment event."""
        from post_reply import main
        import sys

        # Write sample input
        input_file = tmp_path / "reply.json"
        input_file.write_text(json.dumps(sample_reply_payload))

        # Mock sys.argv
        with patch.object(sys, "argv", [
            "post_reply.py",
            "--repo", "owner/repo",
            "--pr", "42",
            "--event-type", "issue_comment",
            "--thread-node-id", "PRRT_abc",
            "--input", str(input_file)
        ]):
            main()

        mock_post.assert_called_once_with(42, sample_reply_payload["reply"])
        mock_resolve.assert_called_once_with("PRRT_abc")

    @patch("post_reply.run_gh")
    @patch("post_reply.post_reply_to_review_comment")
    @patch("post_reply.resolve_thread")
    def test_main_review_comment(self, mock_resolve, mock_post, mock_gh, tmp_path, sample_reply_payload):
        """Test main function with pull_request_review_comment event."""
        from post_reply import main
        import sys

        # Write sample input
        input_file = tmp_path / "reply.json"
        input_file.write_text(json.dumps(sample_reply_payload))

        # Mock sys.argv
        with patch.object(sys, "argv", [
            "post_reply.py",
            "--repo", "owner/repo",
            "--pr", "42",
            "--event-type", "pull_request_review_comment",
            "--in-reply-to", "12345",
            "--thread-node-id", "PRRT_abc",
            "--input", str(input_file)
        ]):
            main()

        mock_post.assert_called_once_with("owner/repo", 12345, sample_reply_payload["reply"])

    @patch("post_reply.run_gh")
    def test_main_no_resolve(self, mock_gh, tmp_path):
        """Test main function when resolve_thread is false."""
        from post_reply import main
        import sys

        payload = {"reply": "Answer", "resolve_thread": False}
        input_file = tmp_path / "reply.json"
        input_file.write_text(json.dumps(payload))

        with patch.object(sys, "argv", [
            "post_reply.py",
            "--repo", "owner/repo",
            "--pr", "42",
            "--event-type", "issue_comment",
            "--input", str(input_file)
        ]):
            with patch("post_reply.post_reply_to_issue_comment"):
                with patch("post_reply.resolve_thread") as mock_resolve:
                    main()

        mock_resolve.assert_not_called()

    @patch("post_reply.run_gh")
    def test_main_missing_reply_exits(self, mock_gh, tmp_path, capsys):
        """Test main function exits with error when reply is missing."""
        from post_reply import main
        import sys

        payload = {"resolve_thread": True}  # No reply
        input_file = tmp_path / "reply.json"
        input_file.write_text(json.dumps(payload))

        with patch.object(sys, "argv", [
            "post_reply.py",
            "--repo", "owner/repo",
            "--pr", "42",
            "--event-type", "issue_comment",
            "--input", str(input_file)
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No reply content" in captured.err
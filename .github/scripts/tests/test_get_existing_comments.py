"""Tests for get_existing_comments.py script."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from get_existing_comments import (
    run_gh,
    get_bot_review_comments,
)


class TestRunGh:
    """Tests for run_gh function."""

    def test_run_gh_success(self, mock_run_gh):
        """Test successful gh CLI execution."""
        mock_run_gh.return_value = MagicMock(
            returncode=0,
            stdout="output",
            stderr=""
        )

        result = run_gh(["api", "endpoint"])

        assert result == "output"

    def test_run_gh_failure_returns_empty(self, mock_run_gh, capsys):
        """Test failed gh CLI returns empty string."""
        mock_run_gh.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error"
        )

        result = run_gh(["api", "endpoint"])

        assert result == ""
        captured = capsys.readouterr()
        assert "Error" in captured.err


class TestGetBotReviewComments:
    """Tests for get_bot_review_comments function."""

    @patch("get_existing_comments.run_gh")
    def test_get_comments_with_threads(self, mock_gh, sample_bot_comments, sample_threads_graphql_response):
        """Test fetching comments and merging with thread status."""
        mock_gh.side_effect = [
            json.dumps(sample_bot_comments),  # REST API
            json.dumps(sample_threads_graphql_response)  # GraphQL
        ]

        result = get_bot_review_comments("owner/repo", 42)

        assert len(result) == 2
        # First comment should have thread info
        assert result[0]["id"] == 12345
        assert result[0]["thread_id"] == "PRRT_thread1"
        assert result[0]["is_resolved"] is False
        # Second comment should be resolved
        assert result[1]["id"] == 67890
        assert result[1]["thread_id"] == "PRRT_thread2"
        assert result[1]["is_resolved"] is True

    @patch("get_existing_comments.run_gh")
    def test_get_comments_empty(self, mock_gh):
        """Test with no comments."""
        mock_gh.return_value = ""

        result = get_bot_review_comments("owner/repo", 42)

        assert result == []

    @patch("get_existing_comments.run_gh")
    def test_get_comments_no_threads(self, mock_gh, sample_bot_comments):
        """Test when GraphQL returns no threads."""
        mock_gh.side_effect = [
            json.dumps(sample_bot_comments),
            ""  # Empty GraphQL response
        ]

        result = get_bot_review_comments("owner/repo", 42)

        assert len(result) == 2
        # Comments should have empty thread_id and is_resolved=False
        assert result[0]["thread_id"] == ""
        assert result[0]["is_resolved"] is False

    @patch("get_existing_comments.run_gh")
    def test_pagination_merges_pages(self, mock_gh):
        """Test that pagination properly merges multiple pages."""
        page1 = [{"id": 1, "path": "a.py", "line": 1, "body": "test1", "created_at": "2024-01-01", "node_id": "n1"}]
        page2 = [{"id": 2, "path": "b.py", "line": 2, "body": "test2", "created_at": "2024-01-02", "node_id": "n2"}]

        # --paginate with --jq outputs one JSON array per page, separated by newlines
        paginated_output = json.dumps(page1) + "\n" + json.dumps(page2)

        mock_gh.side_effect = [
            paginated_output,  # REST API with pagination
            ""  # Empty GraphQL
        ]

        result = get_bot_review_comments("owner/repo", 42)

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    @patch("get_existing_comments.run_gh")
    def test_handles_malformed_pagination(self, mock_gh):
        """Test handling malformed JSON in pagination."""
        # Some valid, some invalid - invalid lines should be skipped
        paginated_output = '[{"id": 1, "path": "a.py", "line": 1, "body": "test", "created_at": "2024-01-01", "node_id": "n1"}]\ninvalid json\n[{"id": 2, "path": "b.py", "line": 2, "body": "test2", "created_at": "2024-01-02", "node_id": "n2"}]'

        mock_gh.side_effect = [
            paginated_output,
            ""
        ]

        result = get_bot_review_comments("owner/repo", 42)

        # Should have 2 comments (skipping invalid line)
        assert len(result) == 2


class TestMainFunction:
    """Tests for main function."""

    @patch("get_existing_comments.get_bot_review_comments")
    def test_main_stdout(self, mock_get, capsys):
        """Test main function outputs to stdout."""
        from get_existing_comments import main
        import sys

        mock_get.return_value = [
            {"id": 1, "path": "file.py", "line": 10, "body": "test", "created_at": "2024-01-01", "thread_id": "T1", "is_resolved": False}
        ]

        with patch.object(sys, "argv", [
            "get_existing_comments.py",
            "--repo", "owner/repo",
            "--pr", "42"
        ]):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert len(output) == 1
        assert output[0]["id"] == 1

    @patch("get_existing_comments.get_bot_review_comments")
    def test_main_unresolved_only(self, mock_get, capsys):
        """Test --unresolved-only filter."""
        from get_existing_comments import main
        import sys

        mock_get.return_value = [
            {"id": 1, "path": "a.py", "line": 1, "body": "unresolved", "created_at": "2024-01-01", "thread_id": "T1", "is_resolved": False},
            {"id": 2, "path": "b.py", "line": 2, "body": "resolved", "created_at": "2024-01-02", "thread_id": "T2", "is_resolved": True}
        ]

        with patch.object(sys, "argv", [
            "get_existing_comments.py",
            "--repo", "owner/repo",
            "--pr", "42",
            "--unresolved-only"
        ]):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert len(output) == 1
        assert output[0]["id"] == 1

    @patch("get_existing_comments.get_bot_review_comments")
    def test_main_output_file(self, mock_get, tmp_path, capsys):
        """Test --output writes to file."""
        from get_existing_comments import main
        import sys

        mock_get.return_value = [
            {"id": 1, "path": "file.py", "line": 10, "body": "test", "created_at": "2024-01-01", "thread_id": "T1", "is_resolved": False}
        ]

        output_file = tmp_path / "comments.json"

        with patch.object(sys, "argv", [
            "get_existing_comments.py",
            "--repo", "owner/repo",
            "--pr", "42",
            "--output", str(output_file)
        ]):
            main()

        # Check file was written
        assert output_file.exists()
        with open(output_file) as f:
            output = json.load(f)
        assert len(output) == 1

        # Check stderr message
        captured = capsys.readouterr()
        assert "Wrote 1 comments" in captured.err

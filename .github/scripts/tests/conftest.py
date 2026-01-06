"""Pytest configuration for GitHub Actions scripts tests."""

import pytest
from unittest.mock import patch


@pytest.fixture
def mock_run_gh():
    """Mock the run_gh function to avoid actual gh CLI calls."""
    with patch("subprocess.run") as mock:
        yield mock


@pytest.fixture
def sample_review_payload():
    """Sample Codex review output."""
    return {
        "decision": "CHANGES_REQUESTED",
        "summary": "## 🔍 Code Review Summary\n\nFound issues.",
        "inline_comments": [
            {
                "path": "src/api/routes.py",
                "line": 42,
                "body": "```suggestion\nfixed code\n```\nExplanation",
                "start_line": None
            }
        ],
        "resolve_thread_ids": ["PRRT_abc123"]
    }


@pytest.fixture
def sample_reply_payload():
    """Sample Codex reply output."""
    return {
        "reply": "Here is my response to your question.",
        "resolve_thread": True
    }


@pytest.fixture
def sample_bot_comments():
    """Sample bot comments from REST API."""
    return [
        {
            "id": 12345,
            "path": "src/api/routes.py",
            "line": 42,
            "body": "```suggestion\nold code\n```",
            "created_at": "2024-01-01T00:00:00Z",
            "node_id": "PRR_abc"
        },
        {
            "id": 67890,
            "path": "src/services/auth.py",
            "line": 100,
            "body": "Missing type hint",
            "created_at": "2024-01-02T00:00:00Z",
            "node_id": "PRR_def"
        }
    ]


@pytest.fixture
def sample_threads_graphql_response():
    """Sample GraphQL response for thread status."""
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": [
                            {
                                "id": "PRRT_thread1",
                                "isResolved": False,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "PRR_abc",
                                            "databaseId": 12345,
                                            "author": {"login": "github-actions[bot]"}
                                        }
                                    ]
                                }
                            },
                            {
                                "id": "PRRT_thread2",
                                "isResolved": True,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "PRR_def",
                                            "databaseId": 67890,
                                            "author": {"login": "github-actions[bot]"}
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

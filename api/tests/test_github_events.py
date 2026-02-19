"""Tests for GitHub event parsing — verifies activity feed correctness."""

from api.services.github_events import _parse_events


def _make_event(event_type, actor_login, payload, event_id="1"):
    return {
        "id": event_id,
        "type": event_type,
        "actor": {"login": actor_login},
        "payload": payload,
        "created_at": "2026-01-15T10:00:00Z",
    }


def test_parse_issues_event_opened():
    events = [
        _make_event(
            "IssuesEvent",
            "fishbowl-engineer[bot]",
            {
                "action": "opened",
                "issue": {
                    "title": "Fix RSS timeout handling",
                    "html_url": "https://github.com/test/repo/issues/1",
                },
            },
        )
    ]
    parsed = _parse_events(events)
    assert len(parsed) == 1
    assert parsed[0]["type"] == "issue_created"
    assert parsed[0]["actor"] == "engineer"  # mapped via ACTOR_MAP
    assert "Fix RSS timeout" in parsed[0]["description"]


def test_parse_pr_merged_vs_closed():
    merged_event = _make_event(
        "PullRequestEvent",
        "fishbowl-reviewer[bot]",
        {
            "action": "closed",
            "pull_request": {"title": "Add caching", "html_url": "...", "merged": True},
        },
        event_id="2",
    )
    closed_event = _make_event(
        "PullRequestEvent",
        "fishbowl-reviewer[bot]",
        {
            "action": "closed",
            "pull_request": {
                "title": "Rejected PR",
                "html_url": "...",
                "merged": False,
            },
        },
        event_id="3",
    )

    # Merged PR should be included
    parsed_merged = _parse_events([merged_event])
    assert len(parsed_merged) == 1
    assert parsed_merged[0]["type"] == "pr_merged"

    # Closed-but-not-merged PR should NOT be included
    parsed_closed = _parse_events([closed_event])
    assert len(parsed_closed) == 0


def test_parse_push_event_multiple_commits():
    events = [
        _make_event(
            "PushEvent",
            "fbomb111",
            {
                "commits": [
                    {"message": "first commit", "sha": "aaa"},
                    {"message": "second commit", "sha": "bbb"},
                    {"message": "Fix the thing\n\nLonger description", "sha": "ccc"},
                ],
            },
        )
    ]
    parsed = _parse_events(events)
    assert len(parsed) == 1
    assert parsed[0]["actor"] == "human"  # fbomb111 -> human via ACTOR_MAP
    # Should show last commit's first line + count
    assert "Fix the thing" in parsed[0]["description"]
    assert "+2 more" in parsed[0]["description"]

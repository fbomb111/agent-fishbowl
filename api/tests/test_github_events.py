"""Tests for GitHub event parsing — verifies activity feed correctness."""

from api.services.github_events import parse_events


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
    parsed = parse_events(events)
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
    parsed_merged = parse_events([merged_event])
    assert len(parsed_merged) == 1
    assert parsed_merged[0]["type"] == "pr_merged"

    # Closed-but-not-merged PR should NOT be included
    parsed_closed = parse_events([closed_event])
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
    parsed = parse_events(events)
    assert len(parsed) == 1
    assert parsed[0]["actor"] == "human"  # fbomb111 -> human via ACTOR_MAP
    # Should show last commit's first line + count
    assert "Fix the thing" in parsed[0]["description"]
    assert "+2 more" in parsed[0]["description"]


def test_deduplicates_label_events():
    """GitHub fires multiple IssuesEvent/labeled for a single label action.

    parse_events should keep only one per unique (actor, description, issue),
    even when timestamps differ by a second.
    """
    # Simulate 4 duplicate label events with consecutive IDs and slightly
    # different timestamps (GitHub often emits these 1-2s apart)
    base = {
        "action": "labeled",
        "label": {"name": "source/qa-analyst"},
        "issue": {
            "number": 179,
            "title": "Some issue",
            "html_url": "https://github.com/test/repo/issues/179",
        },
    }
    events = [
        {
            "id": str(i),
            "type": "IssuesEvent",
            "actor": {"login": "fishbowl-product-owner[bot]"},
            "payload": base,
            "created_at": f"2026-02-20T15:23:{40 + i}Z",
        }
        for i in range(4)
    ]
    parsed = parse_events(events)
    labeled = [e for e in parsed if e["type"] == "issue_labeled"]
    assert len(labeled) == 1
    assert "source/qa-analyst" in labeled[0]["description"]


def test_parse_pr_event_null_title():
    """GitHub Events API often returns null for pull_request.title.

    parse_events should treat null title as empty string, not propagate None.
    """
    event = _make_event(
        "PullRequestEvent",
        "fishbowl-reviewer[bot]",
        {
            "action": "closed",
            "pull_request": {
                "number": 177,
                "title": None,
                "html_url": "https://github.com/test/repo/pull/177",
                "merged": True,
            },
        },
    )
    parsed = parse_events([event])
    assert len(parsed) == 1
    assert parsed[0]["type"] == "pr_merged"
    # subject_title should not be set (empty string is falsy, _make_event skips it)
    assert "subject_title" not in parsed[0]
    # Description should not contain "None"
    assert "None" not in parsed[0]["description"]
    assert "PR #177" in parsed[0]["description"]


def test_parse_pr_review_null_title():
    """PullRequestReviewEvent also gets null titles from the Events API."""
    event = _make_event(
        "PullRequestReviewEvent",
        "fishbowl-reviewer[bot]",
        {
            "review": {"state": "approved", "body": "LGTM"},
            "pull_request": {
                "number": 177,
                "title": None,
                "html_url": "https://github.com/test/repo/pull/177",
            },
        },
    )
    parsed = parse_events([event])
    assert len(parsed) == 1
    assert parsed[0]["type"] == "pr_reviewed"
    assert "None" not in parsed[0]["description"]
    assert "PR #177" in parsed[0]["description"]


def test_dedup_keeps_different_labels():
    """Dedup should not collapse events for different labels on the same issue."""
    base_payload = {
        "action": "labeled",
        "issue": {
            "number": 42,
            "title": "Test",
            "html_url": "https://github.com/test/repo/issues/42",
        },
    }
    events = [
        _make_event(
            "IssuesEvent",
            "fishbowl-product-owner[bot]",
            {**base_payload, "label": {"name": "priority/high"}},
            event_id="1",
        ),
        _make_event(
            "IssuesEvent",
            "fishbowl-product-owner[bot]",
            {**base_payload, "label": {"name": "source/tech-lead"}},
            event_id="2",
        ),
    ]
    parsed = parse_events(events)
    labeled = [e for e in parsed if e["type"] == "issue_labeled"]
    assert len(labeled) == 2

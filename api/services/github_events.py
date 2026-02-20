"""GitHub event parsing — converts raw GitHub API events into ActivityEvent dicts.

Maps GitHub actor logins to agent roles and parses various event types
(issues, PRs, reviews, pushes, comments, releases) into a normalized format.
"""

from typing import Any

from api.config import get_settings

# Map GitHub login to agent role for display
ACTOR_MAP: dict[str, str] = {
    "fishbowl-engineer[bot]": "engineer",
    "fishbowl-reviewer[bot]": "reviewer",
    "fishbowl-product-owner[bot]": "po",
    "fishbowl-product-manager[bot]": "pm",
    "fishbowl-tech-lead[bot]": "tech-lead",
    "fishbowl-user-experience[bot]": "ux",
    "fishbowl-triage[bot]": "triage",
    "fishbowl-site-reliability[bot]": "sre",
    "fishbowl-content-creator[bot]": "content-creator",
    "github-actions[bot]": "github-actions",
    "YourMoveLabs": "org",
}

# Event types that represent interactive human actions (issues, comments, reviews)
_HUMAN_EVENT_TYPES = {
    "IssuesEvent",
    "IssueCommentEvent",
    "PullRequestEvent",
    "PullRequestReviewEvent",
    "PullRequestReviewCommentEvent",
}


def _map_actor(login: str, event_type: str = "") -> str:
    """Map a GitHub login to a friendly agent name.

    For fbomb111 (Frankie), we split attribution based on event type:
    interactive actions (issues, comments, reviews) → "human",
    process actions (releases, pushes, branch ops) → "org".
    """
    if login == "fbomb111":
        return "human" if event_type in _HUMAN_EVENT_TYPES else "org"
    return ACTOR_MAP.get(login, login)


def _make_event(
    event: dict[str, Any],
    *,
    event_type: str,
    actor: str,
    description: str,
    url: str | None = None,
    subject_type: str | None = None,
    subject_number: int | None = None,
    subject_title: str | None = None,
    comment_body: str | None = None,
    comment_url: str | None = None,
) -> dict[str, Any]:
    """Build a parsed event dict with optional subject fields."""
    entry: dict[str, Any] = {
        "id": event["id"],
        "type": event_type,
        "actor": actor,
        "avatar_url": event.get("actor", {}).get("avatar_url"),
        "description": description,
        "timestamp": event.get("created_at", ""),
        "url": url,
    }
    if subject_type:
        entry["subject_type"] = subject_type
    if subject_number is not None:
        entry["subject_number"] = subject_number
    if subject_title:
        entry["subject_title"] = subject_title
    if comment_body:
        entry["comment_body"] = comment_body
    if comment_url:
        entry["comment_url"] = comment_url
    return entry


# Labels worth surfacing in the feed (others are noise)
_INTERESTING_LABELS = {
    "status/in-progress",
    "review/approved",
    "review/changes-requested",
    "pm/misaligned",
}
_INTERESTING_LABEL_PREFIXES = ("priority/", "source/")


def _is_interesting_label(label_name: str) -> bool:
    if label_name in _INTERESTING_LABELS:
        return True
    return any(label_name.startswith(p) for p in _INTERESTING_LABEL_PREFIXES)


def _deduplicate_label_events(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove duplicate label events that GitHub fires for a single action.

    GitHub often creates multiple IssuesEvent/labeled entries with consecutive
    IDs for one label action. We keep only the first per unique combination
    of (actor, description, subject_number, timestamp).
    """
    seen_labels: set[tuple[str, str, int | None, str]] = set()
    result: list[dict[str, Any]] = []
    for evt in events:
        if evt["type"] == "issue_labeled":
            key = (
                evt.get("actor", ""),
                evt.get("description", ""),
                evt.get("subject_number"),
                evt.get("timestamp", ""),
            )
            if key in seen_labels:
                continue
            seen_labels.add(key)
        result.append(evt)
    return result


def parse_events(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert GitHub API events into ActivityEvent dicts."""
    parsed: list[dict[str, Any]] = []

    for event in raw_events:
        event_type = event.get("type", "")
        actor = _map_actor(event.get("actor", {}).get("login", "unknown"), event_type)
        payload = event.get("payload", {})

        if event_type == "IssuesEvent":
            action = payload.get("action", "")
            issue = payload.get("issue", {})
            number = issue.get("number")
            title = issue.get("title", "")
            subject = dict(
                subject_type="issue",
                subject_number=number,
                subject_title=title,
            )

            if action == "opened":
                parsed.append(
                    _make_event(
                        event,
                        event_type="issue_created",
                        actor=actor,
                        description=f"Opened issue #{number}: {title}",
                        url=issue.get("html_url"),
                        **subject,
                    )
                )
            elif action == "closed":
                parsed.append(
                    _make_event(
                        event,
                        event_type="issue_closed",
                        actor=actor,
                        description=f"Closed issue #{number}: {title}",
                        url=issue.get("html_url"),
                        **subject,
                    )
                )
            elif action == "labeled":
                label_name = payload.get("label", {}).get("name", "")
                if _is_interesting_label(label_name):
                    parsed.append(
                        _make_event(
                            event,
                            event_type="issue_labeled",
                            actor=actor,
                            description=f"Labeled #{number} with {label_name}",
                            url=issue.get("html_url"),
                            **subject,
                        )
                    )

        elif event_type == "PullRequestEvent":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            title = pr.get("title") or ""
            number = pr.get("number")
            url = pr.get("html_url")
            subject = dict(
                subject_type="pr",
                subject_number=number,
                subject_title=title,
            )

            if action == "opened":
                parsed.append(
                    _make_event(
                        event,
                        event_type="pr_opened",
                        actor=actor,
                        description=f"Opened PR #{number}: {title}",
                        url=url,
                        **subject,
                    )
                )
            elif action == "closed" and pr.get("merged"):
                parsed.append(
                    _make_event(
                        event,
                        event_type="pr_merged",
                        actor=actor,
                        description=f"Merged PR #{number}: {title}",
                        url=url,
                        **subject,
                    )
                )
            elif action == "closed" and not pr.get("merged"):
                parsed.append(
                    _make_event(
                        event,
                        event_type="pr_closed",
                        actor=actor,
                        description=f"Closed PR #{number}: {title}",
                        url=url,
                        **subject,
                    )
                )

        elif event_type == "PullRequestReviewEvent":
            pr = payload.get("pull_request", {})
            review = payload.get("review", {})
            state = review.get("state", "")
            title = pr.get("title") or ""
            number = pr.get("number")
            subject = dict(
                subject_type="pr",
                subject_number=number,
                subject_title=title,
            )

            if state == "approved":
                desc = f"Approved PR #{number}: {title}"
            elif state == "changes_requested":
                desc = f"Requested changes on PR #{number}: {title}"
            else:
                desc = f"Reviewed PR #{number}: {title}"

            # Include review body text (up to 500 chars)
            review_body_raw = review.get("body") or ""
            review_body = review_body_raw[:500]
            review_url = review.get("html_url") or pr.get("html_url")

            parsed.append(
                _make_event(
                    event,
                    event_type="pr_reviewed",
                    actor=actor,
                    description=desc,
                    url=review_url,
                    comment_body=review_body if review_body else None,
                    comment_url=review_url
                    if review_body_raw and len(review_body_raw) > 500
                    else None,
                    **subject,
                )
            )

        elif event_type == "PushEvent":
            commits = payload.get("commits", [])
            if commits:
                msg = commits[-1].get("message", "").split("\n")[0]
                count = len(commits)
                suffix = f" (+{count - 1} more)" if count > 1 else ""
                parsed.append(
                    _make_event(
                        event,
                        event_type="commit",
                        actor=actor,
                        description=f"{msg}{suffix}",
                        url=f"https://github.com/{get_settings().github_repo}/commit/{commits[-1].get('sha', '')}",
                    )
                )

        elif event_type == "IssueCommentEvent":
            issue = payload.get("issue", {})
            comment = payload.get("comment", {})
            number = issue.get("number")
            title = issue.get("title", "")
            body_raw = comment.get("body", "")
            body = body_raw[:300]
            is_pr = "pull_request" in issue
            html_url = comment.get("html_url")
            parsed.append(
                _make_event(
                    event,
                    event_type="comment",
                    actor=actor,
                    description=f"Commented on #{number}: {title}",
                    url=html_url,
                    subject_type="pr" if is_pr else "issue",
                    subject_number=number,
                    subject_title=title,
                    comment_body=body if body else None,
                    comment_url=html_url if len(body_raw) > 300 else None,
                )
            )

        elif event_type == "ReleaseEvent":
            action = payload.get("action", "")
            release = payload.get("release", {})
            tag = release.get("tag_name", "")
            name = release.get("name", tag)
            if action == "published":
                parsed.append(
                    _make_event(
                        event,
                        event_type="release",
                        actor=actor,
                        description=f"Published release: {name}",
                        url=release.get("html_url"),
                    )
                )

    return _deduplicate_label_events(parsed)

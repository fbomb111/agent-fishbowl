"""Tests for goals_parser — markdown parsing and file caching."""

from unittest.mock import patch

from api.services.goals_parser import parse_goals_file

WELL_FORMED_GOALS = """\
# Agent Fishbowl — Strategic Goals

## Mission

Build software with AI agents in public.

## Goal 1: Ship Quality

Deliver working software that solves real problems.

- Clean PRs with substantive reviews
- Consistent code conventions

## Goal 2: Self-Improvement

Grow more capable and autonomous over time.

The curated feed is the learning pipeline.

- Curate actionable content
- Learn and apply from curated sources

## Constraints

- **Agents do all implementation.** The human sets goals only.
- **Ship incrementally.** Small working improvements over redesigns.
"""

GOALS_WITH_SKIPPED_LINES = """\
# Goals

## Mission

Test mission.

## Goal 1: Quality

Summary paragraph.

Examples of what counts:

- Example one
- Example two

## Goal 2: Revenue

Revenue summary.

PM decides which model fits best.

- Attract visitors
"""


def _write_goals(tmp_path, content):
    """Write content to a goals.md file and return its path."""
    goals_file = tmp_path / "goals.md"
    goals_file.write_text(content)
    return str(goals_file)


def test_parse_well_formed_goals(tmp_path):
    path = _write_goals(tmp_path, WELL_FORMED_GOALS)
    with patch("api.services.goals_parser._find_goals_file", return_value=path):
        result = parse_goals_file()

    assert result["mission"] == "Build software with AI agents in public."
    assert len(result["goals"]) == 2
    assert len(result["constraints"]) == 2


def test_goal_fields_extracted(tmp_path):
    path = _write_goals(tmp_path, WELL_FORMED_GOALS)
    with patch("api.services.goals_parser._find_goals_file", return_value=path):
        result = parse_goals_file()

    goal1 = result["goals"][0]
    assert goal1["number"] == 1
    assert goal1["title"] == "Ship Quality"
    assert "working software" in goal1["summary"]
    assert goal1["examples"] == [
        "Clean PRs with substantive reviews",
        "Consistent code conventions",
    ]

    goal2 = result["goals"][1]
    assert goal2["number"] == 2
    assert goal2["title"] == "Self-Improvement"
    assert goal2["examples"] == [
        "Curate actionable content",
        "Learn and apply from curated sources",
    ]


def test_constraints_extracted(tmp_path):
    path = _write_goals(tmp_path, WELL_FORMED_GOALS)
    with patch("api.services.goals_parser._find_goals_file", return_value=path):
        result = parse_goals_file()

    assert result["constraints"] == [
        "Agents do all implementation",
        "Ship incrementally",
    ]


def test_skipped_lines_filtered(tmp_path):
    """Lines like 'Examples of ...' and 'PM decides ...' are excluded from summaries."""
    path = _write_goals(tmp_path, GOALS_WITH_SKIPPED_LINES)
    with patch("api.services.goals_parser._find_goals_file", return_value=path):
        result = parse_goals_file()

    goal1 = result["goals"][0]
    assert goal1["summary"] == "Summary paragraph."
    assert goal1["examples"] == ["Example one", "Example two"]

    goal2 = result["goals"][1]
    assert goal2["summary"] == "Revenue summary."
    assert goal2["examples"] == ["Attract visitors"]


def test_empty_file(tmp_path):
    path = _write_goals(tmp_path, "")
    with patch("api.services.goals_parser._find_goals_file", return_value=path):
        result = parse_goals_file()

    assert result["mission"] == ""
    assert result["goals"] == []
    assert result["constraints"] == []


def test_missing_sections(tmp_path):
    content = "# Goals\n\n## Mission\n\nOnly a mission here.\n"
    path = _write_goals(tmp_path, content)
    with patch("api.services.goals_parser._find_goals_file", return_value=path):
        result = parse_goals_file()

    assert result["mission"] == "Only a mission here."
    assert result["goals"] == []
    assert result["constraints"] == []


def test_goal_with_no_examples(tmp_path):
    content = """\
# Goals

## Goal 1: Simple

Just a summary, no bullet points.
"""
    path = _write_goals(tmp_path, content)
    with patch("api.services.goals_parser._find_goals_file", return_value=path):
        result = parse_goals_file()

    assert len(result["goals"]) == 1
    assert result["goals"][0]["summary"] == "Just a summary, no bullet points."
    assert result["goals"][0]["examples"] == []


def test_file_not_found_returns_empty():
    with patch(
        "api.services.goals_parser._find_goals_file",
        return_value="/nonexistent/goals.md",
    ):
        result = parse_goals_file()

    assert result == {"mission": "", "goals": [], "constraints": []}


def test_mtime_cache_returns_cached_result(tmp_path):
    """Second call with same mtime returns cached result without re-reading."""
    path = _write_goals(tmp_path, WELL_FORMED_GOALS)
    with patch("api.services.goals_parser._find_goals_file", return_value=path):
        result1 = parse_goals_file()
        result2 = parse_goals_file()

    assert result1 is result2


def test_mtime_cache_invalidates_on_change(tmp_path):
    """When the file changes (new mtime), the cache is invalidated."""
    import os

    goals_file = tmp_path / "goals.md"
    goals_file.write_text(WELL_FORMED_GOALS)
    path = str(goals_file)

    with patch("api.services.goals_parser._find_goals_file", return_value=path):
        result1 = parse_goals_file()
        assert len(result1["goals"]) == 2

        # Write new content with different goals
        new_content = """\
# Goals

## Mission

New mission.

## Goal 1: Only One

Single goal now.

- One example
"""
        goals_file.write_text(new_content)
        # Ensure mtime changes (filesystem granularity can be coarse)
        new_mtime = os.path.getmtime(path) + 1
        os.utime(path, (new_mtime, new_mtime))

        result2 = parse_goals_file()

    assert result2 is not result1
    assert result2["mission"] == "New mission."
    assert len(result2["goals"]) == 1
    assert result2["goals"][0]["title"] == "Only One"

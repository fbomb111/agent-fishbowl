"""Goals file parser — reads and caches config/goals.md.

Parses the markdown into structured data: mission, goals, and constraints.
Results are cached based on file mtime so the file is only re-read when changed.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

# File-based cache for goals.md (keyed by mtime)
_goals_file_cache: dict[str, Any] | None = None
_goals_file_mtime: float = 0.0


class GoalsFileData(TypedDict):
    """Parsed structure of goals.md."""

    mission: str
    goals: list[dict[str, Any]]
    constraints: list[str]


@dataclass
class Goal:
    number: int
    title: str
    summary: str
    examples: list[str] = field(default_factory=list)


def _find_goals_file() -> str:
    """Find config/goals.md relative to the project root."""
    # Walk up from this file to find the project root (contains config/)
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        candidate = os.path.join(current, "config", "goals.md")
        if os.path.exists(candidate):
            return candidate
        current = os.path.dirname(current)
    return os.path.join("config", "goals.md")


def parse_goals_file() -> GoalsFileData:
    """Parse config/goals.md into structured data.

    Results are cached based on file modification time so the file is only
    read and parsed once unless it changes on disk.
    """
    global _goals_file_cache, _goals_file_mtime

    path = _find_goals_file()

    # Check mtime to avoid re-reading an unchanged file
    try:
        current_mtime = os.path.getmtime(path)
    except OSError:
        logger.warning("goals.md not found at %s", path)
        return {"mission": "", "goals": [], "constraints": []}

    if _goals_file_cache is not None and current_mtime == _goals_file_mtime:
        return _goals_file_cache

    try:
        with open(path) as f:
            content = f.read()
    except FileNotFoundError:
        logger.warning("goals.md not readable at %s", path)
        return {"mission": "", "goals": [], "constraints": []}

    # Extract mission (text between ## Mission and next ##)
    mission_match = re.search(r"## Mission\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    mission = mission_match.group(1).strip() if mission_match else ""

    # Extract goals (## Goal N: Title)
    goals: list[dict[str, Any]] = []
    goal_pattern = re.compile(r"## Goal (\d+): (.+?)\s*\n(.*?)(?=\n## |\Z)", re.DOTALL)
    for match in goal_pattern.finditer(content):
        number = int(match.group(1))
        title = match.group(2).strip()
        body = match.group(3).strip()

        # Split body into summary (paragraphs before bullet list) and examples (bullets)
        lines = body.split("\n")
        summary_lines: list[str] = []
        examples: list[str] = []
        in_examples = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- "):
                in_examples = True
                examples.append(stripped[2:])
            elif in_examples and stripped == "":
                continue
            elif not in_examples and stripped:
                # Skip lines that are just headers for examples
                if (
                    "examples of" in stripped.lower()
                    or "example categories" in stripped.lower()
                ):
                    continue
                if "pm" in stripped.lower() and (
                    "decides" in stripped.lower()
                    or "chooses" in stripped.lower()
                    or "should" in stripped.lower()
                ):
                    continue
                if "metrics will sometimes" in stripped.lower():
                    continue
                summary_lines.append(stripped)

        goals.append(
            {
                "number": number,
                "title": title,
                "summary": " ".join(summary_lines),
                "examples": examples,
            }
        )

    # Extract constraints
    constraints: list[str] = []
    constraints_match = re.search(
        r"## Constraints\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if constraints_match:
        for line in constraints_match.group(1).strip().split("\n"):
            stripped = line.strip()
            if stripped.startswith("- **"):
                # Extract bold text as the constraint name
                bold_match = re.match(r"- \*\*(.+?)\*\*", stripped)
                if bold_match:
                    constraints.append(bold_match.group(1).rstrip("."))

    result: GoalsFileData = {
        "mission": mission,
        "goals": goals,
        "constraints": constraints,
    }
    _goals_file_cache = result
    _goals_file_mtime = current_mtime
    return result

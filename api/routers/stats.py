"""Agent team statistics endpoint."""

from fastapi import APIRouter

from api.services.stats import get_team_stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def team_stats():
    """Get aggregate agent team statistics for the last 7 days."""
    stats = await get_team_stats()
    return stats

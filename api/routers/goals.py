"""Goals dashboard endpoint — serves goals, roadmap, and agent metrics."""

from fastapi import APIRouter

from api.services.goals import get_goals_data

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("")
async def list_goals():
    """Get goals, roadmap items, and agent metrics for the dashboard."""
    return await get_goals_data()

"""Board health endpoint — project board metrics."""

from fastapi import APIRouter

from api.services.board_health import get_board_health

router = APIRouter(prefix="/board-health", tags=["board-health"])


@router.get("")
async def board_health():
    """Get project board health metrics (work distribution, drafts)."""
    return await get_board_health()

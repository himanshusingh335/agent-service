from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/chat", tags=["logs"])


@router.get("/{session_id}/logs")
async def get_session_logs(session_id: str):
    raise HTTPException(status_code=501, detail="Not implemented yet")

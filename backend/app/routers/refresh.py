"""Sprint 10: manual trigger endpoints for price and score refresh."""
from fastapi import APIRouter, BackgroundTasks, Depends

from app.security import require_api_key

router = APIRouter(prefix="/api/v1/refresh", tags=["refresh"])


@router.post("/vix", dependencies=[Depends(require_api_key)])
def manual_refresh_vix(background_tasks: BackgroundTasks):
    """Trigger an immediate regime/VIX refresh in the background."""
    from app.scheduler import job_refresh_regime
    background_tasks.add_task(job_refresh_regime)
    return {
        "status": "queued",
        "job": "refresh_vix",
        "message": "Regime/VIX refresh started in background",
    }


@router.post("/scores", dependencies=[Depends(require_api_key)])
def manual_refresh_scores(background_tasks: BackgroundTasks):
    """Trigger an immediate score refresh for all active stocks in the background."""
    from app.scheduler import job_refresh_scores
    background_tasks.add_task(job_refresh_scores)
    return {
        "status":  "queued",
        "job":     "refresh_scores",
        "message": "Score refresh started in background",
    }

"""Sprint 10: manual trigger endpoints for price and score refresh."""
from fastapi import APIRouter, BackgroundTasks, Depends

from app.security import require_api_key

router = APIRouter(prefix="/api/v1/refresh", tags=["refresh"])


@router.post("/prices", dependencies=[Depends(require_api_key)])
def manual_refresh_prices(background_tasks: BackgroundTasks):
    """Trigger an immediate price refresh in the background.

    Returns instantly; the refresh runs asynchronously.
    Check GET /api/v1/config/refresh-schedule → last_price_update for completion.
    """
    from app.scheduler import job_refresh_prices
    background_tasks.add_task(job_refresh_prices)
    return {
        "status":  "queued",
        "job":     "refresh_prices",
        "message": "Price refresh started in background",
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

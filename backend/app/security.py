"""
API key authentication for admin endpoints.

Usage:
    from app.security import require_api_key
    from fastapi import Depends

    @router.post("/admin/run-backtest")
    def run_backtest(db=..., _: None = Depends(require_api_key)):
        ...

Configuration:
    Set API_KEY env var in .env or docker-compose.yml:
        API_KEY=your_secret_key_here
    Clients must then send the header:
        X-API-Key: your_secret_key_here

    If API_KEY is not set (default), all requests pass through (dev mode).
"""
import os

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_API_KEY = os.environ.get("API_KEY", "")


def require_api_key(api_key: str | None = Security(_API_KEY_HEADER)) -> None:
    """FastAPI dependency — validates X-API-Key header.

    No-op when API_KEY env var is not configured (development mode).
    """
    if not _API_KEY:
        return  # dev mode: no key required
    if api_key != _API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )

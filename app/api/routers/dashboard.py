from datetime import datetime

from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.api.schemas import DashboardSummary
from app.products.catalog_service import dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _since_today() -> str:
    # created_at/sent_at/recorded_at são gravados via SQLite datetime('now') em UTC
    return datetime.utcnow().strftime("%Y-%m-%d 00:00:00")


@router.get("/summary", response_model=DashboardSummary)
def get_summary(conn=Depends(get_db)):
    return dashboard_summary(conn, since=_since_today())

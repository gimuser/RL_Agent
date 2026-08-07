from fastapi import APIRouter
from app.schemas import DashboardSummary
from app.database.repository import get_dashboard_summary_from_db

# إزالة prefix="/dashboard"
router = APIRouter(tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary():
    """Récupère le résumé complet des métriques pour le Dashboard."""
    return get_dashboard_summary_from_db()
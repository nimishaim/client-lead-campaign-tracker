from uuid import UUID
from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User
from app.schemas.import_log import DashboardMetrics, TimeSeriesPoint, PipelineDistribution
from app.services.auth_service import get_current_active_user, get_user_clients
from app.services.dashboard_service import get_dashboard_metrics, get_time_series, get_pipeline_distribution

router = APIRouter()

@router.get('/metrics', response_model=DashboardMetrics)
def dashboard_metrics(
    client_id: Optional[UUID] = None,
    campaign_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    client_ids = get_user_clients(db, current_user)
    if client_id and client_id in client_ids:
        client_ids = [client_id]
    elif client_id:
        client_ids = [client_id]  # Admin can see all
    return get_dashboard_metrics(db, client_ids, campaign_id=campaign_id, start_date=start_date, end_date=end_date)

@router.get('/time-series', response_model=List[TimeSeriesPoint])
def time_series(
    days: int = Query(30, ge=7, le=365),
    client_id: Optional[UUID] = None,
    campaign_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    client_ids = get_user_clients(db, current_user)
    if client_id and client_id in client_ids:
        client_ids = [client_id]
    elif client_id:
        client_ids = [client_id]
    return get_time_series(db, client_ids, days=days, campaign_id=campaign_id)

@router.get('/pipeline', response_model=List[PipelineDistribution])
def pipeline_distribution(
    client_id: Optional[UUID] = None,
    campaign_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    client_ids = get_user_clients(db, current_user)
    if client_id and client_id in client_ids:
        client_ids = [client_id]
    elif client_id:
        client_ids = [client_id]
    return get_pipeline_distribution(db, client_ids, campaign_id=campaign_id)

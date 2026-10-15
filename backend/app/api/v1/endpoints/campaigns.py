from uuid import UUID
from typing import Optional, List
from math import ceil
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User, UserRole
from app.models.campaign import Campaign, CampaignPlatform, CampaignStatus
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    PaginatedCampaignsResponse,
    CampaignDailyMetricResponse,
)
from app.services.auth_service import get_current_active_user, get_user_clients, require_admin
from app.services.campaign_service import (
    get_campaigns,
    get_campaign_by_id,
    create_campaign,
    update_campaign,
    delete_campaign,
    calculate_metrics,
    get_campaign_daily_metrics,
)

router = APIRouter()


@router.get('/', response_model=PaginatedCampaignsResponse)
def list_campaigns(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[CampaignStatus] = None,
    platform: Optional[CampaignPlatform] = None,
    client_id: Optional[UUID] = None,
    search: Optional[str] = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    client_ids = get_user_clients(db, current_user)
    if client_id:
        if client_id not in client_ids and current_user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail='Access denied')
        client_ids = [client_id]

    campaigns, total = get_campaigns(
        db,
        client_ids,
        page=page,
        per_page=per_page,
        status=status,
        platform=platform,
        search=search,
        include_archived=include_archived,
    )
    pages = ceil(total / per_page) if per_page > 0 else 0

    items = []
    for c in campaigns:
        metrics = calculate_metrics(c)
        resp = CampaignResponse.model_validate(c)
        resp.cpl = metrics.get('cpl')
        resp.budget_utilisation = metrics.get('budget_utilisation')
        items.append(resp)

    return PaginatedCampaignsResponse(items=items, total=total, page=page, per_page=per_page, pages=pages)


@router.post('/', response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_new_campaign(
    campaign_in: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_campaign(db, campaign_in)


@router.get('/{campaign_id}', response_model=CampaignResponse)
def get_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    client_ids = get_user_clients(db, current_user)
    campaign = get_campaign_by_id(db, campaign_id, client_ids)
    if not campaign:
        raise HTTPException(status_code=404, detail='Campaign not found')
    metrics = calculate_metrics(campaign)
    resp = CampaignResponse.model_validate(campaign)
    resp.cpl = metrics.get('cpl')
    resp.budget_utilisation = metrics.get('budget_utilisation')
    return resp


@router.patch('/{campaign_id}', response_model=CampaignResponse)
def update_existing_campaign(
    campaign_id: UUID,
    campaign_update: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    client_ids = get_user_clients(db, current_user)
    campaign = get_campaign_by_id(db, campaign_id, client_ids)
    if not campaign:
        raise HTTPException(status_code=404, detail='Campaign not found')
    updated = update_campaign(db, campaign, campaign_update)
    metrics = calculate_metrics(updated)
    resp = CampaignResponse.model_validate(updated)
    resp.cpl = metrics.get('cpl')
    resp.budget_utilisation = metrics.get('budget_utilisation')
    return resp


@router.delete('/{campaign_id}', status_code=status.HTTP_204_NO_CONTENT)
def archive_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    client_ids = get_user_clients(db, current_user)
    campaign = get_campaign_by_id(db, campaign_id, client_ids)
    if not campaign:
        raise HTTPException(status_code=404, detail='Campaign not found')
    delete_campaign(db, campaign)


@router.get('/{campaign_id}/metrics', response_model=List[CampaignDailyMetricResponse])
def get_metrics(
    campaign_id: UUID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    client_ids = get_user_clients(db, current_user)
    campaign = get_campaign_by_id(db, campaign_id, client_ids)
    if not campaign:
        raise HTTPException(status_code=404, detail='Campaign not found')
    return get_campaign_daily_metrics(db, campaign_id, start_date, end_date)

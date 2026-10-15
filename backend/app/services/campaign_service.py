from uuid import UUID
from datetime import date
from decimal import Decimal
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from app.models.campaign import Campaign, CampaignDailyMetric, CampaignPlatform, CampaignStatus
from app.schemas.campaign import CampaignCreate, CampaignUpdate

def get_campaigns(
    db: Session,
    client_ids: List[UUID],
    page: int = 1,
    per_page: int = 25,
    status: Optional[CampaignStatus] = None,
    platform: Optional[CampaignPlatform] = None,
    search: Optional[str] = None,
    include_archived: bool = False,
) -> Tuple[List[Campaign], int]:
    query = db.query(Campaign).filter(Campaign.client_id.in_(client_ids))
    if not include_archived:
        query = query.filter(Campaign.is_archived == False)
    if status:
        query = query.filter(Campaign.status == status)
    if platform:
        query = query.filter(Campaign.platform == platform)
    if search:
        query = query.filter(Campaign.name.ilike(f'%{search}%'))
    total = query.count()
    campaigns = query.order_by(desc(Campaign.created_at)).offset((page-1)*per_page).limit(per_page).all()
    return campaigns, total

def get_campaign_by_id(db: Session, campaign_id: UUID, client_ids: List[UUID]) -> Optional[Campaign]:
    return db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.client_id.in_(client_ids)
    ).first()

def create_campaign(db: Session, campaign_in: CampaignCreate) -> Campaign:
    campaign = Campaign(**campaign_in.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign

def update_campaign(db: Session, campaign: Campaign, campaign_update: CampaignUpdate) -> Campaign:
    update_data = campaign_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return campaign

def delete_campaign(db: Session, campaign: Campaign) -> None:
    campaign.is_archived = True
    db.commit()

def calculate_metrics(campaign: Campaign) -> dict:
    """Calculate CPL and budget utilisation. Returns None for unavailable values."""
    cpl = None
    budget_utilisation = None

    attributed = campaign.attributed_leads or 0
    spend = float(campaign.total_spend or 0)

    if attributed > 0 and spend > 0:
        cpl = round(Decimal(str(spend)) / Decimal(str(attributed)), 2)

    budget = float(campaign.budget or 0)
    if budget > 0 and spend >= 0:
        budget_utilisation = round(Decimal(str(spend)) / Decimal(str(budget)) * 100, 2)

    return {'cpl': cpl, 'budget_utilisation': budget_utilisation}

def get_campaign_daily_metrics(
    db: Session,
    campaign_id: UUID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[CampaignDailyMetric]:
    query = db.query(CampaignDailyMetric).filter(
        CampaignDailyMetric.campaign_id == campaign_id
    )
    if start_date:
        query = query.filter(CampaignDailyMetric.date >= start_date)
    if end_date:
        query = query.filter(CampaignDailyMetric.date <= end_date)
    return query.order_by(CampaignDailyMetric.date).all()

def upsert_daily_metric(
    db: Session,
    campaign_id: UUID,
    metric_date: date,
    spend: Decimal,
    impressions: int,
    clicks: int,
    leads: int,
) -> CampaignDailyMetric:
    existing = db.query(CampaignDailyMetric).filter(
        CampaignDailyMetric.campaign_id == campaign_id,
        CampaignDailyMetric.date == metric_date
    ).first()

    if existing:
        existing.spend = spend
        existing.impressions = impressions
        existing.clicks = clicks
        existing.leads = leads
        db.commit()
        db.refresh(existing)
        return existing
    else:
        metric = CampaignDailyMetric(
            campaign_id=campaign_id,
            date=metric_date,
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            leads=leads,
        )
        db.add(metric)
        db.commit()
        db.refresh(metric)
        return metric

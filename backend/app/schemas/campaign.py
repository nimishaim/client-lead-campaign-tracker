from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel
from typing import Optional, List
from app.models.campaign import CampaignPlatform, CampaignStatus

class CampaignBase(BaseModel):
    name: str
    platform: CampaignPlatform = CampaignPlatform.meta_ads
    objective: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[Decimal] = None

class CampaignCreate(CampaignBase):
    client_id: UUID
    external_campaign_id: Optional[str] = None

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    platform: Optional[CampaignPlatform] = None
    objective: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[Decimal] = None
    status: Optional[CampaignStatus] = None
    is_archived: Optional[bool] = None

class CampaignDailyMetricResponse(BaseModel):
    id: UUID
    date: date
    spend: Decimal
    impressions: int
    clicks: int
    leads: int
    
    model_config = {'from_attributes': True}

class CampaignResponse(CampaignBase):
    id: UUID
    client_id: UUID
    external_campaign_id: Optional[str] = None
    status: CampaignStatus
    total_spend: Decimal
    impressions: int
    clicks: int
    attributed_leads: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    cpl: Optional[Decimal] = None
    budget_utilisation: Optional[Decimal] = None
    
    model_config = {'from_attributes': True}

class PaginatedCampaignsResponse(BaseModel):
    items: List[CampaignResponse]
    total: int
    page: int
    per_page: int
    pages: int

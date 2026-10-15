from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from app.models.lead import LeadStatus, LeadSource

class LeadBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    source: LeadSource = LeadSource.other
    notes: Optional[str] = None

class LeadCreate(LeadBase):
    client_id: UUID
    campaign_id: Optional[UUID] = None
    external_id: Optional[str] = None
    status: LeadStatus = LeadStatus.new

class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    source: Optional[LeadSource] = None
    notes: Optional[str] = None
    campaign_id: Optional[UUID] = None
    is_archived: Optional[bool] = None

class LeadStatusUpdate(BaseModel):
    status: LeadStatus
    notes: Optional[str] = None

class LeadStatusHistoryResponse(BaseModel):
    id: UUID
    from_status: Optional[LeadStatus] = None
    to_status: LeadStatus
    changed_at: datetime
    notes: Optional[str] = None
    
    model_config = {'from_attributes': True}

class LeadResponse(LeadBase):
    id: UUID
    client_id: UUID
    campaign_id: Optional[UUID] = None
    status: LeadStatus
    external_id: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    contacted_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None
    status_history: List[LeadStatusHistoryResponse] = []
    
    model_config = {'from_attributes': True}

class PaginatedLeadsResponse(BaseModel):
    items: List[LeadResponse]
    total: int
    page: int
    per_page: int
    pages: int

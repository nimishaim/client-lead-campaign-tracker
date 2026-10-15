from uuid import UUID
from typing import Optional, List
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User, UserRole
from app.models.client import ClientMembership
from app.models.lead import LeadStatus, LeadSource
from app.schemas.lead import LeadCreate, LeadUpdate, LeadStatusUpdate, LeadResponse, PaginatedLeadsResponse
from app.services.auth_service import get_current_active_user, get_user_clients
from app.services.lead_service import (
    get_leads,
    get_lead_by_id,
    create_lead,
    update_lead,
    update_lead_status,
    delete_lead,
    check_duplicate,
)

router = APIRouter()


@router.get('/', response_model=PaginatedLeadsResponse)
def list_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[LeadStatus] = None,
    source: Optional[LeadSource] = None,
    campaign_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None,
    search: Optional[str] = None,
    sort_by: str = Query('created_at'),
    sort_order: str = Query('desc'),
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    client_ids = get_user_clients(db, current_user)
    if client_id:
        if client_id not in client_ids and current_user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail='Access denied')
        client_ids = [client_id]

    leads, total = get_leads(
        db,
        client_ids,
        page=page,
        per_page=per_page,
        status=status,
        source=source,
        campaign_id=campaign_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        include_archived=include_archived,
    )
    pages = ceil(total / per_page) if per_page > 0 else 0
    return PaginatedLeadsResponse(items=leads, total=total, page=page, per_page=per_page, pages=pages)


@router.post('/', response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
def create_new_lead(
    lead_in: LeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    client_ids = get_user_clients(db, current_user)
    if lead_in.client_id not in client_ids:
        raise HTTPException(status_code=403, detail='Access denied to this client')

    # Check for duplicates by email or external_id
    dup = check_duplicate(db, lead_in.client_id, email=lead_in.email, external_id=lead_in.external_id)
    if dup:
        raise HTTPException(status_code=409, detail=f'Duplicate lead found (ID: {dup.id})')

    return create_lead(db, lead_in, current_user)


@router.get('/{lead_id}', response_model=LeadResponse)
def get_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    client_ids = get_user_clients(db, current_user)
    lead = get_lead_by_id(db, lead_id, client_ids)
    if not lead:
        raise HTTPException(status_code=404, detail='Lead not found')
    return lead


@router.patch('/{lead_id}', response_model=LeadResponse)
def update_existing_lead(
    lead_id: UUID,
    lead_update: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    client_ids = get_user_clients(db, current_user)
    lead = get_lead_by_id(db, lead_id, client_ids)
    if not lead:
        raise HTTPException(status_code=404, detail='Lead not found')
    return update_lead(db, lead, lead_update)


@router.patch('/{lead_id}/status', response_model=LeadResponse)
def update_status(
    lead_id: UUID,
    status_update: LeadStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    client_ids = get_user_clients(db, current_user)
    lead = get_lead_by_id(db, lead_id, client_ids)
    if not lead:
        raise HTTPException(status_code=404, detail='Lead not found')
    # Enforce can_update_leads permission for client-role users
    if current_user.role == UserRole.client:
        membership = (
            db.query(ClientMembership)
            .filter(
                ClientMembership.user_id == current_user.id,
                ClientMembership.client_id == lead.client_id,
            )
            .first()
        )
        if not membership or not membership.can_update_leads:
            raise HTTPException(status_code=403, detail='Not authorized to update lead status')
    return update_lead_status(db, lead, status_update, current_user)


@router.delete('/{lead_id}', status_code=status.HTTP_204_NO_CONTENT)
def archive_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail='Only admins can delete leads')
    client_ids = get_user_clients(db, current_user)
    lead = get_lead_by_id(db, lead_id, client_ids)
    if not lead:
        raise HTTPException(status_code=404, detail='Lead not found')
    delete_lead(db, lead)

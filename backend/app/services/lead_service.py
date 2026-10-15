"""
Lead management service layer.

All database interactions for leads live here so that routers stay thin and
business logic is easily unit-testable.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.lead import Lead, LeadSource, LeadStatus, LeadStatusHistory
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadStatusUpdate, LeadUpdate


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def get_leads(
    db: Session,
    client_ids: List[UUID],
    page: int = 1,
    per_page: int = 25,
    status: Optional[LeadStatus] = None,
    source: Optional[LeadSource] = None,
    campaign_id: Optional[UUID] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    include_archived: bool = False,
) -> Tuple[List[Lead], int]:
    """
    Return a paginated list of leads visible to the caller, plus the total
    count that matches the applied filters (for frontend pagination).

    :param client_ids: Restricts results to these client scopes.
    :param page: 1-indexed page number.
    :param per_page: Number of records per page.
    :param status: Optional status filter.
    :param source: Optional lead-source filter.
    :param campaign_id: Optional campaign scope filter.
    :param search: Case-insensitive substring match on name, email, or phone.
    :param sort_by: Column name to sort on (defaults to ``created_at``).
    :param sort_order: ``'asc'`` or ``'desc'`` (default).
    :param include_archived: When ``False`` (default) archived leads are hidden.
    :returns: ``(leads, total)`` tuple.
    """
    query = (
        db.query(Lead)
        .options(joinedload(Lead.status_history))
        .filter(Lead.client_id.in_(client_ids))
    )

    if not include_archived:
        query = query.filter(Lead.is_archived == False)  # noqa: E712
    if status:
        query = query.filter(Lead.status == status)
    if source:
        query = query.filter(Lead.source == source)
    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)
    if search:
        query = query.filter(
            or_(
                Lead.name.ilike(f"%{search}%"),
                Lead.email.ilike(f"%{search}%"),
                Lead.phone.ilike(f"%{search}%"),
            )
        )

    total = query.count()

    sort_column = getattr(Lead, sort_by, Lead.created_at)
    if sort_order == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))

    offset = (page - 1) * per_page
    leads = query.offset(offset).limit(per_page).all()
    return leads, total


def get_lead_by_id(
    db: Session,
    lead_id: UUID,
    client_ids: List[UUID],
) -> Optional[Lead]:
    """
    Fetch a single lead by its primary key, scoped to *client_ids*.

    Returns ``None`` when the lead does not exist or is outside the caller's
    client scope.
    """
    return (
        db.query(Lead)
        .options(joinedload(Lead.status_history))
        .filter(
            Lead.id == lead_id,
            Lead.client_id.in_(client_ids),
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def check_duplicate(
    db: Session,
    client_id: UUID,
    email: Optional[str] = None,
    external_id: Optional[str] = None,
    lead_id: Optional[UUID] = None,
) -> Optional[Lead]:
    """
    Check for duplicate leads within a client scope.

    Deduplication strategy:
    1. Match by ``external_id`` first (most authoritative).
    2. Fall back to matching by ``email`` within the same client.

    Pass *lead_id* to exclude the lead being edited from its own duplicate
    check (useful during updates).

    Returns the first matching duplicate or ``None``.
    """
    if external_id:
        q = db.query(Lead).filter(
            Lead.client_id == client_id,
            Lead.external_id == external_id,
            Lead.is_archived == False,  # noqa: E712
        )
        if lead_id:
            q = q.filter(Lead.id != lead_id)
        existing = q.first()
        if existing:
            return existing

    if email:
        q = db.query(Lead).filter(
            Lead.client_id == client_id,
            Lead.email == email,
            Lead.is_archived == False,  # noqa: E712
        )
        if lead_id:
            q = q.filter(Lead.id != lead_id)
        existing = q.first()
        if existing:
            return existing

    return None


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def create_lead(db: Session, lead_in: LeadCreate, created_by: User) -> Lead:
    """
    Persist a new lead and record its initial status in the history table.

    The caller is responsible for duplicate checking before calling this
    function.
    """
    lead = Lead(**lead_in.model_dump())
    db.add(lead)
    db.flush()  # populate lead.id before creating history row

    history = LeadStatusHistory(
        lead_id=lead.id,
        from_status=None,
        to_status=lead.status,
        changed_by_id=created_by.id,
    )
    db.add(history)
    db.commit()
    db.refresh(lead)
    return lead


def update_lead(db: Session, lead: Lead, lead_update: LeadUpdate) -> Lead:
    """
    Apply a partial update to *lead* using only the fields present in
    *lead_update* (``exclude_unset=True``).
    """
    update_data = lead_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


def update_lead_status(
    db: Session,
    lead: Lead,
    status_update: LeadStatusUpdate,
    changed_by: User,
) -> Lead:
    """
    Transition *lead* to a new status, recording the change in history.

    Side effects:
    - Sets ``contacted_at`` on the first transition to ``contacted``.
    - Sets ``converted_at`` on the first transition to ``converted``.
    """
    old_status = lead.status
    lead.status = status_update.status
    lead.updated_at = datetime.utcnow()

    if status_update.status == LeadStatus.contacted and not lead.contacted_at:
        lead.contacted_at = datetime.utcnow()
    elif status_update.status == LeadStatus.converted and not lead.converted_at:
        lead.converted_at = datetime.utcnow()

    history = LeadStatusHistory(
        lead_id=lead.id,
        from_status=old_status,
        to_status=status_update.status,
        changed_by_id=changed_by.id,
        notes=status_update.notes,
    )
    db.add(history)
    db.commit()
    db.refresh(lead)
    return lead


def delete_lead(db: Session, lead: Lead) -> None:
    """
    Soft-delete *lead* by setting its ``is_archived`` flag.

    The record is retained in the database for audit purposes and can be
    recovered by un-archiving if needed.
    """
    lead.is_archived = True
    db.commit()

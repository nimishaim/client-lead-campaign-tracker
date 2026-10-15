import csv
import io
from uuid import UUID
from typing import Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User
from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.campaign import Campaign
from app.services.auth_service import get_current_active_user, get_user_clients
from app.services.dashboard_service import get_dashboard_metrics

router = APIRouter()


@router.get('/leads/export')
def export_leads(
    client_id: Optional[UUID] = None,
    campaign_id: Optional[UUID] = None,
    status: Optional[LeadStatus] = None,
    source: Optional[LeadSource] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    client_ids = get_user_clients(db, current_user)
    if client_id:
        client_ids = [client_id]

    query = db.query(Lead).filter(
        Lead.client_id.in_(client_ids),
        Lead.is_archived == False
    )
    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)
    if status:
        query = query.filter(Lead.status == status)
    if source:
        query = query.filter(Lead.source == source)
    if start_date:
        query = query.filter(Lead.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(Lead.created_at <= datetime.combine(end_date, datetime.max.time()))

    leads = query.order_by(Lead.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Name', 'Email', 'Phone', 'Source', 'Status',
        'Campaign ID', 'Created At', 'Converted At', 'Notes'
    ])
    for lead in leads:
        writer.writerow([
            str(lead.id),
            lead.name,
            lead.email or '',
            lead.phone or '',
            lead.source.value,
            lead.status.value,
            str(lead.campaign_id) if lead.campaign_id else '',
            lead.created_at.isoformat() if lead.created_at else '',
            lead.converted_at.isoformat() if lead.converted_at else '',
            lead.notes or ''
        ])

    output.seek(0)
    filename = f'leads_export_{date.today().isoformat()}.csv'
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@router.get('/campaigns/export')
def export_campaigns(
    client_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    client_ids = get_user_clients(db, current_user)
    if client_id:
        client_ids = [client_id]

    campaigns = db.query(Campaign).filter(
        Campaign.client_id.in_(client_ids),
        Campaign.is_archived == False
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Name', 'Platform', 'Status', 'Budget', 'Total Spend',
        'Impressions', 'Clicks', 'Attributed Leads', 'CPL', 'Budget Utilisation %'
    ])
    for c in campaigns:
        cpl = None
        budget_util = None
        if c.attributed_leads and c.attributed_leads > 0 and c.total_spend:
            cpl = round(float(c.total_spend) / c.attributed_leads, 2)
        if c.budget and float(c.budget) > 0 and c.total_spend:
            budget_util = round(float(c.total_spend) / float(c.budget) * 100, 1)
        writer.writerow([
            str(c.id),
            c.name,
            c.platform.value,
            c.status.value,
            str(c.budget or ''),
            str(c.total_spend or 0),
            c.impressions or 0,
            c.clicks or 0,
            c.attributed_leads or 0,
            str(cpl) if cpl is not None else '',
            str(budget_util) if budget_util is not None else ''
        ])

    output.seek(0)
    filename = f'campaigns_export_{date.today().isoformat()}.csv'
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

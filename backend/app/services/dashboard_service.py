"""
Dashboard aggregation service layer.

Computes summary KPIs, time-series data, and pipeline distribution data
for the analytics dashboard.  All queries are scoped to the caller's
accessible client IDs to enforce data isolation.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.campaign import Campaign, CampaignDailyMetric
from app.models.lead import Lead, LeadStatus
from app.schemas.import_log import DashboardMetrics, PipelineDistribution, TimeSeriesPoint


# ---------------------------------------------------------------------------
# Top-level metrics
# ---------------------------------------------------------------------------


def get_dashboard_metrics(
    db: Session,
    client_ids: List[UUID],
    campaign_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> DashboardMetrics:
    """
    Compute the high-level KPIs shown on the dashboard overview card.

    Scopes data to *client_ids* and optionally narrows by *campaign_id* and
    a created-at date range.

    :returns: A :class:`DashboardMetrics` Pydantic model ready for the API
        response.
    """
    # ------------------------------------------------------------------
    # Lead counts
    # ------------------------------------------------------------------
    lead_q = db.query(Lead).filter(
        Lead.client_id.in_(client_ids),
        Lead.is_archived == False,  # noqa: E712
    )
    if campaign_id:
        lead_q = lead_q.filter(Lead.campaign_id == campaign_id)
    if start_date:
        lead_q = lead_q.filter(
            Lead.created_at >= datetime.combine(start_date, datetime.min.time())
        )
    if end_date:
        lead_q = lead_q.filter(
            Lead.created_at <= datetime.combine(end_date, datetime.max.time())
        )

    total_leads = lead_q.count()
    new_leads = lead_q.filter(Lead.status == LeadStatus.new).count()
    contacted_leads = lead_q.filter(Lead.status == LeadStatus.contacted).count()
    converted_leads = lead_q.filter(Lead.status == LeadStatus.converted).count()
    lost_leads = lead_q.filter(Lead.status == LeadStatus.lost).count()

    # Conversion rate: converted / (total – new – lost) – excludes leads
    # that haven't entered the funnel yet or have already been lost.
    eligible = total_leads - new_leads - lost_leads
    conversion_rate: Optional[float] = None
    if eligible > 0:
        conversion_rate = round((converted_leads / eligible) * 100, 2)

    # ------------------------------------------------------------------
    # Campaign-level aggregates
    # ------------------------------------------------------------------
    camp_q = db.query(Campaign).filter(
        Campaign.client_id.in_(client_ids),
        Campaign.is_archived == False,  # noqa: E712
    )
    if campaign_id:
        camp_q = camp_q.filter(Campaign.id == campaign_id)

    campaigns = camp_q.all()
    total_campaigns = len(campaigns)
    active_campaigns = sum(1 for c in campaigns if c.status.value == "active")

    total_spend = float(sum(c.total_spend or 0 for c in campaigns))
    total_attributed = sum(c.attributed_leads or 0 for c in campaigns)

    average_cpl: Optional[float] = None
    if total_attributed > 0 and total_spend > 0:
        average_cpl = round(total_spend / total_attributed, 2)

    total_budget = sum(float(c.budget or 0) for c in campaigns if c.budget)
    budget_utilisation: Optional[float] = None
    if total_budget > 0:
        budget_utilisation = round((total_spend / total_budget) * 100, 2)

    return DashboardMetrics(
        total_leads=total_leads,
        new_leads=new_leads,
        contacted_leads=contacted_leads,
        converted_leads=converted_leads,
        lost_leads=lost_leads,
        conversion_rate=conversion_rate,
        total_spend=total_spend,
        average_cpl=average_cpl,
        budget_utilisation=budget_utilisation,
        total_campaigns=total_campaigns,
        active_campaigns=active_campaigns,
    )


# ---------------------------------------------------------------------------
# Time-series data
# ---------------------------------------------------------------------------


def get_time_series(
    db: Session,
    client_ids: List[UUID],
    days: int = 30,
    campaign_id: Optional[UUID] = None,
) -> List[TimeSeriesPoint]:
    """
    Build a continuous daily time-series for the last *days* calendar days.

    For each day the series records:
    - ``leads``    – number of new leads created that day.
    - ``converted``– number of leads converted that day (by ``converted_at``).
    - ``spend``    – total ad spend aggregated from campaign daily metrics.

    Days with no activity are still included with zero values so the frontend
    chart renders a complete, unbroken x-axis.
    """
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=days - 1)

    # Full date range for the x-axis (no gaps)
    all_dates = [start_dt + timedelta(days=i) for i in range(days)]

    # ------------------------------------------------------------------ leads
    lead_q = (
        db.query(
            func.date(Lead.created_at).label("day"),
            func.count(Lead.id).label("count"),
        )
        .filter(
            Lead.client_id.in_(client_ids),
            Lead.is_archived == False,  # noqa: E712
            func.date(Lead.created_at) >= start_dt,
            func.date(Lead.created_at) <= end_dt,
        )
    )
    if campaign_id:
        lead_q = lead_q.filter(Lead.campaign_id == campaign_id)
    lead_q = lead_q.group_by(func.date(Lead.created_at))
    lead_by_date = {str(row.day): row.count for row in lead_q.all()}

    # ------------------------------------------------------------ conversions
    conv_q = (
        db.query(
            func.date(Lead.converted_at).label("day"),
            func.count(Lead.id).label("count"),
        )
        .filter(
            Lead.client_id.in_(client_ids),
            Lead.is_archived == False,  # noqa: E712
            Lead.status == LeadStatus.converted,
            Lead.converted_at.isnot(None),
            func.date(Lead.converted_at) >= start_dt,
            func.date(Lead.converted_at) <= end_dt,
        )
    )
    if campaign_id:
        conv_q = conv_q.filter(Lead.campaign_id == campaign_id)
    conv_q = conv_q.group_by(func.date(Lead.converted_at))
    conv_by_date = {str(row.day): row.count for row in conv_q.all()}

    # --------------------------------------------------------------- ad spend
    camp_id_q = db.query(Campaign.id).filter(
        Campaign.client_id.in_(client_ids)
    )
    if campaign_id:
        camp_id_q = camp_id_q.filter(Campaign.id == campaign_id)
    camp_ids = [r.id for r in camp_id_q.all()]

    spend_by_date: dict = {}
    if camp_ids:
        spend_q = (
            db.query(
                CampaignDailyMetric.date,
                func.sum(CampaignDailyMetric.spend).label("total_spend"),
            )
            .filter(
                CampaignDailyMetric.campaign_id.in_(camp_ids),
                CampaignDailyMetric.date >= start_dt,
                CampaignDailyMetric.date <= end_dt,
            )
            .group_by(CampaignDailyMetric.date)
        )
        spend_by_date = {
            str(row.date): float(row.total_spend or 0) for row in spend_q.all()
        }

    # Assemble result, filling gaps with zeroes
    result: List[TimeSeriesPoint] = []
    for d in all_dates:
        ds = str(d)
        result.append(
            TimeSeriesPoint(
                date=ds,
                leads=lead_by_date.get(ds, 0),
                spend=spend_by_date.get(ds, 0.0),
                converted=conv_by_date.get(ds, 0),
            )
        )
    return result


# ---------------------------------------------------------------------------
# Pipeline distribution
# ---------------------------------------------------------------------------


def get_pipeline_distribution(
    db: Session,
    client_ids: List[UUID],
    campaign_id: Optional[UUID] = None,
) -> List[PipelineDistribution]:
    """
    Return the count and percentage share of leads at each pipeline status.

    Useful for rendering a funnel or donut chart on the dashboard.
    """
    query = (
        db.query(
            Lead.status,
            func.count(Lead.id).label("count"),
        )
        .filter(
            Lead.client_id.in_(client_ids),
            Lead.is_archived == False,  # noqa: E712
        )
    )
    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)

    rows = query.group_by(Lead.status).all()
    total = sum(r.count for r in rows)

    result: List[PipelineDistribution] = []
    for row in rows:
        pct = round((row.count / total * 100), 1) if total > 0 else 0.0
        result.append(
            PipelineDistribution(
                status=row.status.value,
                count=row.count,
                percentage=pct,
            )
        )
    return result

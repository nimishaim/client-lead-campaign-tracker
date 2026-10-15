import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class CampaignPlatform(str, enum.Enum):
    meta_ads = "meta_ads"
    google_ads = "google_ads"
    tiktok_ads = "tiktok_ads"
    linkedin_ads = "linkedin_ads"
    other = "other"


class CampaignStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    external_campaign_id = Column(String(255), nullable=True, index=True)
    platform = Column(SAEnum(CampaignPlatform), nullable=False, default=CampaignPlatform.meta_ads)
    status = Column(SAEnum(CampaignStatus), nullable=False, default=CampaignStatus.active)
    objective = Column(String(100), nullable=True)

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    budget = Column(Numeric(12, 2), nullable=True)
    total_spend = Column(Numeric(12, 2), default=0, nullable=False)
    impressions = Column(Integer, default=0, nullable=False)
    clicks = Column(Integer, default=0, nullable=False)
    attributed_leads = Column(Integer, default=0, nullable=False)

    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # relationships
    client = relationship("Client", back_populates="campaigns")
    leads = relationship("Lead", back_populates="campaign")
    daily_metrics = relationship(
        "CampaignDailyMetric",
        back_populates="campaign",
        order_by="CampaignDailyMetric.date",
    )
    import_logs = relationship("ImportLog", back_populates="campaign")

    __table_args__ = (Index("ix_campaigns_client_status", "client_id", "status"),)


class CampaignDailyMetric(Base):
    __tablename__ = "campaign_daily_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, index=True)

    spend = Column(Numeric(12, 2), default=0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    leads = Column(Integer, default=0)

    campaign = relationship("Campaign", back_populates="daily_metrics")

    __table_args__ = (Index("ix_campaign_daily_unique", "campaign_id", "date", unique=True),)

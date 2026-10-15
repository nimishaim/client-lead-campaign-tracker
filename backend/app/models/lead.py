import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    converted = "converted"
    lost = "lost"


class LeadSource(str, enum.Enum):
    meta_ads = "meta_ads"
    google_ads = "google_ads"
    organic = "organic"
    referral = "referral"
    email = "email"
    other = "other"


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)

    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    source = Column(SAEnum(LeadSource), nullable=False, default=LeadSource.other)
    status = Column(SAEnum(LeadStatus), nullable=False, default=LeadStatus.new, index=True)
    notes = Column(Text, nullable=True)

    # For dedup from Meta Ads etc.
    external_id = Column(String(255), nullable=True, index=True)
    is_archived = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    contacted_at = Column(DateTime, nullable=True)
    converted_at = Column(DateTime, nullable=True)

    import_id = Column(UUID(as_uuid=True), ForeignKey("imports.id", ondelete="SET NULL"), nullable=True)

    # relationships
    client = relationship("Client", back_populates="leads")
    campaign = relationship("Campaign", back_populates="leads")
    status_history = relationship(
        "LeadStatusHistory",
        back_populates="lead",
        order_by="LeadStatusHistory.changed_at",
    )
    import_log = relationship("ImportLog", back_populates="leads")

    __table_args__ = (
        Index("ix_leads_client_status", "client_id", "status"),
        Index("ix_leads_client_campaign", "client_id", "campaign_id"),
        Index("ix_leads_external_id_client", "external_id", "client_id"),
    )


class LeadStatusHistory(Base):
    __tablename__ = "lead_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    from_status = Column(SAEnum(LeadStatus), nullable=True)
    to_status = Column(SAEnum(LeadStatus), nullable=False)
    changed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)

    lead = relationship("Lead", back_populates="status_history")

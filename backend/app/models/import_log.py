import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class ImportStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    partial = "partial"


class ImportType(str, enum.Enum):
    leads = "leads"
    campaign_metrics = "campaign_metrics"


class ImportLog(Base):
    __tablename__ = "imports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    initiated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)

    import_type = Column(SAEnum(ImportType), nullable=False)
    status = Column(SAEnum(ImportStatus), nullable=False, default=ImportStatus.pending)

    filename = Column(String(255), nullable=False)
    # SHA-256 hash for dedup detection
    file_hash = Column(String(64), nullable=True, index=True)

    total_rows = Column(Integer, default=0)
    successful_rows = Column(Integer, default=0)
    failed_rows = Column(Integer, default=0)
    skipped_rows = Column(Integer, default=0)

    error_summary = Column(JSON, nullable=True)
    column_mapping = Column(JSON, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # relationships
    initiated_by_user = relationship("User", back_populates="import_logs")
    leads = relationship("Lead", back_populates="import_log")
    import_errors = relationship("ImportError", back_populates="import_log")
    campaign = relationship("Campaign", back_populates="import_logs")


class ImportError(Base):
    __tablename__ = "import_errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_id = Column(UUID(as_uuid=True), ForeignKey("imports.id", ondelete="CASCADE"), nullable=False)
    row_number = Column(Integer, nullable=False)
    error_message = Column(Text, nullable=False)
    raw_data = Column(JSON, nullable=True)

    import_log = relationship("ImportLog", back_populates="import_errors")

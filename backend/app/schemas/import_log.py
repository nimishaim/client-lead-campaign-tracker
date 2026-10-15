from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.models.import_log import ImportStatus, ImportType

class ImportLogResponse(BaseModel):
    id: UUID
    import_type: ImportType
    status: ImportStatus
    filename: str
    total_rows: int
    successful_rows: int
    failed_rows: int
    skipped_rows: int
    error_summary: Optional[Any] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    model_config = {'from_attributes': True}

class ImportPreviewResponse(BaseModel):
    filename: str
    detected_columns: List[str]
    sample_rows: List[Dict[str, Any]]
    total_rows: int
    suggested_mapping: Dict[str, str]
    file_hash: str

class ImportErrorResponse(BaseModel):
    row_number: int
    error_message: str
    raw_data: Optional[Dict[str, Any]] = None
    
    model_config = {'from_attributes': True}

class DashboardMetrics(BaseModel):
    total_leads: int
    new_leads: int
    contacted_leads: int
    converted_leads: int
    lost_leads: int
    conversion_rate: Optional[float] = None
    total_spend: float
    average_cpl: Optional[float] = None
    budget_utilisation: Optional[float] = None
    total_campaigns: int
    active_campaigns: int

class TimeSeriesPoint(BaseModel):
    date: str
    leads: int = 0
    spend: float = 0.0
    converted: int = 0

class PipelineDistribution(BaseModel):
    status: str
    count: int
    percentage: float

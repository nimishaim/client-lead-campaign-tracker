import hashlib
import csv
import io
import json
from uuid import UUID
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User, UserRole
from app.models.import_log import ImportLog, ImportError as ImportErrorModel, ImportStatus, ImportType
from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.campaign import Campaign, CampaignDailyMetric
from app.schemas.import_log import ImportLogResponse, ImportPreviewResponse
from app.services.auth_service import get_current_active_user, require_admin
from app.core.config import get_settings
from decimal import Decimal

router = APIRouter()
settings = get_settings()

MAX_FILE_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_CONTENT_TYPES = {'text/csv', 'application/csv', 'text/plain', 'application/vnd.ms-excel'}

# Meta Ads canonical column names and alternates
META_ADS_COLUMN_MAP = {
    'campaign_name': ['Campaign name', 'Campaign Name', 'campaign_name', 'Campaign'],
    'campaign_id': ['Campaign ID', 'campaign_id', 'Ad Set ID', 'Ad set ID'],
    'date': ['Day', 'Date', 'date', 'Report Date', 'Date Start'],
    'spend': ['Amount spent (USD)', 'Amount spent', 'Spend', 'spend', 'Cost'],
    'impressions': ['Impressions', 'impressions'],
    'clicks': ['Clicks (all)', 'Clicks', 'clicks', 'Link clicks'],
    'leads': ['Leads', 'leads', 'Results', 'Lead form opens'],
}

LEAD_COLUMN_MAP = {
    'name': ['name', 'Name', 'full_name', 'Full Name', 'Contact Name'],
    'email': ['email', 'Email', 'Email Address', 'email_address'],
    'phone': ['phone', 'Phone', 'Phone Number', 'phone_number', 'Mobile'],
    'source': ['source', 'Source', 'Lead Source'],
    'external_id': ['id', 'ID', 'lead_id', 'Lead ID', 'external_id'],
    'notes': ['notes', 'Notes', 'Comment', 'comment'],
}


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def detect_columns(headers: List[str], column_map: Dict[str, List[str]]) -> Dict[str, str]:
    """Suggest mapping from source column -> internal field."""
    mapping = {}
    header_lower = {h.lower().strip(): h for h in headers}
    for internal_field, alternates in column_map.items():
        for alt in alternates:
            if alt.lower().strip() in header_lower:
                mapping[header_lower[alt.lower().strip()]] = internal_field
                break
    return mapping


def parse_date(value: str) -> Optional[date]:
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%m-%d-%Y'):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_decimal(value: str) -> Optional[Decimal]:
    try:
        cleaned = value.replace('$', '').replace(',', '').strip()
        return Decimal(cleaned)
    except Exception:
        return None


@router.post('/preview', response_model=ImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    import_type: ImportType = ImportType.campaign_metrics,
    current_user: User = Depends(require_admin)
):
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f'File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB.')

    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            text = content.decode('latin-1')
        except Exception:
            raise HTTPException(status_code=400, detail='Could not decode file. Ensure UTF-8 or Latin-1 encoding.')

    file_hash = compute_file_hash(content)

    reader = csv.DictReader(io.StringIO(text))
    try:
        headers = reader.fieldnames or []
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Invalid CSV: {e}')

    if not headers:
        raise HTTPException(status_code=400, detail='CSV has no headers')

    rows = []
    total = 0
    for row in reader:
        total += 1
        if total <= 5:
            rows.append(dict(row))

    column_map = META_ADS_COLUMN_MAP if import_type == ImportType.campaign_metrics else LEAD_COLUMN_MAP
    suggested_mapping = detect_columns(list(headers), column_map)

    return ImportPreviewResponse(
        filename=file.filename or 'upload.csv',
        detected_columns=list(headers),
        sample_rows=rows,
        total_rows=total,
        suggested_mapping=suggested_mapping,
        file_hash=file_hash,
    )


@router.post('/campaign-metrics', response_model=ImportLogResponse, status_code=status.HTTP_201_CREATED)
async def import_campaign_metrics(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    campaign_id: UUID = Query(...),
    column_mapping: str = Query('{}'),  # JSON string of {source_col: internal_field}
    dry_run: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f'File too large.')

    file_hash = compute_file_hash(content)

    # Check for duplicate import
    existing = db.query(ImportLog).filter(
        ImportLog.file_hash == file_hash,
        ImportLog.status == ImportStatus.completed
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail='This file has already been imported successfully.')

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail='Campaign not found')

    try:
        mapping = json.loads(column_mapping)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail='Invalid column_mapping JSON')

    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    # Create import log
    import_log = ImportLog(
        initiated_by=current_user.id,
        client_id=campaign.client_id,
        campaign_id=campaign_id,
        import_type=ImportType.campaign_metrics,
        status=ImportStatus.processing,
        filename=file.filename or 'upload.csv',
        file_hash=file_hash,
        column_mapping=mapping,
    )
    db.add(import_log)
    db.commit()
    db.refresh(import_log)

    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])

    # Auto-detect mapping if not provided
    if not mapping:
        mapping = detect_columns(headers, META_ADS_COLUMN_MAP)

    # Invert mapping for lookup: internal_field -> source_col
    inv_map = {v: k for k, v in mapping.items()}

    successful = 0
    failed = 0
    skipped = 0
    errors = []

    rows_processed = []
    for row in reader:
        rows_processed.append(dict(row))

    import_log.total_rows = len(rows_processed)

    for i, row in enumerate(rows_processed, start=2):
        try:
            date_val = None
            if 'date' in inv_map and inv_map['date'] in row:
                date_val = parse_date(row[inv_map['date']])
            if not date_val:
                errors.append({'row': i, 'error': 'Missing or invalid date', 'data': row})
                failed += 1
                continue

            spend = Decimal('0')
            if 'spend' in inv_map and inv_map['spend'] in row:
                parsed = parse_decimal(row[inv_map['spend']])
                if parsed is not None:
                    spend = parsed

            impressions = 0
            if 'impressions' in inv_map and inv_map['impressions'] in row:
                try:
                    impressions = int(row[inv_map['impressions']].replace(',', '').strip())
                except Exception:
                    pass

            clicks = 0
            if 'clicks' in inv_map and inv_map['clicks'] in row:
                try:
                    clicks = int(row[inv_map['clicks']].replace(',', '').strip())
                except Exception:
                    pass

            leads = 0
            if 'leads' in inv_map and inv_map['leads'] in row:
                try:
                    leads = int(row[inv_map['leads']].replace(',', '').strip())
                except Exception:
                    pass

            if not dry_run:
                # Upsert daily metric
                from app.services.campaign_service import upsert_daily_metric
                upsert_daily_metric(db, campaign_id, date_val, spend, impressions, clicks, leads)

            successful += 1
        except Exception as e:
            errors.append({'row': i, 'error': str(e), 'data': row})
            failed += 1

    if not dry_run and successful > 0:
        # Recalculate campaign totals
        from sqlalchemy import func
        totals = db.query(
            func.sum(CampaignDailyMetric.spend),
            func.sum(CampaignDailyMetric.impressions),
            func.sum(CampaignDailyMetric.clicks),
            func.sum(CampaignDailyMetric.leads),
        ).filter(CampaignDailyMetric.campaign_id == campaign_id).first()
        campaign.total_spend = totals[0] or Decimal('0')
        campaign.impressions = totals[1] or 0
        campaign.clicks = totals[2] or 0
        campaign.attributed_leads = totals[3] or 0

    import_log.successful_rows = successful
    import_log.failed_rows = failed
    import_log.skipped_rows = skipped
    import_log.status = ImportStatus.completed if failed == 0 else (
        ImportStatus.partial if successful > 0 else ImportStatus.failed
    )
    import_log.completed_at = datetime.utcnow()
    import_log.error_summary = errors[:100]  # Store first 100 errors

    # Store individual error rows
    for err in errors:
        db.add(ImportErrorModel(
            import_id=import_log.id,
            row_number=err['row'],
            error_message=err['error'],
            raw_data=err.get('data'),
        ))

    db.commit()
    db.refresh(import_log)
    return import_log


@router.post('/leads', response_model=ImportLogResponse, status_code=status.HTTP_201_CREATED)
async def import_leads(
    file: UploadFile = File(...),
    client_id: UUID = Query(...),
    campaign_id: Optional[UUID] = None,
    column_mapping: str = Query('{}'),
    dry_run: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail='File too large.')

    file_hash = compute_file_hash(content)
    existing = db.query(ImportLog).filter(
        ImportLog.file_hash == file_hash,
        ImportLog.status == ImportStatus.completed
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail='This file has already been imported.')

    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    try:
        mapping = json.loads(column_mapping)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail='Invalid column_mapping JSON')

    import_log = ImportLog(
        initiated_by=current_user.id,
        client_id=client_id,
        campaign_id=campaign_id,
        import_type=ImportType.leads,
        status=ImportStatus.processing,
        filename=file.filename or 'leads.csv',
        file_hash=file_hash,
        column_mapping=mapping,
    )
    db.add(import_log)
    db.commit()
    db.refresh(import_log)

    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    if not mapping:
        mapping = detect_columns(headers, LEAD_COLUMN_MAP)
    inv_map = {v: k for k, v in mapping.items()}

    rows_processed = [dict(row) for row in reader]
    import_log.total_rows = len(rows_processed)

    successful = 0
    failed = 0
    skipped = 0
    errors = []

    for i, row in enumerate(rows_processed, start=2):
        try:
            name = row.get(inv_map.get('name', ''), '').strip()
            if not name:
                errors.append({'row': i, 'error': 'Name is required', 'data': row})
                failed += 1
                continue

            email = row.get(inv_map.get('email', ''), '').strip() or None
            phone = row.get(inv_map.get('phone', ''), '').strip() or None
            external_id = row.get(inv_map.get('external_id', ''), '').strip() or None
            notes = row.get(inv_map.get('notes', ''), '').strip() or None
            source_raw = row.get(inv_map.get('source', ''), '').strip().lower()

            # Map source to enum
            source = LeadSource.other
            if 'meta' in source_raw or 'facebook' in source_raw:
                source = LeadSource.meta_ads
            elif 'google' in source_raw:
                source = LeadSource.google_ads
            elif 'organic' in source_raw:
                source = LeadSource.organic
            elif 'referral' in source_raw:
                source = LeadSource.referral
            elif 'email' in source_raw:
                source = LeadSource.email

            # Validate email format if provided
            if email:
                import re
                if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
                    errors.append({'row': i, 'error': f'Invalid email: {email}', 'data': row})
                    failed += 1
                    continue

            # Check duplicate
            from app.services.lead_service import check_duplicate
            dup = check_duplicate(db, client_id, email=email, external_id=external_id)
            if dup:
                skipped += 1
                continue

            if not dry_run:
                lead = Lead(
                    client_id=client_id,
                    campaign_id=campaign_id,
                    name=name,
                    email=email,
                    phone=phone,
                    external_id=external_id,
                    notes=notes,
                    source=source,
                    status=LeadStatus.new,
                    import_id=import_log.id,
                )
                db.add(lead)
            successful += 1
        except Exception as e:
            errors.append({'row': i, 'error': str(e), 'data': row})
            failed += 1

    if not dry_run:
        db.flush()

    import_log.successful_rows = successful
    import_log.failed_rows = failed
    import_log.skipped_rows = skipped
    import_log.status = ImportStatus.completed if failed == 0 else (
        ImportStatus.partial if successful > 0 else ImportStatus.failed
    )
    import_log.completed_at = datetime.utcnow()
    import_log.error_summary = errors[:100]

    for err in errors:
        db.add(ImportErrorModel(
            import_id=import_log.id,
            row_number=err['row'],
            error_message=err['error'],
            raw_data=err.get('data'),
        ))

    db.commit()
    db.refresh(import_log)
    return import_log


@router.get('/', response_model=List[ImportLogResponse])
def list_imports(
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(ImportLog)
    if current_user.role != UserRole.admin:
        query = query.filter(ImportLog.initiated_by == current_user.id)
    total = query.count()
    imports = query.order_by(ImportLog.started_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return imports


@router.get('/{import_id}/errors')
def get_import_errors(
    import_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    import_log = db.query(ImportLog).filter(ImportLog.id == import_id).first()
    if not import_log:
        raise HTTPException(status_code=404, detail='Import not found')

    errors = db.query(ImportErrorModel).filter(ImportErrorModel.import_id == import_id).all()

    # Return as CSV download
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Row', 'Error', 'Raw Data'])
    for err in errors:
        writer.writerow([err.row_number, err.error_message, json.dumps(err.raw_data or {})])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename=import_errors_{import_id}.csv'}
    )

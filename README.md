# Client Lead & Campaign Tracker

A production-focused web API built for digital marketing freelancers and agencies to manage client leads, track lead pipeline stages, import Meta Ads campaign performance data, and monitor key marketing metrics.

---

## 1. Project Overview & Problem Statement

Digital marketing professionals often manage campaigns across multiple ad platforms and client accounts while tracking lead conversion through disjointed spreadsheets or generic CRMs. This causes:
- Fragmented lead attribution and delayed follow-ups.
- Inaccurate Cost Per Lead (CPL) calculations when ad spend and lead conversion live in separate tools.
- Weak data isolation across clients when agencies manage multiple accounts simultaneously.
- Difficulty monitoring funnel progression from ad click to lead contact and conversion.

The **Client Lead & Campaign Tracker** solves this by providing a centralized backend with strict client-level data isolation, multi-stage lead tracking, automated duplicate detection, campaign performance aggregation, and a flexible CSV import pipeline for Meta Ads metrics.

---

## 2. Current Implementation Status

> [!NOTE]
> This repository is currently in the **backend-complete** milestone. The FastAPI REST API, database models, Alembic migrations, authentication, business services, and automated test suite are fully implemented and verified. The frontend user interface and Docker deployment configurations are planned for upcoming milestones.

| Area | Status | Notes |
| :--- | :--- | :--- |
| **REST API (`/api/v1`)** | **Implemented** | 23 endpoints covering Auth, Users, Clients, Leads, Campaigns, Dashboard, Imports, and Reports. |
| **Database Models** | **Implemented** | SQLAlchemy 2.0 models with UUID primary keys, relationships, cascading foreign keys, and composite indexes. |
| **Alembic Migrations** | **Implemented** | Initial migration (`7141e6575647_initial_schema`) verified with fresh upgrades, downgrades, and `alembic check`. |
| **Authentication & RBAC** | **Implemented** | JWT tokens (access + refresh), secure password hashing via Bcrypt, `admin` and `client` roles. |
| **Client Data Isolation** | **Implemented** | Query-level tenant scoping; clients access only their assigned organization data; admins access aggregate data. |
| **Lead Pipeline** | **Implemented** | Stages (`new`, `contacted`, `converted`, `lost`), automatic transition timestamps, and full history audit trail. |
| **Campaign Analytics** | **Implemented** | Zero-denominator safe calculations for Cost Per Lead (CPL), Lead Conversion Rate, and Budget Utilisation. |
| **CSV Import Pipeline** | **Implemented** | Header auto-detection, schema preview, duplicate file prevention via SHA-256 hash, and error CSV export. |
| **Automated Tests** | **Implemented** | 32 passing pytest tests covering auth, RBAC, leads, metrics, and imports with 90% statement coverage. |
| **Frontend UI** | *Planned* | Directory structure created; React + TypeScript + Vite + Tailwind + Recharts implementation pending. |
| **Docker & Deployment** | *Planned* | Containerization and Render deployment setup pending in subsequent milestones. |
| **Demo Seed Scripts** | *Planned* | Automated database seeding with fictional demo clients and sample CSV files pending in subsequent milestones. |

---

## 3. Technology Stack

### Backend
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) `0.115.0`
- **ASGI Server:** [Uvicorn](https://www.uvicorn.org/) `0.31.0`
- **ORM:** [SQLAlchemy](https://www.sqlalchemy.org/) `2.0.35`
- **Database Migrations:** [Alembic](https://alembic.sqlalchemy.org/) `1.20.0`
- **Data Validation & Settings:** [Pydantic v2](https://docs.pydantic.dev/) `2.9.2` & `pydantic-settings` `2.5.2`
- **Authentication & Security:** `python-jose` (JWT), `passlib` with `bcrypt` (`bcrypt<4.0.0`)
- **Database Support:** PostgreSQL (`psycopg2-binary`) for production; SQLite supported for testing and local development
- **File Upload & Parsing:** `python-multipart`, standard Python `csv` and `hashlib`

### Testing
- **Test Runner:** [pytest](https://docs.pytest.org/) `9.1.1`
- **Test Client:** [HTTPX](https://www.python-httpx.org/) `0.27.2`
- **Coverage:** `pytest-cov` `7.1.0` (90% measured backend coverage)

### Planned Frontend (Not Yet Built)
- React 18 with TypeScript and Vite
- Tailwind CSS
- Recharts for analytics visualizations
- React Router

---

## 4. Project Structure

```text
client-lead-campaign-tracker/
├── .env.example                  # Environment configuration template
├── .gitignore                    # Excludes secrets, virtual environments, caches, DB files
├── README.md                     # Project documentation
├── backend/
│   ├── alembic.ini               # Alembic CLI configuration
│   ├── requirements.txt          # Python dependencies with pinned versions
│   ├── alembic/
│   │   ├── env.py                # Dynamic Alembic environment connecting to app settings
│   │   ├── script.py.mako        # Migration template
│   │   └── versions/
│   │       └── 7141e6575647_initial_schema.py  # Initial database schema revision
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI application factory, CORS, and health checks
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py     # Aggregates all v1 endpoint routers
│   │   │       └── endpoints/
│   │   │           ├── auth.py       # Login and profile endpoints
│   │   │           ├── campaigns.py  # Campaign CRUD & daily metrics
│   │   │           ├── clients.py    # Client CRUD & membership assignment
│   │   │           ├── dashboard.py  # KPI metrics, time-series, and pipeline distribution
│   │   │           ├── imports.py    # CSV preview, campaign metrics & lead imports
│   │   │           ├── leads.py      # Lead CRUD, status transitions, search, and pagination
│   │   │           ├── reports.py    # Filtered CSV export endpoints
│   │   │           └── users.py      # User management (admin only)
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic BaseSettings, env parsing, CORS validators
│   │   │   └── security.py       # Password hashing and JWT generation/decoding
│   │   ├── db/
│   │   │   └── base.py           # SQLAlchemy engine, SessionLocal, and get_db dependency
│   │   ├── models/               # SQLAlchemy ORM models
│   │   │   ├── campaign.py       # Campaign & CampaignDailyMetric
│   │   │   ├── client.py         # Client & ClientMembership
│   │   │   ├── import_log.py     # ImportLog & ImportError
│   │   │   ├── lead.py           # Lead & LeadStatusHistory
│   │   │   └── user.py           # User & UserRole enum
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── services/             # Business logic layer
│   │   │   ├── auth_service.py       # Auth guards, role checks, client access rules
│   │   │   ├── campaign_service.py   # CPL and budget utilization calculation
│   │   │   ├── dashboard_service.py  # Conversion rate & gap-free time series
│   │   │   └── lead_service.py       # Duplicate detection & stage transitions
│   │   └── utils/
│   │       └── validators.py     # Email, phone, and string sanitation helpers
│   ├── tests/
│   │   ├── conftest.py           # Isolated in-memory SQLite fixtures and TestClient
│   │   ├── test_auth.py          # Password hashing, JWT auth, RBAC user tests
│   │   ├── test_campaigns_and_metrics.py # CPL, budget utilisation, zero-division safety
│   │   ├── test_clients_and_isolation.py # Tenant isolation and membership tests
│   │   ├── test_imports.py       # CSV preview, deduplication, error reports
│   │   ├── test_leads.py         # Lead lifecycle, duplicate matching, stage history
│   │   └── test_reports_and_utils.py # CSV export endpoints and validators
│   └── uploads/                  # Temporary file upload directory (gitignored)
├── docs/                         # Additional documentation
├── frontend/                     # Frontend directory (placeholder for upcoming milestone)
├── sample-data/                  # Sample CSV exports (placeholder for upcoming milestone)
└── scripts/                      # Utility scripts (placeholder for upcoming milestone)
```

---

## 5. Local Setup Instructions (macOS)

### Prerequisites
- macOS (arm64 or x86_64)
- Python 3.11 installed (via Homebrew: `brew install python@3.11` or official installer)
- Git

### 1. Clone & Enter the Repository
```bash
git clone https://github.com/nimishaim/client-lead-campaign-tracker.git
cd client-lead-campaign-tracker
```

### 2. Set Up a Python Virtual Environment
```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

---

## 6. Environment Configuration

Copy the example environment template:
```bash
cp .env.example backend/.env
```

The application uses the following configuration parameters:

| Variable | Description | Default / Example Value |
| :--- | :--- | :--- |
| `APP_NAME` | Name of the application | `Client Lead & Campaign Tracker` |
| `APP_VERSION` | Application semver version | `1.0.0` |
| `DEBUG` | Enable debug mode | `false` |
| `ENVIRONMENT` | Environment name | `development` / `production` |
| `DATABASE_URL` | PostgreSQL or SQLite database connection URL | `postgresql://clct_user:clct_password@localhost:5432/clct_db` |
| `SECRET_KEY` | Secret key for signing JWT tokens (min 32 characters) | `your-super-secret-key-change-in-production-min-32-chars` |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifespan in minutes | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifespan in days | `7` |
| `CORS_ORIGINS` | Allowed origins (comma-separated or JSON list) | `http://localhost:3000,http://localhost:5173` |
| `UPLOAD_DIR` | Directory for temporary file uploads | `./uploads` |
| `MAX_UPLOAD_SIZE_MB` | Maximum allowed file upload size in megabytes | `50` |

> [!TIP]
> For fast local development without running a local PostgreSQL server, you can point `DATABASE_URL` to a local SQLite file in your `backend/.env`:
> ```bash
> DATABASE_URL="sqlite:///./clct_dev.db"
> ```

---

## 7. Database Migrations

Alembic manages schema migrations. Run commands from the `backend/` directory:

### Run Migrations (Apply All Upgrades)
```bash
cd backend
python -m alembic upgrade head
```

### Roll Back Migrations
```bash
# Roll back one revision
python -m alembic downgrade -1

# Roll back all migrations to base
python -m alembic downgrade base
```

### Verify Migration Status
```bash
# Check current migration revision
python -m alembic current

# Verify that migrations match models (drift check)
python -m alembic check
```

---

## 8. Backend Startup Instructions

Start the FastAPI application using Uvicorn with auto-reload:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Once started:
- **API Base:** `http://localhost:8000`
- **Health Check:** `http://localhost:8000/health`
- **Interactive Swagger Docs:** `http://localhost:8000/api/docs`
- **ReDoc Documentation:** `http://localhost:8000/api/redoc`
- **OpenAPI JSON Schema:** `http://localhost:8000/api/openapi.json`

Verify the server is healthy:
```bash
curl -s http://localhost:8000/health
# Response: {"status":"healthy","version":"1.0.0"}
```

---

## 9. Automated Testing & Code Coverage

The backend test suite runs against an **isolated in-memory SQLite database** created dynamically per test run. Tests never touch or modify development or production databases.

### Run All Tests
```bash
cd backend
python -m pytest -v
```

### Run Tests with Measured Coverage
```bash
cd backend
python -m pytest --cov=app --cov-report=term-missing
```

### Verified Test Results
```text
============================= test session starts ==============================
collected 32 items

tests/test_auth.py ..........                                            [ 31%]
tests/test_campaigns_and_metrics.py ....                                 [ 43%]
tests/test_clients_and_isolation.py ....                                 [ 56%]
tests/test_imports.py ....                                               [ 68%]
tests/test_leads.py ......                                               [ 87%]
tests/test_reports_and_utils.py ....                                     [100%]

======================== 32 passed, 3 warnings in 7.08s ========================
TOTAL: 1504 statements, 150 missed, 90% COVERAGE
```

---

## 10. API Documentation & Available Endpoints

The API is versioned under `/api/v1`. All endpoints enforce authentication (except `/auth/login` and `/health`) and validate role permissions.

### Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/login` — Authenticate user and receive access and refresh tokens.
- `GET /api/v1/auth/me` — Return profile of currently authenticated user.

### Users (`/api/v1/users`) *(Admin Only)*
- `GET /api/v1/users/` — List all registered users.
- `POST /api/v1/users/` — Create new user with role (`admin` or `client`).
- `GET /api/v1/users/{id}` — Get user details by ID.
- `PATCH /api/v1/users/{id}` — Update user name or active state.
- `DELETE /api/v1/users/{id}` — Deactivate user (self-deactivation prevented).

### Clients (`/api/v1/clients`)
- `GET /api/v1/clients/` — List accessible client organizations (all for admin; assigned only for client role).
- `POST /api/v1/clients/` — Create new client organization *(Admin only)*.
- `GET /api/v1/clients/{id}` — Get client details (scoped to authorized clients).
- `PATCH /api/v1/clients/{id}` — Update client details *(Admin only)*.
- `POST /api/v1/clients/{id}/members/{user_id}` — Assign client user to organization *(Admin only)*.
- `DELETE /api/v1/clients/{id}/members/{user_id}` — Remove user membership *(Admin only)*.

### Leads (`/api/v1/leads`)
- `GET /api/v1/leads/` — Paginated lead list with filtering by `status`, `source`, `campaign_id`, and `search`.
- `POST /api/v1/leads/` — Create lead with duplicate detection (`external_id` and `email`).
- `GET /api/v1/leads/{id}` — Get single lead with full status history.
- `PATCH /api/v1/leads/{id}` — Update lead fields.
- `PATCH /api/v1/leads/{id}/status` — Transition status (`new` -> `contacted` -> `converted` -> `lost`).
- `DELETE /api/v1/leads/{id}` — Soft-delete / archive lead *(Admin only)*.

### Campaigns (`/api/v1/campaigns`)
- `GET /api/v1/campaigns/` — List campaigns with computed `cpl` and `budget_utilisation`.
- `POST /api/v1/campaigns/` — Create campaign *(Admin only)*.
- `GET /api/v1/campaigns/{id}` — Get single campaign details and computed metrics.
- `PATCH /api/v1/campaigns/{id}` — Update campaign budget, dates, or status *(Admin only)*.
- `DELETE /api/v1/campaigns/{id}` — Archive campaign *(Admin only)*.
- `GET /api/v1/campaigns/{id}/metrics` — Get daily metrics for a campaign by date range.

### Dashboard (`/api/v1/dashboard`)
- `GET /api/v1/dashboard/metrics` — Aggregate summary KPIs (total leads, conversion rate, spend, average CPL, budget utilisation).
- `GET /api/v1/dashboard/time-series` — Daily continuous time-series (leads, spend, conversions) for trend charts.
- `GET /api/v1/dashboard/pipeline` — Lead distribution counts and percentages by pipeline stage.

### Imports (`/api/v1/imports`)
- `POST /api/v1/imports/preview` — Upload CSV to preview detected headers, row counts, and auto-mapped fields.
- `POST /api/v1/imports/campaign-metrics` — Transactional Meta Ads metrics import with deduplication and daily metric aggregation.
- `POST /api/v1/imports/leads` — Transactional lead CSV import with row validation and duplicate skipping.
- `GET /api/v1/imports/` — List historical import jobs.
- `GET /api/v1/imports/{id}/errors` — Download CSV error report of failed rows.

### Reports (`/api/v1/reports`)
- `GET /api/v1/reports/leads/export` — Download filtered lead data as CSV.
- `GET /api/v1/reports/campaigns/export` — Download campaign performance summary as CSV.

---

## 11. Known Limitations & Architecture Decisions

1. **Frontend Pending:** The React UI dashboard has not yet been built. All current features are accessed via the REST API and OpenAPI interactive documentation.
2. **Demo Seed Data:** Deterministic database fixtures and documented sample CSV files for Meta Ads exports are planned for subsequent milestones. Currently, data can be created via the API or test suite.
3. **Database Concurrency in Tests:** Automated tests run on an isolated in-memory SQLite database for high speed and independence from external services. Full PostgreSQL concurrency under multiple worker processes is planned to be verified with Docker Compose.
4. **File Size Limits:** Upload size is capped at 50MB (configurable via `MAX_UPLOAD_SIZE_MB`). Multi-gigabyte file streaming is not currently supported.
5. **Zero-Denominator Handling:** Zero-denominator cases (such as CPL when attributed leads = 0, or budget utilisation when budget = 0) safely return `None` (rendered as `null` in JSON) rather than infinity or zero, allowing clients to cleanly display `—`.
import uuid
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, get_db
from app.main import app as fastapi_app
from app.models import (
    Campaign,
    CampaignPlatform,
    CampaignStatus,
    Client,
    ClientMembership,
    User,
    UserRole,
)


@pytest.fixture(scope="session")
def engine():
    """In-memory SQLite database engine shared via StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """Provide a fresh, clean database session for each test function."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session: Session):
    """Create an admin user and return user object, JWT token, and auth headers."""
    password = "AdminPassword123!"
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        full_name="Admin User",
        role=UserRole.admin,
        hashed_password=get_password_hash(password),
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    headers = {"Authorization": f"Bearer {token}"}
    return {
        "user": user,
        "token": token,
        "headers": headers,
        "raw_password": password,
    }


@pytest.fixture
def client_user(db_session: Session):
    """Create a client-role user and return user object, JWT token, and auth headers."""
    password = "ClientPassword123!"
    user = User(
        id=uuid.uuid4(),
        email="clientuser@example.com",
        full_name="Client Regular User",
        role=UserRole.client,
        hashed_password=get_password_hash(password),
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    headers = {"Authorization": f"Bearer {token}"}
    return {
        "user": user,
        "token": token,
        "headers": headers,
        "raw_password": password,
    }


@pytest.fixture
def test_client_a(db_session: Session) -> Client:
    """Create first client organization."""
    client_obj = Client(
        id=uuid.uuid4(),
        name="Acme Corp",
        company="Acme Corp Inc",
        email="contact@acme.com",
        phone="+15551234567",
        industry="Technology",
        is_active=True,
    )
    db_session.add(client_obj)
    db_session.commit()
    db_session.refresh(client_obj)
    return client_obj


@pytest.fixture
def test_client_b(db_session: Session) -> Client:
    """Create second client organization (for isolation testing)."""
    client_obj = Client(
        id=uuid.uuid4(),
        name="Beta LLC",
        company="Beta LLC",
        email="contact@beta.com",
        phone="+15559876543",
        industry="Retail",
        is_active=True,
    )
    db_session.add(client_obj)
    db_session.commit()
    db_session.refresh(client_obj)
    return client_obj


@pytest.fixture
def client_user_membership_a(
    db_session: Session, client_user, test_client_a
) -> ClientMembership:
    """Assign client_user to test_client_a with can_update_leads=True."""
    membership = ClientMembership(
        id=uuid.uuid4(),
        user_id=client_user["user"].id,
        client_id=test_client_a.id,
        can_update_leads=True,
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)
    return membership


@pytest.fixture
def test_campaign_a(db_session: Session, test_client_a) -> Campaign:
    """Create a campaign under test_client_a."""
    campaign = Campaign(
        id=uuid.uuid4(),
        client_id=test_client_a.id,
        name="Summer Q3 Promo",
        platform=CampaignPlatform.meta_ads,
        status=CampaignStatus.active,
        budget=5000.00,
        total_spend=1250.00,
        impressions=25000,
        clicks=1200,
        attributed_leads=50,
        is_archived=False,
    )
    db_session.add(campaign)
    db_session.commit()
    db_session.refresh(campaign)
    return campaign

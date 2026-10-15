from uuid import UUID
from typing import List
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User, UserRole
from app.models.client import Client, ClientMembership
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    user_id: str = payload.get('sub')
    if not user_id:
        raise credentials_exception
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise credentials_exception
    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Inactive user')
    return current_user

def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Admin access required')
    return current_user

def get_user_clients(db: Session, user: User) -> List[UUID]:
    """Returns list of client IDs the user can access. Admins get all."""
    if user.role == UserRole.admin:
        return [c.id for c in db.query(Client.id).all()]
    else:
        memberships = db.query(ClientMembership).filter(ClientMembership.user_id == user.id).all()
        return [m.client_id for m in memberships]

def check_client_access(db: Session, user: User, client_id: UUID) -> bool:
    """True if user is admin or has membership for this client."""
    if user.role == UserRole.admin:
        return True
    membership = db.query(ClientMembership).filter(
        ClientMembership.user_id == user.id,
        ClientMembership.client_id == client_id
    ).first()
    return membership is not None

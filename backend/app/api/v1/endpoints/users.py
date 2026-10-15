from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.core.security import get_password_hash
from app.services.auth_service import get_current_active_user, require_admin

router = APIRouter()


@router.get('/', response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return db.query(User).all()


@router.post('/', response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail='Email already registered')
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        role=user_in.role,
        hashed_password=get_password_hash(user_in.password),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get('/{user_id}', response_model=UserResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user


@router.patch('/{user_id}', response_model=UserResponse)
def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete('/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail='Cannot deactivate your own account')
    user.is_active = False
    db.commit()

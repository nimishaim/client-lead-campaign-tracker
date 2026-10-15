from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import Token, UserResponse, UserCreate
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from app.services.auth_service import get_current_active_user

router = APIRouter()


@router.post('/login', response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid credentials',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Account is disabled')
    user.last_login = datetime.utcnow()
    db.commit()
    access_token = create_access_token(data={'sub': str(user.id), 'role': user.role.value})
    refresh_token = create_refresh_token(data={'sub': str(user.id), 'role': user.role.value})
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.get('/me', response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user

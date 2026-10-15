from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User
from app.models.client import Client, ClientMembership
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from app.services.auth_service import get_current_active_user, require_admin, check_client_access

router = APIRouter()


@router.get('/', response_model=List[ClientResponse])
def list_clients(
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.models.user import UserRole

    if current_user.role == UserRole.admin:
        query = db.query(Client)
        if is_active is not None:
            query = query.filter(Client.is_active == is_active)
        return query.all()
    else:
        # Return only clients the user has access to via membership
        memberships = (
            db.query(ClientMembership)
            .filter(ClientMembership.user_id == current_user.id)
            .all()
        )
        client_ids = [m.client_id for m in memberships]
        query = db.query(Client).filter(Client.id.in_(client_ids))
        if is_active is not None:
            query = query.filter(Client.is_active == is_active)
        return query.all()


@router.post('/', response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    client_in: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    client = Client(**client_in.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get('/{client_id}', response_model=ClientResponse)
def get_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_client_access(db, current_user, client_id):
        raise HTTPException(status_code=403, detail='Access denied')
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail='Client not found')
    return client


@router.patch('/{client_id}', response_model=ClientResponse)
def update_client(
    client_id: UUID,
    client_update: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail='Client not found')
    update_data = client_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


@router.post('/{client_id}/members/{user_id}', status_code=status.HTTP_201_CREATED)
def add_member(
    client_id: UUID,
    user_id: UUID,
    can_update_leads: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail='Client not found')
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    existing = (
        db.query(ClientMembership)
        .filter(
            ClientMembership.client_id == client_id,
            ClientMembership.user_id == user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail='User already a member')
    membership = ClientMembership(
        client_id=client_id,
        user_id=user_id,
        can_update_leads=can_update_leads,
    )
    db.add(membership)
    db.commit()
    return {'message': 'Member added'}


@router.delete('/{client_id}/members/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    client_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    membership = (
        db.query(ClientMembership)
        .filter(
            ClientMembership.client_id == client_id,
            ClientMembership.user_id == user_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail='Membership not found')
    db.delete(membership)
    db.commit()

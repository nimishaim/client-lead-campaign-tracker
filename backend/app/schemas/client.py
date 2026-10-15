from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional

class ClientBase(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    notes: Optional[str] = None

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class ClientResponse(ClientBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = {'from_attributes': True}

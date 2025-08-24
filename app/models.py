from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# User models
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool
    
    class Config:
        from_attributes = True

# Chat models
class ChatMessage(BaseModel):
    id: int
    message: str
    response: str
    sources: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class QuestionRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5

# Document models
class Document(BaseModel):
    id: int
    filename: str
    processed_at: datetime
    chunk_count: int
    is_active: bool
    
    class Config:
        from_attributes = True

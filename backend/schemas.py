from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class UserBase(BaseModel):
    name: str
    student_id: str

class UserCreate(UserBase):
    # Base64 image sent from frontend to calculate face encodings on backend
    enrollment_image: Optional[str] = None 

class UserOut(UserBase):
    id: int
    status: str
    
    class Config:
        from_attributes = True

class SessionCreate(BaseModel):
    student_id: int

class SessionOut(BaseModel):
    id: int
    student_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    trust_score: float

    class Config:
        from_attributes = True

class ViolationOut(BaseModel):
    id: int
    session_id: int
    timestamp: datetime
    violation_type: str
    snapshot_url: Optional[str]

    class Config:
        from_attributes = True

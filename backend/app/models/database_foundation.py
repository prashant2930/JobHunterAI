from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class SystemStatus(SQLModel, table=True):
    __tablename__ = "system_status"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    initialized_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "ok"

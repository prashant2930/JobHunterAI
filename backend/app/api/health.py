from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.database import get_session
from app.models import SystemStatus
import logging

router = APIRouter()
logger = logging.getLogger("jobhunter")

@router.get("/health")
def health_check(session: Session = Depends(get_session)):
    db_status = "disconnected"
    try:
        # Query the system status to verify DB reads
        status_entry = session.exec(select(SystemStatus)).first()
        if status_entry:
            db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "error"
        
    return {
        "status": "ok",
        "service": "jobhunter-ai",
        "database": db_status
    }

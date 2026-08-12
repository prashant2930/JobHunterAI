from sqlmodel import SQLModel, create_engine, Session, select
from app.config import settings

# Adjust SQLite connect args for FastAPI asynchronous thread pooling
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL, 
    echo=False,  # Set to True for verbose SQL logging
    connect_args=connect_args
)

def init_db():
    # Import models here to ensure they are registered on the SQLModel metadata
    import app.models
    SQLModel.metadata.create_all(engine)
    
    # Initialize system status entry to verify DB writes are functional
    with Session(engine) as session:
        from app.models import SystemStatus
        # Check if status row exists, if not, write one
        status = session.exec(select(SystemStatus)).first()
        if not status:
            session.add(SystemStatus())
            session.commit()

def get_session():
    with Session(engine) as session:
        yield session

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.db.models import Base

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def init_db():
    Base.metadata.create_all(engine)
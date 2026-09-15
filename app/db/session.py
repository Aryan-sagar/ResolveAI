from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.db.models import Base

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def init_db():
    Base.metadata.create_all(engine)
    # create_all does not ALTER existing tables — add new columns by hand
    with engine.begin() as conn:
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(conversations)")]
        if "summary" not in cols:
            conn.exec_driver_sql("ALTER TABLE conversations ADD COLUMN summary TEXT")
        if "summarized_up_to" not in cols:
            conn.exec_driver_sql("ALTER TABLE conversations ADD COLUMN summarized_up_to INTEGER")
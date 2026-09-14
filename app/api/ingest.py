from fastapi import APIRouter
from app.services.ingestion import ingest_directory
from app.services.retrieval import retriever

router = APIRouter(prefix="/api")

@router.post("/ingest")
def ingest(data_dir: str = "data", tenant_id: str = "acme", access_level: str = "public"):
    result = ingest_directory(data_dir, tenant_id, access_level)
    retriever.invalidate()
    return result

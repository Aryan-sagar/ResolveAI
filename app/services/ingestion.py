import uuid
from pathlib import Path
from qdrant_client import models
from app.config import settings
from app.core.embeddings import embedder
from app.core.vectorstore import qdrant, ensure_collection
from app.db.session import SessionLocal
from app.db.models import Document, Chunk

def chunk_text(text, words=None, overlap=None):
    words, overlap = words or settings.chunk_words, overlap or settings.chunk_overlap_words
    tokens, chunks, step = text.split(), [], words - overlap
    for i in range(0, len(tokens), step):
        c = " ".join(tokens[i:i + words]).strip()
        if c:
            chunks.append(c)
        if i + words >= len(tokens):
            break
    return chunks

def parse_file(path: Path) -> str:
    if path.suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="ignore")

def ingest_directory(data_dir="data", tenant_id="acme", access_level="public"):
    ensure_collection()
    db = SessionLocal()
    # idempotent re-ingest: wipe this tenant first (prod: versioned upserts instead)
    qdrant.delete(collection_name=settings.collection_name,
                  points_selector=models.FilterSelector(filter=models.Filter(must=[
                      models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id))])))
    old_ids = [r.id for r in db.query(Document.id).filter(Document.tenant_id == tenant_id)]
    if old_ids:
        db.query(Chunk).filter(Chunk.document_id.in_(old_ids)).delete(synchronize_session=False)
        db.query(Document).filter(Document.id.in_(old_ids)).delete(synchronize_session=False)
        db.commit()

    files = [p for p in Path(data_dir).rglob("*") if p.suffix in {".md", ".txt", ".pdf"}]
    indexed = []  # (qid, payload, content)
    for path in files:
        doc_type = ("policy" if "policies" in str(path) else "faq" if "faqs" in str(path)
                    else "product" if "products" in str(path) else "doc")
        rel_parts = [p.lower() for p in path.relative_to(Path(data_dir)).parts[:-1]]
        doc_access = "internal" if "internal" in rel_parts else access_level
        doc = Document(title=path.stem, source=path.name, doc_type=doc_type,
                       tenant_id=tenant_id, access_level=doc_access)
        db.add(doc)
        db.flush()  # assigns doc.id via SQLite autoincrement before chunks reference it
        for i, content in enumerate(chunk_text(parse_file(path))):
            qid = str(uuid.uuid4())
            db.add(Chunk(document_id=doc.id, chunk_index=i, content=content, qdrant_id=qid))
            indexed.append((qid, {"document_id": doc.id, "source": path.name, "doc_type": doc_type,
                                  "tenant_id": tenant_id, "access_level": access_level,
                                  "chunk_index": i, "content": content}, content))
    db.commit(); db.close()

    vectors = embedder.embed([c for _, _, c in indexed])
    qdrant.upsert(collection_name=settings.collection_name,
                  points=[models.PointStruct(id=qid, vector=v, payload=p)
                          for (qid, p, _), v in zip(indexed, vectors)])
    return {"documents": len(files), "chunks": len(indexed), "tenant_id": tenant_id}
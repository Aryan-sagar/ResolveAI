from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.session import init_db
from app.api import chat, ingest, actions

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title="SupportOps AI Copilot", version="0.1.0", lifespan=lifespan)
app.include_router(chat.router)
app.include_router(ingest.router)
app.include_router(actions.router)

@app.get("/health")
def health():
    return {"status": "ok"}
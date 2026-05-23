"""AccessBank AI Customer Support Agent — FastAPI application."""

import io
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.voice_processor import transcribe_audio
from config import get_settings
from database.db import get_db, init_db
from models.case import CaseStatus, Channel
from models.message import MessageRole
from services.case_service import CaseService
from services.email_service import EmailService
from services.pipeline import MessagePipeline
from services.rag_service import get_rag_service
from services.telegram_service import TelegramAlertService
from utils.logging_utils import log_event
from utils.token_tracker import token_tracker

settings = get_settings()

app = FastAPI(
    title="AccessBank AI Support Agent",
    description="AI-powered customer support for AccessBank Azerbaijan",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting: 20 req/min per user
_rate_buckets: Dict[str, List[datetime]] = defaultdict(list)


def check_rate_limit(user_id: str) -> None:
    now = datetime.utcnow()
    window = now - timedelta(minutes=1)
    bucket = _rate_buckets[user_id]
    _rate_buckets[user_id] = [t for t in bucket if t > window]
    if len(_rate_buckets[user_id]) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    _rate_buckets[user_id].append(now)


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=4000)
    session_id: Optional[str] = None
    channel: str = "WEB"


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    transcribed_text: Optional[str] = None
    sentiment: Optional[str] = None
    emotion: Optional[str] = None
    urgency_score: Optional[int] = None
    is_critical: bool = False
    intent: Optional[str] = None
    case_id: Optional[str] = None
    department: Optional[str] = None


class CaseStatusUpdate(BaseModel):
    status: str


def get_pipeline(db: Session = Depends(get_db)) -> MessagePipeline:
    alert = TelegramAlertService(
        settings.telegram_bot_token,
        settings.telegram_supervisor_chat_id,
    )
    return MessagePipeline(CaseService(db), EmailService(), telegram_alert=alert)


def _seed_demo_case(db: Session) -> None:
    """Seed Case #001 for demo flow 5."""
    from models.case import Case, CaseStatus, Channel

    if db.query(Case).filter(Case.case_id == "001").first():
        return
    db.add(
        Case(
            case_id="001",
            customer_name="Demo User",
            customer_phone="***-**-01",
            issue_description="Demo case for status lookup",
            department="Customer Service / Branch",
            routing_reason="Seeded for hackathon demo",
            sentiment="NEUTRAL",
            emotion="NEUTRAL",
            urgency_score=2,
            is_critical=False,
            status=CaseStatus.OPEN,
            channel=Channel.WEB,
        )
    )
    db.commit()


@app.on_event("startup")
def startup() -> None:
    init_db()
    rag = get_rag_service()
    count = rag.ingest_knowledge_base()
    log_event("app_startup", rag_chunks=count)
    from database.db import SessionLocal

    db = SessionLocal()
    try:
        _seed_demo_case(db)
    finally:
        db.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "accessbank-agent"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    session_id = req.session_id or str(uuid.uuid4())
    check_rate_limit(session_id)

    pipeline = get_pipeline(db)
    channel = Channel.TELEGRAM if req.channel.upper() == "TELEGRAM" else Channel.WEB
    result = pipeline.process(req.message, session_id, channel=channel)
    db.commit()

    return ChatResponse(
        reply=result.reply,
        session_id=result.session_id,
        transcribed_text=result.transcribed_text,
        sentiment=result.sentiment,
        emotion=result.emotion,
        urgency_score=result.urgency_score,
        is_critical=result.is_critical,
        intent=result.intent,
        case_id=result.case_id,
        department=result.department,
    )


@app.post("/api/voice", response_model=ChatResponse)
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    language_hint: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> ChatResponse:
    sid = session_id or str(uuid.uuid4())
    check_rate_limit(sid)

    audio_bytes = await audio.read()
    log_event(
        "message_received",
        channel="WEB",
        type="voice",
        length=len(audio_bytes),
    )

    transcription = transcribe_audio(
        audio_bytes,
        filename=audio.filename or "audio.webm",
        language_hint=language_hint,
    )

    pipeline = get_pipeline(db)
    result = pipeline.process(transcription.text, sid, channel=Channel.WEB)
    db.commit()

    return ChatResponse(
        reply=result.reply,
        session_id=sid,
        transcribed_text=transcription.text,
        sentiment=result.sentiment,
        emotion=result.emotion,
        urgency_score=result.urgency_score,
        is_critical=result.is_critical,
        intent=result.intent,
        case_id=result.case_id,
        department=result.department,
    )


@app.get("/api/cases")
def list_cases(
    department: Optional[str] = None,
    status: Optional[str] = None,
    is_critical: Optional[bool] = None,
    sentiment: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[dict]:
    cases = CaseService(db).list_cases(
        department=department,
        status=status,
        is_critical=is_critical,
        sentiment=sentiment,
    )
    return [
        {
            "case_id": c.case_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "customer_name": c.customer_name,
            "customer_phone": c.customer_phone,
            "issue_description": c.issue_description,
            "department": c.department,
            "sentiment": c.sentiment,
            "emotion": c.emotion,
            "urgency_score": c.urgency_score,
            "is_critical": c.is_critical,
            "status": c.status.value if hasattr(c.status, "value") else c.status,
            "channel": c.channel.value if hasattr(c.channel, "value") else c.channel,
            "email_sent": c.email_sent,
        }
        for c in cases
    ]


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)) -> dict:
    case = CaseService(db).get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    messages = CaseService(db).get_conversation(case.case_id)
    return {
        "case": {
            "case_id": case.case_id,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "customer_name": case.customer_name,
            "customer_phone": case.customer_phone,
            "issue_description": case.issue_description,
            "department": case.department,
            "routing_reason": case.routing_reason,
            "sentiment": case.sentiment,
            "emotion": case.emotion,
            "urgency_score": case.urgency_score,
            "is_critical": case.is_critical,
            "status": case.status.value if hasattr(case.status, "value") else case.status,
        },
        "messages": [
            {
                "role": m.role.value if hasattr(m.role, "value") else m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@app.patch("/api/cases/{case_id}/status")
def update_case_status(
    case_id: str,
    body: CaseStatusUpdate,
    db: Session = Depends(get_db),
) -> dict:
    try:
        status = CaseStatus(body.status.upper())
    except ValueError:
        raise HTTPException(400, f"Invalid status. Use: {[s.value for s in CaseStatus]}")
    case = CaseService(db).update_status(case_id, status)
    if not case:
        raise HTTPException(404, "Case not found")
    db.commit()
    return {"case_id": case.case_id, "status": case.status.value}


@app.get("/api/stats/dashboard")
def dashboard_stats(db: Session = Depends(get_db)) -> dict:
    stats = CaseService(db).get_dashboard_stats()
    stats["token_usage"] = token_tracker.get_summary()
    return stats


@app.get("/api/stats/today")
def today_stats(db: Session = Depends(get_db)) -> dict:
    return CaseService(db).get_daily_stats()


@app.get("/api/token-usage")
def token_usage() -> dict:
    return token_tracker.get_summary()


@app.post("/api/rag/reindex")
def reindex_rag() -> dict:
    count = get_rag_service().ingest_knowledge_base()
    return {"new_chunks": count}


class ConnectionManager:
    def __init__(self) -> None:
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict) -> None:
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(ws)


ws_manager = ConnectionManager()


@app.websocket("/ws/cases")
async def cases_websocket(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.app_env == "development")

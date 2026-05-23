"""Case model for support escalations."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text

from database.db import Base


class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Channel(str, enum.Enum):
    TELEGRAM = "TELEGRAM"
    WEB = "WEB"


class Case(Base):
    __tablename__ = "cases"

    case_id = Column(String(20), primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    customer_name = Column(String(200), nullable=True)
    customer_phone = Column(String(50), nullable=True)  # masked
    issue_description = Column(Text, nullable=True)
    incident_datetime = Column(String(100), nullable=True)
    department = Column(String(100), nullable=False)
    routing_reason = Column(Text, nullable=True)
    sentiment = Column(String(20), nullable=True)
    emotion = Column(String(30), nullable=True)
    urgency_score = Column(Integer, default=1)
    is_critical = Column(Boolean, default=False)
    status = Column(
        Enum(CaseStatus), default=CaseStatus.OPEN, nullable=False
    )
    email_sent = Column(Boolean, default=False)
    email_thread_id = Column(String(255), nullable=True)
    channel = Column(Enum(Channel), default=Channel.WEB, nullable=False)
    intent = Column(String(50), nullable=True)
    language = Column(String(10), default="az")

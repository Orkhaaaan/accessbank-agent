"""Conversation message model."""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text

from database.db import Base


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(20), ForeignKey("cases.case_id"), nullable=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    channel = Column(String(20), default="WEB")
    message_type = Column(String(10), default="text")  # text | voice
    sentiment = Column(String(20), nullable=True)
    emotion = Column(String(30), nullable=True)
    intent = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

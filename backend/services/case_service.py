"""Case creation and management."""

import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.case import Case, CaseStatus, Channel
from models.message import Message, MessageRole
from utils.logging_utils import log_event, mask_phone


class CaseService:
    def __init__(self, db: Session):
        self.db = db

    def _next_case_id(self) -> str:
        count = self.db.query(func.count(Case.case_id)).scalar() or 0
        return f"{count + 1:03d}"

    def create_case(
        self,
        customer_name: str,
        customer_phone: str,
        issue_description: str,
        department: str,
        routing_reason: str,
        channel: Channel = Channel.WEB,
        sentiment: Optional[str] = None,
        emotion: Optional[str] = None,
        urgency_score: int = 1,
        is_critical: bool = False,
        intent: Optional[str] = None,
        incident_datetime: Optional[str] = None,
        language: str = "az",
    ) -> Case:
        case_id = self._next_case_id()
        masked = mask_phone(customer_phone)
        case = Case(
            case_id=case_id,
            customer_name=customer_name,
            customer_phone=masked,
            issue_description=issue_description,
            incident_datetime=incident_datetime,
            department=department,
            routing_reason=routing_reason,
            sentiment=sentiment,
            emotion=emotion,
            urgency_score=urgency_score,
            is_critical=is_critical,
            status=CaseStatus.OPEN,
            channel=channel,
            intent=intent,
            language=language,
        )
        self.db.add(case)
        self.db.flush()
        log_event(
            "case_created",
            case_id=case_id,
            department=department,
            urgency=urgency_score,
        )
        return case

    def get_case(self, case_id: str) -> Optional[Case]:
        normalized = case_id.strip().lstrip("#")
        if normalized.isdigit():
            normalized = f"{int(normalized):03d}"
        return self.db.query(Case).filter(Case.case_id == normalized).first()

    def update_email_status(
        self, case_id: str, thread_id: str, sent: bool = True
    ) -> None:
        case = self.get_case(case_id)
        if case:
            case.email_sent = sent
            case.email_thread_id = thread_id
            self.db.flush()
            log_event("email_sent", case_id=case_id, thread_id=thread_id[:20])

    def update_status(self, case_id: str, status: CaseStatus) -> Optional[Case]:
        case = self.get_case(case_id)
        if case:
            case.status = status
            self.db.flush()
        return case

    def list_cases(
        self,
        department: Optional[str] = None,
        status: Optional[str] = None,
        is_critical: Optional[bool] = None,
        sentiment: Optional[str] = None,
        date_from: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Case]:
        q = self.db.query(Case).order_by(Case.created_at.desc())
        if department:
            q = q.filter(Case.department == department)
        if status:
            q = q.filter(Case.status == CaseStatus(status))
        if is_critical is not None:
            q = q.filter(Case.is_critical == is_critical)
        if sentiment:
            q = q.filter(Case.sentiment == sentiment)
        if date_from:
            q = q.filter(Case.created_at >= date_from)
        return q.limit(limit).all()

    def save_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        case_id: Optional[str] = None,
        channel: str = "WEB",
        message_type: str = "text",
        sentiment: Optional[str] = None,
        emotion: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> Message:
        msg = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            case_id=case_id,
            role=role,
            content=content,
            channel=channel,
            message_type=message_type,
            sentiment=sentiment,
            emotion=emotion,
            intent=intent,
        )
        self.db.add(msg)
        self.db.flush()
        return msg

    def get_conversation(self, case_id: str) -> List[Message]:
        return (
            self.db.query(Message)
            .filter(Message.case_id == case_id)
            .order_by(Message.created_at)
            .all()
        )

    def get_session_messages(self, session_id: str) -> List[Message]:
        return (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at)
            .all()
        )

    def get_daily_stats(self) -> Dict[str, Any]:
        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cases_today = (
            self.db.query(Case).filter(Case.created_at >= today_start).all()
        )
        total = len(cases_today)
        critical = sum(1 for c in cases_today if c.is_critical)
        dept_counts: Dict[str, int] = {}
        sentiment_counts: Dict[str, int] = {}
        for c in cases_today:
            dept_counts[c.department] = dept_counts.get(c.department, 0) + 1
            s = c.sentiment or "UNKNOWN"
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
        top_dept = max(dept_counts, key=dept_counts.get) if dept_counts else "N/A"
        return {
            "total": total,
            "critical": critical,
            "top_department": top_dept,
            "sentiment_breakdown": sentiment_counts,
            "department_breakdown": dept_counts,
        }

    def get_dashboard_stats(self) -> Dict[str, Any]:
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        def count_since(dt):
            return self.db.query(func.count(Case.case_id)).filter(
                Case.created_at >= dt
            ).scalar() or 0

        all_cases = self.db.query(Case).all()
        resolved = [
            c for c in all_cases if c.status in (CaseStatus.RESOLVED, CaseStatus.CLOSED)
        ]
        avg_resolution = None
        if resolved:
            deltas = [
                (datetime.utcnow() - c.created_at).total_seconds() / 3600
                for c in resolved
            ]
            avg_resolution = round(sum(deltas) / len(deltas), 1)

        dept_load: Dict[str, int] = {}
        for c in all_cases:
            dept_load[c.department] = dept_load.get(c.department, 0) + 1

        return {
            "today": count_since(today_start),
            "week": count_since(week_ago),
            "month": count_since(month_ago),
            "avg_resolution_hours": avg_resolution,
            "department_load": dept_load,
            "open_cases": self.db.query(func.count(Case.case_id))
            .filter(Case.status == CaseStatus.OPEN)
            .scalar()
            or 0,
        }

    @staticmethod
    def parse_case_status_query(text: str) -> Optional[str]:
        m = re.search(r"case\s*#?\s*(\d+)", text, re.I)
        if m:
            return f"{int(m.group(1)):03d}"
        m = re.search(r"#(\d{3})", text)
        if m:
            return m.group(1)
        return None

"""Telegram bot — primary customer interface."""

import asyncio
import logging
from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import get_settings
from database.db import SessionLocal, init_db
from models.case import Case, Channel
from services.case_service import CaseService
from services.email_service import EmailService
from services.pipeline import MessagePipeline
from utils.logging_utils import log_event

settings = get_settings()
logger = logging.getLogger("accessbank.telegram")
BAKU_TZ = ZoneInfo("Asia/Baku")


class TelegramAlertService:
    def __init__(self, bot_token: str, supervisor_chat_id: str):
        self.bot_token = bot_token
        self.supervisor_chat_id = supervisor_chat_id
        self._app: Optional[Application] = None

    def set_application(self, app: Application) -> None:
        self._app = app

    async def send_critical_alert(self, case: Case) -> None:
        if not self.supervisor_chat_id or not self._app:
            return
        text = (
            f"⚠️ CRITICAL CASE #{case.case_id}\n"
            f"Department: {case.department}\n"
            f"Urgency: {case.urgency_score}/5\n"
            f"Emotion: {case.emotion}\n"
            f"Sentiment: {case.sentiment}\n"
            f"Status: {case.status.value if hasattr(case.status, 'value') else case.status}"
        )
        try:
            await self._app.bot.send_message(
                chat_id=self.supervisor_chat_id, text=text
            )
        except Exception as e:
            log_event("telegram_alert_error", error=str(e)[:80])

    def send_critical_alert_sync(self, case: Case) -> None:
        if not self._app or not self.supervisor_chat_id:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.send_critical_alert(case))
            else:
                loop.run_until_complete(self.send_critical_alert(case))
        except RuntimeError:
            asyncio.run(self.send_critical_alert(case))


def _get_pipeline(db) -> MessagePipeline:
    cases = CaseService(db)
    email = EmailService()
    alert = TelegramAlertService(
        settings.telegram_bot_token,
        settings.telegram_supervisor_chat_id,
    )
    return MessagePipeline(cases, email, telegram_alert=alert)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome = (
        "Salam! AccessBank AI müştəri dəstəyinə xoş gəlmisiniz.\n\n"
        "Probleminizi sərbəst şəkildə yazın — kömək edəcəyəm.\n"
        "Case statusu: «Case #001 statusu nədir?»\n\n"
        "Əmrlər: /status <id>, /today"
    )
    await update.message.reply_text(welcome)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("İstifadə: /status 001")
        return
    case_id = context.args[0].lstrip("#")
    db = SessionLocal()
    try:
        cases = CaseService(db)
        case = cases.get_case(case_id)
        if case:
            st = case.status.value if hasattr(case.status, "value") else str(case.status)
            await update.message.reply_text(
                f"Case #{case.case_id}\nStatus: {st}\nŞöbə: {case.department}"
            )
        else:
            await update.message.reply_text(f"Case #{case_id} tapılmadı.")
    finally:
        db.close()


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        stats = CaseService(db).get_daily_stats()
        lines = [
            "📊 Bugünkü xülasə (Bakı vaxtı)",
            f"Cəmi case: {stats['total']}",
            f"Kritik: {stats['critical']}",
            f"Ən çox şöbə: {stats['top_department']}",
            "Sentiment:",
        ]
        for s, c in stats.get("sentiment_breakdown", {}).items():
            lines.append(f"  • {s}: {c}")
        await update.message.reply_text("\n".join(lines))
    finally:
        db.close()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user_id = str(update.effective_user.id)
    session_id = f"tg-{user_id}"
    text = update.message.text

    db = SessionLocal()
    try:
        pipeline = _get_pipeline(db)
        alert_svc = pipeline.telegram_alert
        if alert_svc and context.application:
            alert_svc.set_application(context.application)

        result = pipeline.process(text, session_id, channel=Channel.TELEGRAM)
        db.commit()
        await update.message.reply_text(result.reply)

        if result.is_critical and result.case_id:
            cases = CaseService(db)
            case = cases.get_case(result.case_id)
            if case and alert_svc:
                await alert_svc.send_critical_alert(case)
    except Exception as e:
        logger.exception("Telegram message error")
        await update.message.reply_text(
            "Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
        )
    finally:
        db.close()


async def daily_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not settings.telegram_supervisor_chat_id:
        return
    db = SessionLocal()
    try:
        stats = CaseService(db).get_daily_stats()
        text = (
            f"📊 Gündəlik xülasə ({datetime.now(BAKU_TZ).strftime('%d.%m.%Y')})\n"
            f"Cəmi: {stats['total']}\n"
            f"Kritik: {stats['critical']}\n"
            f"Ən çox şöbə: {stats['top_department']}\n"
            f"Sentiment: {stats.get('sentiment_breakdown', {})}"
        )
        await context.bot.send_message(
            chat_id=settings.telegram_supervisor_chat_id, text=text
        )
    finally:
        db.close()


def run_telegram_bot() -> None:
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot not started")
        return

    init_db()
    app = Application.builder().token(settings.telegram_bot_token).build()

    alert = TelegramAlertService(
        settings.telegram_bot_token,
        settings.telegram_supervisor_chat_id,
    )
    alert.set_application(app)

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Daily summary at 18:00 Baku time
    if settings.telegram_supervisor_chat_id and app.job_queue:
        app.job_queue.run_daily(
            daily_summary_job,
            time=time(hour=18, minute=0, tzinfo=BAKU_TZ),
            name="daily_summary",
        )

    logger.info("Starting Telegram bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

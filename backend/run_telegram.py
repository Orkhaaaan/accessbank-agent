#!/usr/bin/env python3
"""Run Telegram bot separately from FastAPI."""

from services.telegram_service import run_telegram_bot

if __name__ == "__main__":
    run_telegram_bot()

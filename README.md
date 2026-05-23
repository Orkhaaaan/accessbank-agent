# AccessBank AI Customer Support Agent

AI-powered customer support platform for **AccessBank Azerbaijan**, combining Telegram and web channels with intent classification, sentiment analysis, RAG-based FAQ answers, department routing, case management, and official email escalation.

## What Was Built

A full-stack support agent that processes text and voice (Whisper) in Azerbaijani, Russian, and English; analyzes emotion and urgency; answers FAQs from a ChromaDB knowledge base; escalates issues to the correct department with Gmail/Microsoft Graph email; and alerts supervisors on Telegram for critical cases.

## Architecture

```
┌─────────────┐     ┌─────────────┐
│  Web UI     │     │  Telegram   │
│  (React)    │     │  Bot        │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 ▼
        ┌────────────────┐
        │  FastAPI       │
        │  main.py       │
        └────────┬───────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
 Pipeline    ChromaDB     SQLite/PG
 (agents)    (RAG)        (cases)
    │
    ├── Sentiment (gpt-4o-mini)
    ├── Intent (gpt-4o-mini)
    ├── Router → 5 departments
    ├── RAG (top 3 chunks)
    ├── Case + Email + Telegram alert
    └── Whisper (voice only)
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | Python 3.11, FastAPI, Uvicorn |
| AI | OpenAI gpt-4o-mini, text-embedding-3-small, whisper-1 |
| Vector DB | ChromaDB |
| Database | SQLite (default) / PostgreSQL |
| Email | Gmail API OAuth2 or Microsoft Graph |
| Bot | python-telegram-bot |
| Frontend | React 18, Vite, Recharts |

## Sentiment & Emotion Scoring

1. **Emoji preprocessing** — 😡🤬 boost ANGRY; 😢😭 boost SAD; 😊👍 boost POSITIVE; ❗❗ boost URGENCY.
2. **LLM analysis** (gpt-4o-mini, max 500 tokens) returns `sentiment`, `emotion`, `urgency_score` (1–5).
3. **Merged scores** — emoji boosts are applied on top of LLM output.
4. **CRITICAL flag** — `urgency >= 4` OR `emotion in (ANGRY, URGENT)` → `is_critical=true` → supervisor Telegram alert + ⚠️ email prefix.

## Department Routing

Routing uses a **two-step decision**:

1. **Intent mapping (primary)**  
   - `ACCOUNT_ISSUE` → Digital Banking  
   - `CARD_ISSUE` → Card Operations  
   - `TRANSFER_ISSUE` → Transfers & Payments  
   - `LOAN_ISSUE` → Loans & Applications  
   - `COMPLAINT` → Customer Service / Branch  

2. **Keyword scoring (fallback)** — if intent is unclear, keywords in the message are scored per department (e.g. "köçürmə", "transfer" → Transfers & Payments). Highest score wins; tie/default → Customer Service / Branch.

Every routing decision is logged with `department` and `reason` in application logs.

## RAG Context Selection

1. Knowledge base is stored in `backend/data/knowledge_base.json` (sourced from public AccessBank info).
2. On startup, chunks are embedded with **text-embedding-3-small** and stored in ChromaDB (existing chunk IDs are **not** re-embedded — cost control).
3. For `GENERAL_QUESTION`, only **top 3** chunks are retrieved (cosine similarity).
4. Each chunk is trimmed to ~300 tokens max before sending to the model.
5. The LLM receives **only** those 3 chunks — never the full knowledge base.

## Setup

### a. Clone

```bash
git clone <your-repo-url>
cd accessbank-agent
```

### b. Environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your keys (never commit .env)
```

### c. Gmail OAuth2 setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project → enable **Gmail API**.
3. Create OAuth 2.0 credentials (Desktop or Web).
4. Use [OAuth Playground](https://developers.google.com/oauthplayground/) with scope `https://www.googleapis.com/auth/gmail.send` to obtain a **refresh token**.
5. Set in `.env`:
   - `GMAIL_CLIENT_ID`
   - `GMAIL_CLIENT_SECRET`
   - `GMAIL_REFRESH_TOKEN`
   - `GMAIL_SENDER_EMAIL`

### c-alt. Microsoft Graph setup

1. Register an app in [Azure Portal](https://portal.azure.com/) → App registrations.
2. Add application permission `Mail.Send` and grant admin consent.
3. Create a client secret.
4. Set in `.env`:
   - `MS_CLIENT_ID`
   - `MS_CLIENT_SECRET`
   - `MS_TENANT_ID`
   - `MS_SENDER_EMAIL`

### d. Install backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### e. Run API

```bash
cd backend
python main.py
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### f. Docker (optional)

```bash
cp backend/.env.example backend/.env
# fill .env
docker compose up --build
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

## Telegram Bot

```bash
cd backend
# Set TELEGRAM_BOT_TOKEN and TELEGRAM_SUPERVISOR_CHAT_ID in .env
python run_telegram.py
```

**User flows:** natural language messages, FAQ answers, case creation, `Case #001 statusu nədir?`

**Supervisor:** critical alerts in real time; daily summary at **18:00 Baku (AZT)**.

**Commands:** `/start`, `/status 001`, `/today`

## Demo Flows

| Demo | Input | Expected |
|------|-------|----------|
| 1 FAQ | `AccessBank-ın iş saatları nədir?` | RAG answer, no case |
| 2 Voice | Audio: "Kartım bloklandı, nə edim?" | Transcription → CARD_ISSUE → collection |
| 3 Critical | `Transferim uğursuz oldu pulum getdi heç cavab yoxdu 😡😡❗❗` | NEGATIVE/ANGRY, urgency 5, CRITICAL, Transfers & Payments |
| 4 Security | `PIN kodum 1234-dür, kömək edin` | Security refusal in Azerbaijani |
| 5 Status | `Case #001 statusu nədir?` | Returns OPEN (seeded on startup) |
| 6 Summary | `/today` in Telegram | Daily stats |

## API Cost Control

- **gpt-4o-mini** — intent, sentiment, answers (max 500 tokens/call)
- **text-embedding-3-small** — run once at ingest, cached in ChromaDB
- **whisper-1** — only for voice uploads
- RAG: max 3 chunks × 300 tokens
- Token usage tracked in `/api/token-usage` and operator dashboard

## Security

- All secrets in `.env` (gitignored)
- Phone numbers masked as `***-**-XX` in DB and logs
- Rate limit: 20 requests/minute per session
- PIN/CVV/OTP/full card/password detection and refusal
- Input sanitization on all endpoints

## Known Limitations

- Session state for multi-step collection is in-memory (use Redis in production)
- Rule-based fallbacks when `OPENAI_API_KEY` is missing
- Email requires Gmail or Microsoft credentials; set `SKIP_EMAIL=true` for local dev
- WebSocket broadcast is basic; dashboard uses polling

## Future Improvements

- Redis session store and horizontal scaling
- Live operator handoff and CRM integration
- Automated accessbank.az KB refresh cron
- Azerbaijani fine-tuned sentiment model
- PostgreSQL + Alembic migrations in production

## Project Structure

See repository root `accessbank-agent/` for `backend/`, `frontend/`, `docker-compose.yml`, and `README.md`.

## License

Hackathon submission — AccessBank Azerbaijan AI Support Agent.

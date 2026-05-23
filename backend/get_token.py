"""Obtain Gmail OAuth2 refresh token for GMAIL_REFRESH_TOKEN in .env.

Usage:
  1. Google Cloud Console → APIs → Gmail API → OAuth client (Desktop).
  2. Download JSON → place in this folder as client_secret.json
     (or keep Google's name: client_secret_XXXX.json — auto-detected).
  3. source venv/bin/activate && python get_token.py
  4. Copy printed values into .env (never commit .env)
"""

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
BACKEND_DIR = Path(__file__).resolve().parent


def find_client_secrets_file() -> Path:
    """Locate OAuth client JSON (client_secret.json or client_secret_*.json)."""
    explicit = BACKEND_DIR / "client_secret.json"
    if explicit.is_file():
        return explicit

    matches = [
        p
        for p in sorted(BACKEND_DIR.glob("client_secret*.json"))
        if p.name != "client_secret.json.example"
    ]
    if matches:
        print(f"Using: {matches[0].name}")
        return matches[0]

    print(
        "ERROR: OAuth client JSON not found.\n\n"
        "1. Go to https://console.cloud.google.com/apis/credentials\n"
        "2. Create OAuth 2.0 Client ID → Application type: Desktop app\n"
        "3. Download JSON\n"
        "4. Save it here as:\n"
        f"   {explicit}\n"
        "   (or leave Google's name, e.g. client_secret_123456.json)\n"
    )
    sys.exit(1)


secrets_path = find_client_secrets_file()

flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)

creds = flow.run_local_server(port=0)

print("\n--- Copy these into backend/.env ---")
print("GMAIL_REFRESH_TOKEN=" + (creds.refresh_token or ""))
print("GMAIL_CLIENT_ID=" + (creds.client_id or ""))
print("GMAIL_CLIENT_SECRET=" + (creds.client_secret or ""))
print("GMAIL_SENDER_EMAIL=your@gmail.com")
print("-----------------------------------\n")

if not creds.refresh_token:
  print(
    "WARNING: refresh_token is empty. In Google Cloud, set OAuth consent to "
    "Testing and add your Google account as a test user, then run again."
  )

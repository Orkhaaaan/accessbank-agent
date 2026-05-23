#!/bin/bash
# Run before git push — fails if sensitive files would be committed
set -e
cd "$(dirname "$0")/.."

FORBIDDEN=(
  "backend/.env"
  "backend/client_secret.json"
  "backend/venv"
  "backend/accessbank.db"
)

echo "Checking for secrets..."
for f in "${FORBIDDEN[@]}"; do
  if git ls-files --error-unmatch "$f" 2>/dev/null; then
    echo "ERROR: $f is tracked by git. Remove it: git rm --cached $f"
    exit 1
  fi
done

# Scan staged files except this script (avoid false positive on pattern text)
STAGED=$(git diff --cached --name-only | grep -v 'check-secrets.sh' || true)
if [ -n "$STAGED" ]; then
  if git diff --cached -- $STAGED 2>/dev/null | grep -qiE 'GOCSPX-[a-zA-Z0-9_-]{10,}|sk-proj-[a-zA-Z0-9]{10,}|TELEGRAM_BOT_TOKEN=[0-9]{8,}:'; then
    echo "ERROR: Possible API key in staged changes. Unstage and fix .env"
    exit 1
  fi
fi

echo "OK — no forbidden files staged."

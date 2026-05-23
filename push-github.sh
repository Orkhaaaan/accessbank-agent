#!/bin/bash
# GitHub-a push — bir dəfə gh auth login lazımdır
set -e
cd "$(dirname "$0")"

REPO="https://github.com/Orkhaaaan/accessbank-agent.git"

echo "=== AccessBank Agent → GitHub push ==="

if ! command -v gh &>/dev/null; then
  echo "GitHub CLI yoxdur. Quraşdırın: brew install gh"
  exit 1
fi

if ! gh auth status &>/dev/null; then
  echo ""
  echo "GitHub-a daxil olun (brauzer açılacaq):"
  gh auth login -h github.com -p https -w
  gh auth setup-git
fi

git remote remove origin 2>/dev/null || true
git remote add origin "$REPO"

echo "Push edilir: origin main ..."
git push -u origin main

echo ""
echo "Hazır: https://github.com/Orkhaaaan/accessbank-agent"

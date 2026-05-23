# GitHub-a yükləmə (AccessBank Agent)

## Vacib — əvvəl oxuyun

Bu fayllar **heç vaxt** GitHub-a getməməlidir:

- `backend/.env`
- `backend/client_secret.json`
- `backend/venv/`
- `backend/accessbank.db`
- `backend/data/chroma/`

Əgər terminal loglarında **Telegram bot token** və ya **Gmail secret** görünübsə, push etməzdən əvvəl:

1. [@BotFather](https://t.me/BotFather) → `/revoke` → yeni token → `.env`-ə yazın
2. Google Cloud → OAuth client secret **rotate** → `get_token.py` yenidən

---

## Addım 1: GitHub-da repo yaradın

1. https://github.com/new
2. Repository name: `accessbank-agent` (və ya istədiyiniz ad)
3. **Private** seçin (hackathon üçün tövsiyə olunur)
4. README, .gitignore əlavə **etməyin** (layihədə artıq var)

---

## Addım 2: Terminal əmrləri

Layihə qovluğunda (hər sətir ayrıca):

```bash
cd /Users/madat/Documents/accessbanktg/accessbank-agent

git init
git add .
git status
```

`git status`-da **görməməlisiniz**: `.env`, `client_secret.json`, `venv/`, `*.db`

Yoxlama:

```bash
chmod +x scripts/check-secrets.sh
./scripts/check-secrets.sh
```

Commit:

```bash
git commit -m "Initial commit: AccessBank AI customer support agent"
```

Remote (öz GitHub istifadəçi adınızı yazın):

```bash
git branch -M main
git remote add origin https://github.com/SIZIN_USERNAME/accessbank-agent.git
git push -u origin main
```

---

## GitHub CLI ilə (alternativ)

```bash
cd /Users/madat/Documents/accessbanktg/accessbank-agent
git init && git add . && ./scripts/check-secrets.sh
git commit -m "Initial commit: AccessBank AI customer support agent"
gh repo create accessbank-agent --private --source=. --push
```

---

## Push sonrası

- Repo **Private** qalsın
- Collaborators yalnız hackathon komandası
- `.env.example` GitHub-da qalır (dəyərlər boş) — bu düzgündür

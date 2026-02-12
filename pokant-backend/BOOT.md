# Booting Pokant Backend & Frontend

## Quick start (backend only, no DB)

```bash
cd pokant-backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- **API docs:** http://127.0.0.1:8000/docs  
- **Health:** http://127.0.0.1:8000/health (returns 503 until Postgres/Redis are up)

## Full stack (Postgres + Redis + backend + frontend)

### 1. Start Postgres & Redis

```bash
cd pokant-backend
docker compose up -d db redis
# Wait a few seconds, then:
.venv/bin/python -m scripts.init_db
```

### 2. Start backend

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. Start frontend (static demo)

```bash
cd ../pokant-landing-page/public
python3 -m http.server 3000
```

- **Frontend:** http://localhost:3000/setup.html (demo flow: setup → dashboard → testing → results)  
- **API:** http://127.0.0.1:8000/docs  

### 4. Optional: Celery worker (background analysis)

```bash
cd pokant-backend
.venv/bin/celery -A app.celery_app worker --loglevel=info
```

## Environment

Copy `.env.example` to `.env` and set at least:

- `DATABASE_URL` – Postgres connection string (default: `postgresql://postgres:password@localhost:5432/pokant`)
- `ENCRYPTION_KEY` – for encrypting API keys (generate: `python -c "from app.services.encryption import generate_key; print(generate_key())"`)
- `CLAUDE_API_KEY`, `OPENAI_API_KEY` – for analysis and variant generation

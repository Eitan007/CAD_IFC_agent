# Run locally (bare metal)

Docker is optional. Use **2 terminals** (plus a database).

## 0. Database (pick one)

Your `.env` uses **Neo4j** (`DB_BACKEND=neo4j`). Neo4j must be running on your machine.

In `bim_assistant/.env` set:

```env
NEO4J_URI=bolt://localhost:7687
```

Install Neo4j Community locally, or use Neo4j Desktop, default password `bim_secret` (or match `NEO4J_PASSWORD` in `.env`).

**Or** switch to Postgres: `DB_BACKEND=postgres` and `POSTGRES_URL=postgresql+asyncpg://bim:bim_secret@localhost:5432/bim_db` with local Postgres running.

## 1. Backend API (terminal 1)

```bash
cd bim_assistant
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/seed_db.py   # once
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Check: http://localhost:8000/health

## 2. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — Vite proxies `/api` to port 8000.

## Vercel tunnel from WSL

After installing and authenticating [ngrok](https://ngrok.com/docs/getting-started/) in Windows PowerShell, start the full local stack and tunnel with:

```bash
./start_main.sh
```

It opens a separate Windows PowerShell window running `ngrok http 8000`, then starts the normal `start_dev.sh` tmux session. Keep the ngrok window open while Vercel needs access to the local API.

## Env checklist

| Where | Variables |
|-------|-----------|
| `bim_assistant/.env` | `ANTHROPIC_API_KEY`, `NEO4J_URI` → `localhost` |
| `frontend/.env` | `VITE_API_URL` empty = use Vite proxy |

## Docker (unchanged)

```bash
cd bim_assistant && docker compose up --build -d
```

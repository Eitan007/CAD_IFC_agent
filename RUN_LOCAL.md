# Run locally (bare metal)

Docker is optional. Use **3 terminals** (plus a database).

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

## 2. LiveKit voice worker (terminal 2)

Only needed for the **Voice** tab. Uses LiveKit Cloud (not a local LiveKit server).

```bash
cd livekit-voice-agent
# if you already have .venv from uv:
source .venv/bin/activate
# else:
# uv sync && source .venv/bin/activate

export BIM_API_BASE=http://127.0.0.1:8000
# LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET from .env (load_dotenv in agent.py)

python agent.py dev
# or un run agent.py dev
```

## 3. Frontend (terminal 3)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — Vite proxies `/api` to port 8000.

## Env checklist

| Where | Variables |
|-------|-----------|
| `bim_assistant/.env` | `ANTHROPIC_API_KEY`, `NEO4J_URI` → `localhost`, `LIVEKIT_*` for voice tokens |
| `livekit-voice-agent/.env` | Same `LIVEKIT_*`, optional `BIM_API_BASE` |
| `frontend/.env` | `VITE_API_URL` empty = use Vite proxy |

## Docker (unchanged)

```bash
cd bim_assistant && docker compose up --build -d
```

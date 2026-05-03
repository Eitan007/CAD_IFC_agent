# BIM/CAD AI Assistant

A minimal, production-extensible AI-powered BIM/CAD assistant that parses IFC/STEP files, stores building elements in a graph/relational database, and exposes an LLM agent that answers queries via deterministic tool calls.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                       │
│         /upload  /process  /query  /tasks                   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  Ingestion Layer                             │
│   IFC/STEP/DWG/RVT → IfcOpenShell / OpenCascade / FreeCAD   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│               Normalization Layer                            │
│   Elements · Properties · Relationships · Derived metrics    │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴──────────────┐
         │                              │
┌────────▼────────┐           ┌─────────▼────────┐
│  Neo4j (graph)  │    OR     │  PostgreSQL+JSONB │
│  (preferred)    │           │  (MVP)            │
└────────┬────────┘           └─────────┬─────────┘
         └───────────────┬──────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Tool Layer (deterministic Python)               │
│  get_elements · get_quantities · estimate_cost               │
│  generate_schedule · check_compliance                        │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              LLM Agent Layer (Claude / GPT-4o)               │
│   User query → tool selection → chained calls → answer       │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              RAG Layer (optional)                            │
│   Building codes · Cost DBs · Chroma / pgvector              │
└─────────────────────────────────────────────────────────────┘

⚠ LLM NEVER receives raw IFC/STEP — only structured tool outputs
```

---

## Folder Structure

```
bim_assistant/
├── app/
│   ├── main.py                    # FastAPI entrypoint
│   ├── config.py                  # Settings (env vars)
│   ├── api/
│   │   ├── upload.py              # /upload endpoint
│   │   ├── process.py             # /process endpoint
│   │   ├── query.py               # /query endpoint
│   │   └── tasks.py               # /tasks endpoint
│   ├── ingestion/
│   │   ├── converter.py           # Native CAD → IFC/STEP
│   │   └── ifc_parser.py          # IfcOpenShell parsing
│   ├── normalization/
│   │   ├── normalizer.py          # Unified schema builder
│   │   └── schema.py              # Pydantic models
│   ├── storage/
│   │   ├── database.py            # DB connection + session
│   │   ├── models.py              # SQLAlchemy / Neo4j models
│   │   └── repository.py         # CRUD operations
│   ├── tools/
│   │   ├── elements.py            # get_elements, get_by_type
│   │   ├── quantities.py          # get_material_quantities
│   │   ├── cost.py                # estimate_cost
│   │   ├── schedule.py            # generate_schedule
│   │   └── compliance.py         # check_compliance
│   ├── agent/
│   │   ├── agent.py               # LLM agent + tool routing
│   │   └── tool_definitions.py   # Tool schemas for LLM
│   ├── rag/
│   │   └── retriever.py           # Optional RAG (building codes)
│   └── utils/
│       ├── file_utils.py
│       └── logging.py
├── tests/
│   ├── test_parser.py
│   ├── test_tools.py
│   └── test_agent.py
├── scripts/
│   └── seed_db.py
├── data/
│   ├── uploads/                   # Uploaded CAD files
│   └── processed/                 # Parsed JSON output
├── docs/
│   └── example_flow.md
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Docker | 24+ (for Postgres/Neo4j) |
| IfcOpenShell | 0.7.x |

---

### Docker (API + Postgres)

Requires [Docker Desktop](https://docs.docker.com/desktop/) (or Docker Engine) with WSL 2 integration enabled if you develop inside WSL.

```bash
cd bim_assistant
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY or OPENAI_API_KEY for /query features.

mkdir -p data/uploads data/processed
docker compose up --build -d
```

The Compose file sets `POSTGRES_URL` to use the `postgres` service hostname (you can keep `localhost` in `.env` for local non-Docker runs; Compose overrides it for the API container).

- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Neo4j **starts with the same Compose stack** (Bolt on **7687**, Browser **7474**). To use it as storage, set `DB_BACKEND=neo4j` and `NEO4J_URI=bolt://neo4j:7687` in `.env` for the API container (Compose injects `NEO4J_URI` automatically).

Postgres is exposed on host port **5433** (not 5432) so it does not conflict with an existing local Postgres.

If **8000** is already taken on your machine, publish the API on another host port and point the frontend dev proxy at it:

```bash
BIM_API_HOST_PORT=8001 docker compose up --build -d
cd ../frontend && BIM_API_PROXY_TARGET=http://127.0.0.1:8001 npm run dev
```

---

### macOS

```bash
# 1. Clone and enter project
git clone <repo> && cd bim_assistant

# 2. Create virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY (or OPENAI_API_KEY), DB_URL

# 5. Start backing services
docker-compose up -d postgres  # or neo4j

# 6. Initialise DB schema
python scripts/seed_db.py

# 7. Run the API
uvicorn app.main:app --reload --port 8000
```

### Windows (PowerShell)

```powershell
# 1. Clone and enter project
git clone <repo>; cd bim_assistant

# 2. Create virtual environment
python -m venv .venv; .\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
Copy-Item .env.example .env
# Edit .env with your keys

# 5. Start Docker services
docker-compose up -d postgres

# 6. Initialise DB
python scripts/seed_db.py

# 7. Run API
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for the interactive Swagger UI.

---

## Example Queries

```bash
# Upload a file
curl -F "file=@building.ifc" http://localhost:8000/upload

# Trigger processing
curl -X POST http://localhost:8000/process -H "Content-Type: application/json" \
  -d '{"file_id": "abc123"}'

# Ask the LLM agent
curl -X POST http://localhost:8000/query -H "Content-Type: application/json" \
  -d '{"query": "How much concrete is used in this building?", "project_id": "abc123"}'

# Run a predefined workflow
curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" \
  -d '{"task": "cost_estimation", "project_id": "abc123"}'
```

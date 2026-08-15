# DevTrack AI — Backend Foundation Engine

Production-ready, clean-architecture backend foundation built with **FastAPI**, **Async SQLAlchemy 2.0**, **Alembic**, **PostgreSQL**, **Redis**, **Docker**, and **Docker Compose**.

---

## 🏗️ Architecture Overview (Clean Architecture)

```
app/
├── api/
│   └── v1/
│       ├── endpoints/
│       │   └── health.py       # Health check endpoints (/health, /health/live, /health/ready)
│       └── router.py           # API v1 router aggregator
├── core/
│   ├── config.py               # Type-safe pydantic-settings configuration
│   ├── exceptions.py           # Custom domain and application exceptions
│   ├── handlers.py             # Global FastAPI exception handlers
│   ├── logging.py              # Structured JSON/Console logging setup
│   └── redis.py                # Async Redis connection pool & DI provider
├── db/
│   ├── base.py                 # DeclarativeBase & UUID/Timestamp BaseModel
│   └── session.py              # Async SQLAlchemy 2.0 engine & get_db DI
├── domain/                     # Core Domain Entities & Business Rules
├── repositories/               # Data Access Interfaces & Implementations
└── services/                   # Application Business Logic Services
```

---

## 🚀 Quick Start (Local Setup)

### Option 1: Docker Compose (Recommended)

To spin up the application along with PostgreSQL 16 and Redis 7 in containers:

```bash
docker compose up --build -d
```

Access API Documentation:
- **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc UI:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Aggregated Health Check:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **Readiness Probe:** [http://localhost:8000/api/v1/health/ready](http://localhost:8000/api/v1/health/ready)

### Option 2: Local Python Environment

1. **Create Virtual Environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Environment Variables:**
   Copy `.env.example` to `.env` and adjust database/redis hosts as needed:
   ```bash
   cp .env.example .env
   ```

4. **Run Database Migrations:**
   ```bash
   alembic upgrade head
   ```

5. **Start Dev Server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

---

## 🛡️ Health & Diagnostic Endpoints

| Endpoint | Purpose | SLA / Behavior |
| :--- | :--- | :--- |
| `GET /api/v1/health` | Aggregated Health Summary | Checks app, DB query (`SELECT 1`), and Redis ping |
| `GET /api/v1/health/live` | Liveness Probe | Confirms FastAPI process is alive |
| `GET /api/v1/health/ready` | Readiness Probe | Returns 200 OK if DB & Redis connections succeed, 503 if failing |

---

## 🔧 Database Migrations (Alembic)

Generate a new migration script:
```bash
alembic revision --autogenerate -m "create_initial_tables"
```

Apply migrations to database:
```bash
---

## 🧪 Development & Demo Data

To populate your local development PostgreSQL database with realistic demo data (Organization, Users, Projects, Kanban Board, 25+ Issues, Subtasks, Dependencies, Comments, Labels, and Saved Searches):

```bash
# Via Python Virtual Environment
python -m app.scripts.seed_demo

# Or via Docker Container
docker compose exec api python -m app.scripts.seed_demo
```

### 🔑 Demo Login Credentials

| Role | Email | Password |
|---|---|---|
| **Admin / Owner** | `demo@devtrack.ai` | `DemoPass123!` |
| **Project Manager** | `pm@devtrack.ai` | `DemoPass123!` |
| **Developer** | `dev@devtrack.ai` | `DemoPass123!` |

> **Note:** Demo data seeding is idempotent and safe for local development use only. It will never run in production environments.


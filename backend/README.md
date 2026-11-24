# HealthSpeak AI — Backend (Phase 1)

FastAPI + PostgreSQL backend for HealthSpeak AI. Phase 1 contains only the
skeleton: configuration, a database connection, migrations and health checks.
There are **no users, patients or intake features yet** (they start in Phase 2),
and the React frontend is **not connected** to this API yet.

## What runs where

| Piece | How it runs | Address |
|---|---|---|
| PostgreSQL 17 | Docker container `healthspeak-db` | `127.0.0.1:5432` |
| FastAPI API | Python on your machine (`.venv`) | `http://127.0.0.1:8000` |
| React frontend | `npm.cmd run dev` (unchanged) | `http://localhost:5173` |

## Folder layout

```
backend/
├── app/
│   ├── main.py              # creates the FastAPI app, CORS, registers routers
│   ├── core/config.py       # settings read from the repo-root .env file
│   ├── database/
│   │   ├── base.py          # SQLAlchemy Base that future models inherit from
│   │   └── session.py       # engine + get_db() per-request session
│   └── routers/health.py    # GET /api/health and GET /api/health/db
├── alembic/                 # database migrations (versions/ holds each change)
├── alembic.ini
├── tests/test_health.py
├── pytest.ini
└── requirements.txt
```

## First-time setup

Use **PowerShell**, starting in the repository root
(`...\HealthSpeakAI\healthspeak-ai`). Docker Desktop must be running.

1. **Create your `.env`** (skip if it already exists):
   ```powershell
   Copy-Item .env.example .env
   ```
   Open `.env` and change `change-me-local-dev-password` to your own password
   **in both places** (`POSTGRES_PASSWORD` and inside `DATABASE_URL`).
   `.env` is ignored by Git — never commit it.

2. **Start PostgreSQL:**
   ```powershell
   docker compose up -d
   docker compose ps
   ```
   Success: `healthspeak-db` shows `Up ... (healthy)`. The first run downloads
   the `postgres:17` image, which takes a minute.

3. **Install the Python packages** into the project's virtual environment:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   ```
   (If `.venv` doesn't exist yet: `py -3.12 -m venv .venv` first.)

4. **Apply database migrations:**
   ```powershell
   cd backend
   ..\.venv\Scripts\python.exe -m alembic upgrade head
   ..\.venv\Scripts\python.exe -m alembic current
   ```
   Success: the last line shows `0001 (head)`.

## Everyday commands (run from `backend\`)

```powershell
# Start the API (auto-reloads when you edit code). Stop it with Ctrl+C.
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Run the tests
..\.venv\Scripts\python.exe -m pytest -v
```

With the API running, open in a browser:

- <http://127.0.0.1:8000/api/health> → `{"status":"ok",...}`
- <http://127.0.0.1:8000/api/health/db> → `{"status":"ok","database":"connected"}`
- <http://127.0.0.1:8000/docs> → interactive API documentation

## Stopping the database

```powershell
docker compose down      # stops the container, KEEPS your data
```

**Do not** run `docker compose down -v` — the `-v` deletes the database volume
and all its data permanently.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `/api/health/db` returns 503 `Database unavailable` | PostgreSQL isn't running → `docker compose up -d`, then check `docker compose ps`. |
| `password authentication failed` | The password in `DATABASE_URL` doesn't match `POSTGRES_PASSWORD`. Note: PostgreSQL only reads `POSTGRES_PASSWORD` the *first* time the volume is created. |
| Commands hang when connecting | Make sure `DATABASE_URL` uses `127.0.0.1`, not `localhost` (on Windows, `localhost` tries IPv6 first and Docker only listens on IPv4). |
| Port 5432 or 8000 already in use | Change `POSTGRES_PORT` (and the port in `DATABASE_URL`) in `.env`, or run uvicorn with a different `--port`. |

## Adding database tables later (Phase 2+)

1. Create a model class inheriting from `app.database.base.Base`.
2. Import the model module in `alembic/env.py` (see the comment there).
3. `..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "add users"`
4. Review the generated file in `alembic/versions/`, then `alembic upgrade head`.

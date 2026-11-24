# HealthSpeak AI

A multilingual (English / Hindi / Urdu) patient-intake and clinic-queue system.
Patients describe their symptoms by typing or speaking; the server transcribes and
translates locally, produces a **traceable, rule-based** summary and a department
suggestion, and staff review everything before it is acted on.

> **Safety:** HealthSpeak AI does not diagnose, prescribe, or give medical advice.
> All AI-generated text is labelled *unreviewed* until staff confirm it. Use only
> synthetic data until the limitations below have been addressed.

## Architecture

| Layer | Technology | Runs as |
|---|---|---|
| Frontend | React 18 + Vite, i18next (EN/HI/UR, Urdu RTL) | `npm.cmd run dev` → `http://localhost:5173` |
| Backend API | FastAPI, SQLAlchemy, Alembic | `uvicorn` → `http://127.0.0.1:8000` |
| Database | PostgreSQL 17 | Docker container via `compose.yaml` |
| Speech-to-text | Whisper (local, via `transformers`) | inside the backend process |
| Translation | IndicTrans2 (local, needs a Hugging Face login) | inside the backend process |

Everything runs on your own machine: no audio or text is sent to a cloud AI service.

```text
healthspeak-ai/
├── src/                 # React app
│   ├── pages/           #   patient / staff / doctor / admin screens
│   ├── services/        #   API client modules (auth, intake, visits, kiosk, admin)
│   ├── i18n/            #   en.json, hi.json, ur.json
│   └── components/
├── backend/             # FastAPI app — see backend/README.md
│   ├── app/             #   routers, services, schemas, database models, ai/
│   ├── alembic/         #   database migrations
│   └── tests/           #   pytest suite
├── e2e/                 # browser end-to-end tests (Edge/Chrome via CDP)
├── compose.yaml         # PostgreSQL
├── .env.example         # copy to .env
└── HealthSpeak_AI_CONTEXT.md   # project brief and phase plan
```

### What it does

- **Roles:** patient, doctor, staff, admin — enforced on the backend, not just hidden in the UI.
- **Patients:** sign-up/login, profile, consent history, typed or spoken intake in their own language, visit status and queue token.
- **Speech and translation:** original transcript and English translation are stored separately; the patient approves or edits the transcript before submission; raw audio is deleted right after transcription.
- **Structured intake:** a rule-based extractor quotes the patient's own words (reported vs. denied symptoms, duration, severity, medicines, allergies, what was *not* mentioned) and suggests a department from configurable routing rules. Tied or empty matches are flagged for staff.
- **Staff:** review, correct, confirm and route intakes; queue management; doctor schedules; appointments; notifications.
- **Admin:** user management, departments and routing rules, kiosk registration, system health.
- **Hardening:** Argon2id passwords, expiring sessions, login lockout, audit events, upload checks by file content, retention maintenance job.

## Quick start (Windows, PowerShell)

Prerequisites: **Node.js LTS**, **Python 3.12**, **Docker Desktop** (running), and
Git. Run everything from the repository root unless stated.

1. **Configure** — copy the example file and set your own passwords
   (`POSTGRES_PASSWORD`, the password inside `DATABASE_URL`, `SEED_DEMO_PASSWORD`):
   ```powershell
   Copy-Item .env.example .env
   ```
   `.env` is Git-ignored. Never commit it.

2. **Start PostgreSQL:**
   ```powershell
   docker compose up -d
   docker compose ps          # wait for "healthy"
   ```

3. **Install and prepare the backend:**
   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   cd backend
   ..\.venv\Scripts\python.exe -m alembic upgrade head
   ..\.venv\Scripts\python.exe -m app.seed        # synthetic demo accounts
   ```

4. **Start the API** (still in `backend\`):
   ```powershell
   ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```
   Check <http://127.0.0.1:8000/api/health/db> and the API docs at <http://127.0.0.1:8000/docs>.

5. **Start the frontend** (new terminal, repository root):
   ```powershell
   npm.cmd install
   npm.cmd run dev
   ```
   Open <http://localhost:5173>.

Demo accounts (synthetic, password = your `SEED_DEMO_PASSWORD`):

| Role | Email |
|---|---|
| patient | `patient@example.com` |
| doctor | `doctor@example.com` |
| staff | `staff@example.com` |
| admin | `admin@example.com` |

### Optional: local AI models

Speech recognition and translation are optional; without them the app still works
with typed intake and reports each model as *unavailable* at `GET /api/ai/status`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-ai.txt
```

Then follow **Local voice and translation** in [backend/README.md](backend/README.md)
for model download, the Hugging Face login the translation model needs, and the
optional GPU (CUDA) setup. Voice also needs **ffmpeg** installed and on your PATH (`ffmpeg -version`).

## Testing

| What | Command | Needs |
|---|---|---|
| Backend unit + API + migration + security tests | `cd backend; ..\.venv\Scripts\python.exe -m pytest -v` | PostgreSQL running |
| Frontend production build | `npm.cmd run build` | Node |
| Browser end-to-end (EN/HI/UR, Urdu RTL, kiosk) | `node e2e/run-all.mjs` | DB, API, frontend running, demo data, Edge or Chrome |

Tests use synthetic data. `pytest` uses a separate `healthspeak_test` database; the
e2e tests write synthetic records to your development database. A passing frontend
build says nothing about the backend — run the other two as well.

## Documentation

- [backend/README.md](backend/README.md) — setup details, full API list by phase, AI models, queue/appointments, i18n/kiosks, troubleshooting, adding migrations.
- [HealthSpeak_AI_CONTEXT.md](HealthSpeak_AI_CONTEXT.md) — project brief, safety rules, phase plan.
- Interactive API reference: `/docs` on the running backend.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/api/health/db` returns 503 | PostgreSQL isn't running: `docker compose up -d`. |
| `password authentication failed` | Password in `DATABASE_URL` differs from `POSTGRES_PASSWORD`. Postgres only reads `POSTGRES_PASSWORD` when the volume is first created. |
| Commands hang connecting to the DB | Use `127.0.0.1`, not `localhost`, in `DATABASE_URL` (Windows tries IPv6 first). |
| Port 5432 / 8000 / 5173 in use | Change `POSTGRES_PORT` and `DATABASE_URL`, or pass another `--port`. |
| Frontend can't reach the API | Check `CORS_ORIGINS` and `VITE_API_BASE_URL` in `.env`, then restart both servers. |
| Voice or translation says *unavailable* | See `GET /api/ai/status` (staff/admin) for the reason; install `requirements-ai.txt` and download the models. |

Never run `docker compose down -v` casually — it deletes the database volume.

## Known limitations

- **Translation is not verified with the real model.** The gated IndicTrans2 model needs a Hugging Face login; the code path has only been tested with a stand-in engine. Check medical vocabulary and Hindi/Urdu–English code-switching before relying on it.
- **Hindi and Urdu speech recognition is untested.** Only synthetic English audio has been used. Whisper-small quality on Hindi/Urdu speech, accents and noisy clinics is unknown.
- **The symptom lexicon and department routing rules are DRAFT** and need clinical review. The "attention" flags are a visibility aid, not triage.
- **Hindi and Urdu UI strings need native-speaker review.**
- **Not a medical device.** No diagnosis, prescribing or emergency handling. Do not use for real patient care.
- **Single-machine setup.** A clean install on a second machine has not been verified yet.
- **Notifications are recorded in-app only**; no SMS/email/WhatsApp delivery is connected.
- Speech runs roughly in real time on CPU (≈35 s for a 44 s recording on the development PC); a GPU is recommended for busy use.

## Deployment requirements (before any real use)

- HTTPS in front of the API and frontend; set `APP_ENV=production`; restrict `CORS_ORIGINS` to the real frontend origin.
- Strong, unique secrets; secret storage outside the repository; no demo accounts (do not run `app.seed`).
- A managed, backed-up, access-controlled PostgreSQL (not the development container), with encryption at rest.
- A documented consent, retention and deletion policy, and a scheduled run of the maintenance commands (`python -m app.maintenance purge-sessions|purge-audio|status`, run from `backend\`).
- Legal and privacy review for the jurisdiction (health data), clinical sign-off on the lexicon and routing rules, and a security review/penetration test.
- Audio storage outside synced folders (default `%LOCALAPPDATA%\HealthSpeakAI\audio`), and `AUDIO_KEEP_AFTER_PROCESSING=false` unless policy says otherwise.
- Monitoring and log handling that keeps patient text out of logs.

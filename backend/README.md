# HealthSpeak AI — Backend

FastAPI + PostgreSQL backend for HealthSpeak AI.

| Phase | Status |
|---|---|
| 1 — Skeleton, database, health checks | done |
| 2 — Users, login/logout, roles, UI-language preference | done |
| 3 — Patient profiles, consent history; React login + sign-up connected | done |
| 4 — Conversations, intake submission, staff review/correction/confirmation | done |
| 5 — Local speech recognition (working) and translation (code ready, model needs your HF login) | partly |
| 6 — Structured intake, traceable summary, configurable department suggestion | done |
| 7 — Queue tokens, doctor schedules, appointments, notifications, dashboards | done |
| 8 — English/Hindi/Urdu UI, Urdu RTL, kiosks + system health, accessibility | done (translations need native review) |

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
│   ├── seed.py              # creates synthetic demo users
│   ├── core/
│   │   ├── config.py        # settings read from the repo-root .env file
│   │   ├── enums.py         # Role, UiLanguage
│   │   ├── security.py      # Argon2id hashing, session tokens, phone/email normalising
│   │   └── permissions.py   # get_current_user (401) and require_roles (403)
│   ├── database/
│   │   ├── base.py          # SQLAlchemy Base that every model inherits from
│   │   ├── session.py       # engine + get_db() per-request session
│   │   └── models/          # users, auth_sessions, audit_events
│   ├── schemas/             # request/response shapes (validation)
│   ├── services/            # business logic (auth, users, audit)
│   └── routers/             # health, auth, users, admin_users
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
   Success: the last line shows the newest revision followed by `(head)`.

5. **Create the synthetic demo accounts** (still in `backend\`):
   ```powershell
   ..\.venv\Scripts\python.exe -m app.seed
   ```
   This uses `SEED_DEMO_PASSWORD` from `.env` for all four accounts:

   | Role | Email | Phone |
   |---|---|---|
   | patient | `patient@example.com` | `9000000001` |
   | doctor | `doctor@example.com` | `9000000002` |
   | staff | `staff@example.com` | `9000000003` |
   | admin | `admin@example.com` | `9000000004` |

   These are made-up accounts for local development only. Running the command
   again does nothing to accounts that already exist.

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

## Trying login in the browser (`/docs`)

1. Open <http://127.0.0.1:8000/docs>.
2. `POST /api/auth/login` → **Try it out** → body
   `{"identifier": "admin@example.com", "password": "<SEED_DEMO_PASSWORD>"}` → **Execute**.
3. Copy `access_token` from the response, click **Authorize** (top right), paste it, **Authorize**.
4. Now `GET /api/users/me` and `GET /api/admin/users` work. Log in as the patient
   instead and `GET /api/admin/users` returns **403 Not permitted**.

## API so far

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/health`, `GET /api/health/db` | anyone | API / database up? |
| `POST /api/auth/login` | anyone | `{identifier, password}` (email or phone) → token |
| `POST /api/auth/logout` | logged in | Revokes the current token |
| `GET /api/users/me` | logged in | Own profile |
| `PATCH /api/users/me/preferences` | logged in | `{ui_language: "en" \| "hi" \| "ur"}` for this user only |
| `GET /api/admin/users` | admin | List users (`?role=doctor&limit=50&offset=0`) |
| `POST /api/admin/users` | admin | Create an account |
| `GET /api/consent/current?language=hi` | anyone | Current consent wording + version (en/hi/ur) |
| `POST /api/patients/register` | anyone | Patient sign-up: account + profile + consent in one step, returns a token |
| `GET/PATCH /api/patients/me` | patient | Own profile |
| `GET/POST /api/patients/me/consents` | patient | Own consent history / grant or withdraw |
| `POST /api/patients` | staff | Register a walk-in patient (no login account) |
| `GET /api/patients?q=` | staff | Search by name or phone |
| `GET/PATCH /api/patients/{id}` | staff | View (audited) / correct a patient |
| `GET/POST /api/patients/{id}/consents` | staff | Consent history / record consent on the patient's behalf |

| `POST /api/conversations` | patient | Resume the open conversation or start one (needs valid consent) |
| `GET /api/conversations/{id}` | owner patient | Conversation with messages |
| `POST /api/conversations/{id}/messages` | owner patient | `{content, language, input_mode}` → stored message + fixed acknowledgement |
| `POST /api/conversations/{id}/submit` | owner patient | Creates the intake (awaiting staff review) |
| `GET /api/patients/me/intakes` | patient | Own submissions and their review status |
| `GET /api/intakes?review_status=pending_review` | staff | Review list, oldest first |
| `GET /api/intakes/{id}` | staff | Full intake incl. messages and change history (audited) |
| `PATCH /api/intakes/{id}` | staff | `{final_text, reason}` — staff-reviewed English text |
| `POST /api/intakes/{id}/confirm` | staff | Confirm (optionally with a last edit) |

**Intake text rules:** `original_text` is exactly what the patient typed or
approved and is never changed. `english_text` is a copy when the patient used
English; for Hindi/Urdu it stays empty with `translation_status = pending` until
the local translation phase. `final_text` is the staff-reviewed version — every
change keeps the old and new value in `intake_revisions`. An intake cannot be
confirmed without English text. The chat assistant only sends a fixed
acknowledgement; it never interprets, diagnoses or advises.

**Consent:** the wording lives in `app/core/consent.py` and is a **draft that
must be reviewed by the hospital's legal, privacy and clinical teams**. Each
consent record stores the version the patient saw; consent history is
append-only (withdrawal adds a new row). Changing the wording means bumping
`CONSENT_VERSION`.

**Who sees patient records (for now):** front-desk staff only. Doctors will get
access to patients assigned to them once intake and queue features exist;
administrators manage accounts, not clinical records.

How login works: the server returns a random token valid for
`SESSION_TTL_MINUTES` (8 hours by default). Send it as
`Authorization: Bearer <token>`. The database stores only a SHA-256 hash of it,
so logout and deactivating a user take effect immediately. After 5 wrong
passwords an account is locked for 15 minutes. Every failure returns the same
`401 Invalid credentials` so nobody can probe which accounts exist. Logins,
logouts, failed attempts, preference changes and account creation are written
to the `audit_events` table (never passwords or tokens).

## Local voice and translation (Phase 5)

Everything runs on this computer. The browser records audio and uploads it to
**this** API; nothing is sent to an outside AI service. (The earlier prototype
used the browser's built-in speech recognition, which sends audio to Google or
Microsoft servers — it has been removed.)

**1. Install the AI packages** (from `backend\`, ~200 MB, CPU version):

```powershell
..\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt --extra-index-url https://download.pytorch.org/whl/cpu
```

ffmpeg must be installed and on PATH (`ffmpeg -version`).

**2. Download the speech model** (~1 GB, once per computer):

```powershell
..\.venv\Scripts\python.exe -m app.ai.download_models
```

Models go to the Hugging Face cache (`%USERPROFILE%\.cache\huggingface`), which
is outside this project, so they are never committed or synced by OneDrive.

**3. Translation model (needs your action).** The IndicTrans2 models are
*gated* on Hugging Face:

1. Create a free account at <https://huggingface.co>, open
   <https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M> and accept
   the terms (do the same for the `-1B` model if you want the larger one).
2. Create an access token (Settings → Access Tokens, "Read") and run
   `..\.venv\Scripts\huggingface-cli.exe login`.
3. `..\.venv\Scripts\python.exe -m app.ai.download_models --translation-only`

Until then, Hindi/Urdu intakes are saved with *Translation pending*, the review
screen shows why, and staff can type the English version (or press
**Retry machine translation** after the model is installed).

| Setting | Default | Notes |
|---|---|---|
| Speech model | `openai/whisper-small` (Apache-2.0, 0.97 GB) | Revision pinned |
| Translation model | `ai4bharat/indictrans2-indic-en-dist-200M` (MIT, 0.91 GB) | `...-indic-en-1B` (4.1 GB) is more accurate; set `TRANSLATION_MODEL_ID`/`_REVISION` |
| Device | `auto` (GPU if a CUDA PyTorch is installed) | See GPU note below |
| Audio | max 10 MB / 120 s; webm, ogg, wav, mp3, m4a | Type checked by content, not file name |
| Raw audio | deleted right after transcription | Stored meanwhile in `%LOCALAPPDATA%\HealthSpeakAI\audio` |

**What is stored:** the raw machine transcript (`audio_transcriptions`), the
text the patient approved/edited (the message), and model id/revision, duration,
processing time and a SHA-256 of the audio — but not the audio itself.

**Status:** staff/admin can call `GET /api/ai/status` (add `?load=true` to load
models now) to see whether each model is ready, unavailable, or failed, and why.

**Measured on this development PC** (i7-11700K CPU, CPU-only PyTorch, synthetic
English text-to-speech recordings): model load ≈ 1.5–5 s; a 6 s recording takes
≈ 5–7 s; a 44 s recording ≈ 35 s (roughly real time). Transcription of the
synthetic sample was word-for-word correct.

**Not yet verified (be careful):**
- Hindi and Urdu *speech* recognition quality — no Hindi/Urdu speech samples were
  available (only English voices are installed for synthetic audio). Test with
  synthetic or consented, non-identifying Hindi/Urdu recordings before relying on it.
- Translation output — the gated model could not be downloaded without your
  Hugging Face login, so the translation code path has only been tested with a
  stand-in engine. Check medical vocabulary and Hindi/Urdu–English code-switching.

**GPU (optional, faster):** this PC has an NVIDIA RTX 3070. Installing the CUDA
build of PyTorch (~2.5 GB download) lets `AI_DEVICE=auto` use it:
`..\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu126`

## Structured intake and department suggestion (Phase 6)

When an intake has English text (typed in English, or after translation), the
server runs a **transparent rule-based analysis** — no generative AI model:

- `app/ai/lexicon.py` — approved symptom vocabulary (DRAFT, needs clinical
  review). Only phrases that literally appear are extracted; each item keeps the
  exact source words and their position.
- `app/ai/text_processing.py` — reported vs. **denied** symptoms ("no fever"),
  time and severity words, uncertainty, medicine/allergy sentences (verbatim),
  and a list of what was **not mentioned**. The summary quotes every item and
  says "Not a diagnosis. Requires staff review."
- `app/ai/department_classification.py` — scores departments with routing rules
  from the database. Ties are reported as *ambiguous* (staff must choose); no
  match falls back to the default department, labelled as such. "Attention"
  rules raise a visible flag for words hospital policy marks for prompt staff
  attention (e.g. "chest pain") — a flag, not a triage decision.
- Each run is stored in `intake_analyses` with the source text hash, engine,
  vocabulary and ruleset versions (append-only).

Staff must **choose the department when confirming** (the suggestion is only
pre-selected). Patients only ever see the department staff confirmed.

Default departments/rules (`app/core/default_routing.py`, DRAFT) are created by
`python -m app.seed`. Administrators can change them without code:

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/departments` | staff, doctor, admin | Active departments |
| `GET/POST /api/admin/departments`, `PATCH /api/admin/departments/{id}` | admin | Manage departments (only one default) |
| `GET/POST /api/admin/routing-rules`, `PATCH /api/admin/routing-rules/{id}` | admin | Manage rules (`route`: phrase → department, weight 1–10; `attention`: flag phrase) |
| `POST /api/intakes/{id}/analyse` | staff | Re-run analysis (`{"source": "final_text"}` uses the staff-reviewed text) |
| `POST /api/intakes/{id}/confirm` | staff | Now requires `department_id` |

## Context-aware extraction, symptom review and returning-patient history

**Extraction (`rules-v2`)** still only reports what the patient literally said, but
every symptom mention now carries a status:

| Status | Example | Counts for routing? |
|---|---|---|
| `current` | "I have a cough" | yes |
| `uncertain` | "I think I might have a fever" | yes, flagged for review |
| `negated` | "I do not have fever" | no |
| `historical` | "I had fever last week" | no |
| `third_party` | "my mother has a headache" | no |

Severity, duration, frequency, timing and triggers are attached to a symptom
only when stated in the **same clause** (marked `shared` when the clause names
several symptoms). One-typo spellings ("vomitting") are matched conservatively
(6+ letters, same first letter, never when two symptoms are equally close, with
an ordinary-word stoplist) and flagged for review. Text that matched nothing is
kept verbatim in `extraction.unmatched`. Symptom ids are internal (`hs.fever`);
`external_codes` is empty on purpose: SNOMED/ICD mapping needs a clinical
terminologist and must not be guessed.

**Department suggestion** ignores negated / past / other-person phrases (listed
under `suggestion.excluded`), can return `out_of_scope` or `ambiguous`, lists
`review_reasons`, and **never reports a confidence number** (rule weights are not
probabilities). It is never final: staff choose the department. A trained model
can be plugged in later through `DepartmentClassifier` /
`register_classifier` once a reviewed, labelled dataset exists; none does today.
Urgent escalation stays with the hospital's own workflow; "attention" phrases are
only a visible flag.

**Translation safety.** Machine-translated English is always flagged for review,
and `app/ai/translation_checks.py` warns when a negation word or a number in the
Hindi/Urdu original has no counterpart in the English. The original text is
never overwritten.

**Persistence (migration `0009`, additive only).** `extracted_symptoms` stores
the AI reading (immutable) beside the staff decision (`review_status`,
`confirmed_term`, `confirmed_status`, reviewer, time, note). Each staff change is
also appended to `intake_revisions` (`field = 'symptom'`) and the audit log.
Reviews carry over when an intake is re-analysed. Analyses made before the
migration keep their JSON; "Re-create summary" creates the rows.

**Returning patients.** Each submission is its own intake (encounter) tied to the
patient *record id* of the logged-in account — never matched by name or phone.
History is assembled when read, so earlier encounters are never copied into or
changed by new ones.

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/intakes/{id}/history?limit&offset` | staff | Earlier encounters of the same patient (before this intake) + recurring symptoms; audited |
| `GET /api/patients/{id}/history?limit&offset` | staff | All encounters of one patient; audited |
| `GET /api/patients/me/history?limit&offset` | patient | Own visits, staff-confirmed information only (no AI output) |
| `POST /api/intakes/{id}/symptoms/{symptom_id}/review` | staff | `confirm` / `reject` / `correct` one symptom |
| `POST /api/intakes/{id}/symptoms` | staff | Add a symptom the system missed |

Limits: `limit` 1–50. Symptom changes are refused (409) once an intake is
confirmed. Doctors and admins have no history access yet (doctor access should
follow the queue-assignment rules).

## Queue, appointments, notifications, dashboards (Phase 7)

- **Queue (D5):** confirming an intake puts the patient in that department's
  queue *in the same database transaction*. Tokens count per department per
  hospital-local day (`ORT-001`, `GM-002`; an atomic counter makes concurrent
  requests safe). One active visit per patient per day. Status flow:
  `waiting → checked_in → in_consultation → completed` (or `cancelled` /
  `no_show` before consultation). Staff may make every allowed change; doctors
  may only call in and complete patients **assigned to them**, and cannot see
  anyone else's visits (404).
- **Schedules & appointments (D6):** weekly doctor schedules in local time
  (`HOSPITAL_TIMEZONE`, default `Asia/Kolkata`; stored as UTC). Free slots are
  computed from schedules minus booked appointments; the database refuses two
  booked appointments for one doctor at the same start time. Doctors can mark
  their own appointments completed / no-show, not cancel them.
- **Notifications:** short in-app messages (no clinical details) for: visit
  token, intake reviewed, "it's your turn", appointment booked/cancelled,
  doctor assigned.
- **Dashboards:** staff (today's queue, intakes awaiting review, attention
  flags, appointments, average wait), doctor (own counts), admin (totals by
  role/status/language/department, transcription and translation results, AI
  model state). Dashboards contain counts only — no names or identifiers.
- `python -m app.seed` also gives the demo doctor a synthetic schedule
  (Mon–Sat 09:00–13:00, General Medicine, Room 101).

| Method & path | Who | Purpose |
|---|---|---|
| `POST /api/queue` | staff | Add a patient to today's queue (`patient_id`, `department_id`, optional doctor) |
| `GET /api/queue?status=&q=&day=` | staff (all) / doctor (own) | Today's queue with tokens and position |
| `GET /api/queue/{id}` | staff / assigned doctor | Visit details, confirmed intake, notes (audited) |
| `POST /api/queue/{id}/status` | staff / assigned doctor | Change status (rules above) |
| `PATCH /api/queue/{id}` | staff | Assign/unassign doctor, move department (new token) |
| `POST /api/queue/{id}/notes` | staff / assigned doctor | Care-team note |
| `GET /api/patients/me/visits` | patient | Own token, status, people ahead |
| `GET /api/doctors` | staff, doctor, admin | Doctors and their departments |
| `GET/POST /api/doctor-schedules`, `PATCH .../{id}` | staff, admin (doctors read own) | Weekly schedules |
| `GET /api/appointments/slots?doctor_user_id=&day=` | staff | Free slots |
| `POST /api/appointments` | staff | Book (`starts_at` must include a time-zone offset) |
| `GET /api/appointments?day=` | staff / doctor (own) | Appointments for a day |
| `POST /api/appointments/{id}/status` | staff / own doctor | completed, cancelled, no_show |
| `GET /api/patients/me/appointments` | patient | Own appointments |
| `GET /api/notifications`, `POST .../{id}/read`, `POST .../read-all` | any logged-in user | Own messages |
| `GET /api/dashboard/staff` / `doctor` / `admin` | that role | Aggregated counts |

## Languages, Urdu RTL, kiosks, system health (Phase 8)

**Display languages (frontend, `src/i18n/`):** English, Hindi and Urdu with
react-i18next (`en.json`, `hi.json`, `ur.json` — same keys). Urdu switches the
whole page to right-to-left (`<html dir="rtl">`), mirrors arrows and
direction-dependent spacing, and uses Noto Naskh Arabic; Hindi uses Noto Sans
Devanagari. **The Hindi and Urdu texts have not been reviewed by a native
speaker or clinician yet — please arrange that before real use.**

- Before login the device's language is used (remembered in this browser).
- After login each user's **own** `ui_language` is applied and changes are saved
  to *their* account only (`PATCH /api/users/me/preferences`). A patient picking
  Urdu never changes a doctor's or staff member's screen. Logging out returns to
  the device language.
- The display language is separate from the language a patient **speaks** in
  (chosen on the voice/chat screens).
- Patient-facing pages are fully translated; staff, doctor and admin screens have
  translated navigation, headings and lists, while detailed review panels and
  machine-generated summaries remain in English.
- Known server messages (wrong password, duplicate account, voice errors...)
  are shown translated; other server errors appear in English.

**Kiosks (D8):** an administrator registers a kiosk on the admin dashboard (or
`POST /api/admin/kiosks`) and receives a secret key **once**. Open
`http://<frontend>/?kiosk=<key>` once on the kiosk device: the key is stored on
that device, removed from the address bar, and the kiosk sends a heartbeat every
minute (`POST /api/kiosks/heartbeat`, header `X-Kiosk-Key`) with its microphone
permission state. On a kiosk, a logged-in person is **logged out automatically
after 2 minutes without activity** so the next person never sees their data.
Only the key's SHA-256 hash is stored; keys can be rotated and kiosks
deactivated.

**System health:** `GET /api/admin/system-health` (shown on the admin
dashboard): database, ffmpeg, audio storage (writable / free space), each AI
model's state and reason, failed transcriptions (24 h), pending/failed
translations, and kiosks online.

| Method & path | Who | Purpose |
|---|---|---|
| `POST /api/kiosks/heartbeat` | kiosk device (key) | Heartbeat |
| `GET/POST /api/admin/kiosks`, `PATCH .../{id}`, `POST .../{id}/rotate-key` | admin | Manage kiosks |
| `GET /api/admin/system-health` | admin | Service status |

**Accessibility:** visible keyboard focus, labelled icon-only buttons and form
fields, `aria-live` notifications, reduced-motion support, `lang`/`dir` set on
the page.

## Profile, past history and forgot-password (patients)

- **My Profile** (`GET/PATCH /api/patients/me`): a patient can change name, date of birth, gender and
  speaking language. Mobile number and email are shown read-only (they are the login; changing them
  is done at the front desk). Past visits are never copied from the profile, so editing it cannot
  change them.
- **Past History** (`GET /api/patients/me/history`): its own page, read-only. The dashboard's
  *View* button on a submitted concern opens this page with that visit highlighted.
- **Forgot password by SMS code** (`POST /api/auth/password-reset/request` then `/confirm`):
  patients only. 6-digit code, valid 10 minutes, stored only as a hash, locked after 5 wrong tries,
  one new code per minute and 5 per hour. The request step answers the same for every number. A
  successful reset signs the account out on all devices and clears any login lockout. Staff, doctor
  and admin passwords are still reset by an administrator.
- **Delivery:** `SMS_PROVIDER=console` (default) prints the code in the API window - local demo only,
  refused in production. `SMS_PROVIDER=twilio` sends a real SMS (needs your Twilio account; the Twilio
  call itself is not tested here). Sending phone numbers to an SMS provider is a privacy decision for
  the hospital to approve first.

## Tests

`pytest` uses a separate database named `healthspeak_test` (created
automatically). Tables there are emptied before every test, so your development
data is never touched. The migration test briefly creates and deletes a scratch
database `healthspeak_migration_test`.

Tests never use the real AI models unless you opt in: by default the models are
replaced with stand-ins (and "not installed" behaviour is tested too). To also
run the real Whisper model on the synthetic recording in `tests/fixtures/`:

```powershell
$env:HEALTHSPEAK_AI_TESTS = "1"; ..\.venv\Scripts\python.exe -m pytest -k real_whisper
```

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

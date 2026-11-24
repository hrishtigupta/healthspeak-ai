# HealthSpeak AI --- Project Context for AI Coding Agents

**Document purpose:** Give an AI coding agent the product, technical,
architectural, and workflow context needed to work safely and
consistently on HealthSpeak AI.

**Project status:** Existing React/Vite frontend prototype; backend,
PostgreSQL integration, authentication, and production AI pipeline are
planned work unless the current repository proves otherwise.

------------------------------------------------------------------------

## 1. Agent instructions --- read this first

You are working on **HealthSpeak AI**, an existing healthcare
patient-intake and hospital workflow application.

Your job is to evolve the existing project into a working, maintainable
application. Do not treat this as a greenfield project.

### Non-negotiable rules

1.  **Inspect before editing.** Start by examining the repository,
    package files, source tree, current routes/pages, styling, existing
    components, and Git status. Do not assume this document's proposed
    structure exactly matches the current code.
2.  **Preserve the existing frontend.** Do not delete, replace, or
    unnecessarily redesign the current React/Vite application. Reuse
    existing pages and components wherever practical.
3.  **Do not fabricate completion.** Never say a feature is implemented,
    tested, connected, secure, or production-ready unless you have
    actually implemented and verified it.
4.  **Work in small phases.** Before a substantial change, explain the
    goal, files to be changed, and acceptance criteria. Implement one
    coherent phase, run relevant tests/builds, report results, and then
    continue.
5.  **Avoid giant rewrites.** Prefer incremental refactoring. Do not
    replace the large existing `App.jsx` or the CSS wholesale without
    first understanding dependencies and presenting a migration plan.
6.  **Keep the application runnable.** After frontend changes, run
    `npm.cmd run build` (PowerShell on Windows). After backend changes,
    run the relevant Python tests and verify the API starts.
7.  **Do not expose secrets.** Use environment variables and
    `.env.example`. Never commit `.env`, passwords, API keys, signing
    keys, patient information, audio recordings, or local database
    files.
8.  **Do not commit model weights.** Large AI model files must be
    downloaded separately on each developer machine and excluded from
    Git.
9.  **No external paid AI inference.** The intended speech-recognition
    and translation pipeline should run locally. The React frontend will
    still call the application's own FastAPI backend over HTTP; that is
    normal and is not an external AI inference service.
10. **Healthcare safety is essential.** AI may transcribe, translate,
    organise, summarise, and suggest a department for staff review. It
    must not diagnose, prescribe, or make final clinical decisions.
11. **Do not use real patient data for demos or tests.** Use synthetic
    sample records.
12. **Ask before destructive operations.** Never delete database
    volumes, patient data, user data, migrations, or major code without
    explicit approval. In particular, do not use
    `docker compose down -v` as a routine stop command.
13. **Do not add unnecessary infrastructure.** Start with FastAPI +
    PostgreSQL + the existing frontend. Do not add Redis, Kubernetes,
    microservices, or other infrastructure unless a demonstrated
    requirement justifies it.
14. **Explain commands for a beginner.** State which terminal to use,
    the working directory, the exact command, what success looks like,
    and what to share if it fails.

If an instruction in this document conflicts with the actual repository
state, inspect the repository and explain the discrepancy before
changing anything.

------------------------------------------------------------------------

## 2. Product vision

HealthSpeak AI is a multilingual patient-intake and hospital workflow
management system. It helps patients communicate their concerns in a
language they understand and helps hospital staff organise, review, and
route those concerns.

The product is **not an autonomous medical diagnosis chatbot**.

### Core goals

-   Allow patients to communicate through a simple interface, including
    voice-based intake.
-   Support English, Hindi, and Urdu for patient-facing interactions.
-   Capture speech and produce a transcript.
-   Translate non-English input into English for a common downstream
    processing workflow.
-   Preserve the original transcript and language alongside the English
    translation.
-   Organise patient concerns into structured intake records.
-   Assist with department routing and queue/appointment workflows.
-   Let authorised staff review and correct AI-generated content before
    it is treated as final.
-   Provide role-appropriate dashboards for patients, doctors,
    front-desk/medical staff, and administrators.
-   Support hospital kiosks and monitoring of kiosk/voice-AI service
    status.

### Product principle

**The patient speaks. The system organises. Hospital staff review and
confirm.**

AI output is assistance, not a clinical decision.

------------------------------------------------------------------------

## 3. Existing project and development environment

### Known repository

-   GitHub repository: `https://github.com/muktiporwal/healthspeak-ai`
-   Existing local project has previously been opened from:
    `C:\Users\HP\Downloads\healthspeak-ai-prototype\healthspeak-ai`
-   Confirm the current active workspace path before running commands or
    editing files. The user may have moved or cloned the repository
    since this path was recorded.

### Existing frontend

Known technologies: - React - Vite - JavaScript / JSX - CSS -
`lucide-react`

The frontend prototype has previously included these views/features
(verify current code before relying on this list): - Landing page -
Login and signup - Patient voice-intake experience - Chat/conversation
view - Patient dashboard - Doctor profile/dashboard - Staff dashboard -
Sample patient records - Status updates and notes

At an earlier point, much of the application was concentrated in a large
`App.jsx` file (around 1,600 lines), a stylesheet, and `main.jsx`. This
may have changed. Inspect the current repository.

The frontend previously built successfully using:

``` powershell
npm.cmd run build
```

The browser's Web Speech API (`SpeechRecognition` /
`webkitSpeechRecognition`) was previously used for a prototype
voice-capture feature. It is not automatically the final
speech-recognition architecture. Verify its current implementation and
avoid breaking it while the backend pipeline is developed.

### User's development environment

-   Operating system: Windows 11 (Windows PowerShell / VS Code
    terminal).
-   Docker Desktop: installed.
-   Python: installed. A previous check showed Python 3.12.10 and pip
    25.0 in a project virtual environment; verify current versions.
-   Node.js: installed.
-   VS Code: used for development.
-   Git: used with GitHub.
-   User prefers guided, step-by-step development and is still learning
    backend/database integration.

### PowerShell command note

PowerShell may block `npm.ps1`. Use `npm.cmd`:

``` powershell
npm.cmd install
npm.cmd run dev
npm.cmd run build
```

Do not tell the user to use `npm` if it triggers the PowerShell
execution-policy error; use `npm.cmd`.

### Verify tools before development

Run from a PowerShell terminal:

``` powershell
docker --version
docker compose version
python --version
node --version
npm.cmd --version
git --version
```

Docker Desktop must be open and its engine running before using Docker
Compose.

Hardware checks before selecting/downloading local AI models:

``` powershell
systeminfo | findstr /C:"Total Physical Memory"
Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM
```

Do not assume that the machine has an NVIDIA GPU or enough RAM/VRAM.
Windows' reported adapter memory may not fully represent shared GPU
memory. Assess the machine before recommending large model downloads.

------------------------------------------------------------------------

## 4. User roles and permissions

The system has four primary roles:

### Patient

-   Choose a preferred interface language.
-   Provide intake details and consent.
-   Describe concerns by voice or text.
-   Review their submitted information where appropriate.
-   View their intake/visit status, queue token, or appointment
    information as permitted.

### Doctor

-   Have an independent interface-language preference.
-   View only records they are authorised to access.
-   Review patient intake summaries and source transcripts/translation
    where permitted.
-   Correct or annotate information.
-   Make clinical decisions themselves; AI must not make those
    decisions.

### Front-desk / medical staff

-   Have an independent interface-language preference.
-   Register patients and assist with intake.
-   Review and correct transcription/translation.
-   Confirm or edit structured intake information.
-   Manage routing, queues, tokens, and appointments within their
    permissions.

### Hospital administrator

-   Manage authorised users, roles, departments, rules, schedules, and
    operational settings.
-   View appropriate dashboards/reports.
-   Monitor kiosk and voice-AI service status.
-   Access audit information according to policy.

### Security requirements

-   Implement role-based access control (RBAC) on the backend, not only
    by hiding frontend buttons.
-   Enforce authentication and authorisation for protected API
    endpoints.
-   Use secure password hashing (Argon2id or a well-maintained bcrypt
    implementation).
-   Use appropriately configured, expiring authentication tokens or
    secure sessions.
-   Validate all input on the server.
-   Keep an audit trail for important access and record changes.
-   Apply least-privilege access to patient records.
-   Do not expose patient data in logs, error messages, URLs, or
    analytics.
-   Design consent capture and retention/deletion rules explicitly; do
    not assume consent.
-   Treat healthcare data as sensitive. Before real deployment, obtain
    appropriate legal, security, privacy, and clinical review for the
    jurisdiction and institution.

------------------------------------------------------------------------

## 5. Language requirements --- important

There are **two separate language concepts**. Never mix them up.

### A. Patient-facing and dashboard UI language

The supported patient-facing languages are:

1.  English
2.  Hindi
3.  Urdu

The user should be able to select a UI language. The visible interface
should switch language, including: - Labels - Buttons - Menus -
Validation messages - Status text - Patient-facing instructions -
Relevant dashboard content

Use `react-i18next` (or a compatible i18next setup) with translation
resource files such as:

``` text
src/i18n/
  en.json
  hi.json
  ur.json
```

Do not hardcode user-visible text throughout components if it should be
translated.

#### Urdu RTL

Urdu uses right-to-left layout. Implement RTL deliberately: - Set
document direction to `rtl` when Urdu is selected and `ltr` otherwise. -
Check text alignment, navigation, forms, icons, spacing, tables, and
dashboard layout. - Prefer logical CSS properties
(`margin-inline-start`, `padding-inline-end`, `text-align: start`) over
hardcoded left/right values where appropriate. - Ensure mixed English
numbers, dates, identifiers, and Urdu text remain readable. - Test the
full patient-facing flow in Urdu, not just the language selector.

#### Independent preferences

A patient's selected language must not globally switch the doctor's,
staff's, or administrator's UI. Each authenticated user should have
their own language preference stored with their profile (or equivalent
user settings) and restored after login.

Keep these fields conceptually separate: - `ui_language`: language used
to display the application to this user. - `audio_language` /
`detected_language`: language spoken in the audio. -
`original_transcript`: transcript in the language spoken. -
`english_translation`: English translation used by the processing
pipeline.

### B. Backend processing language

The common downstream processing language is **English**.

Intended flow:

``` text
English audio
  -> speech recognition
  -> original English transcript
  -> English processing pipeline

Hindi audio
  -> speech recognition
  -> original Hindi transcript
  -> translate to English
  -> English processing pipeline

Urdu audio
  -> speech recognition
  -> original Urdu transcript
  -> translate to English
  -> English processing pipeline
```

Important: - Preserve the original transcript exactly as
captured/approved. - Store the original language code. - Store the
English translation separately. - Never overwrite the original
transcript with its translation. - Record processing status,
model/version where practical, timestamps, and any staff correction. -
Staff should be able to review/correct the transcript and translation. -
A correction should be auditable and should not silently erase the
AI-generated version. - English-only downstream processing must not
force the user's dashboard UI to English.

------------------------------------------------------------------------

## 6. AI and language-processing approach

These are **candidate technologies**, not claims that the models are
already installed, tested, or validated.

### Speech recognition candidate

-   Hugging Face model: `openai/whisper-small`
-   Model page: `https://huggingface.co/openai/whisper-small`
-   Use the multilingual model, not `whisper-small.en`, because Hindi
    and Urdu are required.
-   Test real representative Hindi and Urdu samples before committing to
    the model.
-   Evaluate transcription quality, latency, RAM/VRAM use, and
    licensing/deployment constraints.

### Translation candidate

-   Hugging Face model: `ai4bharat/indictrans2-indic-en-1B`
-   Model page:
    `https://huggingface.co/ai4bharat/indictrans2-indic-en-1B`
-   Verify the exact model-card language support and language codes for
    Hindi and Urdu before relying on it.
-   Test medical vocabulary and code-switching (for example, Hindi/Urdu
    mixed with English terms).
-   Do not assume support for Urdu is adequate just because it is an
    Indic translation model.

### Model selection policy

Before downloading any model: 1. Check the user's hardware. 2. Verify
the model card, supported languages, license, size, dependencies, and
inference requirements. 3. Estimate storage, RAM, and VRAM. 4. Run a
small proof-of-concept with synthetic/non-identifying samples. 5. Record
measured performance and limitations. 6. Provide a fallback or clear
unavailable state if the model cannot load.

Do not download multi-gigabyte checkpoints without warning and approval.

### Local-only inference requirement

The intended ASR and translation models run locally on the
machine/server hosting the application. Do not silently send patient
audio or text to an external AI provider.

The frontend may call the application's own FastAPI endpoints. Those
endpoints run the local processing pipeline.

### Text processing and clinical boundaries

Start with transparent, testable Python processing: - Normalisation and
cleaning without changing meaning. - Extraction of explicitly stated
symptoms and relevant details. - Structured intake fields. - A concise
summary that is traceable to the source. - A department suggestion based
on documented, configurable routing rules.

Do not present a rule-based department suggestion as a diagnosis. Do not
infer symptoms the patient did not report. Preserve uncertainty and
missing information. Do not invent duration, severity, medication,
allergies, or medical history.

Do not add a generative medical LLM as a default dependency. If a
summarisation model is considered later, evaluate it separately for
safety, accuracy, privacy, licensing, local hardware, and traceability.

------------------------------------------------------------------------

## 7. Functional workflow

A target patient-intake workflow:

1.  Patient opens the application or kiosk.
2.  Patient selects a UI language (English, Hindi, or Urdu).
3.  Application displays the correct language and text direction.
4.  Patient reads and provides required consent.
5.  Patient provides identifying/registration information according to
    hospital policy.
6.  Patient describes their concern by voice or text.
7.  Backend receives the submission securely.
8.  If voice: local ASR generates a transcript and records the
    detected/selected language.
9.  If the transcript is Hindi or Urdu: translation produces a separate
    English version.
10. English processing organises the information into structured intake
    fields and a summary.
11. The system may suggest a department using transparent rules.
12. An authorised staff member reviews and corrects the transcript,
    translation, summary, and suggested routing.
13. Staff confirms the intake and routes the patient according to
    hospital workflow.
14. The system creates or updates queue/token/appointment information as
    appropriate.
15. Patient and authorised staff see appropriate status updates.
16. Relevant actions are recorded in an audit trail.

The exact workflow must be reconciled with the existing UI and the
hospital's intended operating process before implementation.

------------------------------------------------------------------------

## 8. DFD data stores and process mapping

The user's Level 1 Data Flow Diagram identifies these logical data
stores. Map the backend data model to these concepts. They do not
necessarily need to be eight physical databases or eight separate
database schemas.

  -----------------------------------------------------------------------
  DFD ID                  Logical data store      Purpose / likely
                                                  entities
  ----------------------- ----------------------- -----------------------
  D1                      User Accounts and Roles Users, credentials,
                                                  roles, user
                                                  preferences, account
                                                  status

  D2                      Patient Profiles and    Patient profile,
                          Consent                 identifiers, consent
                                                  records, consent
                                                  history

  D3                      Conversations and       Conversations,
                          Transcripts             messages, audio
                                                  metadata, original
                                                  transcripts,
                                                  translations

  D4                      Intake Records          Structured intake,
                                                  symptoms explicitly
                                                  reported, summaries,
                                                  review/correction
                                                  status

  D5                      Queue and Visit Tokens  Queue entries, token
                                                  numbers, status,
                                                  timestamps, department

  D6                      Appointments and Doctor Appointments, doctor
                          Schedules               availability,
                                                  schedules,
                                                  cancellations

  D7                      Departments and         Departments, routing
                          Knowledge Base          rules, approved
                                                  terminology/reference
                                                  content

  D8                      Kiosk and Voice AI      Kiosk registry/status,
                          Status                  service health, model
                                                  availability,
                                                  processing failures
  -----------------------------------------------------------------------

The DFD includes processes for: - Capturing patient enquiries. -
Transcribing, translating, and cleaning input. - Extracting symptoms and
preparing summaries. - Classifying/suggesting departments. - Registering
and authenticating users. - Reviewing, confirming, and routing
patients. - Managing appointments and doctor availability. - Managing
walk-in queues. - Sending notifications/alerts. - Generating
dashboards/reports. - Monitoring kiosks and Voice AI. - Managing
departments and rules.

Implement only the necessary entities and endpoints for each phase. Do
not create empty routers or tables just to match the diagram.

------------------------------------------------------------------------

## 9. Recommended technical architecture

This is the proposed architecture. Inspect the existing repository and
make changes incrementally.

### Frontend

-   Keep existing React + Vite frontend at the repository root unless
    there is a compelling, agreed reason to move it.
-   Use existing components and styles.
-   Add an organised API/service layer for backend calls.
-   Add i18next for language resources.
-   Keep patient, doctor, staff, and admin UI language preferences
    independent.
-   Use protected routes for usability, but enforce permissions again on
    the backend.
-   Provide loading, empty, validation, and error states.

### Backend

-   Python 3.12
-   FastAPI
-   Pydantic for request/response validation
-   SQLAlchemy 2.x
-   Alembic for database migrations
-   PostgreSQL
-   `psycopg` PostgreSQL driver
-   Uvicorn ASGI server
-   Pytest for tests

Use a clean separation between: - API routers - Schemas - Database
models - Services/business logic - Authentication/security - AI
pipeline - Configuration

Keep business logic out of route handlers where practical.

### Database

-   PostgreSQL is the intended relational database.
-   Use Docker Compose for local PostgreSQL so developers do not need to
    install and configure a database server manually.
-   Store credentials in environment variables.
-   Use migrations for schema changes.
-   Include synthetic seed/demo data only.
-   Do not commit database volumes or database dumps containing personal
    data.

### Local development process

Preferred initial setup: - Docker Compose runs PostgreSQL. - Python
virtual environment runs FastAPI on the host. - `npm.cmd run dev` runs
React/Vite. - Local model weights are downloaded separately when the AI
phase is ready.

This keeps the first setup understandable and avoids containerising
every part prematurely.

### Suggested ports

Choose and document stable ports, checking for conflicts first. A
typical arrangement is: - Frontend Vite: `5173` - FastAPI: `8000` -
PostgreSQL: `5432`

Do not assume these ports are free; verify the current configuration.

------------------------------------------------------------------------

## 10. Suggested repository structure

This is a target direction, not a mandate to create every folder
immediately. Keep the existing frontend structure intact and adapt after
inspection.

``` text
healthspeak-ai/
├── src/                         # Existing React/Vite frontend
│   ├── components/
│   ├── pages/
│   │   ├── patient/
│   │   ├── doctor/
│   │   ├── staff/
│   │   └── admin/
│   ├── services/                 # API client and frontend services
│   ├── i18n/
│   │   ├── en.json
│   │   ├── hi.json
│   │   └── ur.json
│   ├── hooks/
│   ├── context/
│   ├── utils/
│   ├── App.jsx
│   ├── main.jsx
│   └── styles.css
├── public/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                 # Config, security, permissions
│   │   ├── database/             # Connection, base, models
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── ai/
│   │   │   ├── model_loader.py
│   │   │   ├── speech_to_text/
│   │   │   ├── translation/
│   │   │   ├── text_processing/
│   │   │   └── department_classification/
│   │   └── utils/
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── alembic.ini
├── ai_models/                    # Local model files; Git-ignored
├── storage/                      # Local uploads/audio; Git-ignored
├── database/
│   └── seed.sql                  # Optional synthetic seed data
├── docs/
│   ├── architecture/
│   ├── diagrams/
│   └── API_Documentation.md
├── package.json
├── package-lock.json
├── vite.config.js
├── compose.yaml
├── .env.example
├── .gitignore
└── README.md
```

Do not create placeholder files/folders without a concrete use. Adapt
naming to existing conventions.

------------------------------------------------------------------------

## 11. API areas to plan

Design REST endpoints around the actual user workflows. Example areas:

-   Authentication and user profile/preferences.
-   Patient registration and patient profiles.
-   Consent.
-   Conversations and intake submission.
-   Audio upload and transcription.
-   Translation and text processing.
-   Intake review/correction/confirmation.
-   Doctor and staff views.
-   Department and routing rules.
-   Queue and visit tokens.
-   Appointments and schedules.
-   Notifications.
-   Kiosk registration/health status.
-   Dashboards and reports.

For every endpoint: - Define request and response schemas. - Validate
input. - Authenticate and authorise the caller. - Return appropriate
HTTP status codes. - Avoid leaking internal exceptions or sensitive
data. - Add tests for success, invalid input, unauthorised access, and
forbidden access. - Document it in the API docs.

Do not expose an endpoint that lets an unauthorised user fetch arbitrary
patient records.

------------------------------------------------------------------------

## 12. Database and data design principles

-   Use stable primary keys (UUIDs are a reasonable default).
-   Add created/updated timestamps where useful.
-   Use foreign keys and appropriate indexes.
-   Store language codes explicitly and consistently.
-   Separate original transcript, English translation, AI-generated
    summary, and human-corrected/final version.
-   Track review state and who performed the review.
-   Keep a record of consent and its purpose/time/version.
-   Use soft deletion or retention policies only when justified by
    requirements; define them explicitly.
-   Use transactions for multi-step operations such as intake
    confirmation and queue creation.
-   Avoid duplicating patient data unnecessarily.
-   Use UTC for stored timestamps and convert to local time for display.
-   Keep audit records for sensitive actions.
-   Never store passwords in plain text.
-   Never store raw audio indefinitely by default. Retention must be
    consented, justified, configurable, and documented.

Potential statuses should be explicit enums or validated values rather
than arbitrary strings scattered through the code.

------------------------------------------------------------------------

## 13. Security, privacy, and reliability

Minimum expectations: - `.env` is ignored by Git. - `.env.example`
contains variable names and safe placeholders only. - CORS is configured
for known development origins, not unrestricted in production. -
Passwords are securely hashed. - Authentication tokens/session handling
is designed safely. - Role checks happen on the backend. - File upload
size/type limits are enforced. - Audio files are stored outside the
public frontend directory. - Logs do not contain patient audio, full
transcripts, passwords, tokens, or unnecessary identifiers. - Error
messages do not reveal database credentials, stack traces, or sensitive
records to clients. - Database backups and retention are considered
before real deployment. - AI model and processing failures are visible
to staff and do not silently discard patient submissions. - The system
must clearly distinguish unreviewed AI output from staff-confirmed
information.

This is a student/development project until independently reviewed. Do
not claim regulatory compliance or production readiness without
evidence.

------------------------------------------------------------------------

## 14. Git and portability

The project should be reproducible on another developer's machine.

Commit: - Application source code. - `package.json` and
`package-lock.json`. - Backend dependency declarations. - Docker Compose
configuration. - `.env.example`. - Alembic migrations. - Synthetic seed
scripts/data. - Tests. - Setup and troubleshooting documentation.

Do not commit: - `.env` or secrets. - `node_modules/`. - Python
`.venv/`. - Local model weights/checkpoints. - Patient audio,
transcripts, or real patient data. - Local database volumes or dumps
with personal data. - Build output unless the deployment workflow
explicitly requires it.

Each developer machine should have its own local environment and
database unless the team deliberately configures a shared development
database.

Docker Compose commands:

``` powershell
# Start services in the background
docker compose up -d

# View running services
docker compose ps

# View logs
docker compose logs -f

# Stop services but preserve named volumes/data
docker compose down
```

Do not routinely use:

``` powershell
docker compose down -v
```

The `-v` option removes volumes and can permanently delete local
database data.

------------------------------------------------------------------------

## 15. Recommended implementation phases

Work in this order unless repository inspection reveals a dependency
that requires a change. Do not attempt all phases in one massive code
generation.

### Phase 0 --- Repository audit and baseline

-   Inspect Git status and current branch.
-   Inspect project tree and package configuration.
-   Identify current pages, components, state management, routes, mock
    data, and voice-capture implementation.
-   Run the existing frontend build.
-   Record existing issues before changing anything.
-   Produce a short audit report and proposed file-level plan.
-   Do not edit files until the user approves the plan.

**Acceptance:** Existing frontend status and baseline build result are
documented.

### Phase 1 --- Backend skeleton and database

-   Add a FastAPI backend in a separate `backend/` directory.
-   Add environment-based configuration.
-   Add Docker Compose PostgreSQL service and persistent named volume.
-   Add SQLAlchemy database connection/session.
-   Add Alembic and initial migration.
-   Add a health endpoint and database health check.
-   Add `.env.example` and update `.gitignore`.
-   Document setup and commands.

**Acceptance:** PostgreSQL starts with Docker Compose; FastAPI starts;
health endpoint works; backend can connect to the database; frontend
still builds.

### Phase 2 --- Authentication, users, roles, and preferences

-   Add user model and secure password hashing.
-   Add login/logout or token/session workflow.
-   Add roles and backend permission checks.
-   Add user profile and independent UI-language preference.
-   Add synthetic seed users for patient, doctor, staff, and admin.
-   Protect relevant endpoints.

**Acceptance:** Tests prove valid login works and unauthorised/forbidden
requests are rejected.

### Phase 3 --- Patient profile and consent

-   Implement patient profile and consent models/APIs.
-   Define required fields and consent wording with the user.
-   Add audit trail for consent actions.
-   Connect relevant existing frontend forms.

**Acceptance:** Patient data and consent persist in PostgreSQL and can
only be accessed by authorised roles.

### Phase 4 --- Intake and conversation records

-   Implement conversation and intake models.
-   Implement text-based intake submission first.
-   Preserve original user input.
-   Add review status and staff correction history.
-   Connect existing frontend intake flow to the backend.
-   Replace mock data only where the corresponding API is ready; avoid
    breaking unrelated pages.

**Acceptance:** A synthetic intake can be submitted, stored, retrieved
by authorised staff, reviewed, and updated with an audit record.

### Phase 5 --- Local speech recognition and translation

-   Assess hardware and choose the final models.
-   Verify model licenses and supported language codes.
-   Implement local model loading with lazy loading and clear error
    states.
-   Implement audio upload validation and temporary/private storage.
-   Implement English/Hindi/Urdu transcription.
-   Translate Hindi/Urdu transcripts to English.
-   Preserve original transcript, language, translation, and model
    metadata.
-   Add tests using synthetic/non-identifying audio samples.
-   Do not block the entire application if models are unavailable.

**Acceptance:** Test samples demonstrate the end-to-end pipeline and the
original transcript is never overwritten. Report quality and hardware
limitations honestly.

### Phase 6 --- Structured intake, summary, and department suggestion

-   Extract only explicitly stated information.
-   Build traceable summaries.
-   Implement transparent, configurable department rules.
-   Make missing/uncertain information visible.
-   Require staff review/confirmation.
-   Never diagnose or prescribe.

**Acceptance:** Tests cover common, ambiguous, missing-information, and
out-of-scope cases. UI labels suggestions as AI-assisted and unconfirmed
until reviewed.

### Phase 7 --- Queue, appointments, and dashboards

-   Implement queue entries/tokens and status transitions.
-   Implement doctor schedules and appointments.
-   Connect staff/doctor/patient views to authorised APIs.
-   Add notifications only after core state transitions work.
-   Add dashboard aggregates with access controls.

**Acceptance:** Queue and appointment changes persist and are visible
only to authorised users.

### Phase 8 --- i18n, Urdu RTL, kiosk monitoring, and polish

-   Complete English/Hindi/Urdu translations.
-   Implement and test Urdu RTL throughout patient-facing views.
-   Ensure each user has independent UI language preference.
-   Add kiosk/service status monitoring.
-   Improve accessibility, responsive layout, empty/loading/error
    states.

**Acceptance:** End-to-end flows are tested in all three UI languages,
including Urdu RTL.

### Phase 9 --- Hardening and handover

-   Run frontend build and backend tests.
-   Add integration tests and migration verification.
-   Review access control, secrets, uploads, logs, and retention.
-   Document setup, architecture, API endpoints, model installation, and
    troubleshooting.
-   Verify a clean setup on a second machine if possible.
-   List known limitations and deployment requirements.

**Acceptance:** Another developer can follow the README and run the
project without relying on undocumented steps.

------------------------------------------------------------------------

## 16. Testing expectations

At minimum: - Frontend production build. - Backend unit tests. - API
integration tests. - Database migration tests. - Authentication and
role-permission tests. - Language preference isolation tests. - Urdu RTL
UI checks. - Intake submission and review tests. -
Transcript/translation preservation tests. - Invalid audio/file upload
tests. - AI model unavailable/error-path tests. - Synthetic end-to-end
workflow tests.

Never use a successful frontend build as proof that the backend,
database, authentication, or AI pipeline works.

For each phase, report: - What changed. - Files created/modified. -
Commands run. - Actual test/build output. - What is working. - What is
not working or remains mocked. - Any security/privacy concerns. - Exact
next step.

------------------------------------------------------------------------

## 17. How to collaborate with the user

The user is a beginner with backend and database setup but understands
the frontend project and wants to learn while building.

-   Use plain language before introducing technical terminology.
-   Give exact file paths and complete file contents when appropriate.
-   For edits to existing files, inspect and explain the relevant
    existing code first.
-   Avoid telling the user to paste a small snippet at an ambiguous
    location.
-   If a file is large, make a precise patch and explain where it goes.
-   Give one manageable group of steps at a time.
-   State the exact terminal and working directory.
-   Use Windows PowerShell commands.
-   Use `npm.cmd` rather than `npm` where needed.
-   Wait for the user to confirm or share output before moving to a step
    that depends on it.
-   Do not assume the user has completed a command merely because it was
    suggested.
-   When an error occurs, diagnose the actual error before suggesting
    unrelated changes.
-   Do not ask the user to repeat facts already present in this document
    or repository.

When using an agentic coding tool with filesystem access, it may inspect
and edit the workspace. It must still follow the phase boundaries,
preserve the existing frontend, and report actual verification.

------------------------------------------------------------------------

## 18. First task for the coding agent

**Do not start implementing the entire system immediately.**

Begin with this exact task:

1.  Confirm the repository root and current Git branch.
2.  Run `git status --short`.
3.  Inspect the existing file/folder structure (exclude `node_modules`,
    `.git`, `dist`, and other generated folders).
4.  Inspect `package.json`, `vite.config.js`, `src/main.jsx`,
    `src/App.jsx` (or current app entry points), relevant CSS, and
    existing frontend services/components.
5.  Identify how navigation, login, role selection, mock data, and voice
    capture currently work.
6.  Run the existing frontend build using `npm.cmd run build`.
7.  Report:
    -   Current architecture.
    -   Existing working features.
    -   Mocked/nonfunctional features.
    -   Existing build errors, if any.
    -   Any security or data-handling risks noticed.
    -   A proposed incremental plan with exact files to add/change.
8.  **Stop and wait for the user's approval before modifying files.**

The first goal is to understand and protect the existing project.
Backend and database implementation comes after the audit is approved.

------------------------------------------------------------------------

## 19. Definition of success

HealthSpeak AI is successful when: - The existing frontend remains
functional and is connected to a real backend. - PostgreSQL stores
users, roles, consent, patient profiles, conversations, intake, queues,
and appointments as implemented. - Authentication and backend role
permissions protect data. - English, Hindi, and Urdu patient UI works;
Urdu RTL is correct. - Each user's UI language preference is
independent. - Speech recognition and translation run locally, subject
to verified model support and hardware. - Original transcripts and
English translations are stored separately. - AI-generated information
is clearly marked as unreviewed until staff review it. - AI does not
diagnose or prescribe. - Staff can review, correct, confirm, and route
intake records. - Kiosk/service health and operational workflows are
observable. - Tests, documentation, migrations, and environment examples
make the project reproducible. - The agent reports limitations honestly
and never claims unverified functionality.

**Remember:** Build a safe, understandable, working system
incrementally. Do not sacrifice the existing frontend or healthcare
safety to generate code quickly.

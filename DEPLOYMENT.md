# Deploying HealthSpeak AI (beginner guide)

Netlify can only host the **website** (the `dist` folder). The **backend** (FastAPI), the
**database** (PostgreSQL) and the **AI models** (Whisper, IndicTrans2) must run somewhere else,
and the website must be told that address when it is built.

```
Visitor's browser ──► Netlify (static React site, HTTPS)
        │
        └──► your backend address (HTTPS) ──► FastAPI + Whisper + IndicTrans2 ──► PostgreSQL
```

Everything below uses **synthetic data only**. This is a demonstration system, not a certified
medical product: do not use it with real patients until clinicians have reviewed the department
rules and the legal/consent requirements of your hospital and country are met.

---------------------------------------------------------------------------------------------

## Path A — demo tomorrow: backend on your own PC + HTTPS tunnel (recommended for the demo)

Why: your PC already runs everything (both models are downloaded, ~1.8 GB; the API uses about
2.1 GB RAM with both models loaded). A "tunnel" gives your PC a public HTTPS address without
renting a server. Trade-offs: your PC must stay **on, awake and online** during the demo, and the
free quick-tunnel address **changes every time the tunnel restarts** (then rebuild + re-upload the
site, step 6).

### 0. Once: install the tunnel program
```powershell
winget install --id Cloudflare.cloudflared
```
Close and reopen PowerShell afterwards. (No account needed for a quick tunnel.)

### 1. Decide the website address
Open Netlify → your site → copy its address, e.g. `https://my-healthspeak.netlify.app`
(no trailing slash). Call it `NETLIFY_URL`.

### 2. Make a separate demo settings file (never commit it; `.env.*` is already git-ignored)
In the repository folder create the file `.env.demo` with:
```
DATABASE_URL=postgresql+psycopg://healthspeak:PASTE_THE_POSTGRES_PASSWORD_FROM_YOUR_.env@127.0.0.1:5432/healthspeak_demo
APP_ENV=production
CORS_ORIGINS=https://my-healthspeak.netlify.app
```
Replace the password and the Netlify address. `APP_ENV=production` turns on the safety checks (it
refuses to start with demo passwords or localhost CORS, and hides `/docs`).

### 3. Create a NEW demo database (your development data is not touched)
```powershell
cd C:\Users\mukti\OneDrive\Desktop\HealthSpeakAI\healthspeak-ai
docker compose up -d
docker exec healthspeak-db psql -U healthspeak -d healthspeak -c "CREATE DATABASE healthspeak_demo"
cd backend
$env:HEALTHSPEAK_ENV_FILE = "C:\Users\mukti\OneDrive\Desktop\HealthSpeakAI\healthspeak-ai\.env.demo"
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.bootstrap --email you@example.com --name "Your Name"
```
`alembic upgrade head` builds the tables (safe on a new empty database). `app.bootstrap` asks for
an administrator password (typed hidden) and loads the default departments and **draft** routing
rules. It creates no demo users.

### 4. Start the backend (leave this window open)
```powershell
cd C:\Users\mukti\OneDrive\Desktop\HealthSpeakAI\healthspeak-ai\backend
$env:HEALTHSPEAK_ENV_FILE = "C:\Users\mukti\OneDrive\Desktop\HealthSpeakAI\healthspeak-ai\.env.demo"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Check: open http://127.0.0.1:8000/api/health/db — it must say `"database":"connected"`.

### 5. Start the tunnel (second PowerShell window, leave it open)
```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```
It prints an address like `https://random-words.trycloudflare.com`. Open
`https://random-words.trycloudflare.com/api/health` in a browser: it must show `"status":"ok"`.

### 6. Build the website with that address and upload it
```powershell
cd C:\Users\mukti\OneDrive\Desktop\HealthSpeakAI\healthspeak-ai
$env:VITE_API_BASE_URL = "https://random-words.trycloudflare.com/api"
npm run build
```
(The build **refuses** to run if this address is missing, `http://` or localhost — this prevents
uploading a site that only works on your PC.) Then in Netlify → your site → **Deploys** → drag the
`dist` folder onto the page. Netlify keeps the previous deploy, so you can roll back.

### 7. Create the people for the demo
Log in on the Netlify site with the admin account from step 3 and create the staff and doctor
accounts in the admin screens (patients can sign up themselves). Add a doctor schedule if you want
to show appointments. Everything you enter lives in the `healthspeak_demo` database.

### 8. Check it works end to end (do this BEFORE the audience arrives)
1. Open the Netlify site on your **phone using mobile data** (proves it works from outside your PC).
2. Sign up a synthetic patient, accept consent, send a typed message, end the chat.
3. Record a short voice message (the first voice/translation request loads the models and is slower).
4. Log in as staff: the intake appears with the original words, the translation (Hindi/Urdu),
   extracted symptoms and a department suggestion; confirm it.
5. Refresh the page / restart the backend window: the record is still there.

If the site loads but every action fails, the three usual causes are: the tunnel address in the
build is old (re-run step 6), `CORS_ORIGINS` does not exactly match the Netlify address (fix
`.env.demo` and restart step 4), or the backend/tunnel window was closed.

---------------------------------------------------------------------------------------------

## Path B — permanent hosting (after the demo)

Requirements measured on this project:

| Need | Value |
|---|---|
| RAM | about 2.1 GB used with both models loaded — plan for **at least 4 GB, preferably 8 GB** |
| Disk | models ~1.8 GB (Whisper-small 927 MB, IndicTrans2-200M 879 MB) + PyTorch + database — **20 GB persistent** |
| CPU | Whisper-small took 5–6.6 s for 6–7.5 s of audio on an 8-core desktop CPU; on a 2-vCPU server expect several times slower (**not measured**), so prefer 4+ vCPUs |
| GPU | not required |
| Other | `ffmpeg` installed; HTTPS; persistent disk for PostgreSQL; the gated IndicTrans2 model needs a Hugging Face token **once** to download |

Recommended: **one Linux virtual machine (VPS) with 4 vCPU / 8 GB RAM**, running Docker with
three containers: the API, PostgreSQL (with a volume and daily backups) and Caddy (automatic
HTTPS). Typical providers: Hetzner, DigitalOcean, AWS Lightsail (verify current prices; this class
of machine is roughly 15–40 USD/month). Put a domain name in front of it (needed for HTTPS).

Free tiers are **not** suitable: they typically give 512 MB–1 GB RAM (the models alone need more),
sleep when idle (first request fails or takes a minute), and have ephemeral disks (models would be
re-downloaded on every restart, requiring the Hugging Face token again). Managed platforms such as
Render/Railway/Fly.io can work but only on paid plans with ≥4 GB RAM and a persistent disk.

PostgreSQL: either the same VPS (cheapest; you must configure backups) or a managed database
(backups included; the connection string goes into `DATABASE_URL`). Free managed tiers may pause
when idle — fine for experiments, not for a live service.

**Not yet in the repository for Path B:** a `Dockerfile`, a production `docker compose` file and a
`Caddyfile`. They need to be written and tested before this path works (about half a day).

---------------------------------------------------------------------------------------------

## What was verified, and what was not

Verified locally on this PC (synthetic data): text and voice intake are saved in PostgreSQL and are
still there after the API process restarts; Hindi/Urdu translation with the real model; production
mode refuses unsafe settings; CORS allows only the configured website; `/docs` is hidden in
production; the new bootstrap command; the build refuses a localhost/`http://` API address.

**Not verified:** the public Netlify website talking to a backend (no backend is public yet), the
tunnel, any cloud hosting, and the contents of the existing Netlify deployment.

## Safety checklist before showing anyone
- Use synthetic patients only. Do not type real names, numbers or symptoms.
- Do not put passwords, tokens or `.env*` files in Git, screenshots or chat.
- Revoke the Hugging Face token you created for the model download.
- The department rules are drafts; the suggestions always require staff confirmation.

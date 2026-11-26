# HealthSpeak AI: API collection

Files
- `HealthSpeak_AI.postman_collection.json`: Postman collection (v2.1). Import with **Import → File**.
- `openapi.json`: the API's OpenAPI 3 document (also served live at `http://127.0.0.1:8000/openapi.json`; Swagger UI at `/docs`).

## Run it (2 minutes)
1. Start the database and the API (see `backend/README.md`): `docker compose up -d db`, then
   `python -m uvicorn app.main:app --port 8000` from `backend/`.
2. In Postman open the collection → **Variables** tab → set **seedPassword** to `SEED_DEMO_PASSWORD`
   from your local `.env` (current value column; **never commit it**). Leave `baseUrl` as
   `http://127.0.0.1:8000/api` (use `127.0.0.1`, not `localhost`).
3. Right-click the **Demo flow** folder → **Run folder**. The requests run in order and every one has tests.

## What is in it
- **Demo flow** (35 requests, 55 checks): health → register a synthetic patient → chat (input guard refuses
  off-topic and harmful requests, symptoms understood, emergency guidance first) → submit → staff queue
  (urgent first) → per-field evidence → staff add a symptom → change priority with a reason → confirm the
  department → security tests (401, 403, 404, 409, 422, SQL-injection text) → admin and doctor checks.
- **All endpoints**: every one of the 78 operations generated from the OpenAPI document, grouped by area,
  with the right role token pre-selected. Each has a "no server error" test.

Roles and tokens: the login requests save `patientToken`, `staffToken`, `adminToken` and `doctorToken`
as collection variables; other requests use them automatically.

Synthetic data only. The demo patient gets a random phone number on every run, so the folder can be re-run.

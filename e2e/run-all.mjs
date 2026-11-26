// Runs every browser end-to-end test against the RUNNING app.
//
// Needs: PostgreSQL (docker compose up -d), the API on 127.0.0.1:8000, the
// frontend on 127.0.0.1:5173, demo data (python -m app.seed) and Microsoft Edge
// or Google Chrome. No npm packages are needed (Node 22+).
//
//   node e2e/run-all.mjs            (from the repository root)
//
// Translation: suites 04/05 adapt to whether the local translation model is installed;
// suite 11 exercises the real model and reports SKIPPED without it.
//
// Notes: the tests create SYNTHETIC patients and intakes in your development
// database. The demo patient's display language is switched to English while the
// tests run and restored afterwards.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const API = process.env.E2E_API || "http://127.0.0.1:8000/api";

function seedPassword() {
  if (process.env.SEED_DEMO_PASSWORD) return process.env.SEED_DEMO_PASSWORD;
  const env = readFileSync(join(here, "..", ".env"), "utf8");
  const m = env.match(/^SEED_DEMO_PASSWORD=(.*)$/m);
  if (!m) throw new Error("SEED_DEMO_PASSWORD not found in .env");
  return m[1].trim();
}

function browserPath() {
  const candidates = [
    process.env.E2E_BROWSER,
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ].filter(Boolean);
  const found = candidates.find((p) => existsSync(p));
  if (!found) throw new Error("No Edge/Chrome found. Set E2E_BROWSER to the browser executable.");
  return found;
}

// Node's keep-alive sockets are sometimes reset by uvicorn (ECONNRESET): retry a few times.
async function api(url, init) {
  let last;
  for (let i = 0; i < 4; i++) {
    try { return await fetch(url, init); } catch (e) { last = e; await new Promise((r) => setTimeout(r, 400 * (i + 1))); }
  }
  throw last;
}

async function demoPatientLanguage(pw, lang) {
  const login = await api(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier: "patient@example.com", password: pw }),
  });
  if (!login.ok) throw new Error("Cannot log in as the demo patient. Did you run python -m app.seed?");
  const { access_token: tok, user } = await login.json();
  if (lang) {
    await api(`${API}/users/me/preferences`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${tok}`, "Content-Type": "application/json" },
      body: JSON.stringify({ ui_language: lang }),
    });
  }
  await api(`${API}/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${tok}` } });
  return user.ui_language;
}

const pw = seedPassword();
const browser = browserPath();
let health = null;
for (let i = 0; i < 4 && !(health && health.ok); i++) health = await fetch(`${API}/health`).catch(() => null);
if (!health || !health.ok) throw new Error("API not reachable at 127.0.0.1:8000");

// Warm up Vite (it compiles modules on first request; a cold start can make the first suite's page load time out).
for (const path of ["/", "/src/main.jsx", "/src/App.jsx"]) {
  const app = (process.env.E2E_APP || "http://127.0.0.1:5173").replace(/\/+$/, "");
  await fetch(`${app}${path}`).then((r) => r.arrayBuffer()).catch(() => {});
}

const suites = [
  ["03-login-signup.mjs"],
  ["04-intake-review.mjs"],
  ["05-voice.mjs", join(here, "fixtures", "synthetic_en_tts.wav")],
  ["06-structured-intake.mjs"],
  ["07-queue-appointments.mjs"],
  ["08-languages-kiosk.mjs"],
  ["09-symptoms-history.mjs"],
  ["10-script-hint.mjs"],
  ["11-real-translation.mjs"], // skips itself when the local translation model is not installed
  ["12-chat-profile-otp.mjs"], // needs APP_ENV=development + SMS_PROVIDER=console (the local default)
  ["14-priority-evidence-guard.mjs"], // input guard, saved Urgent/Normal priority, per-field evidence labels
  ["13-dogri.mjs"], // Dogri: picker, chat, urgent symptoms, staff view (real translation if the model is installed)
];

const original = await demoPatientLanguage(pw, "en");
let failed = 0;
try {
  for (const [file, ...extra] of suites) {
    const r = spawnSync(process.execPath, [join(here, file), browser, pw, ...extra], { encoding: "utf8" });
    const out = (r.stdout || "") + (r.stderr || "");
    const summary = (out.match(/\d+\/\d+ checks passed/) || ["no summary"])[0];
    const ok = r.status === 0;
    if (!ok) failed += 1;
    console.log(`${ok ? "PASS" : "FAIL"}  ${file.padEnd(28)} ${summary}`);
    if (!ok) console.log(out.split("\n").filter((l) => /^FAIL|PAGE TEXT|TOAST|script error/.test(l)).join("\n"));
  }
} finally {
  await demoPatientLanguage(pw, original);
}
console.log(failed ? `\n${failed} suite(s) failed` : "\nAll browser suites passed");
process.exit(failed ? 1 : 0);

// Kiosk mode: a shared device opened once with ?kiosk=<key> (given by an administrator).
// The key is kept on this device only and sent with a heartbeat every minute so
// administrators can see the kiosk is running. No patient data is sent.
import { api } from "./api.js";

const KEY = "healthspeak.kioskKey";
const IDLE_KEY = "healthspeak.kioskIdleSeconds";
export const DEFAULT_IDLE_SECONDS = 120;

export function kioskKey() {
  try {
    const url = new URL(window.location.href);
    const fromUrl = url.searchParams.get("kiosk");
    if (fromUrl) {
      window.localStorage.setItem(KEY, fromUrl);
      url.searchParams.delete("kiosk"); // do not leave the key visible in the address bar
      window.history.replaceState(null, "", url.toString());
    }
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

// Seconds of no activity before a logged-in person is logged out on a kiosk.
export function kioskIdleSeconds() {
  try {
    const v = parseInt(window.localStorage.getItem(IDLE_KEY), 10);
    return Number.isFinite(v) && v >= 15 ? v : DEFAULT_IDLE_SECONDS;
  } catch {
    return DEFAULT_IDLE_SECONDS;
  }
}

async function microphoneState() {
  try {
    const s = await navigator.permissions.query({ name: "microphone" });
    return s.state; // granted | denied | prompt
  } catch {
    return "unknown";
  }
}

export async function sendHeartbeat(key, uiLanguage) {
  return api("/kiosks/heartbeat", {
    method: "POST",
    auth: false,
    headers: { "X-Kiosk-Key": key },
    body: {
      app_version: "0.8.0",
      ui_language: ["en", "hi", "ur"].includes(uiLanguage) ? uiLanguage : null,
      microphone: await microphoneState(),
      online: navigator.onLine !== false,
    },
  });
}

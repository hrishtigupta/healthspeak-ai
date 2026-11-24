// Small fetch wrapper for the HealthSpeak AI FastAPI backend.
//
// The backend address comes from VITE_API_BASE_URL (see .env.example) and
// defaults to the local development server.

const DEFAULT_BASE = "http://127.0.0.1:8000/api";
const env = typeof import.meta !== "undefined" && import.meta.env ? import.meta.env : {};
export const API_BASE = (env.VITE_API_BASE_URL || DEFAULT_BASE).replace(/\/+$/, "");

const TOKEN_KEY = "healthspeak.token";

// sessionStorage: the login is forgotten when the browser tab is closed.
// Every access is wrapped because storage can be unavailable (private mode, tests).
function storage() {
  try {
    return typeof window !== "undefined" ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

export const tokenStore = {
  get() {
    try {
      return storage()?.getItem(TOKEN_KEY) || null;
    } catch {
      return null;
    }
  },
  set(token) {
    try {
      storage()?.setItem(TOKEN_KEY, token);
    } catch {
      /* ignore */
    }
  },
  clear() {
    try {
      storage()?.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

export class ApiError extends Error {
  constructor(status, message, data) {
    super(message);
    this.name = "ApiError";
    this.status = status; // 0 = server not reachable
    this.data = data;
  }
}

const FALLBACK_MESSAGES = {
  401: "Please log in again.",
  403: "You do not have permission to do that.",
  404: "Not found.",
  409: "This conflicts with existing information.",
  422: "Please check the information you entered.",
};

// Turn FastAPI error bodies into one readable sentence.
function messageFrom(data, status) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const msg = String(first.msg || "").replace(/^Value error,\s*/i, "");
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : "";
    return msg && field && !/required/i.test(msg) ? msg : msg || `Invalid ${field}`;
  }
  return FALLBACK_MESSAGES[status] || "Something went wrong. Please try again.";
}

// body: a plain object (sent as JSON) or FormData (sent as multipart, e.g. audio).
export async function api(path, { method = "GET", body, auth = true, signal } = {}) {
  const headers = { Accept: "application/json" };
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  const token = auth ? tokenStore.get() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (err && err.name === "AbortError") throw err;
    throw new ApiError(
      0,
      "Cannot reach the HealthSpeak server. Please check that the backend is running.",
    );
  }

  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    if (res.status === 401 && token) tokenStore.clear(); // expired or revoked login
    throw new ApiError(res.status, messageFrom(data, res.status), data);
  }
  return data;
}

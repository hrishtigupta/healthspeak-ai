// Authentication, patient sign-up and consent calls.
import { api, tokenStore } from "./api.js";

// The existing UI uses language/gender labels; the API uses short codes.
export const LANGUAGE_CODES = { English: "en", Hindi: "hi", Urdu: "ur" };
export const GENDER_CODES = {
  Female: "female",
  Male: "male",
  Other: "other",
  "Prefer not to say": "prefer_not_to_say",
};

export async function login(identifier, password) {
  const data = await api("/auth/login", {
    method: "POST",
    body: { identifier: identifier.trim(), password },
    auth: false,
  });
  tokenStore.set(data.access_token);
  return data.user;
}

export async function logout() {
  try {
    if (tokenStore.get()) await api("/auth/logout", { method: "POST" });
  } finally {
    tokenStore.clear(); // always forget the token locally, even if the server is down
  }
}

export function getMe() {
  return api("/users/me");
}

// Save THIS user's display language on the server (independent per user).
export function updateMyLanguage(uiLanguage) {
  return api("/users/me/preferences", { method: "PATCH", body: { ui_language: uiLanguage } });
}

export function hasStoredLogin() {
  return Boolean(tokenStore.get());
}

export function getConsent(language = "en") {
  return api(`/consent/current?language=${encodeURIComponent(language)}`, { auth: false });
}

// payload: { full_name, phone, date_of_birth, gender, password, ui_language,
//            preferred_language, consent: { version, granted, language } }
export async function registerPatient(payload) {
  const data = await api("/patients/register", { method: "POST", body: payload, auth: false });
  tokenStore.set(data.access_token);
  return data;
}

// ----- own profile (basic details only; never touches past visit records) -----
export const getMyProfile = () => api("/patients/me");

// fields: any of { full_name, date_of_birth, gender, preferred_language }
export const updateMyProfile = (fields) => api("/patients/me", { method: "PATCH", body: fields });

// ----- forgot password by one-time code sent to the mobile number (patients) -----
export const requestPasswordReset = (identifier) =>
  api("/auth/password-reset/request", { method: "POST", body: { identifier: identifier.trim() }, auth: false });

export const confirmPasswordReset = (identifier, code, newPassword) =>
  api("/auth/password-reset/confirm", {
    method: "POST",
    body: { identifier: identifier.trim(), code: code.trim(), new_password: newPassword },
    auth: false,
  });

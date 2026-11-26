// Patient conversations / intake submission, and staff intake review.
import { api } from "./api.js";

// ----- patient -----
export const openConversation = () => api("/conversations", { method: "POST" });

export const sendMessage = (
  conversationId,
  content,
  language,
  inputMode = "text",
  transcriptionId = null,
) =>
  api(`/conversations/${conversationId}/messages`, {
    method: "POST",
    body: {
      content,
      language,
      input_mode: inputMode,
      ...(transcriptionId ? { transcription_id: transcriptionId } : {}),
    },
  });

// Upload a recording; the server transcribes it locally and returns text to review.
export const transcribeAudio = (conversationId, blob, language) => {
  const form = new FormData();
  const ext = (blob.type || "").includes("ogg") ? "ogg" : (blob.type || "").includes("mp4") ? "m4a" : "webm";
  form.append("audio", blob, `recording.${ext}`);
  form.append("language", language);
  return api(`/conversations/${conversationId}/transcriptions`, { method: "POST", body: form });
};

export const retryTranslation = (id) => api(`/intakes/${id}/translate`, { method: "POST" });

export const submitConversation = (conversationId) =>
  api(`/conversations/${conversationId}/submit`, { method: "POST" });

export const myIntakes = () => api("/patients/me/intakes");

// ----- staff -----
// The API returns urgent intakes first, then oldest first. 200 is the API maximum: the default page of 50
// would hide the newest intakes once more than 50 were waiting.
export const listIntakes = (reviewStatus) =>
  api(`/intakes?limit=200${reviewStatus ? `&review_status=${encodeURIComponent(reviewStatus)}` : ""}`);

export const getIntake = (id) => api(`/intakes/${id}`);

export const correctIntake = (id, finalText, reason) =>
  api(`/intakes/${id}`, {
    method: "PATCH",
    body: { final_text: finalText, reason: reason || null },
  });

export const confirmIntake = (id, departmentId, finalText, reason) =>
  api(`/intakes/${id}/confirm`, {
    method: "POST",
    body: {
      department_id: departmentId,
      final_text: finalText || null,
      reason: reason || null,
    },
  });

export const analyseIntake = (id, source = "final_text") =>
  api(`/intakes/${id}/analyse`, { method: "POST", body: { source } });

export const listDepartments = () => api("/departments");

// ----- display helpers -----
export { NAME_BY_CODE as LANGUAGE_NAMES } from "../i18n/languages.js";

export const REVIEW_LABELS = {
  pending_review: "Awaiting staff review",
  confirmed: "Confirmed by staff",
};

export const TRANSLATION_LABELS = {
  not_needed: "Original is English",
  pending: "Translation pending",
  completed: "Machine translation (unreviewed)",
  failed: "Translation failed",
};

export const formatDate = (iso) =>
  iso
    ? new Date(iso).toLocaleString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

// ----- staff: symptoms and the patient's earlier encounters -----
// History is requested by intake id (the server finds the verified patient record). It is kept
// only in component state, never in storage or logs.
export const getIntakeHistory = (id, { limit = 5, offset = 0 } = {}) =>
  api(`/intakes/${id}/history?limit=${limit}&offset=${offset}`);

// Staff set the Urgent / Normal flag. The reason is required and kept in the change history.
export const setIntakePriority = (intakeId, priority, reason) =>
  api(`/intakes/${intakeId}/priority`, { method: "PATCH", body: { priority, reason } });

export const reviewSymptom = (intakeId, symptomId, { action, term, status, note }) =>
  api(`/intakes/${intakeId}/symptoms/${symptomId}/review`, {
    method: "POST",
    body: {
      action,
      ...(term ? { term } : {}),
      ...(status ? { status } : {}),
      ...(note ? { note } : {}),
    },
  });

export const addSymptom = (intakeId, { term, status, evidenceText, note }) =>
  api(`/intakes/${intakeId}/symptoms`, {
    method: "POST",
    body: {
      term,
      status,
      ...(evidenceText ? { evidence_text: evidenceText } : {}),
      ...(note ? { note } : {}),
    },
  });

// The patient's own past visits (staff-confirmed information only).
export const myHistory = ({ limit = 10, offset = 0 } = {}) =>
  api(`/patients/me/history?limit=${limit}&offset=${offset}`);

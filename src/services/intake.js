// Patient conversations / intake submission, and staff intake review.
import { api } from "./api.js";

// ----- patient -----
export const openConversation = () => api("/conversations", { method: "POST" });

export const sendMessage = (conversationId, content, language, inputMode = "text") =>
  api(`/conversations/${conversationId}/messages`, {
    method: "POST",
    body: { content, language, input_mode: inputMode },
  });

export const submitConversation = (conversationId) =>
  api(`/conversations/${conversationId}/submit`, { method: "POST" });

export const myIntakes = () => api("/patients/me/intakes");

// ----- staff -----
export const listIntakes = (reviewStatus) =>
  api(`/intakes${reviewStatus ? `?review_status=${encodeURIComponent(reviewStatus)}` : ""}`);

export const getIntake = (id) => api(`/intakes/${id}`);

export const correctIntake = (id, finalText, reason) =>
  api(`/intakes/${id}`, {
    method: "PATCH",
    body: { final_text: finalText, reason: reason || null },
  });

export const confirmIntake = (id, finalText, reason) =>
  api(`/intakes/${id}/confirm`, {
    method: "POST",
    body: { final_text: finalText || null, reason: reason || null },
  });

// ----- display helpers -----
export const LANGUAGE_NAMES = { en: "English", hi: "Hindi", ur: "Urdu" };

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

// UI translations (English, Hindi, Urdu) with react-i18next.
//
// Two separate ideas (never mix them up):
// - the DISPLAY language of the app for the person using it (this file), and
// - the language a patient SPEAKS/TYPES in (chosen on the voice/chat screens).
//
// Before login the device's language is used (remembered in this browser).
// After login each user's own ui_language from the server is used, so a
// patient choosing Urdu never changes a doctor's or staff member's screen.
//
// *** Hindi and Urdu texts were written without a native-speaker review. ***
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import hi from "./hi.json";
import ur from "./ur.json";
import doi from "./doi.json";
import { LANGUAGES, LANGUAGE_CODE_LIST, isRtl } from "./languages.js";

// Dogri: the screens a patient uses to chat, speak and choose a language are translated in doi.json
// (DRAFT, needs a fluent Dogri speaker's review). Any text not yet translated falls back to Hindi
// (Dogri is written in the same Devanagari script) and then to English, so a screen is never blank.
export const UI_LANGUAGES = LANGUAGES.map(({ code, label }) => ({ code, label }));
const CODES = LANGUAGE_CODE_LIST;
const DEVICE_KEY = "healthspeak.deviceLanguage";

export function deviceLanguage() {
  try {
    const v = window.localStorage.getItem(DEVICE_KEY);
    return CODES.includes(v) ? v : "en";
  } catch {
    return "en";
  }
}

export function setDeviceLanguage(code) {
  try {
    window.localStorage.setItem(DEVICE_KEY, code);
  } catch {
    /* storage unavailable: the choice simply is not remembered */
  }
}

// Urdu is written right-to-left: switch the whole document direction.
export function applyDocumentLanguage(code) {
  if (typeof document === "undefined") return;
  const html = document.documentElement;
  html.lang = code;
  html.dir = isRtl(code) ? "rtl" : "ltr";
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en }, hi: { translation: hi }, ur: { translation: ur }, doi: { translation: doi },
  },
  lng: deviceLanguage(),
  fallbackLng: { doi: ["hi", "en"], default: ["en"] },
  interpolation: { escapeValue: false }, // React already escapes
  returnNull: false,
});
i18n.on("languageChanged", applyDocumentLanguage);
applyDocumentLanguage(i18n.language);

// Server error messages are English; show the patient a translated version when we know it.
const ERROR_KEYS = [
  [/^Cannot reach the HealthSpeak server/, "errors.network"],
  [/^Invalid credentials$/, "errors.invalidCredentials"],
  [/^SMS delivery is not available/, "errors.smsUnavailable"],
  [/^We could not send the SMS/, "errors.smsSendFailed"],
  [/already registered to another account/, "errors.phoneInUse"],
  [/already your verified mobile number/, "errors.phoneAlreadyVerified"],
  [/^A code was sent recently/, "errors.codeTooSoon"],
  [/^The code is wrong or has expired/, "errors.badCode"],
  [/already exists\. Please log in\.$/, "errors.duplicateAccount"],
  [/^Please give consent/, "errors.consentNeeded"],
  [/^Voice transcription is unavailable/, "errors.asrUnavailable"],
  [/^We could not hear any speech/, "errors.silent"],
  [/^The recording is too short/, "errors.tooShort"],
  [/^Recordings can be at most/, "errors.tooLong"],
  [/^No words were recognised/, "errors.noSpeech"],
  [/^Please log in again\.$|^Not authenticated$/, "errors.sessionExpired"],
  [/^You do not have permission|^Not permitted$/, "errors.notAllowed"],
  [/^This conversation has already been submitted/, "errors.conversationClosed"],
  [/^This conversation is too long/, "errors.conversationTooLong"],
  [/^Please describe your concern before submitting/, "errors.nothingToSubmit"],
  [/^That voice transcription cannot be used/, "errors.badTranscription"],
  [/^Text cannot be empty/, "errors.emptyMessage"],
  [/^Something went wrong/, "errors.generic"],
];

export function translateError(err) {
  const msg = (err && err.message) || "";
  const hit = ERROR_KEYS.find(([re]) => re.test(msg));
  return hit ? i18n.t(hit[1]) : msg || i18n.t("errors.generic");
}

export default i18n;

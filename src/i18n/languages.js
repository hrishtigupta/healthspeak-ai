// The ONE place that lists the languages the app supports. Add a language here (and in the backend
// enums + a migration) instead of scattering names and codes through the screens.
//
//  code    - API / database value. Dogri uses its ISO 639-3 code "doi" (there is no ISO 639-1 code).
//  name    - English name; also the value kept in the speaking-language state of the chat screens.
//  label   - how the language is written in its own script, shown in the display-language picker.
//  rtl     - right-to-left script.
//  typedIn - script a patient should type in (used for the "you are typing in English letters" hint).
//  hintKey - translation key of that hint.
export const LANGUAGES = [
  { code: "en", name: "English", label: "English", rtl: false },
  { code: "hi", name: "Hindi", label: "हिन्दी", rtl: false, typedIn: "Devanagari", hintKey: "chat.scriptHintHi" },
  { code: "ur", name: "Urdu", label: "اردو", rtl: true, typedIn: "Urdu", hintKey: "chat.scriptHintUr" },
  {
    code: "doi",
    name: "Dogri",
    label: "Dogri — डोगरी",
    rtl: false,
    typedIn: "Devanagari",
    hintKey: "chat.scriptHintDoi",
    // The assistant's own bubbles (greeting, "reading your message", department card) are shown in the
    // language the patient chose to chat in, even if the rest of the screen is in another language.
    assistantFollowsSpeaking: true,
  },
];

// i18n `lng` option for assistant-authored text, or undefined to keep the screen's display language.
export const assistantLng = (code) => (LANGUAGE_BY_CODE[code] && LANGUAGE_BY_CODE[code].assistantFollowsSpeaking ? code : undefined);

export const LANGUAGE_CODE_LIST = LANGUAGES.map((l) => l.code);
export const LANGUAGE_BY_CODE = Object.fromEntries(LANGUAGES.map((l) => [l.code, l]));
// Used by the screens that store the speaking language by its English name: { English: "en", ... }
export const LANGUAGE_CODES = Object.fromEntries(LANGUAGES.map((l) => [l.name, l.code]));
export const NAME_BY_CODE = Object.fromEntries(LANGUAGES.map((l) => [l.code, l.name]));
export const isSupportedLanguage = (code) => LANGUAGE_CODE_LIST.includes(code);
export const isRtl = (code) => Boolean(LANGUAGE_BY_CODE[code] && LANGUAGE_BY_CODE[code].rtl);

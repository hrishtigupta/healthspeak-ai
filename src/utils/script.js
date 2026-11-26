// Detects Hindi/Urdu typed in English (Latin) letters, e.g. "bukhar nahi hai".
// The translation model only understands Devanagari / Urdu script, so we nudge the
// patient (never block them): the text they send is stored exactly as typed.
const NATIVE_LETTER = /[ऀ-ॿ؀-ۿ]/; // Devanagari + Arabic/Urdu blocks

export function isRomanizedIndic(text, languageCode) {
  if (languageCode !== "hi" && languageCode !== "ur") return false;
  if (!text || NATIVE_LETTER.test(text)) return false;
  return (text.match(/[A-Za-z]{2,}/g) || []).length >= 2;
}

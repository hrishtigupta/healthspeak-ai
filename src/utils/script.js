// Detects Hindi/Urdu/Dogri typed in English (Latin) letters, e.g. "bukhar nahi hai".
// The translation model only understands Devanagari / Urdu script, so we nudge the
// patient (never block them): the text they send is stored exactly as typed, never converted.
// Romanised Dogri is deliberately not transliterated: there is no reliable standard spelling.
import { LANGUAGE_BY_CODE } from "../i18n/languages.js";

const NATIVE_LETTER = /[ऀ-ॿ؀-ۿ]/; // Devanagari + Arabic/Urdu blocks

export function isRomanizedIndic(text, languageCode) {
  if (!LANGUAGE_BY_CODE[languageCode] || !LANGUAGE_BY_CODE[languageCode].typedIn) return false;
  if (!text || NATIVE_LETTER.test(text)) return false;
  return (text.match(/[A-Za-z]{2,}/g) || []).length >= 2;
}

// Real-model translation, end to end through the browser (synthetic text only).
// Needs the local IndicTrans2 model on this computer. When it is not available the suite
// reports SKIPPED and exits 0, because 04/05 already cover the "translation off" behaviour.
//
//   Intake A: typed Devanagari Hindi  -> machine-translated, negation/duration preserved,
//             symptoms extracted from the English, machine-translation warning shown.
//   Intake B: Hindi typed in Latin letters -> staff see the "English (Latin) letters" warning.
import { launch } from "./cdp.mjs";
import { translationState } from "./translation-state.mjs";

const [, , BROWSER, SEED_PW] = process.argv;
const MT = await translationState(SEED_PW);
if (MT.state !== "ready") {
  console.log(`SKIPPED  translation model is ${MT.state}: ${MT.detail}`);
  console.log("\n0/0 checks passed (skipped)");
  process.exit(0);
}

const APP = process.env.E2E_APP || "http://127.0.0.1:5173/";
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + String(extra).slice(0, 200) : ""}`); };
const page = await launch({ browser: BROWSER });
const t = (js) => page.eval(`window.__t.${js}`);
const stamp = Date.now().toString().slice(-6);
const MARK_A = `E2E-T11A-${stamp}`, MARK_B = `E2E-T11B-${stamp}`;
const HINDI = `${MARK_A} मुझे तीन दिन से बुखार है, लेकिन खांसी नहीं है।`;
const LATIN = `${MARK_B} mujhe bukhar hai aur khansi bhi`;

async function login(id) {
  await page.goto(APP);
  await page.waitFor("window.__t.has('Your Language')");
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Welcome Back')");
  await t(`set(window.__t.byPh('Enter your email or mobile'), '${id}')`);
  await t(`set(window.__t.byPh('Enter your password'), ${JSON.stringify(SEED_PW)})`);
  await t("btn('Log in')");
}
async function logout() { await t("btn('Log out')"); await page.waitFor("window.__t.has('Your Health,')"); }
async function patientSubmits(text, mark) {
  await login("patient@example.com");
  await page.waitFor("window.__t.has('Welcome, Demo Patient')");
  await page.waitFor("!window.__t.has('Loading...')");
  await t("btn('Start Text Chat')");
  await page.waitFor("document.querySelector('.chat-page')");
  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'Hindi')");
  await t(`set(window.__t.byPh('Type your message'), ${JSON.stringify(text)})`);
  await t("btn('Send')");
  await page.waitFor(`window.__t.has('${mark}')`);
  await t("btn('End Chat')");
  await page.waitFor("document.querySelector('.overlay')");
  await page.eval("[...document.querySelectorAll('.overlay button')].find(b => b.innerText.trim() === 'End chat').click()");
  // Submitting translates synchronously with the real model (a few seconds on CPU).
  await page.waitFor(`[...document.querySelectorAll('.history-row')].some(r => r.innerText.includes('${mark}'))`, 120000);
  await logout();
}
async function staffOpens(mark) {
  await login("staff@example.com");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
  await page.waitFor(`window.__t.has('${mark}')`);
  await page.eval(`[...document.querySelectorAll('.queue-row')].find(r => r.innerText.includes('${mark}')).querySelector('button').click()`);
  await page.waitFor("window.__t.has('Review intake')");
  await page.waitFor("!window.__t.has('Loading earlier visits')");
}

try {
  // ---- A: Devanagari Hindi ----
  await patientSubmits(HINDI, MARK_A);
  await staffOpens(MARK_A);
  check("original Hindi words are shown unchanged", await t(`has(${JSON.stringify(HINDI)})`));
  check("English version is labelled an unreviewed machine translation by the real model",
        (await t("has('MACHINE TRANSLATION (UNREVIEWED)')")) && (await t("has('ai4bharat/indictrans2')")));
  const body = await page.text();
  check("English translation mentions fever, three days and the cough denial",
        /fever/i.test(body) && /three days|3 days/i.test(body) && /cough/i.test(body));
  check("no retry button (translation already completed)", !(await t("has('Retry machine translation')")));
  check("review warning says the English is a machine translation",
        await t("has('The English text is a machine translation')"));
  const rows = await page.eval("[...document.querySelectorAll('.symptom-row')].map(r => r.innerText)");
  check("symptoms were extracted from the translation with the right context",
        rows.some((r) => /fever/i.test(r) && /Current/.test(r)) && rows.some((r) => /cough/i.test(r) && /Denied/.test(r)),
        rows.join(" | "));
  check("duration is attached to the fever with the patient's words as evidence",
        rows.some((r) => /fever/i.test(r) && /duration/i.test(r)));
  check("symptoms are still AI-extracted and unconfirmed", rows.every((r) => /AI-extracted/.test(r)));
  await t("btn('Back to overview')");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
  await logout();

  // ---- B: Hindi in Latin letters ----
  await patientSubmits(LATIN, MARK_B);
  await staffOpens(MARK_B);
  check("Latin-letter Hindi is stored exactly as typed", await t(`has(${JSON.stringify(LATIN)})`));
  check("staff are warned that the text was in English letters",
        await t("has('written in English (Latin) letters')"));
  check("it is still marked as machine translation needing review",
        await t("has('The English text is a machine translation')"));
  await t("btn('Back to overview')");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
  await logout();

  check("no uncaught page errors", page.consoleErrors.filter((e) => !/unique "key"/.test(e)).length === 0,
        page.consoleErrors.filter((e) => !/unique "key"/.test(e)).slice(0, 2).join(" | "));
} catch (err) {
  check("script error", false, err.message);
  try { console.log("PAGE TEXT:", (await page.text()).slice(0, 900)); console.log("TOAST:", await t("toast()")); } catch {}
} finally {
  await page.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);

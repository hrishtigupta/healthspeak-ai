// End-to-end: staff symptom review and returning-patient history shown during a NEW intake.
// Uses synthetic text only. Visit 1 is confirmed by staff; visit 2 must show visit 1 as history.
import { launch } from "./cdp.mjs";

const [, , BROWSER, SEED_PW] = process.argv;
const APP = "http://127.0.0.1:5173/";
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + String(extra).slice(0, 160) : ""}`); };

const page = await launch({ browser: BROWSER });
const t = (js) => page.eval(`window.__t.${js}`);
const stamp = Date.now().toString().slice(-6);
const VISIT1 = `E2E${stamp} first visit: I have a severe headache for three days.`;
const VISIT2 = `E2E${stamp} second visit: I have a headache again and my mother has a cough. I do not have fever.`;

async function login(id) {
  await page.goto(APP);
  await page.waitFor("window.__t.has('Your Language')");
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Welcome Back')");
  await t(`set(window.__t.byPh('Enter your email or mobile'), '${id}')`);
  await t(`set(window.__t.byPh('Enter your password'), ${JSON.stringify(SEED_PW)})`);
  await t("btn('Log in')");
}
async function logout() {
  await t("btn('Log out')");
  await page.waitFor("window.__t.has('Your Health,')");
}
async function patientSubmits(text) {
  await login("patient@example.com");
  await page.waitFor("window.__t.has('Welcome, Demo Patient')");
  await page.waitFor("!window.__t.has('Loading...')");
  await t("btn('Start Text Chat')");
  await page.waitFor("document.querySelector('.chat-page')");
  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'English')");
  await t(`set(window.__t.byPh('Type your message'), ${JSON.stringify(text)})`);
  await t("btn('Send')");
  await page.waitFor("window.__t.has('added to your intake')");
  await t("btn('End Chat')");
  await page.waitFor("document.querySelector('.overlay')");
  await page.eval("[...document.querySelectorAll('.overlay button')].find(b => b.innerText.trim() === 'End chat').click()");
  await page.waitFor("window.__t.toast().includes('sent for staff review')");
  await logout();
}
async function staffOpens(stampText) {
  await login("staff@example.com");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
  await page.waitFor(`window.__t.has('${stampText}')`);
  await page.eval(`[...document.querySelectorAll('.queue-row')].find(r => r.innerText.includes('${stampText}')).querySelector('button').click()`);
  await page.waitFor("window.__t.has('Review intake')");
  await page.waitFor("!window.__t.has('Loading earlier visits')");
}

try {
  // ---- visit 1: patient submits, staff confirms one symptom and the intake ----
  await patientSubmits(VISIT1);
  await staffOpens(`E2E${stamp} first`);
  check("first visit shows the 'no earlier visits' or earlier-visit history section",
        await t("has('EARLIER VISITS OF THIS PATIENT')"));
  check("symptom panel lists the headache as AI-extracted, not confirmed",
        (await t("has('SYMPTOMS · AI-EXTRACTED UNTIL STAFF CONFIRM')")) && (await t("has('AI-extracted · not confirmed')")));
  check("evidence and stated details are shown for the symptom",
        (await t("has('words:')")) && (await t("has('for three days')")) && (await t("has('severe')")));
  await page.eval("document.querySelector('.symptom-row button').click()"); // Confirm (first button)
  await page.waitFor("document.querySelector('.symptom-row') && document.querySelector('.symptom-row').innerText.includes('Confirmed by staff')");
  check("staff can confirm a symptom", await page.eval("document.querySelector('.symptom-row').innerText.includes('Confirmed by staff')"));
  await page.eval("window.__t.set(document.querySelector('.dept-select'), [...document.querySelector('.dept-select').options].find(o => o.text === 'Neurology').value)");
  await t("btn('Confirm intake')");
  await page.waitFor("window.__t.toast().includes('Intake confirmed')");
  await t("btn('Back to overview')");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
  await logout();

  // ---- visit 2: a NEW encounter; staff must see visit 1 as dated history ----
  await patientSubmits(VISIT2);
  await staffOpens(`E2E${stamp} second`);
  check("earlier visit is shown inside the new intake review",
        (await t(`has('E2E${stamp} first visit')`)) && (await t("has('EARLIER VISITS OF THIS PATIENT')")));
  check("history warns that old symptoms are not assumed current", await t("has('must NOT be assumed')"));
  check("earlier symptom is labelled as confirmed by staff",
        await page.eval("document.querySelector('.history .encounter').innerText.includes('confirmed by staff')"));
  check("repeated symptom is highlighted as context",
        await t("has('Also reported at an earlier visit')"));
  check("history shows the earlier department chosen by staff",
        await page.eval("document.querySelector('.history .encounter').innerText.includes('Neurology')"));
  const rows = await page.eval("[...document.querySelectorAll('.symptom-row')].map(r => r.innerText)");
  check("current symptoms are separated by context (denied / another person)",
        rows.some((r) => /fever/i.test(r) && /Denied/.test(r)) && rows.some((r) => /cough/i.test(r) && /Another person/.test(r)),
        rows.join(" | "));
  check("the new visit's own symptom list does not contain the earlier visit's words",
        !(await page.eval("[...document.querySelectorAll('.symptom-row')].some(r => r.innerText.includes('first visit'))")));
  await t("btn('Back to overview')");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
  await logout();

  check("no uncaught page errors", page.consoleErrors.filter(e => !/unique "key"/.test(e)).length === 0,
        page.consoleErrors.filter(e => !/unique "key"/.test(e)).slice(0, 2).join(" | "));
} catch (err) {
  check("script error", false, err.message);
  try { console.log("PAGE TEXT:", (await page.text()).slice(0, 800)); console.log("TOAST:", await t("toast()")); } catch {}
} finally {
  await page.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);

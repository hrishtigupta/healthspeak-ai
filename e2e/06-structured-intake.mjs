// Phase 6 E2E: rule-based summary, attention flag, department suggestion, staff choice.
import { launch } from "./cdp.mjs";

const [, , BROWSER, SEED_PW] = process.argv;
const APP = "http://127.0.0.1:5173/";
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + String(extra).slice(0, 200) : ""}`); };
const page = await launch({ browser: BROWSER });
const t = (js) => page.eval(`window.__t.${js}`);
const RUN = Date.now().toString().slice(-6);
const CARDIO = `P6-${RUN}A: Sudden chest pain and palpitations since this morning. No fever.`;
const AMBIG = `P6-${RUN}B: Earache and blurred vision.`;
const clearToast = () => page.eval("document.querySelector('.toast button')?.click()");

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
async function submit(text) {
  await t("btn('Start Text Chat')");
  await page.waitFor("document.querySelector('.chat-page')");
  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'English')");
  await t(`set(window.__t.byPh('Type your message'), ${JSON.stringify(text)})`);
  await t("btn('Send')");
  await page.waitFor(`window.__t.has(${JSON.stringify(text)})`);
  await t("btn('End Chat')");
  await page.waitFor("document.querySelector('.overlay')");
  await page.eval("[...document.querySelectorAll('.overlay button')].find(b => b.innerText.trim() === 'End chat').click()");
  await page.waitFor(`document.querySelector('.patient-layout') && [...document.querySelectorAll('.history-row')].some(r => r.innerText.includes(${JSON.stringify(text.slice(0, 12))}))`, 15000);
}
const row = (marker) => `[...document.querySelectorAll('.queue-row')].find(r => r.innerText.includes('${marker}'))`;

try {
  await login("patient@example.com");
  await page.waitFor("window.__t.has('Welcome, Demo Patient')");
  await submit(CARDIO);
  await submit(AMBIG);
  const patientSeesSuggestion = await t("has('Cardiology')") || await t("has('AI suggests')");
  check("patient dashboard does not show the AI suggestion", !patientSeesSuggestion);
  await logout();

  await login("staff@example.com");
  await page.waitFor(`window.__t.has('P6-${RUN}A')`, 10000);
  const cardioRow = await page.eval(`${row(`P6-${RUN}A`)}.innerText`);
  check("staff list shows attention flag + suggestion", /Attention/.test(cardioRow) && /AI suggests: Cardiology/.test(cardioRow), cardioRow.replace(/\n/g, " | "));

  await page.eval(`${row(`P6-${RUN}A`)}.querySelector('button').click()`);
  await page.waitFor("window.__t.has('AI-ASSISTED SUMMARY')");
  check("review shows unconfirmed AI summary with quoted evidence",
        (await t("has('UNCONFIRMED')")) && (await t("has('chest pain: ')")) && (await t("has('Not a diagnosis')")));
  check("denied symptom shown separately", await page.eval("[...document.querySelectorAll('.analysis-grid div')].some(d => d.innerText.includes('do NOT have') && d.innerText.includes('fever'))"));
  check("attention box shown, worded as staff flag", (await t("has('Prompt staff attention')")) && (await t("has('not a triage decision')")));
  const pre = await page.eval("document.querySelector('.dept-select').selectedOptions[0].text");
  check("department pre-selected from suggestion (Cardiology)", pre === "Cardiology", pre);
  await page.eval("window.__t.set(document.querySelector('.dept-select'), [...document.querySelector('.dept-select').options].find(o => o.text === 'General Medicine').value)");
  await clearToast();
  await t("btn('Confirm intake')");
  await page.waitFor("window.__t.toast().includes('Intake confirmed')");
  check("staff overrode suggestion and confirmed", await t("has('General Medicine')"));
  await t("btn('Back to overview')");
  await page.waitFor(`window.__t.has('P6-${RUN}B')`);

  await page.eval(`${row(`P6-${RUN}B`)}.querySelector('button').click()`);
  await page.waitFor("window.__t.has('AI-ASSISTED SUMMARY')");
  check("ambiguous case says staff must choose", await t("has('Several departments possible')"));
  const disabled = await page.eval("[...document.querySelectorAll('button')].find(b => b.innerText.includes('Confirm intake')).disabled");
  check("confirm disabled until a department is chosen", disabled === true);
  await page.eval("window.__t.set(document.querySelector('.dept-select'), [...document.querySelector('.dept-select').options].find(o => o.text.startsWith('ENT')).value)");
  await clearToast();
  await t("btn('Confirm intake')");
  await page.waitFor("window.__t.toast().includes('Intake confirmed')");
  check("ambiguous intake confirmed after staff choice", true);
  await t("btn('Back to overview')");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
  await logout();

  await login("patient@example.com");
  await page.waitFor(`window.__t.has('P6-${RUN}A')`);
  await page.eval(`[...document.querySelectorAll('.history-row')].find(r => r.innerText.includes('P6-${RUN}A')).querySelector('button').click()`);
  await page.waitFor("window.__t.has('Your submitted concern')");
  check("patient sees staff-confirmed department (General Medicine), not the suggestion",
        (await t("has('General Medicine')")) && !(await t("has('Cardiology')")));
  await t("btn('Back')");
  await logout();
  check("no uncaught page errors", page.consoleErrors.filter((e) => !/unique "key"/.test(e)).length === 0,
        page.consoleErrors.filter((e) => !/unique "key"/.test(e)).slice(0, 2).join(" | "));
} catch (err) {
  check("script error", false, err.message);
  try { console.log("PAGE TEXT:", (await page.text()).slice(0, 700)); console.log("TOAST:", await t("toast()")); } catch {}
} finally {
  await page.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);

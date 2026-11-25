// Phase 4 end-to-end: patient chat -> submit intake -> staff review/confirm -> patient sees status.
import { launch } from "./cdp.mjs";
import { translationState } from "./translation-state.mjs";

const [, , BROWSER, SEED_PW] = process.argv;
const APP = "http://127.0.0.1:5173/";
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + String(extra).slice(0, 160) : ""}`); };

// Works with translation on (real model) or off: the expectations below follow the live state.
const MT = await translationState(SEED_PW);
console.log(`translation model: ${MT.state}`);
const page = await launch({ browser: BROWSER });
const t = (js) => page.eval(`window.__t.${js}`);
const stamp = Date.now().toString().slice(-6);
const EN_MSG = `E2E ${stamp}: knee pain when climbing stairs for two weeks.`;
const HI_MSG = `E2E ${stamp}: मुझे सीढ़ियाँ चढ़ते समय घुटने में दर्द होता है।`;

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

try {
  // ---- anonymous visitor cannot save a concern ----
  await page.goto(APP);
  await page.waitFor("window.__t.has('Your Language')");
  await t("btn('Voice Input')");
  await page.waitFor("document.querySelector('.voice-screen textarea')");
  const voiceLangs = await page.eval("[...document.querySelector('.voice-bottom select').options].map(o=>o.text).join(',')");
  check("voice language list is English/Hindi/Urdu", voiceLangs === "English,Hindi,Urdu", voiceLangs);
  await t("set('.voice-screen textarea', 'anonymous words')");
  await t("btn('Continue to chat')");
  await page.waitFor("window.__t.has('Welcome Back')");
  check("anonymous voice continue asks to log in", (await t("toast()")).includes("log in"), await t("toast()"));

  // ---- patient submits an intake (English text + Hindi voice-transcript) ----
  await login("patient@example.com");
  await page.waitFor("window.__t.has('Welcome, Demo Patient')");
  await page.waitFor("!window.__t.has('Loading...')");
  check("fake 94% score / triage removed from dashboard", !(await t("has('94%')")) && !(await t("has('Triage Level')")));
  await t("btn('Start Text Chat')");
  await page.waitFor("document.querySelector('.chat-page')");
  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'English')");
  await t(`set(window.__t.byPh('Type your message'), ${JSON.stringify(EN_MSG)})`);
  await t("btn('Send')");
  await page.waitFor(`window.__t.has(${JSON.stringify(EN_MSG)}) && window.__t.has('added to your intake')`);
  check("text message saved and acknowledged", true);

  // voice screen (browser transcript typed/reviewed) in Hindi
  await page.eval("document.querySelector('.compose-tools button[aria-label], .compose-tools button:last-child').click()");
  await page.waitFor("document.querySelector('.voice-screen textarea')");
  await page.eval("window.__t.set(document.querySelector('.voice-bottom select'), 'Hindi')");
  await t(`set('.voice-screen textarea', ${JSON.stringify(HI_MSG)})`);
  await t("btn('Continue to chat')");
  await page.waitFor(`window.__t.has(${JSON.stringify(HI_MSG)}) && window.__t.has('धन्यवाद')`);
  check("Hindi voice transcript saved with Hindi acknowledgement", true);

  await t("btn('End Chat')");
  await page.waitFor("document.querySelector('.overlay')");
  await page.eval("[...document.querySelectorAll('.overlay button')].find(b => b.innerText.trim() === 'End chat').click()");
  await page.waitFor("window.__t.toast().includes('sent for staff review')", 120000); // real translation runs inside submit
  await page.waitFor(`window.__t.has('E2E ${stamp}')`);
  check("submitted intake appears on dashboard as awaiting review",
        await page.eval(`[...document.querySelectorAll('.history-row')].some(r => r.innerText.includes('E2E ${stamp}') && r.innerText.includes('Awaiting staff review'))`));
  await page.eval(`[...document.querySelectorAll('.history-row')].find(r => r.innerText.includes('E2E ${stamp}')).querySelector('button').click()`);
  await page.waitFor("window.__t.has('Your submitted concern')");
  check("summary shows the patient's exact words", (await t(`has(${JSON.stringify(HI_MSG)})`)) && (await t("has('Awaiting staff review')")));
  await t("btn('Back')");
  await logout();

  // ---- staff reviews and confirms ----
  await login("staff@example.com");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
  await page.waitFor(`window.__t.has('E2E ${stamp}')`);
  check("staff sees the new intake in the review list", true);
  await page.eval(`[...document.querySelectorAll('.queue-row')].find(r => r.innerText.includes('E2E ${stamp}')).querySelector('button').click()`);
  await page.waitFor("window.__t.has('Review intake')");
  check("review screen shows original words and 'never changed' note",
        (await t(`has(${JSON.stringify(HI_MSG)})`)) && (await t("has('never changed')")));
  if (MT.state === "ready") {
    check("mixed-language intake was machine-translated and is labelled unreviewed",
          (await t("has('MACHINE TRANSLATION (UNREVIEWED)')")) && (await t("has('Machine translation by')"))
          && !(await t("has('TRANSLATION PENDING')")) && !(await t("has('Retry machine translation')")));
  } else {
    check("mixed-language intake shows translation pending", await t("has('TRANSLATION PENDING')"));
  }
  const english = `E2E ${stamp}: Knee pain when climbing stairs for two weeks. (Second message: knee pain on stairs.)`;
  await page.eval(`window.__t.set(document.querySelector('.workspace-section textarea'), ${JSON.stringify(english)})`);
  await page.eval("window.__t.set(document.querySelector('input.reason'), 'staff translation of Hindi part')");
  await t("btn('Save correction')");
  await page.waitFor("window.__t.toast().includes('Correction saved')");
  await page.waitFor("window.__t.has('Reviewed text added')");
  check("correction saved and shown in change history", true);
  // Phase 6+: staff must choose the department before confirming.
  await page.eval("window.__t.set(document.querySelector('.dept-select'), [...document.querySelector('.dept-select').options].find(o => o.text === 'Orthopaedics').value)");
  await page.eval("document.querySelector('.toast button')?.click()");
  await t("btn('Confirm intake')");
  await page.waitFor("window.__t.toast().includes('Intake confirmed')");
  await page.waitFor("window.__t.has('Confirmed by staff') && window.__t.has('pending_review → confirmed')");
  check("intake confirmed; status change in history", true);
  await t("btn('Back to overview')");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
  await page.waitFor("!window.__t.has('Loading...')");
  check("confirmed intake left the pending list", !(await t(`has('E2E ${stamp}')`)));
  await logout();

  // ---- patient sees confirmation ----
  await login("patient@example.com");
  await page.waitFor(`window.__t.has('E2E ${stamp}')`);
  check("patient dashboard shows 'Confirmed by staff'",
        await page.eval(`[...document.querySelectorAll('.history-row')].some(r => r.innerText.includes('E2E ${stamp}') && r.innerText.includes('Confirmed by staff'))`));
  await logout();
  check("after logout, chat history is not visible to next user",
        await page.eval("(async()=>{ window.__t.btn('Voice Input'); await new Promise(r=>setTimeout(r,300)); window.__t.btn('Skip to text chat'); await new Promise(r=>setTimeout(r,300)); return !document.body.innerText.includes('E2E'); })()"));

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

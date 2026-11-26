// Phase 10 end-to-end (synthetic data only): language selector, session + chat restored after a
// refresh, multi-turn conversation with follow-up questions and a preliminary department, urgent
// symptoms (Urdu), review-and-send, what staff receive, profile, phone change with an SMS code
// (development mode shows the code on screen) and forgot password using the NEW number.
//
// Needs the API in development mode with the console SMS provider (the default for local runs).
import { launch } from "./cdp.mjs";

const [, , BROWSER, SEED_PW] = process.argv;
const APP = process.env.E2E_APP || "http://127.0.0.1:5173/";
const API = process.env.E2E_API || "http://127.0.0.1:8000/api";
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + String(extra).slice(0, 200) : ""}`); };
const page = await launch({ browser: BROWSER });
const t = (js) => page.eval(`window.__t.${js}`);

const stamp = Date.now().toString().slice(-7);
const PHONE1 = "98" + stamp.padStart(8, "0");
const PHONE2 = "97" + stamp.padStart(8, "0");
const PW1 = `E2E-First-${stamp}`;
const PW2 = `E2E-Second-${stamp}`;
const NAME = `E2E Synthetic ${stamp}`;
const REPLY_N = (n) => `document.querySelectorAll('.message.doctor .bubble > p:not(.thinking)').length >= ${n}`;
const assistantTexts = () => page.eval("[...document.querySelectorAll('.message.doctor .bubble > p:not(.thinking)')].map(p => p.innerText)");
const say = async (text, expectBubbles) => {
  await t(`set(window.__t.byPh('Type your message'), ${JSON.stringify(text)})`);
  await t("btn('Send')");
  await page.waitFor(REPLY_N(expectBubbles) + " && !document.querySelector('.thinking')", 150000);
};
const sidebarSelect = () => page.eval(`(() => { const s = document.querySelector('.patient-sidebar .language select'); const c = getComputedStyle(s);
  return { text: s.selectedOptions[0].text, color: c.color, bg: c.backgroundColor, width: s.getBoundingClientRect().width }; })()`);
const devCode = () => page.eval("document.querySelector('[data-testid=dev-otp] code')?.innerText || ''");

try {
  // ---- a synthetic patient, signed in the way a refresh would find them ----
  await page.goto(APP);
  await page.waitFor("window.__t.has('Your Language')");
  const consent = await page.eval(`fetch('${API}/consent/current?language=en').then(r => r.json())`);
  const reg = await page.eval(`fetch('${API}/patients/register', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({full_name:'${NAME}', phone:'${PHONE1}', date_of_birth:'1990-05-05', gender:'female', password:'${PW1}',
      consent:{version:'${consent.version}', granted:true, language:'en'}})}).then(r => r.json())`);
  await page.eval(`sessionStorage.setItem('healthspeak.token', ${JSON.stringify(reg.access_token)})`);
  await page.goto(APP);
  await page.waitFor(`window.__t.has('Welcome, ${NAME}')`, 20000);
  check("a refresh restores the logged-in session", true);

  // ---- language selector ----
  let sel = await sidebarSelect();
  check("selector shows the selected language (English)", sel.text === "English" && sel.width > 40, JSON.stringify(sel));
  check("selector text is visible on the green box (white text, transparent background)",
        sel.color === "rgb(255, 255, 255)" && (sel.bg === "rgba(0, 0, 0, 0)" || sel.bg === "transparent"), `${sel.color} on ${sel.bg}`);
  await page.eval("window.__t.set(document.querySelector('.patient-sidebar .language select'), 'hi')");
  await page.waitFor("window.__t.has('मरीज़ डैशबोर्ड')");
  sel = await sidebarSelect();
  check("Hindi is shown in its own script", sel.text === "हिन्दी", sel.text);
  await page.goto(APP);
  await page.waitFor("window.__t.has('मरीज़ डैशबोर्ड')", 20000);
  check("the chosen language survives a refresh (saved on the account)", (await sidebarSelect()).text === "हिन्दी");
  await page.eval("window.__t.set(document.querySelector('.patient-sidebar .language select'), 'ur')");
  await page.waitFor("document.documentElement.dir === 'rtl'");
  check("Urdu is shown in its own script and flips the page to right-to-left", (await sidebarSelect()).text === "اردو");
  await page.eval("window.__t.set(document.querySelector('.patient-sidebar .language select'), 'en')");
  await page.waitFor("window.__t.has('PATIENT DASHBOARD')");

  // ---- profile + phone (the code is shown on screen only because this is a development server) ----
  await t("btn('My Profile')");
  await page.waitFor("window.__t.has('Not verified')");
  check("an existing number starts as 'Not verified'", true);
  await page.eval(`window.__t.set(document.querySelector('.profile-form input'), '${NAME} Renamed')`);
  await t("btn('Save changes')");
  await page.waitFor("window.__t.toast().includes('updated')");
  check("profile details can be changed", true);

  await t("btn('Change number')");
  await page.waitFor("window.__t.byPh('Enter your mobile number')");
  await t(`set(window.__t.byPh('Enter your mobile number'), '${PHONE2}')`);
  await t("btn('Send code')");
  await page.waitFor("document.querySelector('[data-testid=dev-otp]')", 20000);
  const code = await devCode();
  check("development mode shows a 6-digit code and says no real SMS was sent",
        /^\d{6}$/.test(code) && (await t("has('No real SMS was sent')")), code);
  const wrong = code === "000000" ? "111111" : "000000";
  await page.eval(`window.__t.set(document.querySelector('input[inputmode=numeric]'), '${wrong}')`);
  await t("btn('Verify and save')");
  await page.waitFor("window.__t.toast().includes('wrong or has expired')");
  const stillOld = await page.eval(`fetch('${API}/patients/me', {headers:{Authorization:'Bearer ' + sessionStorage.getItem('healthspeak.token')}}).then(r => r.json())`);
  check("a wrong code is rejected and the old number stays", stillOld.phone === "+91" + PHONE1, stillOld.phone);
  await page.eval(`window.__t.set(document.querySelector('input[inputmode=numeric]'), '${code}')`);
  await t("btn('Verify and save')");
  await page.waitFor("window.__t.toast().includes('verified and saved')");
  await page.waitFor("document.querySelector('[data-testid=phone-status]')?.innerText.includes('Verified')");
  check("the correct code verifies and replaces the number", (await t("has('" + PHONE2 + "')")));

  // ---- conversation ----
  await t("btn('Back')");
  await page.waitFor(`window.__t.has('Welcome, ${NAME} Renamed')`);
  check("the new name is shown after saving", true);
  await t("btn('Start Text Chat')");
  await page.waitFor("document.querySelector('.chat-page')");
  await say("My stomach has been hurting since yesterday.", 2);
  let texts = await assistantTexts();
  check("it asks WHERE the pain is (not a generic reply)", /Where exactly is the pain/.test(texts[1]), texts[1]);
  check("it does not ask how long: that was already said", !/How long/.test(texts[1]));

  await page.goto(APP); // refresh in the middle of the conversation
  await page.waitFor("window.__t.has('PATIENT DASHBOARD')", 20000);
  await t("btn('Start Text Chat')");
  await page.waitFor(REPLY_N(2), 20000);
  check("after a refresh the conversation is still there",
        (await t("has('My stomach has been hurting since yesterday.')")) && /Where exactly/.test((await assistantTexts())[1]));

  await say("Mostly in the lower abdomen, on the right side.", 3);
  texts = await assistantTexts();
  check("the next question is different (severity), not a repeat", /How strong/.test(texts[2]) && texts[2] !== texts[1], texts[2]);
  await say("It is severe and I also have a fever.", 4);
  for (let i = 0; i < 4 && !(await page.eval("!!document.querySelector('[data-testid=suggestion-card]')")); i++) {
    await say("no", 5 + i);
  }
  await page.waitFor("document.querySelector('[data-testid=suggestion-card]')");
  const card = await page.eval("document.querySelector('[data-testid=suggestion-card]').innerText");
  check("it suggests Gastroenterology as PRELIMINARY, with staff confirming", /Gastroenterology/.test(card) && /Not a diagnosis/.test(card), card);
  const finalText = (await assistantTexts()).pop();
  check("it explains the suggestion and warns about lower-right pain with fever",
        /because you mentioned/.test(finalText) && /urgent/i.test(finalText) && /cannot diagnose or prescribe/.test(finalText), finalText);
  texts = await assistantTexts();
  check("no assistant message is repeated", new Set(texts).size === texts.length);

  await t("btn('Review and send')");
  await page.waitFor("document.querySelector('.review-list')");
  const review = await page.eval("document.querySelector('.review-list').innerText");
  check("the review step lists the patient's own words before sending", /My stomach has been hurting/.test(review) && /severe and I also have a fever/.test(review));
  await page.eval("[...document.querySelectorAll('.overlay button')].find(b => b.innerText.trim() === 'End chat').click()");
  await page.waitFor("window.__t.toast().includes('sent for staff review')", 60000);
  check("the intake is submitted", true);

  // ---- what staff receive ----
  const staffTok = await page.eval(`fetch('${API}/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({identifier:'staff@example.com', password:${JSON.stringify(SEED_PW)}})}).then(r => r.json()).then(j => j.access_token)`);
  const staffGet = (path) => page.eval(`fetch('${API}${path}', {headers:{Authorization:'Bearer ${staffTok}'}}).then(r => r.json())`);
  const list = await staffGet("/intakes?review_status=pending_review&limit=200");
  const mine = list.items.find((i) => i.patient_name.includes(stamp));
  const detail = await staffGet(`/intakes/${mine.id}`);
  check("staff see the original messages in order",
        detail.messages.filter((m) => m.sender === "patient").map((m) => m.content)[0] === "My stomach has been hurting since yesterday.");
  check("staff see the extracted symptoms and the saved department suggestion",
        detail.symptoms.some((s) => s.term === "stomach pain") && detail.symptoms.some((s) => s.term === "fever")
        && detail.analysis.suggestion.department_code === "gastroenterology", detail.analysis && detail.analysis.suggestion.department_code);

  // ---- urgent symptoms, in Urdu ----
  await page.waitFor("window.__t.has('PATIENT DASHBOARD')");
  await t("btn('Start Text Chat')");
  await page.waitFor("document.querySelector('.chat-page')");
  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'Urdu')");
  await say("مجھے سینے میں درد ہے اور سانس لینے میں تکلیف", 2);
  const urdu = (await assistantTexts()).pop();
  check("the reply is in Urdu", /[؀-ۿ]/.test(urdu) && !/[A-Za-z]{4}/.test(urdu.replace(/112/g, "")), urdu);
  check("urgent symptoms get emergency guidance (112) without a follow-up question", urdu.includes("112") && !/[?؟]/.test(urdu), urdu);
  check("the urgent badge is shown", await page.eval("!!document.querySelector('.suggestion.urgent')"));
  await t("btn('Back')").catch(() => {});

  // ---- forgot password, using the number that was just verified ----
  await page.eval("sessionStorage.removeItem('healthspeak.token')");
  await page.goto(APP);
  await page.waitFor("window.__t.has('Your Language')");
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Welcome Back')");
  await t("btn('Forgot Password?')");
  await page.waitFor("window.__t.byPh('Enter your mobile number')");
  await t(`set(window.__t.byPh('Enter your mobile number'), '${PHONE2}')`);
  await t("btn('Send code')");
  await page.waitFor("document.querySelector('[data-testid=dev-otp]')", 20000);
  const resetCode = await devCode();
  check("forgot password sends a code to the updated number", /^\d{6}$/.test(resetCode), resetCode);
  await page.eval(`window.__t.set(document.querySelector('input[inputmode=numeric]'), '${resetCode}')`);
  const pwInputs = "[...document.querySelectorAll('.overlay input[type=password]')]";
  await page.eval(`window.__t.set(${pwInputs}[0], '${PW2}'); window.__t.set(${pwInputs}[1], '${PW2}')`);
  await t("btn('Set new password')");
  await page.waitFor("window.__t.toast().includes('Password changed')", 20000);
  await t(`set(window.__t.byPh('Enter your email or mobile'), '${PHONE2}')`);
  await t(`set(window.__t.byPh('Enter your password'), '${PW2}')`);
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('PATIENT DASHBOARD')", 20000);
  check("the new password works with the new number", true);
  const oldPw = await page.eval(`fetch('${API}/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({identifier:'${PHONE2}', password:'${PW1}'})}).then(r => r.status)`);
  check("the old password no longer works", oldPw === 401, oldPw);
} catch (e) {
  check("script error", false, e.message);
  console.log("PAGE TEXT:", (await page.text().catch(() => "")).slice(0, 700));
  console.log("TOAST:", await t("toast()").catch(() => ""));
} finally {
  const failed = results.filter((r) => !r.ok).length;
  console.log(`${results.length - failed}/${results.length} checks passed`);
  const errs = page.consoleErrors.filter((x) => !/Failed to load resource|favicon/i.test(x));
  if (errs.length) console.log("console errors:", errs.slice(0, 3).join(" | "));
  await page.close();
  process.exit(failed ? 1 : 0);
}

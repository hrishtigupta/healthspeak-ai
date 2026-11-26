// Dogri (doi) end to end, synthetic data only: the language picker (never blank, survives a refresh and
// a login), a multi-turn Dogri conversation that reuses the normal dialogue engine (real IndicTrans2
// translation when installed), context across messages, negation, urgent symptoms, review-and-send,
// and what staff receive (original Dogri text kept, English shown separately).
//
// Voice is NOT covered here: headless Edge has no microphone, and no genuine Dogri audio is available.
// Needs the API in development mode (default for local runs).
import { launch } from "./cdp.mjs";

const [, , BROWSER, SEED_PW] = process.argv;
const APP = process.env.E2E_APP || "http://127.0.0.1:5173/";
const API = process.env.E2E_API || "http://127.0.0.1:8000/api";
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + String(extra).slice(0, 220) : ""}`); };
const page = await launch({ browser: BROWSER });
const t = (js) => page.eval(`window.__t.${js}`);

const stamp = Date.now().toString().slice(-7);
const PHONE = "96" + stamp.padStart(8, "0");
const NAME = `E2E Dogri ${stamp}`;
const DEVANAGARI = /[ऀ-ॿ]/;
const REPLY_N = (n) => `document.querySelectorAll('.message.doctor .bubble > p:not(.thinking)').length >= ${n}`;
const assistantTexts = () => page.eval("[...document.querySelectorAll('.message.doctor .bubble > p:not(.thinking)')].map(p => p.innerText)");
const say = async (text, expectBubbles) => {
  await t(`set(window.__t.byPh('Type your message'), ${JSON.stringify(text)})`);
  await t("btn('Send')");
  await page.waitFor(REPLY_N(expectBubbles) + " && !document.querySelector('.thinking')", 150000);
};
const sidebarSelect = () => page.eval(`(() => { const s = document.querySelector('.patient-sidebar .language select'); const c = getComputedStyle(s);
  return { text: s.selectedOptions[0].text, options: [...s.options].map(o => o.text), color: c.color, width: s.getBoundingClientRect().width, scroll: s.scrollWidth, client: s.clientWidth }; })()`);
const myPrefs = (tok) => page.eval(`fetch('${API}/users/me', {headers:{Authorization:'Bearer ${tok}'}}).then(r => r.json())`);

try {
  await page.goto(APP);
  await page.waitFor("window.__t.has('Your Language')");
  const consent = await page.eval(`fetch('${API}/consent/current?language=doi').then(r => r.json())`);
  check("the consent text is served for Dogri (Hindi text until a reviewed Dogri one exists)", consent.language === "doi" && DEVANAGARI.test(consent.text), consent.language);
  const reg = await page.eval(`fetch('${API}/patients/register', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({full_name:'${NAME}', phone:'${PHONE}', date_of_birth:'1988-03-03', gender:'female', password:'E2E-Dogri-${stamp}',
      preferred_language:'doi', consent:{version:'${consent.version}', granted:true, language:'doi'}})}).then(r => r.json())`);
  const tok = reg.access_token;
  check("a Dogri-speaking patient can register (language stored as doi)", reg.patient && reg.patient.preferred_language === "doi", reg.patient && reg.patient.preferred_language);
  await page.eval(`sessionStorage.setItem('healthspeak.token', ${JSON.stringify(tok)})`);
  await page.goto(APP);
  await page.waitFor(`window.__t.has('Welcome, ${NAME}')`, 20000);

  // ---- language picker ----
  let sel = await sidebarSelect();
  check("the picker lists English, Hindi, Urdu and Dogri", sel.options.length === 4 && sel.options.includes("Dogri — डोगरी"), sel.options.join(" | "));
  await page.eval("window.__t.set(document.querySelector('.patient-sidebar .language select'), 'doi')");
  await page.waitFor("document.documentElement.lang === 'doi'");
  sel = await sidebarSelect();
  check("Dogri is selected and its name is visible (never blank)", sel.text === "Dogri — डोगरी" && sel.width > 40, sel.text);
  check("the name is not clipped in the sidebar box", sel.scroll <= sel.client + 1, `${sel.scroll} vs ${sel.client}`);
  check("Dogri keeps left-to-right layout (Devanagari)", await page.eval("document.documentElement.dir === 'ltr'"));
  check("screens still show text (Dogri, falling back to Hindi/English), not blanks",
        DEVANAGARI.test(await page.eval("document.querySelector('.patient-main').innerText")));
  check("the choice is saved on the account", (await myPrefs(tok)).ui_language === "doi");
  await page.goto(APP);
  await page.waitFor("document.documentElement.lang === 'doi'", 20000);
  check("Dogri is still selected after a refresh", (await sidebarSelect()).text === "Dogri — डोगरी");
  await page.eval("sessionStorage.removeItem('healthspeak.token')");
  await page.goto(APP);
  await page.waitFor("window.__t.has('Your Language')");
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Welcome Back')");
  await t(`set(window.__t.byPh('Enter your email or mobile'), '${PHONE}')`);
  await t(`set(window.__t.byPh('Enter your password'), 'E2E-Dogri-${stamp}')`);
  await t("btn('Log in')");
  await page.waitFor("document.querySelector('.patient-sidebar')", 20000);
  await page.waitFor("document.documentElement.lang === 'doi'", 10000);
  check("after logging in again the Dogri choice is restored", (await sidebarSelect()).text === "Dogri — डोगरी");
  await page.eval("window.__t.set(document.querySelector('.patient-sidebar .language select'), 'en')");
  await page.waitFor("window.__t.has('PATIENT DASHBOARD')");

  // ---- conversation ----
  await t("btn('Start Text Chat')");
  await page.waitFor("document.querySelector('.chat-page')");
  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'Dogri')");
  check("the speaking-language list offers Dogri", await page.eval("[...document.querySelector('.compose-tools select').options].some(o => o.value === 'Dogri')"));
  const greeting = await page.eval("document.querySelector('.message.doctor .bubble > p')?.innerText || ''");
  check("the assistant's greeting is in Dogri even though the screen is in English", DEVANAGARI.test(greeting) && !/Welcome/.test(greeting), greeting);
  check("controls stay in the display language (English)", await page.eval("!!window.__t.byPh('Type your message')"));
  const first = "मिगी कल्लै थमां पेट च दर्द होआ करदा ऐ।";
  await say(first, 2);
  let texts = await assistantTexts();
  check("the assistant replies in Dogri (Devanagari, Dogri question word)", DEVANAGARI.test(texts[1]) && texts[1].includes("कुत्थें"), texts[1]);
  check("it understood abdominal pain: asks WHERE, not how long (duration already given)", !/कदूं थमां/.test(texts[1]), texts[1]);

  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'English')");
  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'Dogri')");
  check("switching the language does not delete the conversation",
        (await page.eval("document.body.innerText")).includes(first) && (await assistantTexts()).length === 2);

  await say("थल्ले, सज्जे पासे", 3);
  texts = await assistantTexts();
  check("the next question is a different one (severity)", /तेज/.test(texts[2]) && texts[2] !== texts[1], texts[2]);
  await say("बड़ा तेज ऐ ते मिगी बुखार बी ऐ", 4);
  for (let i = 0; i < 4 && !(await page.eval("!!document.querySelector('[data-testid=suggestion-card]')")); i++) {
    await say("नेईं", 5 + i);
  }
  await page.waitFor("document.querySelector('[data-testid=suggestion-card]')");
  const card = await page.eval("document.querySelector('[data-testid=suggestion-card]').innerText");
  check("it suggests Gastroenterology as PRELIMINARY, using earlier messages", /Gastroenterology/.test(card), card);
  check("the card is in Dogri (local department name, Dogri note) and shows the strength",
        /पेट रोग/.test(card) && /बमारी दी पन्छान नेईं/.test(card) && /मेल/.test(card), card);
  const finalText = (await assistantTexts()).pop();
  check("the explanation is in Dogri and says it is only preliminary", DEVANAGARI.test(finalText) && finalText.includes("सिर्फ") && finalText.includes("पेट"), finalText);
  texts = await assistantTexts();
  check("no assistant message is repeated", new Set(texts).size === texts.length);

  await t("btn('Review and send')");
  await page.waitFor("document.querySelector('.review-list')");
  const review = await page.eval("document.querySelector('.review-list').innerText");
  check("the review step shows the patient's own Dogri words", review.includes("मिगी कल्लै थमां") && review.includes("बड़ा तेज ऐ"));
  await page.eval("[...document.querySelectorAll('.overlay button')].find(b => b.innerText.trim() === 'End chat').click()");
  await page.waitFor("window.__t.toast().includes('sent for staff review')", 90000);
  check("the Dogri intake is submitted", true);

  // ---- what staff receive ----
  const staffTok = await page.eval(`fetch('${API}/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({identifier:'staff@example.com', password:${JSON.stringify(SEED_PW)}})}).then(r => r.json()).then(j => j.access_token)`);
  const staffGet = (path) => page.eval(`fetch('${API}${path}', {headers:{Authorization:'Bearer ${staffTok}'}}).then(r => r.json())`);
  const list = await staffGet("/intakes?review_status=pending_review&limit=200");
  const mine = list.items.find((i) => i.patient_name.includes(stamp));
  const detail = await staffGet(`/intakes/${mine.id}`);
  check("staff see language Dogri and the ORIGINAL Dogri text, unchanged", detail.original_language === "doi" && detail.original_text.startsWith(first), detail.original_language);
  check("the English text is a separate field (machine translation, not the original)",
        typeof detail.english_text === "string" && /pain/i.test(detail.english_text) && !DEVANAGARI.test(detail.english_text), detail.english_text);
  check("staff see the extracted symptoms and the saved department suggestion",
        detail.symptoms.some((s) => s.term === "stomach pain") && detail.symptoms.some((s) => s.term === "fever")
        && detail.analysis.suggestion.department_code === "gastroenterology", detail.analysis && detail.analysis.suggestion.department_code);

  // ---- urgent symptoms in Dogri ----
  await page.waitFor("window.__t.has('PATIENT DASHBOARD')");
  await t("btn('Start Text Chat')");
  await page.waitFor("document.querySelector('.chat-page')");
  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'Dogri')");
  await say("मेरी छाती च दर्द ऐ ते मिगी साह लैने च परेशानी ऐ", 2);
  const urgent = (await assistantTexts()).pop();
  check("urgent symptoms in Dogri get emergency guidance (112) without a question first",
        DEVANAGARI.test(urgent) && urgent.includes("112") && !/[?؟]/.test(urgent), urgent);
  check("the urgent badge is shown", await page.eval("!!document.querySelector('.suggestion.urgent')"));

  // ---- typing Dogri in English letters is flagged, not converted ----
  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'Dogri')");
  await t("set(window.__t.byPh('Type your message'), 'migi bukhar nei ai')");
  await page.waitFor("document.querySelector('[data-testid=script-hint]')", 5000);
  check("Dogri typed in English letters shows a hint (no silent conversion)", /Devanagari/.test(await page.eval("document.querySelector('[data-testid=script-hint]').innerText")));
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

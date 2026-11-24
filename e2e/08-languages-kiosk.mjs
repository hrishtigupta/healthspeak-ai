// Phase 8 E2E: patient flow in English, Hindi and Urdu (RTL), per-user language
// independence, kiosk heartbeat + idle logout.
import { launch, sleep } from "./cdp.mjs";

const [, , BROWSER, SEED_PW] = process.argv;
const APP = "http://127.0.0.1:5173/";
const API = "http://127.0.0.1:8000/api";
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + String(extra).slice(0, 200) : ""}`); };
const page = await launch({ browser: BROWSER });
const t = (js) => page.eval(`window.__t.${js}`);
const html = () => page.eval("({lang: document.documentElement.lang, dir: document.documentElement.dir, bodyDir: getComputedStyle(document.body).direction})");
const setLang = (code) => page.eval(`window.__t.set(document.querySelector('.lang-switch select'), '${code}')`);
const RUN = Date.now().toString().slice(-6);
const apiAs = (id, pw, path, opts = {}) => page.eval(`(async () => {
  const tok = (await (await fetch('${API}/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({identifier:'${id}', password:${JSON.stringify(pw)}})})).json()).access_token;
  const r = await fetch('${API}${path}', {method:'${opts.method || "GET"}', headers:{Authorization:'Bearer '+tok, 'Content-Type':'application/json'}, body: ${opts.body ? `JSON.stringify(${JSON.stringify(opts.body)})` : "undefined"}});
  await fetch('${API}/auth/logout', {method:'POST', headers:{Authorization:'Bearer '+tok}});
  return r.status === 204 ? null : r.json(); })()`);

// Expected UI words per language (from the translation files).
const L = {
  en: { faq: "FAQs", signup: "Sign up", create: "Create Account", consent: "consent statement", agree: "I agree",
        chat: "Start Text Chat", send: "Send", end: "End Chat", endConfirm: "End chat", pending: "Awaiting staff review",
        logout: "Log out", welcome: "Welcome Back", createTitle: "Create your account" },
  hi: { faq: "सवाल-जवाब", signup: "साइन अप", create: "खाता बनाएँ", consent: "सहमति विवरण", agree: "मैं सहमत हूँ",
        chat: "लिखकर चैट करें", send: "भेजें", end: "चैट समाप्त करें", endConfirm: "चैट समाप्त करें", pending: "कर्मचारियों की समीक्षा बाकी",
        logout: "लॉग आउट", welcome: "फिर से स्वागत है", createTitle: "अपना खाता बनाएँ" },
  ur: { faq: "سوال و جواب", signup: "سائن اپ", create: "اکاؤنٹ بنائیں", consent: "رضامندی کا بیان", agree: "میں متفق ہوں",
        chat: "لکھ کر چیٹ کریں", send: "بھیجیں", end: "چیٹ ختم کریں", endConfirm: "چیٹ ختم کریں", pending: "عملے کا جائزہ باقی",
        logout: "لاگ آؤٹ", welcome: "دوبارہ خوش آمدید", createTitle: "اپنا اکاؤنٹ بنائیں" },
};
const MSG = { en: "I have a mild headache since this morning.", hi: "मुझे सुबह से हल्का सिरदर्द है।", ur: "مجھے صبح سے ہلکا سر درد ہے۔" };

try {
  await page.goto(APP);
  await page.waitFor("window.__t.has('Your Language')");
  // ---------- full patient flow in all three languages ----------
  for (const [i, code] of ["en", "hi", "ur"].entries()) {
    const w = L[code];
    await page.goto(APP);
    await page.waitFor("document.querySelector('.lang-switch select')");
    await setLang(code);
    await page.waitFor(`window.__t.has(${JSON.stringify(w.faq)})`);
    const h = await html();
    check(`[${code}] landing translated, lang/dir = ${h.lang}/${h.dir}`,
          h.lang === code && h.dir === (code === "ur" ? "rtl" : "ltr") && h.bodyDir === (code === "ur" ? "rtl" : "ltr"), JSON.stringify(h));
    if (code === "ur") {
      const flipped = await page.eval("getComputedStyle(document.querySelector('svg.lucide-arrow-right')).transform");
      check("[ur] arrow icons mirrored in RTL", flipped && flipped !== "none", flipped);
    }
    await page.eval(`[...document.querySelectorAll('button')].find(b => b.innerText.trim() === ${JSON.stringify(code === "en" ? "Log in" : code === "hi" ? "लॉग इन" : "لاگ ان")}).click()`);
    await page.waitFor(`window.__t.has(${JSON.stringify(w.welcome)})`);
    await t(`btn(${JSON.stringify(w.signup)})`);
    await page.waitFor(`window.__t.has(${JSON.stringify(w.createTitle)})`);
    const mobile = "96" + RUN + String(i).padStart(2, "0");
    await page.eval(`window.__t.set(document.querySelector('form.signup select'), '${{ en: "English", hi: "Hindi", ur: "Urdu" }[code]}')`);
    await page.eval(`window.__t.set(document.querySelector('form.signup input:not([type])') || document.querySelectorAll('form.signup input')[0], 'P8 ${code} Synthetic')`);
    const inputs = "document.querySelectorAll('form.signup input')";
    await page.eval(`window.__t.set(${inputs}[0], 'P8 ${code} Synthetic')`);
    await page.eval(`window.__t.set(${inputs}[1], '${mobile}')`);
    await page.eval(`window.__t.set(document.querySelector('form.signup input[type=date]'), '1991-02-03')`);
    await page.eval("window.__t.set(document.querySelectorAll('form.signup select')[1], 'Female')");
    await page.eval(`window.__t.set(document.querySelector('form.signup input[type=password]'), 'P8-Synthetic-Pass-1')`);
    await t(`btn(${JSON.stringify(w.consent)})`);
    await page.waitFor("document.querySelector('.overlay') && document.querySelector('.overlay').innerText.length > 100");
    const consentScript = await page.eval("document.querySelector('.overlay p').innerText.slice(0, 40)");
    const scriptOk = code === "hi" ? /[ऀ-ॿ]/.test(consentScript) : code === "ur" ? /[؀-ۿ]/.test(consentScript) : /[a-z]/i.test(consentScript);
    check(`[${code}] consent text shown in ${code}`, scriptOk, consentScript);
    await t(`btn(${JSON.stringify(w.agree)})`);
    await page.waitFor("!document.querySelector('.overlay')");
    await t(`btn(${JSON.stringify(w.create)})`);
    await page.waitFor(`document.querySelector('.patient-layout') && window.__t.has(${JSON.stringify(w.chat)})`, 15000);
    const me = await page.eval(`fetch('${API}/users/me', {headers:{Authorization:'Bearer '+sessionStorage.getItem('healthspeak.token')}}).then(r=>r.json())`);
    check(`[${code}] new patient's saved display language = ${me.ui_language}`, me.ui_language === code);
    await t(`btn(${JSON.stringify(w.chat)})`);
    await page.waitFor("document.querySelector('.chat-page')");
    check(`[${code}] chat greeting translated`, code === "en" ? await t("has('Hello! Welcome')") : code === "hi" ? await t("has('नमस्ते')") : await t("has('السلام علیکم')"));
    await page.eval(`window.__t.set(document.querySelector('.compose-tools select'), '${{ en: "English", hi: "Hindi", ur: "Urdu" }[code]}')`);
    await page.eval(`window.__t.set(document.querySelector('.sendline input'), ${JSON.stringify(MSG[code] + " P8-" + RUN)})`);
    await page.eval(`document.querySelector('.sendline button').click()`);
    await page.waitFor(`window.__t.has(${JSON.stringify("P8-" + RUN)}) && document.querySelectorAll('.message').length >= 3`, 15000);
    await t(`btn(${JSON.stringify(w.end)})`);
    await page.waitFor("document.querySelector('.overlay')");
    await page.eval(`[...document.querySelectorAll('.overlay .btn')].pop().click()`);
    await page.waitFor(`document.querySelector('.patient-layout') && window.__t.has(${JSON.stringify(w.pending)})`, 15000);
    check(`[${code}] intake submitted; dashboard status in ${code}`, true);
    await t(`btn(${JSON.stringify(w.logout)})`);
    await page.waitFor("document.querySelector('.topbar')");
  }

  // ---------- per-user independence ----------
  await setLang("ur");  // this device: Urdu
  await t("btn('لاگ ان')");
  await page.waitFor("window.__t.has('دوبارہ خوش آمدید')");
  await t(`set(window.__t.byPh('اپنا ای میل یا موبائل نمبر درج کریں'), 'staff@example.com')`);
  await t(`set(window.__t.byPh('اپنا پاس ورڈ درج کریں'), ${JSON.stringify(SEED_PW)})`);
  await t("btn('لاگ ان')");
  await page.waitFor("window.__t.has('Hello, Demo Reception Staff')", 15000);
  const staffHtml = await html();
  check("staff logs in on an Urdu device and gets their OWN language (English, LTR)", staffHtml.lang === "en" && staffHtml.dir === "ltr", JSON.stringify(staffHtml));
  await setLang("hi");
  await page.waitFor("window.__t.has('मरीज़ों की कतार')");
  const patientLang = (await apiAs("patient@example.com", SEED_PW, "/users/me")).ui_language;
  check("staff switching to Hindi does not change the demo patient's language", patientLang === "hi" || patientLang === "en" || patientLang === "ur", patientLang);
  const staffMe = await page.eval(`fetch('${API}/users/me', {headers:{Authorization:'Bearer '+sessionStorage.getItem('healthspeak.token')}}).then(r=>r.json())`);
  check("staff's own preference saved as Hindi", staffMe.ui_language === "hi");
  await setLang("en");  // restore staff to English
  await page.waitFor("window.__t.has('Patient queue')");
  await t("btn('Log out')");
  await page.waitFor("document.querySelector('.topbar')");
  check("after logout the device language (Urdu) returns", (await html()).lang === "ur");
  await setLang("en");

  // ---------- kiosk ----------
  const kiosk = await apiAs("admin@example.com", SEED_PW, "/admin/kiosks", { method: "POST", body: { code: `e2e-${RUN}`, name: "E2E kiosk", location: "Test bench" } });
  await page.eval("localStorage.setItem('healthspeak.kioskIdleSeconds', '15')");
  await page.goto(`${APP}?kiosk=${encodeURIComponent(kiosk.key)}`);
  await page.waitFor("window.__t.has('Your Language')");
  await sleep(1500);
  check("kiosk key removed from the address bar", !(await page.eval("location.search")).includes("kiosk="));
  const listed = (await apiAs("admin@example.com", SEED_PW, "/admin/kiosks")).find((k) => k.code === `e2e-${RUN}`);
  check("kiosk heartbeat received: online", listed && listed.online === true, JSON.stringify(listed && listed.last_report));
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Welcome Back')");
  await t(`set(window.__t.byPh('Enter your email or mobile'), 'patient@example.com')`);
  await t(`set(window.__t.byPh('Enter your password'), ${JSON.stringify(SEED_PW)})`);
  await t("btn('Log in')");
  await page.waitFor("document.querySelector('.patient-layout')", 15000);
  await sleep(17000);  // no activity
  const loggedOut = await page.eval("!!document.querySelector('.topbar') && !sessionStorage.getItem('healthspeak.token')");
  check("idle kiosk session logged out automatically (privacy)", loggedOut, await t("toast()"));
  // clean up: deactivate test kiosk, leave this browser out of kiosk mode
  await apiAs("admin@example.com", SEED_PW, `/admin/kiosks/${kiosk.id}`, { method: "PATCH", body: { is_active: false } });
  await page.eval("localStorage.removeItem('healthspeak.kioskKey'); localStorage.removeItem('healthspeak.kioskIdleSeconds'); localStorage.removeItem('healthspeak.deviceLanguage')");

  check("no uncaught page errors", page.consoleErrors.length === 0, page.consoleErrors.slice(0, 2).join(" | "));
} catch (err) {
  check("script error", false, err.message);
  try { console.log("PAGE TEXT:", (await page.text()).slice(0, 700)); console.log("TOAST:", await t("toast()")); } catch {}
} finally {
  if (page.consoleErrors.length) console.log("CONSOLE ERRORS:\n" + page.consoleErrors.map((e) => e.slice(0, 2500)).join("\n----\n"));
  await page.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);

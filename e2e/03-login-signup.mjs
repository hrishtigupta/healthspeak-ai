// Phase 3 end-to-end: real login / sign-up / consent / logout through the React UI.
import { launch, HELPERS, sleep } from "./cdp.mjs";

const [, , BROWSER, SEED_PW] = process.argv;
const APP = process.env.E2E_APP || "http://127.0.0.1:5173/";
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + extra : ""}`); };

const page = await launch({ browser: BROWSER });
const t = (js) => page.eval(`window.__t.${js}`);
try {
  await page.goto(APP);
  await page.waitFor("window.__t.has('Your Language')");
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Welcome Back')");

  // 1. wrong password -> backend 401 message shown
  await t("set(window.__t.byPh('Enter your email or mobile'), 'doctor@example.com')");
  await t("set(window.__t.byPh('Enter your password'), 'definitely-wrong')");
  await t("btn('Log in')");
  await page.waitFor("window.__t.toast().length > 0");
  check("wrong password shows a clear (translated) message", (await t("toast()")).includes("password is not correct"), await t("toast()"));

  // 2. staff login via real API -> staff dashboard with real name
  await page.eval("document.querySelector('.toast button')?.click()");
  await t(`set(window.__t.byPh('Enter your password'), ${JSON.stringify(SEED_PW)})`);
  await t("set(window.__t.byPh('Enter your email or mobile'), 'staff@example.com')");
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Hello, Demo Reception Staff')");
  check("staff login reaches staff dashboard", true);
  check("token kept in sessionStorage", !!(await page.eval("sessionStorage.getItem('healthspeak.token')")));

  // 3. logout -> home, token gone, server rejects it
  const staffToken = await page.eval("sessionStorage.getItem('healthspeak.token')");
  await t("btn('Log out')");
  await page.waitFor("window.__t.has('Your Health,') && window.__t.toast().includes('logged out')");
  check("logout returns home and clears token", !(await page.eval("sessionStorage.getItem('healthspeak.token')")));
  const meAfter = await page.eval(`fetch('${process.env.E2E_API || "http://127.0.0.1:8000/api"}/users/me',{headers:{Authorization:'Bearer ${staffToken}'}}).then(r=>r.status)`);
  check("old token rejected by server after logout", meAfter === 401, `status ${meAfter}`);

  // 4. patient sign-up with consent
  const mobile = "97" + String(Date.now()).slice(-8);
  const name = "E2E Synthetic Patient";
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Welcome Back')");
  await t("btn('Sign up')");
  await page.waitFor("window.__t.has('Create your account')");
  const langOptions = await page.eval("[...document.querySelector('form.signup select').options].map(o=>o.text).join(',')");
  check("sign-up language list is English/Hindi/Urdu", langOptions === "English,Hindi,Urdu", langOptions);
  await page.eval("window.__t.set(document.querySelector('form.signup select'), 'Urdu')");
  await t(`set(window.__t.byPh('e.g. Ankit'), ${JSON.stringify(name)})`);
  await t(`set(window.__t.byPh('+91 Enter your mobile'), '${mobile}')`);
  await t("set('form.signup input[type=date]', '1992-03-04')");
  await page.eval("window.__t.set(document.querySelectorAll('form.signup select')[1], 'Female')");
  await t("set(window.__t.byPh('At least 8 characters'), 'E2E-Synthetic-Pass-1')");
  // submit without consent -> blocked by the browser's required checkbox / our check
  await t("btn('consent statement')");
  await page.waitFor("document.querySelector('.overlay') && window.__t.has('Version draft-')");
  const urduShown = await page.eval("/[\\u0600-\\u06FF]/.test(document.querySelector('.overlay').innerText)");
  check("consent text shown in Urdu with version", urduShown);
  await t("btn('I agree')");
  await page.waitFor("!document.querySelector('.overlay')");
  check("'I agree' ticks the consent checkbox", await page.eval("document.querySelector('form.signup input[type=checkbox]').checked"));
  await t("btn('Create Account')");
  await page.waitFor(`window.__t.has('Welcome, ${name}')`, 10000);
  check("sign-up creates account and opens patient dashboard", true);

  // 5. patient logout, then log in with the mobile number
  await t("btn('Log out')");
  await page.waitFor("window.__t.has('Your Health,')");
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Welcome Back')");
  await t(`set(window.__t.byPh('Enter your email or mobile'), '${mobile}')`);
  await t("set(window.__t.byPh('Enter your password'), 'E2E-Synthetic-Pass-1')");
  await t("btn('Log in')");
  await page.waitFor(`window.__t.has('Welcome, ${name}')`);
  check("new patient logs in with mobile number", true);
  await t("btn('Log out')");
  await page.waitFor("window.__t.has('Your Health,')");

  // 6. duplicate sign-up -> friendly conflict message
  await t("btn('Log in')"); await page.waitFor("window.__t.has('Welcome Back')");
  await t("btn('Sign up')"); await page.waitFor("window.__t.has('Create your account')");
  const leftover = await page.eval(`({ name: window.__t.byPh('e.g. Ankit').value, mobile: window.__t.byPh('+91 Enter your mobile').value,
    dob: document.querySelector('form.signup input[type=date]').value, agreed: document.querySelector('form.signup input[type=checkbox]').checked })`);
  check("previous person's sign-up details are cleared (kiosk privacy)",
        !leftover.name && !leftover.mobile && !leftover.dob && !leftover.agreed, JSON.stringify(leftover));
  await t(`set(window.__t.byPh('e.g. Ankit'), 'Another Synthetic')`);
  await t(`set(window.__t.byPh('+91 Enter your mobile'), '${mobile}')`);
  await t("set('form.signup input[type=date]', '1990-01-01')");
  await page.eval("window.__t.set(document.querySelectorAll('form.signup select')[1], 'Male')");
  await t("set(window.__t.byPh('At least 8 characters'), 'E2E-Synthetic-Pass-2')");
  await page.eval("document.querySelector('form.signup input[type=checkbox]').click()");
  await t("btn('Create Account')");
  await page.waitFor("window.__t.toast().includes('already exists')", 10000).catch(() => {});
  check("duplicate mobile shows 'already exists'", (await t("toast()")).includes("already exists"), await t("toast()"));

  check("no uncaught page errors", page.consoleErrors.filter(e => !/key/i.test(e)).length === 0,
        page.consoleErrors.slice(0, 3).join(" | "));
} catch (err) {
  check("script error", false, err.message);
  try { console.log("PAGE TEXT:", (await page.text()).slice(0, 600)); } catch {}
} finally {
  await page.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);

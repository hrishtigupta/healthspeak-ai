// Patients who type Hindi/Urdu in English letters get a friendly hint (Devanagari / Urdu script
// or voice). The hint never blocks sending. Independent of whether translation is enabled.
import { launch } from "./cdp.mjs";

const [, , BROWSER, SEED_PW] = process.argv;
const APP = process.env.E2E_APP || "http://127.0.0.1:5173/";
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + String(extra).slice(0, 160) : ""}`); };
const page = await launch({ browser: BROWSER });
const t = (js) => page.eval(`window.__t.${js}`);
const HI = "typing Hindi in English letters";
const UR = "typing Urdu in English letters";
const pick = (lang) => page.eval(`window.__t.set(document.querySelector('.compose-tools select'), '${lang}')`);
const type = (text) => t(`set(window.__t.byPh('Type your message'), ${JSON.stringify(text)})`);
const hint = () => page.eval("document.querySelector('[data-testid=script-hint]')?.innerText || ''");

try {
  await page.goto(APP);
  await page.waitFor("window.__t.has('Your Language')");
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Welcome Back')");
  await t("set(window.__t.byPh('Enter your email or mobile'), 'patient@example.com')");
  await t(`set(window.__t.byPh('Enter your password'), ${JSON.stringify(SEED_PW)})`);
  await t("btn('Log in')");
  await page.waitFor("window.__t.has('Welcome, Demo Patient')");
  await page.waitFor("!window.__t.has('Loading...')");
  await t("btn('Start Text Chat')");
  await page.waitFor("document.querySelector('.chat-page')");

  await pick("Hindi");
  await type("");
  check("no hint on an empty message", (await hint()) === "");
  await type("mujhe bukhar hai aur khansi bhi");
  await page.waitFor(`window.__t.has('${HI}')`);
  const h = await hint();
  check("Hindi selected + Latin letters shows the Hindi hint", h.includes(HI) && h.includes("Devanagari") && h.includes("microphone"), h);
  check("hint is friendly and offers a voice shortcut", h.includes("Use voice instead") && !/error|invalid|not allowed/i.test(h), h);

  await type("मुझे बुखार है और खांसी भी");
  await page.waitFor(`!window.__t.has('${HI}')`);
  check("Devanagari text clears the hint", (await hint()) === "");

  await type("मुझे fever है और cough भी");
  check("mixed Devanagari + English medicine/symptom words do not trigger it", (await hint()) === "");

  await type("mujhe bukhar hai aur khansi bhi");
  await page.waitFor(`window.__t.has('${HI}')`);
  await pick("English");
  await page.waitFor(`!window.__t.has('${HI}')`);
  check("switching the language to English removes the hint", (await hint()) === "");

  await pick("Urdu");
  await page.waitFor(`window.__t.has('${UR}')`);
  check("Urdu selected + Latin letters shows the Urdu hint", (await hint()).includes("Urdu script"), await hint());

  await pick("Hindi");
  await type("fever");
  check("a single Latin word does not trigger the hint", (await hint()) === "");

  await type("mujhe bukhar hai aur khansi bhi");
  await page.waitFor(`window.__t.has('${HI}')`);
  check("the Send button is not disabled by the hint",
        await page.eval("!document.querySelector('.sendline button').disabled"));
  await page.eval("document.querySelector('[data-testid=script-hint] button').click()");
  await page.waitFor("document.querySelector('.voice-screen')");
  check("'Use voice instead' opens the voice screen", true);

  check("no uncaught page errors", page.consoleErrors.filter((e) => !/unique "key"/.test(e)).length === 0,
        page.consoleErrors.filter((e) => !/unique "key"/.test(e)).slice(0, 2).join(" | "));
} catch (err) {
  check("script error", false, err.message);
  try { console.log("PAGE TEXT:", (await page.text()).slice(0, 700)); } catch {}
} finally {
  await page.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);

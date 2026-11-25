// Phase 5 end-to-end: fake microphone (synthetic TTS wav) -> MediaRecorder -> upload ->
// local Whisper on the server -> patient reviews text -> submit -> staff review.
import { launch, sleep } from "./cdp.mjs";
import { translationState } from "./translation-state.mjs";

const [, , BROWSER, SEED_PW, WAV] = process.argv;
const APP = "http://127.0.0.1:5173/";
const API = "http://127.0.0.1:8000/api";
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + String(extra).slice(0, 200) : ""}`); };

// Works with translation on (real model) or off: the expectations below follow the live state.
const MT = await translationState(SEED_PW);
console.log(`translation model: ${MT.state}`);
const page = await launch({
  browser: BROWSER,
  args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
         `--use-file-for-fake-audio-capture=${WAV}`, "--autoplay-policy=no-user-gesture-required"],
});
const t = (js) => page.eval(`window.__t.${js}`);
const RUN = Date.now().toString().slice(-6);
const MARK = `E2E-P5-${RUN}`, MARKH = `E2E-P5H-${RUN}`;
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
const token = () => page.eval("sessionStorage.getItem('healthspeak.token')");
const apiGet = async (path) => page.eval(`fetch('${API}${path}', {headers:{Authorization:'Bearer '+sessionStorage.getItem('healthspeak.token')}}).then(r=>r.json())`);

try {
  await login("patient@example.com");
  await page.waitFor("window.__t.has('Welcome, Demo Patient')");
  await t("btn('Tap to Speak')");
  await page.waitFor("document.querySelector('.voice-screen button.mic')");
  await page.eval("window.__t.set(document.querySelector('.voice-bottom select'), 'English')");
  const webSpeechUsed = await page.eval("typeof window.__speechUsed !== 'undefined'");
  await page.eval("document.querySelector('.voice-screen button.mic').click()");
  await page.waitFor("window.__t.has('Listening...')", 8000);
  check("recording starts (fake microphone)", true);
  await sleep(7500);
  await page.eval("document.querySelector('.voice-screen button.mic').click()");
  await page.waitFor("window.__t.has('Writing down your words')", 8000).catch(() => {});
  await page.waitFor("document.querySelector('.voice-screen textarea').value.length > 0 || window.__t.toast().length > 0", 120000);
  const text = await page.eval("document.querySelector('.voice-screen textarea').value");
  check("server-side Whisper transcribed the recording", /sore throat/i.test(text) && /fever/i.test(text), text || await t("toast()"));
  // patient corrects the transcript before sending
  const approved = `${text.trim()} (${MARK})`;
  await t(`set('.voice-screen textarea', ${JSON.stringify(approved)})`);
  await t("btn('Continue to chat')");
  await page.waitFor(`window.__t.has('${MARK}')`, 15000);
  check("patient-approved text appears in chat", true);

  const conv = await page.eval(`(async () => {
    const h = {Authorization:'Bearer '+sessionStorage.getItem('healthspeak.token')};
    const c = await fetch('${API}/conversations', {method:'POST', headers:h}).then(r=>r.json());
    return c; })()`);
  const voiceMsg = conv.messages.find((m) => m.content.includes(MARK));
  check("stored message is 'voice_server' with the patient's edited text",
        voiceMsg && voiceMsg.input_mode === "voice_server" && voiceMsg.content === approved, voiceMsg && voiceMsg.input_mode);

  await t("btn('End Chat')");
  await page.waitFor("document.querySelector('.overlay')");
  await page.eval("[...document.querySelectorAll('.overlay button')].find(b => b.innerText.trim() === 'End chat').click()");
  await page.waitFor("window.__t.toast().includes('sent for staff review')", 15000);
  check("intake submitted", true);

  // second intake in Hindi (typed) to exercise the translation-unavailable path
  await t("btn('Start Text Chat')");
  await page.waitFor("document.querySelector('.chat-page')");
  await page.eval("window.__t.set(document.querySelector('.compose-tools select'), 'Hindi')");
  await t(`set(window.__t.byPh('Type your message'), '${MARKH} मुझे दो दिन से खांसी है।')`);
  await t("btn('Send')");
  await page.waitFor(`window.__t.has('${MARKH}')`);
  await t("btn('End Chat')");
  await page.waitFor("document.querySelector('.overlay')");
  await page.eval("[...document.querySelectorAll('.overlay button')].find(b => b.innerText.trim() === 'End chat').click()");
  await page.waitFor(`document.querySelector('.patient-layout') && [...document.querySelectorAll('.history-row')].some(r => r.innerText.includes('${MARKH}'))`, 30000);
  await logout();

  // staff
  await login("staff@example.com");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
  const status = await apiGet("/ai/status");
  const asr = status.models.find((m) => m.name === "Speech recognition");
  const mt = status.models.find((m) => m.name === "Translation");
  check("AI status: speech model ready", asr.state === "ready", `${asr.state} ${asr.device} load ${asr.load_seconds}s`);
  if (MT.state === "ready") {
    check("AI status: translation model ready", mt.state === "ready", `${mt.state} ${mt.device}`);
  } else {
    check("AI status: translation unavailable with a clear reason", mt.state === "unavailable" && /not on this computer|download/i.test(mt.detail || ""), mt.detail);
  }

  await page.waitFor(`window.__t.has('${MARKH}')`, 10000);
  await page.eval(`[...document.querySelectorAll('.queue-row')].find(r => r.innerText.includes('${MARKH}')).querySelector('button').click()`);
  await page.waitFor("window.__t.has('Review intake')");
  if (MT.state === "ready") {
    check("Hindi intake was machine-translated: labelled unreviewed, English shown, no retry needed",
          (await t("has('MACHINE TRANSLATION (UNREVIEWED)')")) && (await t("has('Machine translation by')"))
          && /cough/i.test(await page.text()) && !(await t("has('Retry machine translation')")));
  } else {
    check("Hindi intake shows translation pending + reason + retry button",
          (await t("has('TRANSLATION PENDING')")) && (await t("has('Retry machine translation')")) && (await t("has('download_models')")));
    await clearToast();
    await t("btn('Retry machine translation')");
    await page.waitFor("window.__t.toast().length > 0", 15000);
    check("retry while model missing gives a clear message", /not on this computer|unavailable/i.test(await t("toast()")), await t("toast()"));
  }
  await t("btn('Back to overview')");
  await page.waitFor(`window.__t.has('${MARK}')`);

  await page.eval(`[...document.querySelectorAll('.queue-row')].find(r => r.innerText.includes('(${MARK})')).querySelector('button').click()`);
  await page.waitFor("window.__t.has('Review intake')");
  check("voice intake: original = patient-approved text, English needs no translation",
        (await t(`has(${JSON.stringify(approved)})`)) && (await t("has('ORIGINAL IS ENGLISH')")));
  await clearToast();
  await t("btn('Confirm intake')");
  await page.waitFor("window.__t.toast().includes('Intake confirmed')");
  check("staff confirmed the voice intake", true);
  await t("btn('Back to overview')");
  await page.waitFor("window.__t.has('Intakes awaiting review')");
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

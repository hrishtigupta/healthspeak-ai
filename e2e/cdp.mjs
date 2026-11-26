// Minimal headless-Edge driver over the Chrome DevTools Protocol (no npm deps).
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function launch({ browser, port = 9333, url = "about:blank", args = [] }) {
  const profile = mkdtempSync(join(tmpdir(), "hs-e2e-"));
  const proc = spawn(browser, [
    "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--no-default-browser-check", "--disable-extensions",
    "--window-size=1280,900", ...args, url,
  ], { stdio: "ignore" });
  let pageWs;
  for (let i = 0; i < 60 && !pageWs; i++) {
    await sleep(250);
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      pageWs = list.find((t) => t.type === "page")?.webSocketDebuggerUrl;
    } catch { /* not up yet */ }
  }
  if (!pageWs) throw new Error("browser did not start");
  const ws = new WebSocket(pageWs);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0;
  const pending = new Map();
  const consoleErrors = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { res, rej } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? rej(new Error(msg.error.message)) : res(msg.result);
    } else if (msg.method === "Runtime.exceptionThrown") {
      consoleErrors.push(msg.params.exceptionDetails?.exception?.description || "exception");
    } else if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
      consoleErrors.push(msg.params.args.map((a) => a.value ?? a.description).join(" "));
    }
  };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const mid = ++id;
    pending.set(mid, { res, rej });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  await send("Runtime.enable");
  await send("Page.enable");

  const page = {
    consoleErrors,
    async eval(expr) {
      const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
      return r.result.value;
    },
    async goto(u) {
      await send("Page.navigate", { url: u });
      await sleep(300);
      await page.waitFor("document.readyState === 'complete'", 30000); // first load can be slow while Vite compiles
      await page.eval(HELPERS);
    },
    async waitFor(expr, timeout = 8000) {
      const t0 = Date.now();
      while (Date.now() - t0 < timeout) {
        try { if (await page.eval(`!!(${expr})`)) return true; } catch { /* retry */ }
        await sleep(100);
      }
      throw new Error(`timeout waiting for: ${expr}`);
    },
    text: () => page.eval("document.body.innerText"),
    async close() {
      try { ws.close(); } catch {}
      proc.kill();
      await sleep(500);
      try { rmSync(profile, { recursive: true, force: true }); } catch {}
    },
  };
  return page;
}

// Injected into the page: helpers that drive React-controlled inputs correctly.
const HELPERS = `
window.__t = {
  set(el, v) {
    if (typeof el === 'string') el = document.querySelector(el);
    if (!el) throw new Error('no element');
    const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype
      : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
    el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
    return true;
  },
  byPh(ph) { return [...document.querySelectorAll('input,textarea')].find(e => (e.placeholder||'').includes(ph)); },
  btn(text) {
    const b = [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null || b.closest('.overlay'))
      .find(b => b.innerText.trim().toLowerCase().includes(text.toLowerCase()) || (b.getAttribute('aria-label')||'').toLowerCase() === text.toLowerCase());
    if (!b) throw new Error('no button: ' + text);
    b.click(); return true;
  },
  has(text) { return document.body.innerText.includes(text); },
  toast() { return document.querySelector('.toast')?.innerText || ''; },
};
true;
`;
export { HELPERS, sleep };

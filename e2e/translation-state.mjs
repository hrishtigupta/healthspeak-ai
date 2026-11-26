// Asks the running API whether the local translation model can be used right now, so
// suites can assert the right behaviour for BOTH states instead of assuming one.
//   "ready"        - the model loads: Hindi/Urdu text is machine-translated on submit
//   "unavailable"  - not downloaded / AI off: intakes stay "translation pending"
// Uses staff credentials (the endpoint is staff-only) and retries (Node keep-alive resets).
const API = process.env.E2E_API || "http://127.0.0.1:8000/api";

async function withRetry(fn, tries = 4) {
  let last;
  for (let i = 0; i < tries; i++) {
    try { return await fn(); } catch (e) { last = e; await new Promise((r) => setTimeout(r, 400 * (i + 1))); }
  }
  throw last;
}

export async function translationState(seedPassword) {
  const login = await withRetry(() => fetch(`${API}/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier: "staff@example.com", password: seedPassword }),
  }));
  if (!login.ok) throw new Error(`staff login failed (${login.status}); was the database seeded?`);
  const { access_token: tok } = await login.json();
  try {
    // load=true makes the server try to load the model now (can take a few seconds on CPU).
    const res = await withRetry(() => fetch(`${API}/ai/status?load=true`, { headers: { Authorization: `Bearer ${tok}` } }));
    const status = await res.json();
    const mt = status.models.find((m) => m.name === "Translation");
    return { state: mt.state === "ready" ? "ready" : "unavailable", detail: mt.detail || "", model: mt };
  } finally {
    await fetch(`${API}/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${tok}` } }).catch(() => {});
  }
}

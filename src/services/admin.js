// Administrator: kiosks and system health.
import { api } from "./api.js";

export const listKiosks = () => api("/admin/kiosks");
export const registerKiosk = (code, name, location) =>
  api("/admin/kiosks", { method: "POST", body: { code, name, location: location || null } });
export const setKioskActive = (id, isActive) =>
  api(`/admin/kiosks/${id}`, { method: "PATCH", body: { is_active: isActive } });
export const rotateKioskKey = (id) => api(`/admin/kiosks/${id}/rotate-key`, { method: "POST" });
export const systemHealth = () => api("/admin/system-health");

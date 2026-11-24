// Queue, schedules, appointments, notifications and dashboards.
import { api } from "./api.js";

const qs = (params) => {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`);
  return parts.length ? `?${parts.join("&")}` : "";
};

// ----- queue -----
export const listQueue = (filters = {}) => api(`/queue${qs(filters)}`);
export const getVisit = (id) => api(`/queue/${id}`);
export const setVisitStatus = (id, status) =>
  api(`/queue/${id}/status`, { method: "POST", body: { status } });
export const assignVisit = (id, changes) => api(`/queue/${id}`, { method: "PATCH", body: changes });
export const addVisitNote = (id, text) =>
  api(`/queue/${id}/notes`, { method: "POST", body: { text } });
export const addToQueue = (patientId, departmentId, doctorId) =>
  api("/queue", {
    method: "POST",
    body: { patient_id: patientId, department_id: departmentId, doctor_user_id: doctorId || null },
  });

// ----- doctors, schedules, appointments -----
export const listDoctors = () => api("/doctors");
export const listSlots = (doctorId, day) => api(`/appointments/slots${qs({ doctor_user_id: doctorId, day })}`);
export const bookAppointment = (patientId, doctorId, startsAt, reason) =>
  api("/appointments", {
    method: "POST",
    body: { patient_id: patientId, doctor_user_id: doctorId, starts_at: startsAt, reason: reason || null },
  });
export const listAppointments = (filters = {}) => api(`/appointments${qs(filters)}`);
export const setAppointmentStatus = (id, status, reason) =>
  api(`/appointments/${id}/status`, { method: "POST", body: { status, reason: reason || null } });

// ----- patient -----
export const myVisits = () => api("/patients/me/visits");
export const myAppointments = () => api("/patients/me/appointments");

// ----- notifications -----
export const myNotifications = () => api("/notifications");
export const markAllNotificationsRead = () => api("/notifications/read-all", { method: "POST" });

// ----- dashboards -----
export const staffDashboard = () => api("/dashboard/staff");
export const doctorDashboard = () => api("/dashboard/doctor");
export const adminDashboard = () => api("/dashboard/admin");

// Local yyyy-mm-dd for <input type="date"> defaults.
export const todayLocal = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

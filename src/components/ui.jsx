// Small shared UI building blocks (moved out of App.jsx so pages can reuse them).
import React from "react";
import { X } from "lucide-react";

export const Btn = ({ children, kind = "", ...p }) => (
  <button className={"btn " + kind} {...p}>
    {children}
  </button>
);

export const Brand = ({ go }) => (
  <button className="brand" onClick={() => go("home")}>
    <span>∿</span> HealthSpeak AI
  </button>
);

export const Field = ({ label, ...p }) => (
  <label className="field">
    <span>{label}</span>
    <input {...p} />
  </label>
);

export const Info = ({ label, value }) => (
  <div className="info">
    <small>{label}</small>
    <b>{value}</b>
  </div>
);

// Visit (queue) status labels and colours, shared by staff, doctor and patient views.
export const QUEUE_STATUS = {
  waiting: { label: "Waiting", tone: "wait" },
  checked_in: { label: "Checked-in", tone: "blue" },
  in_consultation: { label: "With doctor", tone: "blue" },
  completed: { label: "Completed", tone: "done" },
  cancelled: { label: "Cancelled", tone: "wait" },
  no_show: { label: "Did not attend", tone: "wait" },
};

export const Status = ({ value }) => {
  const s = QUEUE_STATUS[value] || { label: value, tone: "wait" };
  return <span className={"status " + s.tone}>{s.label}</span>;
};

export function Stat({ icon, label, value }) {
  return (
    <div className="stat">
      <span>{icon}</span>
      <div>
        <small>{label}</small>
        <b>{value}</b>
      </div>
    </div>
  );
}

export function ModalBox({ title, children, close }) {
  return (
    <div
      className="overlay"
      onClick={(e) => e.target === e.currentTarget && close()}
    >
      <section>
        <header>
          <h3>{title}</h3>
          <button onClick={close} aria-label="Close">
            <X />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

export const pad2 = (n) => (n === null || n === undefined ? "--" : String(n).padStart(2, "0"));

export const initials = (name) =>
  (name || "")
    .split(/\s+/)
    .filter((w) => w && !/^dr\.?$/i.test(w))
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("") || "HS";

export const timeOnly = (iso) =>
  iso ? new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : "";

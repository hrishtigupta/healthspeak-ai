// Administrator overview: aggregated numbers only (no patient details).
import React, { useEffect, useState } from "react";
import { Activity, Clock3, LayoutDashboard, LogOut, Users } from "lucide-react";
import { Brand, Stat, initials, pad2 } from "../../components/ui.jsx";
import { adminDashboard } from "../../services/visits.js";
import { LANGUAGE_NAMES, REVIEW_LABELS } from "../../services/intake.js";

function Table({ title, data, label = (k) => k }) {
  const rows = Object.entries(data || {});
  return (
    <div className="side-card">
      <span className="eyebrow">{title}</span>
      {!rows.length && <p>No data yet.</p>}
      {rows.map(([k, v]) => (
        <p key={k} className="kv">
          <span>{label(k)}</span>
          <b>{v}</b>
        </p>
      ))}
    </div>
  );
}

export default function AdminHome({ go, notify, userName, onLogout }) {
  const [d, SetD] = useState(null);
  useEffect(() => {
    adminDashboard().then(SetD).catch((err) => notify(err.message));
  }, []);
  const roleLabel = (r) => ({ patient: "Patients", doctor: "Doctors", staff: "Staff", admin: "Administrators" })[r] || r;
  return (
    <div className="staff-layout">
      <aside className="staff-sidebar">
        <Brand go={go} />
        <nav>
          <button className="active">
            <LayoutDashboard /> Overview
          </button>
        </nav>
        <div className="staff-user">
          <div className="avatar">{initials(userName)}</div>
          <div>
            <b>{userName}</b>
            <small>Administrator</small>
          </div>
          <button onClick={onLogout} title="Log out" aria-label="Log out">
            <LogOut />
          </button>
        </div>
      </aside>
      <main className="staff-main">
        <header className="dash-head">
          <div>
            <span className="eyebrow">ADMINISTRATOR DASHBOARD</span>
            <h2>Hospital overview</h2>
            <p>Totals only. No patient details are shown here.</p>
          </div>
        </header>
        {!d && <p className="empty">Loading...</p>}
        {d && (
          <>
            <div className="stats">
              <Stat icon={<Users />} label="Visits today" value={pad2(Object.values(d.queue_today).reduce((a, b) => a + b, 0))} />
              <Stat icon={<Clock3 />} label="Average wait (min)" value={d.average_wait_minutes_today ?? "--"} />
              <Stat icon={<Activity />} label="Intakes awaiting review" value={pad2(d.intakes_by_review_status.pending_review || 0)} />
            </div>
            <div className="admin-grid">
              <Table title="ACTIVE ACCOUNTS" data={d.users_by_role} label={roleLabel} />
              <Table title="INTAKES BY REVIEW STATUS" data={d.intakes_by_review_status} label={(k) => REVIEW_LABELS[k] || k} />
              <Table title="LANGUAGE USED (30 DAYS)" data={d.intakes_last_30_days_by_language} label={(k) => LANGUAGE_NAMES[k] || k} />
              <Table title="CONFIRMED BY DEPARTMENT (30 DAYS)" data={d.confirmed_last_30_days_by_department} />
              <Table title="TRANSLATION STATUS" data={d.translation_status} />
              <Table title="VOICE TRANSCRIPTIONS (30 DAYS)" data={d.transcriptions_last_30_days} />
              <Table title="QUEUE TODAY" data={d.queue_today} />
              <div className="side-card">
                <span className="eyebrow">LOCAL AI MODELS</span>
                {d.ai_models.map((m) => (
                  <p key={m.name} className="kv">
                    <span>
                      {m.name}
                      <br />
                      <small>{m.model_id}</small>
                    </span>
                    <b>{m.state.replace(/_/g, " ")}</b>
                  </p>
                ))}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

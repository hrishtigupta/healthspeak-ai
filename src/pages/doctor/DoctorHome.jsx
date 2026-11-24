// Doctor home: only the patients and appointments assigned to this doctor.
import React, { useEffect, useState } from "react";
import { CalendarDays, CheckCircle2, Clock3, LayoutDashboard, LogOut, Users } from "lucide-react";
import { Brand, Stat, initials, pad2, timeOnly } from "../../components/ui.jsx";
import QueuePanel from "../staff/QueuePanel.jsx";
import { doctorDashboard, listAppointments } from "../../services/visits.js";

export default function DoctorHome({ go, notify, userName, onLogout, onOpen }) {
  const [dash, SetDash] = useState(null);
  const [appts, SetAppts] = useState(null);
  useEffect(() => {
    doctorDashboard().then(SetDash).catch((err) => notify(err.message));
    listAppointments().then(SetAppts).catch(() => SetAppts([]));
  }, []);
  const q = dash ? dash.my_queue : null;
  return (
    <div className="staff-layout">
      <aside className="staff-sidebar">
        <Brand go={go} />
        <nav>
          <button className="active">
            <LayoutDashboard /> My day
          </button>
        </nav>
        <div className="staff-user">
          <div className="avatar">{initials(userName)}</div>
          <div>
            <b>{userName}</b>
            <small>Doctor</small>
          </div>
          <button onClick={onLogout} title="Log out" aria-label="Log out">
            <LogOut />
          </button>
        </div>
      </aside>
      <main className="staff-main">
        <header className="dash-head">
          <div>
            <span className="eyebrow">DOCTOR DASHBOARD</span>
            <h2>Hello, {userName}</h2>
            <p>Patients assigned to you today.</p>
          </div>
        </header>
        <div className="stats">
          <Stat icon={<Users />} label="Waiting / checked-in" value={q ? pad2(q.waiting + q.checked_in) : "--"} />
          <Stat icon={<Clock3 />} label="With you now" value={q ? pad2(q.in_consultation) : "--"} />
          <Stat icon={<CheckCircle2 />} label="Completed today" value={q ? pad2(q.completed) : "--"} />
          <Stat icon={<CalendarDays />} label="Appointments today" value={dash ? pad2(dash.my_appointments_today) : "--"} />
        </div>
        <QueuePanel
          eyebrow="MY PATIENTS"
          title="Patients assigned to me"
          emptyText="No patients are assigned to you right now."
          onOpen={onOpen}
          notify={notify}
        />
        <section className="queue">
          <div className="section-title">
            <div>
              <span className="eyebrow">APPOINTMENTS</span>
              <h3>Today's appointments</h3>
            </div>
          </div>
          {appts === null && <p className="empty">Loading...</p>}
          {appts && !appts.length && <p className="empty">No appointments today.</p>}
          {(appts || []).map((a) => (
            <p key={a.id}>
              <b>{timeOnly(a.starts_at)}</b> · {a.patient.name} · {a.department}
              {a.room ? ` · ${a.room}` : ""} · {a.status}
            </p>
          ))}
        </section>
      </main>
    </div>
  );
}

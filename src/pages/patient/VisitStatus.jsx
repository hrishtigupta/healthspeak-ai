// Patient's own visit token, upcoming appointments and messages.
import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Bell } from "lucide-react";
import { Status, timeOnly } from "../../components/ui.jsx";
import {
  markAllNotificationsRead,
  myAppointments,
  myNotifications,
  myVisits,
} from "../../services/visits.js";
import { formatDate } from "../../services/intake.js";

export default function VisitStatus() {
  const { t } = useTranslation();
  const [visits, SetVisits] = useState(null);
  const [appts, SetAppts] = useState(null);
  const [notes, SetNotes] = useState(null);
  useEffect(() => {
    myVisits().then(SetVisits).catch(() => SetVisits([]));
    myAppointments().then(SetAppts).catch(() => SetAppts([]));
    myNotifications().then(SetNotes).catch(() => SetNotes(null));
  }, []);
  const active = (visits || []).find((v) => ["waiting", "checked_in", "in_consultation"].includes(v.status));
  const upcoming = (appts || []).filter((a) => a.status === "booked" && new Date(a.ends_at) > new Date());
  return (
    <section className="history visit-status">
      <div className="section-title">
        <div>
          <span className="eyebrow">{t("visit.today")}</span>
          <h3>{t("visit.title")}</h3>
        </div>
        {notes && notes.unread > 0 && (
          <button
            className="link"
            onClick={() => markAllNotificationsRead().then(() => SetNotes({ ...notes, unread: 0 }))}
          >
            <Bell /> {t("visit.markRead", { n: notes.unread })}
          </button>
        )}
      </div>
      {visits === null ? (
        <p className="empty">{t("common.loading")}</p>
      ) : active ? (
        <div className="token-card">
          <div>
            <small>{t("visit.token")}</small>
            <b className="token">{active.token}</b>
          </div>
          <div>
            <small>{t("common.department")}</small>
            <b>{active.department}</b>
          </div>
          <div>
            <small>{t("common.status")}</small>
            <Status value={active.status} />
            {active.position !== null && (
              <small>
                {active.position === 0 ? t("visit.next") : t("visit.ahead", { n: active.position })}
              </small>
            )}
          </div>
        </div>
      ) : (
        <p>{t("visit.none")}</p>
      )}
      {upcoming.length > 0 && (
        <>
          <span className="eyebrow">{t("visit.upcoming")}</span>
          {upcoming.map((a) => (
            <p key={a.id}>
              <b>{formatDate(a.starts_at)}</b> · {t("visit.with", { department: a.department, doctor: a.doctor })}
              {a.room ? ` · ${a.room}` : ""}
            </p>
          ))}
        </>
      )}
      {notes && notes.items.length > 0 && (
        <>
          <span className="eyebrow">{t("visit.messages")}</span>
          {notes.items.slice(0, 4).map((n) => (
            <p key={n.id} className={n.read_at ? "" : "unread"}>
              <b>{n.title}</b> · <small>{timeOnly(n.created_at)}</small>
              <br />
              {n.body}
            </p>
          ))}
        </>
      )}
    </section>
  );
}

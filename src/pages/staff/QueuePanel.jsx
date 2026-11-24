// Live visit queue for today (staff: everyone; doctors: only patients assigned to them).
import React, { useEffect, useState } from "react";
import { ArrowRight, Search } from "lucide-react";
import { Btn, QUEUE_STATUS, Status } from "../../components/ui.jsx";
import { listQueue } from "../../services/visits.js";

export default function QueuePanel({ title, eyebrow, onOpen, notify, refreshKey, emptyText }) {
  const [items, SetItems] = useState(null);
  const [q, SetQ] = useState("");
  const [status, SetStatus] = useState("");

  useEffect(() => {
    let alive = true;
    SetItems(null);
    const t = setTimeout(() => {
      listQueue({ q: q.trim(), status })
        .then((r) => alive && SetItems(r))
        .catch((err) => {
          if (alive) {
            SetItems([]);
            notify(err.message);
          }
        });
    }, 250); // small delay so typing does not send a request per key
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q, status, refreshKey]);

  return (
    <section className="queue">
      <div className="section-title">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h3>{title}</h3>
        </div>
        <Btn
          kind="outline"
          onClick={() => {
            SetQ("");
            SetStatus("");
          }}
        >
          Clear filters
        </Btn>
      </div>
      <div className="queue-tools">
        <div className="search">
          <Search />
          <input
            placeholder="Search patient name or token number"
            value={q}
            onChange={(e) => SetQ(e.target.value)}
          />
        </div>
        <select value={status} onChange={(e) => SetStatus(e.target.value)} aria-label="Filter by status">
          <option value="">All statuses</option>
          {Object.entries(QUEUE_STATUS).map(([k, v]) => (
            <option key={k} value={k}>
              {v.label}
            </option>
          ))}
        </select>
      </div>
      <div className="queue-table">
        <div className="queue-row queue-head">
          <span>Token</span>
          <span>Patient name</span>
          <span>Department</span>
          <span>Doctor</span>
          <span>Status</span>
          <span>Action</span>
        </div>
        {items === null && <p className="empty">Loading...</p>}
        {items && !items.length && <p className="empty">{emptyText || "No visits match."}</p>}
        {(items || []).map((e) => (
          <div className="queue-row" key={e.id}>
            <b>{e.token}</b>
            <span>
              <b>{e.patient.full_name}</b>
              <small>
                {e.patient.age} yrs · {e.patient.gender.replace(/_/g, " ")}
              </small>
            </span>
            <span>{e.department.name}</span>
            <span>{e.doctor ? e.doctor.name : "Not assigned"}</span>
            <span>
              <Status value={e.status} />
              {e.position !== null && e.position !== undefined && (
                <small className="suggestion">{e.position} ahead</small>
              )}
            </span>
            <button className="link" onClick={() => onOpen(e.id)}>
              Open <ArrowRight />
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

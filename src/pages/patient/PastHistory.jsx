// "Past History": a page that shows ONLY the patient's earlier visits (read-only).
// Opened from the sidebar, or from "View" on a submitted concern (which highlights that visit).
import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { Btn } from "../../components/ui.jsx";
import { formatDate, myHistory } from "../../services/intake.js";
import { translateError } from "../../i18n/index.js";

const PAGE = 10;

export default function PastHistory({ focusId, onBack, notify }) {
  const { t } = useTranslation();
  const [items, SetItems] = useState(null);
  const [total, SetTotal] = useState(0);
  const [loadingMore, SetLoadingMore] = useState(false);
  const focusRef = useRef(null);

  useEffect(() => {
    // Make sure the visit the patient clicked on is loaded, however far down it is.
    (async () => {
      try {
        let all = [];
        let t0 = 0;
        do {
          const page = await myHistory({ limit: PAGE, offset: all.length });
          all = all.concat(page.encounters);
          t0 = page.total;
          SetItems(all);
          SetTotal(t0);
        } while (focusId && all.length < t0 && !all.some((e) => e.intake_id === focusId));
      } catch (err) {
        SetItems((cur) => cur || []);
        notify(translateError(err));
      }
    })();
  }, []);

  useEffect(() => {
    if (focusRef.current) focusRef.current.scrollIntoView({ block: "center" });
  }, [items && items.length]);

  const more = async () => {
    SetLoadingMore(true);
    try {
      const page = await myHistory({ limit: PAGE, offset: items.length });
      SetItems(items.concat(page.encounters));
      SetTotal(page.total);
    } catch (err) {
      notify(translateError(err));
    } finally {
      SetLoadingMore(false);
    }
  };

  return (
    <div className="summary">
      <header>
        <div>
          <h2>{t("history.title")}</h2>
        </div>
        <Btn kind="outline" onClick={onBack}>
          <ArrowLeft /> {t("common.back")}
        </Btn>
      </header>
      <main>
        <p className="disclaimer">
          <ShieldCheck /> {t("history.notice")}
        </p>
        {items === null && <p className="empty">{t("common.loading")}</p>}
        {items && !items.length && <p className="empty">{t("history.none")}</p>}
        {(items || []).map((e) => {
          const focused = e.intake_id === focusId;
          return (
            <section
              key={e.intake_id}
              ref={focused ? focusRef : null}
              className={"structured history-item" + (focused ? " focused" : "")}
            >
              <div className="section-title">
                <h3>{formatDate(e.encounter_date)}</h3>
                <span className={"status " + (e.review_status === "confirmed" ? "done" : "wait")}>
                  {t(`review.${e.review_status}`)}
                </span>
              </div>
              <small>{t("dash.whatYouShared")}</small>
              <blockquote dir="auto">“{e.statement}”</blockquote>
              <div className="summary-grid">
                <span>{t("common.department")}</span>
                <b>{e.confirmed_department || t("common.assignedAfterReview")}</b>
              </div>
              {e.confirmed_symptoms.length > 0 && (
                <>
                  <small>{t("history.confirmedSymptoms")}</small>
                  <ul className="chips">
                    {e.confirmed_symptoms.map((s, i) => (
                      <li key={i}>{s.term}</li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          );
        })}
        {items && items.length < total && (
          <Btn kind="outline" onClick={more} disabled={loadingMore}>
            {loadingMore ? t("common.loading") : t("history.more")}
          </Btn>
        )}
      </main>
    </div>
  );
}

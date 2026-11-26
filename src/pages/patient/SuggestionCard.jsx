// The assistant's PRELIMINARY department suggestion. Always shown as provisional: staff confirm it.
// `lng`: language of the assistant's reply when it differs from the screen's display language (Dogri).
import React from "react";
import { useTranslation } from "react-i18next";
import { ShieldCheck, Siren } from "lucide-react";

export default function SuggestionCard({ meta, lng }) {
  const { t } = useTranslation();
  const d = meta && meta.department;
  if (!d) return null;
  const hasDept = d.status === "matched" && d.name;
  const opt = lng ? { lng } : undefined;
  // Local name first when the assistant answered in that language (kept next to the English name so
  // staff-facing wording and the reviewed department list stay recognisable).
  const label = hasDept ? (lng && d.name_local && d.name_local !== d.name ? `${d.name_local} (${d.name})` : d.name) : null;
  return (
    <aside className={"suggestion" + (meta.urgent ? " urgent" : "")} data-testid="suggestion-card">
      {meta.urgent && (
        <b className="urgent-line">
          <Siren /> {t("chat.urgentBadge", opt)}
        </b>
      )}
      <small>{t("chat.suggestTitle", opt)}</small>
      <b dir="auto">{hasDept ? label : t("chat.suggestStaffChoose", opt)}</b>
      {hasDept && <span className={"strength " + d.strength}>{t(`chat.strength.${d.strength}`, opt)}</span>}
      <p>
        <ShieldCheck /> {t("chat.suggestNote", opt)}
      </p>
    </aside>
  );
}

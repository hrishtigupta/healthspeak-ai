// The assistant's PRELIMINARY department suggestion. Always shown as provisional: staff confirm it.
import React from "react";
import { useTranslation } from "react-i18next";
import { ShieldCheck, Siren } from "lucide-react";

export default function SuggestionCard({ meta }) {
  const { t } = useTranslation();
  const d = meta && meta.department;
  if (!d) return null;
  const hasDept = d.status === "matched" && d.name;
  return (
    <aside className={"suggestion" + (meta.urgent ? " urgent" : "")} data-testid="suggestion-card">
      {meta.urgent && (
        <b className="urgent-line">
          <Siren /> {t("chat.urgentBadge")}
        </b>
      )}
      <small>{t("chat.suggestTitle")}</small>
      <b dir="auto">{hasDept ? d.name : t("chat.suggestStaffChoose")}</b>
      {hasDept && <span className={"strength " + d.strength}>{t(`chat.strength.${d.strength}`)}</span>}
      <p>
        <ShieldCheck /> {t("chat.suggestNote")}
      </p>
    </aside>
  );
}

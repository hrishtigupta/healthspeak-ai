// Display-language picker. Each option is written in its own language/script.
import React from "react";
import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";
import { UI_LANGUAGES } from "../i18n/index.js";

export default function LanguageSwitcher({ onChange, className = "" }) {
  const { t, i18n } = useTranslation();
  return (
    <label className={"lang-switch " + className} title={t("lang.display")}>
      <Languages aria-hidden="true" />
      <span className="sr-only">{t("lang.display")}</span>
      <select
        value={i18n.language}
        onChange={(e) => onChange(e.target.value)}
        aria-label={t("lang.display")}
      >
        {UI_LANGUAGES.map((l) => (
          <option key={l.code} value={l.code} lang={l.code}>
            {l.label}
          </option>
        ))}
      </select>
    </label>
  );
}

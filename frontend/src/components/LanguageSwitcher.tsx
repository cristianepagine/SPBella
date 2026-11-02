import { useTranslation } from "react-i18next";

import { changeLanguage, SUPPORTED_LANGUAGES, type Language } from "../i18n";

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();

  return (
    <label className="flex items-center gap-2 text-sm text-slate-600">
      {t("language.label")}
      <select
        className="rounded-lg border border-slate-300 bg-white px-2 py-1"
        value={i18n.language}
        onChange={(e) => changeLanguage(e.target.value as Language)}
      >
        {SUPPORTED_LANGUAGES.map((lang) => (
          <option key={lang} value={lang}>
            {t(`language.${lang}`)}
          </option>
        ))}
      </select>
    </label>
  );
}

import { useTranslation } from "react-i18next";

import type { ConsentPurpose } from "../../../api/customers";
import { SelectField } from "../../../components/form";

export const PURPOSES: ConsentPurpose[] = ["service", "reminders", "marketing"];

type Locale = "pt-BR" | "es" | null;

/** Idioma das mensagens para o cliente; vazio = o idioma padrão do estabelecimento. */
export function LocaleSelect({ value, onChange }: { value: Locale; onChange: (v: Locale) => void }) {
  const { t } = useTranslation();
  return (
    <SelectField
      label={t("customers.fields.locale")}
      value={value ?? ""}
      onChange={(v) => onChange(v === "" ? null : (v as Locale))}
      options={[
        { value: "", label: t("customers.localeDefault") },
        { value: "pt-BR", label: t("language.pt-BR") },
        { value: "es", label: t("language.es") },
      ]}
    />
  );
}

import { type FormEvent, useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { type TenantSettings, useSaveSettings, useSettings } from "../../api/settings";
import { useAuth } from "../../auth/AuthProvider";
import { Card, FormError, SubmitButton, TextField } from "../../components/form";
import { type Language, SUPPORTED_LANGUAGES } from "../../i18n";
import { formatDateTime, formatLocale, formatMoney, timeZoneLabel } from "../../i18n/format";

/** Configurações do estabelecimento (só o dono): nome, idioma padrão, fuso; moeda só leitura. */
export function SettingsPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const settings = useSettings(slug);

  if (settings.isPending) return <p role="status">{t("auth.loading")}</p>;
  if (settings.isError) return <FormError error={settings.error} />;
  return <SettingsForm current={settings.data} />;
}

const EXAMPLE_PRICE = { BRL: 4590, PYG: 150000 } as const;

function SettingsForm({ current }: { current: TenantSettings }) {
  const { t, i18n } = useTranslation();
  const { slug } = useAuth();
  const save = useSaveSettings(slug);
  const [name, setName] = useState(current.name);
  const [locale, setLocale] = useState<Language>(current.locale);
  const [timezone, setTimezone] = useState(current.timezone);
  const [saved, setSaved] = useState(false);

  useEffect(() => setSaved(false), [name, locale, timezone]);

  const display = formatLocale(i18n.language, current.country);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const ok = await save.mutateAsync({ name, locale, timezone }).then(
      () => true,
      () => false,
    );
    setSaved(ok);
  }

  return (
    <Card title={t("settings.title")}>
      <form onSubmit={submit} noValidate>
        <FormError error={save.error} />
        <TextField
          label={t("settings.name")}
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <Select
          label={t("settings.locale")}
          hint={t("settings.localeHint")}
          value={locale}
          onChange={(value) => setLocale(value as Language)}
          options={SUPPORTED_LANGUAGES.map((lang) => ({ value: lang, label: t(`language.${lang}`) }))}
        />

        <Select
          label={t("settings.timezone")}
          value={timezone}
          onChange={setTimezone}
          options={current.timezone_options.map((zone) => ({
            value: zone,
            label: timeZoneLabel(zone, display),
          }))}
        />

        <div className="mb-4">
          <p className="mb-1 font-medium text-slate-800">{t("settings.currency")}</p>
          <p className="rounded-xl bg-slate-100 px-4 py-3">{t(`currency.${current.currency}`)}</p>
          <p className="mt-1 text-sm text-slate-500">{t("settings.currencyHint")}</p>
        </div>

        <p className="mb-4 rounded-xl bg-brand-50 px-4 py-3 text-sm text-slate-700">
          {t("settings.preview", {
            price: formatMoney(EXAMPLE_PRICE[current.currency], current.currency, display),
            now: formatDateTime(new Date(), timezone, display),
          })}
        </p>

        {saved && (
          <p role="status" className="mb-4 rounded-xl bg-emerald-50 px-4 py-3 text-emerald-800">
            {t("settings.saved")}
          </p>
        )}
        <SubmitButton busy={save.isPending}>{t("settings.save")}</SubmitButton>
      </form>
    </Card>
  );
}

function Select({
  label,
  hint,
  value,
  onChange,
  options,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  const id = useId();
  return (
    <div className="mb-4">
      <label htmlFor={id} className="mb-1 block font-medium text-slate-800">
        {label}
      </label>
      <select
        id={id}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-sm text-slate-500">
          {hint}
        </p>
      )}
    </div>
  );
}

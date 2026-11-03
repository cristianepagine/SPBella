import { type FormEvent, useEffect, useState } from "react";
import { type TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { type TenantSettings, useSaveSettings, useSettings } from "../../api/settings";
import { useAuth } from "../../auth/AuthProvider";
import { Card, FormError, SelectField, SubmitButton, TextField } from "../../components/form";
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

// Página pública: antecedência mínima (minutos) e até quantos dias à frente.
const NOTICE_OPTIONS = [0, 30, 60, 120, 240, 720, 1440, 2880];
const DAYS_AHEAD_OPTIONS = [7, 14, 30, 60, 90, 180];

function withCurrent(options: number[], current: number): number[] {
  return options.includes(current) ? options : [...options, current].sort((a, b) => a - b);
}

function noticeLabel(t: TFunction, minutes: number): string {
  if (minutes === 0) return t("settings.noNotice");
  if (minutes % 1440 === 0) return t("settings.noticeDays", { count: minutes / 1440 });
  if (minutes % 60 === 0) return t("settings.noticeHours", { count: minutes / 60 });
  return t("settings.noticeMinutes", { count: minutes });
}

function SettingsForm({ current }: { current: TenantSettings }) {
  const { t, i18n } = useTranslation();
  const { slug } = useAuth();
  const save = useSaveSettings(slug);
  const [name, setName] = useState(current.name);
  const [locale, setLocale] = useState<Language>(current.locale);
  const [timezone, setTimezone] = useState(current.timezone);
  const [buffer, setBuffer] = useState(current.buffer_min);
  const [step, setStep] = useState(current.slot_step_min);
  const [notice, setNotice] = useState(current.min_notice_min);
  const [daysAhead, setDaysAhead] = useState(current.max_days_ahead);
  const [whatsapp, setWhatsapp] = useState(current.whatsapp_phone ?? "");
  const [saved, setSaved] = useState(false);

  useEffect(() => setSaved(false), [name, locale, timezone, buffer, step, notice, daysAhead, whatsapp]);

  const display = formatLocale(i18n.language, current.country);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const ok = await save
      .mutateAsync({
        name,
        locale,
        timezone,
        buffer_min: buffer,
        slot_step_min: step,
        min_notice_min: notice,
        max_days_ahead: daysAhead,
        whatsapp_phone: whatsapp,
      })
      .then(
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

        <SelectField
          label={t("settings.locale")}
          hint={t("settings.localeHint")}
          value={locale}
          onChange={(value) => setLocale(value as Language)}
          options={SUPPORTED_LANGUAGES.map((lang) => ({ value: lang, label: t(`language.${lang}`) }))}
        />

        <SelectField
          label={t("settings.timezone")}
          value={timezone}
          onChange={setTimezone}
          options={current.timezone_options.map((zone) => ({
            value: zone,
            label: timeZoneLabel(zone, display),
          }))}
        />

        <SelectField
          label={t("settings.buffer")}
          hint={t("settings.bufferHint")}
          value={String(buffer)}
          onChange={(v) => setBuffer(Number(v))}
          options={[0, 5, 10, 15, 20, 30, 45, 60].map((m) => ({
            value: String(m),
            label: m === 0 ? t("settings.noBuffer") : t("services.minutes", { count: m }),
          }))}
        />
        <SelectField
          label={t("settings.step")}
          hint={t("settings.stepHint")}
          value={String(step)}
          onChange={(v) => setStep(Number(v) as typeof step)}
          options={[5, 10, 15, 20, 30, 60].map((m) => ({
            value: String(m),
            label: t("settings.everyMinutes", { count: m }),
          }))}
        />
        <SelectField
          label={t("settings.notice")}
          hint={t("settings.noticeHint")}
          value={String(notice)}
          onChange={(v) => setNotice(Number(v))}
          options={withCurrent(NOTICE_OPTIONS, current.min_notice_min).map((m) => ({
            value: String(m),
            label: noticeLabel(t, m),
          }))}
        />
        <SelectField
          label={t("settings.daysAhead")}
          hint={t("settings.daysAheadHint")}
          value={String(daysAhead)}
          onChange={(v) => setDaysAhead(Number(v))}
          options={withCurrent(DAYS_AHEAD_OPTIONS, current.max_days_ahead).map((d) => ({
            value: String(d),
            label: t("settings.upToDays", { count: d }),
          }))}
        />

        <TextField
          label={t("settings.whatsapp")}
          hint={t("settings.whatsappHint")}
          type="tel"
          autoComplete="off"
          maxLength={32}
          value={whatsapp}
          onChange={(e) => setWhatsapp(e.target.value)}
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

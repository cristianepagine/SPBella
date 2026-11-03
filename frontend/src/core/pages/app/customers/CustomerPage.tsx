import { type FormEvent, useEffect, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";

import {
  type AuditEntry,
  type Customer,
  type CustomerChanges,
  useAudit,
  useChangeConsent,
  useCustomer,
  useUpdateCustomer,
} from "../../../api/customers";
import { useAuth } from "../../../auth/AuthProvider";
import { useCan } from "../../../auth/permissions";
import { Card, CheckboxField, FormError, SubmitButton, TextField } from "../../../components/form";
import { formatDateTime, formatLocale } from "../../../i18n/format";
import { useCurrentTenant } from "../../TenantLayout";
import { LocaleSelect, PURPOSES } from "./shared";

/** Ficha do cliente: dados, consentimentos e (para o dono) o histórico de auditoria. */
export function CustomerPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const { customerId = "" } = useParams();
  const customer = useCustomer(slug, customerId);
  const can = useCan();

  if (customer.isPending) return <p role="status">{t("auth.loading")}</p>;
  if (customer.isError) return <FormError error={customer.error} />;

  return (
    <div className="flex flex-col gap-4">
      <CustomerForm key={customer.data.updated_at} customer={customer.data} />
      <Consents customer={customer.data} />
      {can("audit.view") && <History customerId={customer.data.id} />}
    </div>
  );
}

function CustomerForm({ customer }: { customer: Customer }) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const update = useUpdateCustomer(slug, customer.id);
  const [name, setName] = useState(customer.name);
  const [phone, setPhone] = useState(customer.phone_display);
  const [email, setEmail] = useState(customer.email ?? "");
  const [locale, setLocale] = useState(customer.locale);
  const [saved, setSaved] = useState(false);

  useEffect(() => setSaved(false), [name, phone, email, locale]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    // Só o que mudou vai para o servidor (e para o log de auditoria).
    const changes: CustomerChanges = {};
    if (name !== customer.name) changes.name = name;
    if (phone !== customer.phone_display) changes.phone = phone;
    if (email !== (customer.email ?? "")) changes.email = email || null;
    if (locale !== customer.locale) changes.locale = locale;
    if (Object.keys(changes).length === 0) return setSaved(true);
    const ok = await update.mutateAsync(changes).then(
      () => true,
      () => false,
    );
    setSaved(ok);
  }

  return (
    <Card title={customer.name}>
      <form onSubmit={submit} noValidate>
        <FormError error={update.error} />
        <TextField
          label={t("customers.fields.name")}
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <TextField
          label={t("customers.fields.phone")}
          type="tel"
          inputMode="tel"
          required
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        <TextField
          label={t("customers.fields.emailOptional")}
          type="email"
          inputMode="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <LocaleSelect value={locale} onChange={setLocale} />
        {saved && (
          <p role="status" className="mb-4 rounded-xl bg-emerald-50 px-4 py-3 text-emerald-800">
            {t("customers.saved")}
          </p>
        )}
        <SubmitButton busy={update.isPending}>{t("customers.save")}</SubmitButton>
      </form>
    </Card>
  );
}

function Consents({ customer }: { customer: Customer }) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const change = useChangeConsent(slug, customer.id);
  const active = new Set(customer.consents.map((c) => c.purpose));

  return (
    <Card title={t("consent.title")}>
      <FormError error={change.error} />
      {PURPOSES.map((purpose) => (
        <CheckboxField
          key={purpose}
          label={t(`consent.ask.${purpose}`)}
          checked={active.has(purpose)}
          disabled={change.isPending}
          onChange={(granted) => change.mutate({ purpose, granted })}
        />
      ))}
      {!active.has("service") && (
        <p className="mt-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {t("consent.serviceWithdrawn")}
        </p>
      )}
    </Card>
  );
}

function History({ customerId }: { customerId: string }) {
  const { t, i18n } = useTranslation();
  const { slug } = useAuth();
  const tenant = useCurrentTenant();
  const audit = useAudit(slug, customerId, true);
  const locale = formatLocale(i18n.language, tenant.country);

  return (
    <Card title={t("audit.title")}>
      <p className="mb-3 text-sm text-slate-600">{t("audit.intro")}</p>
      {audit.isPending && <p role="status">{t("auth.loading")}</p>}
      {audit.isError && <FormError error={audit.error} />}
      {audit.data && (
        <ol className="divide-y divide-slate-100">
          {audit.data.map((entry) => (
            <li key={entry.id} className="py-2 text-sm">
              <p className="font-medium">{describe(entry, t)}</p>
              <p className="text-slate-500">
                {formatDateTime(entry.occurred_at, tenant.timezone, locale)} ·{" "}
                {entry.actor?.name ?? t(`audit.actor.${entry.actor_type}`)}
              </p>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function describe(entry: AuditEntry, t: TFunction): string {
  const isConsent = entry.action.startsWith("consent.");
  const fields = entry.fields
    .map((field) => t(isConsent ? `consent.short.${field}` : `audit.fields.${field}`))
    .join(", ");
  return t(`audit.actions.${entry.action}`, { fields, defaultValue: entry.action });
}

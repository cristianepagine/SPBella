import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAuth } from "../../core/auth/AuthProvider";
import { Card, FormError, SelectField, SubmitButton, TextField } from "../../core/components/form";
import { formatLocale, formatMoney, moneyInputValue, parseMoney } from "../../core/i18n/format";
import { useCurrentTenant } from "../../core/pages/TenantLayout";
import { type Service, useChangeService, useCreateService, useServices } from "../api/services";

const DURATIONS = [15, 20, 30, 40, 45, 60, 75, 90, 105, 120, 150, 180, 210, 240, 300, 360, 420, 480];

/** Serviços do salão (só o dono): nome, duração e preço; desativar em vez de apagar. */
export function ServicesPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const services = useServices(slug);
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  return (
    <Card title={t("services.title")}>
      {adding ? (
        <ServiceForm onDone={() => setAdding(false)} />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="mb-4 w-full rounded-xl bg-brand-700 px-4 py-3 font-medium text-white"
        >
          {t("services.new")}
        </button>
      )}

      {services.isPending && <p role="status">{t("auth.loading")}</p>}
      {services.isError && <FormError error={services.error} />}
      {services.data && (
        <ul className="divide-y divide-slate-100">
          {services.data.map((service) =>
            editing === service.id ? (
              <li key={service.id} className="py-3">
                <ServiceForm service={service} onDone={() => setEditing(null)} />
              </li>
            ) : (
              <ServiceRow key={service.id} service={service} onEdit={() => setEditing(service.id)} />
            ),
          )}
        </ul>
      )}
    </Card>
  );
}

function useDisplayLocale(): string {
  const { i18n } = useTranslation();
  return formatLocale(i18n.language, useCurrentTenant().country);
}

function ServiceRow({ service, onEdit }: { service: Service; onEdit: () => void }) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const change = useChangeService(slug);
  const locale = useDisplayLocale();

  return (
    <li className="py-3">
      <div className="flex items-start justify-between gap-3">
        <div className={service.is_active ? "" : "text-slate-400"}>
          <p className="font-medium">{service.name}</p>
          <p className="text-sm">
            {t("services.minutes", { count: service.duration_min })} ·{" "}
            {formatMoney(service.price_minor, service.currency, locale)}
          </p>
          {!service.is_active && <p className="text-sm">{t("services.inactive")}</p>}
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={onEdit}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {t("services.edit")}
          </button>
          <button
            type="button"
            onClick={() => change.mutate({ id: service.id, is_active: !service.is_active })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {service.is_active ? t("services.deactivate") : t("services.activate")}
          </button>
        </div>
      </div>
      <FormError error={change.error} />
    </li>
  );
}

function ServiceForm({ service, onDone }: { service?: Service; onDone: () => void }) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const tenant = useCurrentTenant();
  const locale = useDisplayLocale();
  const create = useCreateService(slug);
  const change = useChangeService(slug);
  const [name, setName] = useState(service?.name ?? "");
  const [duration, setDuration] = useState(service?.duration_min ?? 60);
  const [price, setPrice] = useState(
    service ? moneyInputValue(service.price_minor, service.currency, locale) : "",
  );
  const [priceError, setPriceError] = useState(false);
  const mutation = service ? change : create;

  async function submit(event: FormEvent) {
    event.preventDefault();
    const priceMinor = parseMoney(price, tenant.currency);
    setPriceError(priceMinor === null);
    if (priceMinor === null) return;
    const body = { name, duration_min: duration, price_minor: priceMinor };
    const ok = await (service ? change.mutateAsync({ id: service.id, ...body }) : create.mutateAsync(body))
      .then(() => true, () => false); // prettier-ignore
    if (ok) onDone();
  }

  const options = [...new Set([...DURATIONS, duration])].sort((a, b) => a - b);

  return (
    <form onSubmit={submit} noValidate className="rounded-xl bg-brand-50 p-4">
      <FormError error={mutation.error} />
      <TextField
        label={t("services.name")}
        required
        maxLength={120}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <SelectField
        label={t("services.duration")}
        value={String(duration)}
        onChange={(v) => setDuration(Number(v))}
        options={options.map((m) => ({ value: String(m), label: t("services.minutes", { count: m }) }))}
      />
      <TextField
        label={t("services.price", { currency: tenant.currency })}
        hint={t(`services.priceHint.${tenant.currency}`)}
        inputMode="decimal"
        required
        value={price}
        onChange={(e) => setPrice(e.target.value)}
      />
      {priceError && (
        <p role="alert" className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-red-800">
          {t("services.priceInvalid")}
        </p>
      )}
      <div className="flex gap-2">
        <SubmitButton busy={mutation.isPending}>{t("services.save")}</SubmitButton>
        <button
          type="button"
          onClick={onDone}
          className="mt-2 rounded-xl border border-slate-300 px-4 py-3 font-medium"
        >
          {t("services.cancel")}
        </button>
      </div>
    </form>
  );
}

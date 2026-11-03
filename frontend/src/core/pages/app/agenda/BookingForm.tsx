import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { ApiError } from "../../../api/client";
import { useAvailability, useCreateAppointment } from "../../../api/appointments";
import { type CustomerSummary, useCustomers } from "../../../api/customers";
import { useOfferings, useProviders } from "../../../api/providers";
import { useAuth } from "../../../auth/AuthProvider";
import { Card, FormError, SelectField, SubmitButton, TextField } from "../../../components/form";
import { useDebounced } from "../../../hooks/useDebounced";
import { timeLabel, zonedToUtc } from "../../../i18n/zoned";
import { salonPath } from "../../../paths";
import { useCurrentTenant } from "../../TenantLayout";

/** Conflitos que a recepção pode passar por cima, confirmando um encaixe. */
const SQUEEZABLE = new Set(["outside_working_hours", "provider_time_off", "too_close"]);

/** Marcar horário: cliente, profissional, serviço (do que ele faz), dia e hora. */
export function BookingForm({ day, onDone }: { day: string; onDone: () => void }) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const tenant = useCurrentTenant();
  const providers = useProviders(slug);
  const offerings = useOfferings(slug);
  const create = useCreateAppointment(slug);

  const [customer, setCustomer] = useState<CustomerSummary | null>(null);
  const [providerId, setProviderId] = useState("");
  const [offeringId, setOfferingId] = useState("");
  const [date, setDate] = useState(day);
  const [time, setTime] = useState("09:00");

  const active = (providers.data ?? []).filter((p) => p.is_active);
  const provider = active.find((p) => p.id === providerId) ?? active[0];
  const choices = (offerings.data ?? []).filter((o) => provider?.offering_ids.includes(o.id));
  const offering = choices.find((o) => o.id === offeringId) ?? choices[0];
  const errorCode = create.error instanceof ApiError ? create.error.code : null;
  const free = useAvailability(slug, offering?.id, date, provider?.id);

  async function submit(event: FormEvent | null, allowOutsideHours = false) {
    event?.preventDefault();
    if (!customer || !provider || !offering) return;
    const ok = await create
      .mutateAsync({
        customer_id: customer.id,
        provider_id: provider.id,
        offering_id: offering.id,
        starts_at: zonedToUtc(date, time, tenant.timezone),
        allow_outside_hours: allowOutsideHours,
      })
      .then(
        () => true,
        () => false,
      );
    if (ok) onDone();
  }

  return (
    <Card title={t("booking.title")}>
      <form onSubmit={(e) => void submit(e)} noValidate>
        <CustomerPicker value={customer} onChange={setCustomer} />
        {active.length === 0 ? (
          <p className="mb-4 text-slate-600">{t("agenda.noProviders")}</p>
        ) : (
          <SelectField
            label={t("agenda.provider")}
            value={provider?.id ?? ""}
            onChange={(id) => {
              setProviderId(id);
              setOfferingId("");
            }}
            options={active.map((p) => ({ value: p.id, label: p.name }))}
          />
        )}
        {provider && choices.length === 0 && (
          <p className="mb-4 text-amber-800">{t("booking.noServices")}</p>
        )}
        {choices.length > 0 && (
          <SelectField
            label={t("booking.service")}
            value={offering?.id ?? ""}
            onChange={setOfferingId}
            options={choices.map((o) => ({
              value: o.id,
              label: t("booking.serviceOption", { name: o.name, minutes: o.duration_min }),
            }))}
          />
        )}
        <div className="flex gap-3">
          <TextField
            label={t("booking.date")}
            type="date"
            required
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <TextField
            label={t("booking.time")}
            type="time"
            step={300}
            required
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        </div>

        {free.data && (
          <fieldset className="mb-4">
            <legend className="mb-1 font-medium text-slate-800">{t("booking.freeTimes")}</legend>
            {free.data.slots.length === 0 ? (
              <p className="text-sm text-slate-600">{t("booking.noFreeTimes")}</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {free.data.slots.map((s) => {
                  const label = timeLabel(s.starts_at, tenant.timezone, "pt-BR");
                  return (
                    <button
                      key={s.starts_at}
                      type="button"
                      aria-pressed={label === time}
                      onClick={() => setTime(label)}
                      className={`rounded-lg border px-3 py-2 text-sm ${
                        label === time ? "border-brand-700 bg-brand-700 text-white" : "border-slate-300"
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            )}
          </fieldset>
        )}

        <FormError error={create.error} />
        {errorCode && SQUEEZABLE.has(errorCode) && (
          <button
            type="button"
            onClick={() => void submit(null, true)}
            className="mb-4 w-full rounded-xl border-2 border-amber-600 px-4 py-3 font-medium text-amber-900"
          >
            {t("booking.squeeze")}
          </button>
        )}
        <div className="flex gap-2">
          <SubmitButton busy={create.isPending} disabled={!customer || !offering}>
            {t("booking.save")}
          </SubmitButton>
          <button
            type="button"
            onClick={onDone}
            className="mt-2 rounded-xl border border-slate-300 px-4 py-3"
          >
            {t("services.cancel")}
          </button>
        </div>
      </form>
    </Card>
  );
}

function CustomerPicker({
  value,
  onChange,
}: {
  value: CustomerSummary | null;
  onChange: (c: CustomerSummary | null) => void;
}) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const [search, setSearch] = useState("");
  const query = useDebounced(search);
  const results = useCustomers(slug, 0, query);

  if (value) {
    return (
      <div className="mb-4 flex items-center justify-between rounded-xl bg-brand-50 px-4 py-3">
        <span>
          <span className="block font-medium">{value.name}</span>
          <span className="block text-sm text-slate-500">{value.phone_display}</span>
        </span>
        <button type="button" className="text-sm underline" onClick={() => onChange(null)}>
          {t("booking.changeCustomer")}
        </button>
      </div>
    );
  }

  return (
    <div className="mb-4">
      <label className="block">
        <span className="mb-1 block font-medium text-slate-800">{t("booking.customer")}</span>
        <input
          type="search"
          autoComplete="off"
          className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3"
          placeholder={t("customers.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      {query.trim() && (
        <ul className="mt-2 divide-y divide-slate-100 rounded-xl border border-slate-200">
          {results.data?.items.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className="block w-full px-4 py-2 text-left"
                onClick={() => onChange(c)}
              >
                {c.name} <span className="text-sm text-slate-500">{c.phone_display}</span>
              </button>
            </li>
          ))}
          {results.data?.items.length === 0 && (
            <li className="px-4 py-2 text-sm text-slate-600">
              {t("customers.noResults", { q: query.trim() })}{" "}
              <Link to={salonPath.newCustomer(slug)} className="font-medium underline">
                {t("customers.new")}
              </Link>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

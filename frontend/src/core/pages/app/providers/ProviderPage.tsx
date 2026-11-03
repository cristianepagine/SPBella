import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";

import {
  type Provider,
  type ProviderColor,
  useAddTimeOff,
  useChangeProvider,
  useDeleteTimeOff,
  useOfferings,
  useProviders,
  useSetProviderOfferings,
  useSetWorkingHours,
  useTimeOff,
} from "../../../api/providers";
import { useTeam } from "../../../api/team";
import { useAuth } from "../../../auth/AuthProvider";
import {
  Card,
  CheckboxField,
  FormError,
  SelectField,
  SubmitButton,
  TextField,
} from "../../../components/form";
import { PROVIDER_COLOR_CLASS, PROVIDER_COLORS } from "../../../layout/colors";
import { WeekEditor } from "./WeekEditor";

/** Ficha do profissional: dados, jornada semanal, o que realiza e folgas. */
export function ProviderPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const { providerId = "" } = useParams();
  const providers = useProviders(slug);
  const provider = providers.data?.find((p) => p.id === providerId);

  if (providers.isPending) return <p role="status">{t("auth.loading")}</p>;
  if (providers.isError) return <FormError error={providers.error} />;
  if (!provider) return <p role="alert">{t("errors.not_found")}</p>;

  return (
    <div className="flex flex-col gap-4">
      <Details provider={provider} />
      <Card title={t("providers.hoursTitle")}>
        <Hours provider={provider} />
      </Card>
      <Offerings provider={provider} />
      <TimeOffCard provider={provider} />
    </div>
  );
}

function Details({ provider }: { provider: Provider }) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const change = useChangeProvider(slug, provider.id);
  const team = useTeam(slug);
  const [name, setName] = useState(provider.name);
  const [color, setColor] = useState<ProviderColor>(provider.color);
  const [userId, setUserId] = useState(provider.user_id ?? "");

  function submit(event: FormEvent) {
    event.preventDefault();
    change.mutate({ name, color, user_id: userId || null });
  }

  const accounts = (team.data ?? []).filter((m) => m.is_active);

  return (
    <Card title={provider.name}>
      <form onSubmit={submit} noValidate>
        <FormError error={change.error} />
        <TextField
          label={t("providers.name")}
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <fieldset className="mb-4">
          <legend className="mb-1 font-medium text-slate-800">{t("providers.color")}</legend>
          <div className="flex flex-wrap gap-2">
            {PROVIDER_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={t(`colors.${c}`)}
                aria-pressed={color === c}
                onClick={() => setColor(c)}
                className={`h-9 w-9 rounded-full ${PROVIDER_COLOR_CLASS[c]} ${
                  color === c ? "ring-4 ring-brand-900 ring-offset-2" : ""
                }`}
              />
            ))}
          </div>
        </fieldset>
        <SelectField
          label={t("providers.account")}
          hint={t("providers.accountHint")}
          value={userId}
          onChange={setUserId}
          options={[
            { value: "", label: t("providers.noAccount") },
            ...accounts.map((m) => ({ value: m.id, label: `${m.name} (${m.email})` })),
          ]}
        />
        <SubmitButton busy={change.isPending}>{t("providers.save")}</SubmitButton>
      </form>
      <button
        type="button"
        className="mt-4 text-sm font-medium text-brand-700 underline"
        onClick={() => change.mutate({ is_active: !provider.is_active })}
      >
        {provider.is_active ? t("providers.deactivate") : t("providers.activate")}
      </button>
    </Card>
  );
}

function Hours({ provider }: { provider: Provider }) {
  const { slug } = useAuth();
  const save = useSetWorkingHours(slug, provider.id);
  return (
    <WeekEditor
      value={provider.working_hours}
      onSave={(ranges) => save.mutate(ranges)}
      saving={save.isPending}
      error={save.error}
    />
  );
}

function Offerings({ provider }: { provider: Provider }) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const offerings = useOfferings(slug);
  const save = useSetProviderOfferings(slug, provider.id);
  const selected = new Set(provider.offering_ids);

  function toggle(id: string, on: boolean) {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    save.mutate([...next]);
  }

  return (
    <Card title={t("providers.offeringsTitle")}>
      <FormError error={save.error ?? offerings.error} />
      {offerings.data?.map((offering) => (
        <CheckboxField
          key={offering.id}
          label={offering.name}
          checked={selected.has(offering.id)}
          disabled={save.isPending}
          onChange={(on) => toggle(offering.id, on)}
        />
      ))}
    </Card>
  );
}

function TimeOffCard({ provider }: { provider: Provider }) {
  const { t, i18n } = useTranslation();
  const { slug } = useAuth();
  const list = useTimeOff(slug, provider.id);
  const add = useAddTimeOff(slug, provider.id);
  const remove = useDeleteTimeOff(slug, provider.id);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");

  // As datas vêm como "AAAA-MM-DD" (dia local do estabelecimento): formatamos sem mudar o fuso.
  const day = (iso: string) =>
    new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeZone: "UTC" }).format(
      new Date(`${iso}T00:00:00Z`),
    );

  async function submit(event: FormEvent) {
    event.preventDefault();
    const ok = await add
      .mutateAsync({ start_date: start, end_date: end || start, reason: reason || null })
      .then(
        () => true,
        () => false,
      );
    if (ok) {
      setStart("");
      setEnd("");
      setReason("");
    }
  }

  return (
    <Card title={t("providers.timeOffTitle")}>
      <ul className="mb-4 divide-y divide-slate-100">
        {list.data?.length === 0 && <li className="text-slate-600">{t("providers.noTimeOff")}</li>}
        {list.data?.map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-2 py-2">
            <span>
              {item.start_date === item.end_date
                ? day(item.start_date)
                : t("providers.period", { from: day(item.start_date), to: day(item.end_date) })}
              {item.reason && <span className="text-slate-500"> · {item.reason}</span>}
            </span>
            <button
              type="button"
              className="text-sm text-red-700 underline"
              onClick={() => remove.mutate(item.id)}
            >
              {t("providers.cancelTimeOff")}
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={submit} noValidate>
        <FormError error={add.error ?? remove.error} />
        <TextField
          label={t("providers.fromDate")}
          type="date"
          required
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
        <TextField
          label={t("providers.toDate")}
          hint={t("providers.toDateHint")}
          type="date"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
        <TextField
          label={t("providers.reason")}
          maxLength={120}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <SubmitButton busy={add.isPending}>{t("providers.addTimeOff")}</SubmitButton>
      </form>
    </Card>
  );
}

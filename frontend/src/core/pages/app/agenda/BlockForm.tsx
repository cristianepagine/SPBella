import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Agenda } from "../../../api/agenda";
import { type CreatedBlock, useCreateBlock } from "../../../api/appointments";
import { useAuth } from "../../../auth/AuthProvider";
import { Card, FormError, SelectField, SubmitButton, TextField } from "../../../components/form";
import { timeLabel } from "../../../i18n/zoned";

type Kind = "days" | "hours";

/** Bloquear: o estabelecimento inteiro ou um profissional; dias inteiros ou algumas horas. */
export function BlockForm({
  agenda,
  day,
  locale,
  onDone,
}: {
  agenda: Agenda;
  day: string;
  locale: string;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const create = useCreateBlock(slug);
  const [providerId, setProviderId] = useState("");
  const [kind, setKind] = useState<Kind>("days");
  const [startDate, setStartDate] = useState(day);
  const [endDate, setEndDate] = useState("");
  const [startTime, setStartTime] = useState("12:00");
  const [endTime, setEndTime] = useState("13:00");
  const [reason, setReason] = useState("");
  const [created, setCreated] = useState<CreatedBlock | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const result = await create
      .mutateAsync({
        provider_id: providerId || null,
        start_date: startDate,
        ...(kind === "days"
          ? { end_date: endDate || null }
          : { start_time: startTime, end_time: endTime }),
        reason: reason || null,
      })
      .catch(() => null);
    if (result && result.conflicts.length === 0) onDone();
    else if (result) setCreated(result);
  }

  if (created) {
    return (
      <Card title={t("blocks.title")}>
        <div role="status" className="rounded-xl bg-amber-50 px-4 py-3 text-amber-900">
          <p className="font-medium">{t("blocks.conflicts", { count: created.conflicts.length })}</p>
          <ul className="mt-2 list-disc pl-5">
            {created.conflicts.map((c) => (
              <li key={c.appointment_id}>
                {c.customer_name} · {timeLabel(c.starts_at, agenda.timezone, locale)}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-sm">{t("blocks.conflictsHint")}</p>
        </div>
        <button type="button" onClick={onDone} className="mt-4 font-medium underline">
          {t("booking.close")}
        </button>
      </Card>
    );
  }

  return (
    <Card title={t("blocks.title")}>
      <p className="mb-4 text-sm text-slate-600">{t("blocks.lunchHint")}</p>
      <form onSubmit={submit} noValidate>
        <FormError error={create.error} />
        <SelectField
          label={t("blocks.who")}
          value={providerId}
          onChange={setProviderId}
          options={[
            { value: "", label: t("blocks.everyone") },
            ...agenda.providers.map((p) => ({ value: p.id, label: p.name })),
          ]}
        />
        <SelectField
          label={t("blocks.kind")}
          value={kind}
          onChange={(v) => setKind(v as Kind)}
          options={[
            { value: "days", label: t("blocks.days") },
            { value: "hours", label: t("blocks.hours") },
          ]}
        />
        <TextField
          label={kind === "days" ? t("providers.fromDate") : t("booking.date")}
          type="date"
          required
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
        {kind === "days" ? (
          <TextField
            label={t("providers.toDate")}
            hint={t("providers.toDateHint")}
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        ) : (
          <div className="flex gap-3">
            <TextField
              label={t("blocks.from")}
              type="time"
              step={300}
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
            />
            <TextField
              label={t("blocks.to")}
              type="time"
              step={300}
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
            />
          </div>
        )}
        <TextField
          label={t("providers.reason")}
          maxLength={120}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <div className="flex gap-2">
          <SubmitButton busy={create.isPending}>{t("blocks.save")}</SubmitButton>
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

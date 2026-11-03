import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { Agenda, AgendaAppointment, AppointmentStatus } from "../../../api/agenda";
import { useChangeAppointmentStatus, useMoveAppointment } from "../../../api/appointments";
import { useAuth } from "../../../auth/AuthProvider";
import { useCan } from "../../../auth/permissions";
import { Card, FormError, SelectField, TextField } from "../../../components/form";
import { dayLabel, localDate, timeLabel, zonedToUtc } from "../../../i18n/zoned";
import { STATUS_CLASS, providerOf } from "./AppointmentCard";

/** Detalhe de um agendamento, com as ações que o perfil permite. */
export function AppointmentPanel({
  item,
  agenda,
  locale,
  onClose,
}: {
  item: AgendaAppointment;
  agenda: Agenda;
  locale: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const can = useCan();
  const status = useChangeAppointmentStatus(slug);
  const [moving, setMoving] = useState(false);
  const tz = agenda.timezone;
  const started = new Date(item.starts_at) <= new Date();
  const active = item.status === "scheduled" || item.status === "confirmed";

  // Ações possíveis: confirmar (se ainda não), atendido/faltou (só depois do início),
  // cancelar; um cancelado/encerrado pode voltar a agendado.
  const actions: AppointmentStatus[] = [];
  if (active) {
    if (item.status === "scheduled") actions.push("confirmed");
    if (started) actions.push("completed", "no_show");
    actions.push("cancelled");
  } else {
    actions.push("scheduled");
  }

  return (
    <Card title={item.customer_name}>
      <p className={`mb-3 inline-block rounded-full border-l-4 px-3 py-1 text-sm ${STATUS_CLASS[item.status]}`}>
        {t(`agenda.status.${item.status}`)}
      </p>
      <dl className="mb-4 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-slate-500">{t("booking.service")}</dt>
        <dd>{item.offering_name}</dd>
        <dt className="text-slate-500">{t("agenda.provider")}</dt>
        <dd>{providerOf(agenda, item.provider_id)?.name}</dd>
        <dt className="text-slate-500">{t("booking.when")}</dt>
        <dd className="capitalize">
          {dayLabel(localDate(item.starts_at, tz), locale)},{" "}
          {t("agenda.timeRange", {
            from: timeLabel(item.starts_at, tz, locale),
            to: timeLabel(item.ends_at, tz, locale),
          })}
        </dd>
        {item.customer_phone_display && (
          <>
            <dt className="text-slate-500">{t("customers.fields.phone")}</dt>
            <dd>{item.customer_phone_display}</dd>
          </>
        )}
      </dl>

      {can("agenda.manage") && (
        <>
          <FormError error={status.error} />
          <div className="flex flex-wrap gap-2">
            {actions.map((next) => (
              <button
                key={next}
                type="button"
                disabled={status.isPending}
                onClick={() => status.mutate({ id: item.id, status: next }, { onSuccess: onClose })}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium"
              >
                {t(`booking.actions.${next}`)}
              </button>
            ))}
            {active && (
              <button
                type="button"
                onClick={() => setMoving(true)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium"
              >
                {t("booking.actions.move")}
              </button>
            )}
          </div>
          {moving && <MoveForm item={item} agenda={agenda} onDone={onClose} />}
        </>
      )}
      <button type="button" onClick={onClose} className="mt-4 text-sm underline">
        {t("booking.close")}
      </button>
    </Card>
  );
}

function MoveForm({
  item,
  agenda,
  onDone,
}: {
  item: AgendaAppointment;
  agenda: Agenda;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const move = useMoveAppointment(slug);
  const tz = agenda.timezone;
  const [date, setDate] = useState(localDate(item.starts_at, tz));
  const [time, setTime] = useState(timeLabel(item.starts_at, tz, "pt-BR"));
  const [providerId, setProviderId] = useState(item.provider_id);

  function submit() {
    move.mutate(
      { id: item.id, starts_at: zonedToUtc(date, time, tz), provider_id: providerId },
      { onSuccess: onDone },
    );
  }

  return (
    <div className="mt-4 rounded-xl bg-brand-50 p-4">
      <FormError error={move.error} />
      <div className="flex gap-3">
        <TextField
          label={t("booking.date")}
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
        <TextField
          label={t("booking.time")}
          type="time"
          step={300}
          value={time}
          onChange={(e) => setTime(e.target.value)}
        />
      </div>
      {agenda.providers.length > 1 && (
        <SelectField
          label={t("agenda.provider")}
          value={providerId}
          onChange={setProviderId}
          options={agenda.providers.map((p) => ({ value: p.id, label: p.name }))}
        />
      )}
      <button
        type="button"
        onClick={submit}
        disabled={move.isPending}
        className="mt-2 w-full rounded-xl bg-brand-700 px-4 py-3 font-medium text-white disabled:opacity-60"
      >
        {t("booking.saveMove")}
      </button>
    </div>
  );
}

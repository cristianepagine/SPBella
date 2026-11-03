import { useTranslation } from "react-i18next";

import type { Agenda, AgendaAppointment } from "../../../api/agenda";
import { dayLabel, localDate } from "../../../i18n/zoned";
import { AppointmentCard, providerOf } from "./AppointmentCard";

/** Celular: lista dia a dia, em ordem de horário. */
export function AgendaList({
  agenda,
  dates,
  locale,
  onSelect,
}: {
  agenda: Agenda;
  dates: string[];
  locale: string;
  onSelect: (item: AgendaAppointment) => void;
}) {
  const { t } = useTranslation();

  return (
    <section aria-label={t("agenda.listView")} className="flex flex-col gap-3 md:hidden">
      {dates.map((date) => {
        const items = agenda.appointments.filter(
          (a) => localDate(a.starts_at, agenda.timezone) === date,
        );
        const off = agenda.time_off.filter(
          (o) =>
            localDate(o.starts_at, agenda.timezone) <= date &&
            date < localDate(o.ends_at, agenda.timezone),
        );
        return (
          <div key={date} className="rounded-2xl bg-white p-4 shadow-sm">
            <h2 className="mb-2 font-bold capitalize">{dayLabel(date, locale)}</h2>
            {off.map((o) => (
              <p key={o.id} className="mb-2 rounded-lg bg-slate-100 px-2 py-1 text-sm text-slate-600">
                {o.provider_id
                  ? t("agenda.timeOff", { name: providerOf(agenda, o.provider_id)?.name })
                  : t("agenda.closed")}
                {o.reason && ` · ${o.reason}`}
              </p>
            ))}
            {items.length === 0 && off.length === 0 && (
              <p className="text-sm text-slate-500">{t("agenda.empty")}</p>
            )}
            <ul className="flex flex-col gap-2">
              {items.map((item) => (
                <li key={item.id}>
                  <AppointmentCard item={item} agenda={agenda} locale={locale} onSelect={onSelect} />
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
}

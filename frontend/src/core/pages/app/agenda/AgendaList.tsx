import { useTranslation } from "react-i18next";

import type { Agenda, AgendaAppointment } from "../../../api/agenda";
import { useDeleteBlock } from "../../../api/appointments";
import { useAuth } from "../../../auth/AuthProvider";
import { useCan } from "../../../auth/permissions";
import { dayLabel, localDate } from "../../../i18n/zoned";
import { AppointmentCard, providerOf } from "./AppointmentCard";
import { blockHours, blocksOn, isWholeDays } from "./blocks";

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
  const { slug } = useAuth();
  const can = useCan();
  const remove = useDeleteBlock(slug);
  const tz = agenda.timezone;

  return (
    <section aria-label={t("agenda.listView")} className="flex flex-col gap-3 md:hidden">
      {dates.map((date) => {
        const items = agenda.appointments.filter(
          (a) => localDate(a.starts_at, agenda.timezone) === date,
        );
        const off = blocksOn(agenda, date);
        return (
          <div key={date} className="rounded-2xl bg-white p-4 shadow-sm">
            <h2 className="mb-2 font-bold capitalize">{dayLabel(date, locale)}</h2>
            {off.map((o) => (
              <div
                key={o.id}
                className="mb-2 flex items-center justify-between gap-2 rounded-lg bg-slate-100 px-2 py-1 text-sm text-slate-600"
              >
                <span>
                  {o.provider_id
                    ? t("agenda.timeOff", { name: providerOf(agenda, o.provider_id)?.name })
                    : t("agenda.closed")}
                  {!isWholeDays(o, tz) && ` · ${blockHours(o, tz, locale)}`}
                  {o.reason && ` · ${o.reason}`}
                </span>
                {can("time_off.manage") && (
                  <button
                    type="button"
                    className="shrink-0 text-xs text-red-700 underline"
                    onClick={() => remove.mutate(o.id)}
                  >
                    {t("blocks.remove")}
                  </button>
                )}
              </div>
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

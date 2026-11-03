import { useTranslation } from "react-i18next";

import type { Agenda, AgendaAppointment } from "../../../api/agenda";
import { dayLabel, hhmmToMinutes, isoWeekday, localDate, minutesOfDay } from "../../../i18n/zoned";
import { PROVIDER_COLOR_CLASS } from "../../../layout/colors";
import { AppointmentCard, providerOf } from "./AppointmentCard";

const PX_PER_MINUTE = 1; // 1 hora = 60 px
const DAY_END = 24 * 60;

type Column = { key: string; label: string; date: string; providerId: string | null };

/**
 * Computador: grade de horários. No dia, uma coluna por profissional; na semana, uma coluna
 * por dia. O fundo branco marca a jornada; o cinza, fora dela.
 */
export function AgendaGrid({
  agenda,
  dates,
  locale,
  columnsBy,
  onSelect,
}: {
  agenda: Agenda;
  dates: string[];
  locale: string;
  columnsBy: "provider" | "day";
  onSelect: (item: AgendaAppointment) => void;
}) {
  const { t } = useTranslation();
  const tz = agenda.timezone;

  // Horas visíveis: da primeira jornada/agendamento à última (no mínimo 8h às 19h).
  const ranges = agenda.providers.flatMap((p) => p.working_hours);
  const starts = [
    ...ranges.map((r) => hhmmToMinutes(r.start)),
    ...agenda.appointments.map((a) => minutesOfDay(a.starts_at, tz)),
  ];
  const ends = [
    ...ranges.map((r) => hhmmToMinutes(r.end)),
    ...agenda.appointments.map((a) => minutesOfDay(a.ends_at, tz) || DAY_END),
  ];
  const top = Math.floor(Math.min(8 * 60, ...starts) / 60) * 60;
  const bottom = Math.ceil(Math.max(19 * 60, ...ends) / 60) * 60;
  const hours = Array.from({ length: (bottom - top) / 60 }, (_, i) => top / 60 + i);

  const columns: Column[] =
    columnsBy === "provider"
      ? agenda.providers.map((p) => ({ key: p.id, label: p.name, date: dates[0], providerId: p.id }))
      : dates.map((d) => ({ key: d, label: dayLabel(d, locale), date: d, providerId: null }));

  return (
    <section
      aria-label={t("agenda.gridView")}
      className="hidden overflow-x-auto rounded-2xl bg-white p-4 shadow-sm md:block"
    >
      <div className="flex min-w-max">
        <div className="w-12 shrink-0 pt-8">
          {hours.map((h) => (
            <div key={h} style={{ height: 60 * PX_PER_MINUTE }} className="text-right text-xs text-slate-400">
              {t("agenda.hour", { hour: String(h).padStart(2, "0") })}
            </div>
          ))}
        </div>
        {columns.map((column) => {
          const provider = providerOf(agenda, column.providerId);
          const working = (provider?.working_hours ?? []).filter(
            (r) => r.weekday === isoWeekday(column.date),
          );
          const items = agenda.appointments.filter(
            (a) =>
              localDate(a.starts_at, tz) === column.date &&
              (!column.providerId || a.provider_id === column.providerId),
          );
          return (
            <div key={column.key} className="w-44 shrink-0 border-l border-slate-100 px-1">
              <p className="flex h-8 items-center gap-1 truncate text-sm font-medium capitalize">
                {provider && <span className={`h-3 w-3 rounded-full ${PROVIDER_COLOR_CLASS[provider.color]}`} />}
                {column.label}
              </p>
              <div className="relative bg-slate-50" style={{ height: (bottom - top) * PX_PER_MINUTE }}>
                {working.map((r) => (
                  <div
                    key={r.start}
                    className="absolute inset-x-0 bg-white"
                    style={{
                      top: (hhmmToMinutes(r.start) - top) * PX_PER_MINUTE,
                      height: (hhmmToMinutes(r.end) - hhmmToMinutes(r.start)) * PX_PER_MINUTE,
                    }}
                  />
                ))}
                {items.map((item) => {
                  const begin = minutesOfDay(item.starts_at, tz);
                  const sameDay = localDate(item.ends_at, tz) === column.date;
                  const finish = sameDay ? minutesOfDay(item.ends_at, tz) : DAY_END;
                  return (
                    <div
                      key={item.id}
                      className="absolute inset-x-1"
                      style={{
                        top: (begin - top) * PX_PER_MINUTE,
                        height: Math.max(24, (finish - begin) * PX_PER_MINUTE),
                      }}
                    >
                      <AppointmentCard
                        item={item}
                        agenda={agenda}
                        locale={locale}
                        showProvider={columnsBy === "day"}
                        onSelect={onSelect}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

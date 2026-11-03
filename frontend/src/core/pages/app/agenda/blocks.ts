import type { Agenda } from "../../../api/agenda";
import { localDate, minutesOfDay, timeLabel } from "../../../i18n/zoned";

export type AgendaBlock = Agenda["time_off"][number];

/** Bloqueio de dias inteiros: começa e termina à meia-noite local. */
export function isWholeDays(block: AgendaBlock, tz: string): boolean {
  return minutesOfDay(block.starts_at, tz) === 0 && minutesOfDay(block.ends_at, tz) === 0;
}

/** Bloqueios que tocam o dia (data local). */
export function blocksOn(agenda: Agenda, day: string): AgendaBlock[] {
  const tz = agenda.timezone;
  return agenda.time_off.filter((b) => {
    const first = localDate(b.starts_at, tz);
    const lastInstant = new Date(new Date(b.ends_at).getTime() - 1).toISOString();
    return first <= day && day <= localDate(lastInstant, tz);
  });
}

export function blockHours(block: AgendaBlock, tz: string, locale: string): string {
  return `${timeLabel(block.starts_at, tz, locale)}–${timeLabel(block.ends_at, tz, locale)}`;
}

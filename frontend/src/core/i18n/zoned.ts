/**
 * Datas e horas no fuso do ESTABELECIMENTO (não no do aparelho).
 * Datas locais circulam como texto "AAAA-MM-DD", igual à API.
 */

function parts(utc: string | Date, timeZone: string) {
  const formatted = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(typeof utc === "string" ? new Date(utc) : utc);
  const get = (type: string) => formatted.find((p) => p.type === type)!.value;
  return { date: `${get("year")}-${get("month")}-${get("day")}`, hour: +get("hour"), minute: +get("minute") };
}

/** "2026-11-03T13:30:00Z" em São Paulo → "2026-11-03". */
export function localDate(utc: string | Date, timeZone: string): string {
  return parts(utc, timeZone).date;
}

/** Minutos desde a meia-noite local (10:30 → 630). */
export function minutesOfDay(utc: string | Date, timeZone: string): number {
  const { hour, minute } = parts(utc, timeZone);
  return hour * 60 + minute;
}

export function todayIn(timeZone: string): string {
  return localDate(new Date(), timeZone);
}

export function addDays(day: string, amount: number): string {
  const date = new Date(`${day}T12:00:00Z`); // meio-dia UTC: nunca vira o dia por fuso
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}

/** Dia da semana ISO, como na API: 0 = segunda ... 6 = domingo. */
export function isoWeekday(day: string): number {
  return (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7;
}

export function mondayOf(day: string): string {
  return addDays(day, -isoWeekday(day));
}

/** "ter., 03/11" */
export function dayLabel(day: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    timeZone: "UTC",
  }).format(new Date(`${day}T12:00:00Z`));
}

/** "10:30", no fuso do estabelecimento, sempre 24 h. */
export function timeLabel(utc: string, timeZone: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone,
  }).format(new Date(utc));
}

/** "09:30" → 570 */
export function hhmmToMinutes(value: string): number {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
}

/**
 * Dia e hora locais do estabelecimento → instante UTC (ISO). Ex.: ("2026-11-03", "10:00",
 * "America/Sao_Paulo") → "2026-11-03T13:00:00.000Z". Funciona também com horário de verão.
 */
export function zonedToUtc(day: string, hhmm: string, timeZone: string): string {
  const [y, m, d] = day.split("-").map(Number);
  const [h, min] = hhmm.split(":").map(Number);
  const wanted = Date.UTC(y, m - 1, d, h, min);
  let guess = wanted;
  for (let i = 0; i < 2; i += 1) {
    const local = parts(new Date(guess), timeZone);
    const [ly, lm, ld] = local.date.split("-").map(Number);
    const seen = Date.UTC(ly, lm - 1, ld, local.hour, local.minute);
    guess += wanted - seen; // corrige pela diferença entre o que queríamos e o que o fuso mostra
  }
  return new Date(guess).toISOString();
}

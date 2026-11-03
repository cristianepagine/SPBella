import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { WorkingRange } from "../../../api/providers";
import { FormError } from "../../../components/form";

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6]; // ISO: 0 = segunda ... 6 = domingo (igual à API)
const DEFAULT_RANGE = { start: "09:00", end: "18:00" };

type Range = { start: string; end: string };

function byDay(ranges: WorkingRange[]): Range[][] {
  return WEEKDAYS.map((day) =>
    ranges.filter((r) => r.weekday === day).map(({ start, end }) => ({ start, end })),
  );
}

/** Jornada semanal: para cada dia, se trabalha e em quais faixas (duas faixas = intervalo). */
export function WeekEditor({
  value,
  onSave,
  saving,
  error,
}: {
  value: WorkingRange[];
  onSave: (ranges: WorkingRange[]) => void;
  saving: boolean;
  error: unknown;
}) {
  const { t } = useTranslation();
  const [days, setDays] = useState(() => byDay(value));

  function update(day: number, ranges: Range[]) {
    setDays((current) => current.map((r, i) => (i === day ? ranges : r)));
  }

  function save() {
    onSave(days.flatMap((ranges, weekday) => ranges.map((r) => ({ weekday, ...r }))));
  }

  return (
    <div>
      <FormError error={error} />
      <ul className="divide-y divide-slate-100">
        {days.map((ranges, day) => (
          <li key={day} className="py-3">
            <label className="flex items-center gap-3 font-medium">
              <input
                type="checkbox"
                className="h-5 w-5 accent-brand-700"
                checked={ranges.length > 0}
                onChange={(e) => update(day, e.target.checked ? [{ ...DEFAULT_RANGE }] : [])}
              />
              {t(`weekdays.${day}`)}
            </label>
            {ranges.map((range, index) => (
              <div key={index} className="mt-2 flex flex-wrap items-center gap-2 pl-8">
                <TimeInput
                  label={t(index ? "providers.fromN" : "providers.from", {
                    day: t(`weekdays.${day}`),
                    n: index + 1,
                  })}
                  value={range.start}
                  onChange={(start) => update(day, ranges.map((r, i) => (i === index ? { ...r, start } : r)))}
                />
                <span aria-hidden>–</span>
                <TimeInput
                  label={t(index ? "providers.toN" : "providers.to", {
                    day: t(`weekdays.${day}`),
                    n: index + 1,
                  })}
                  value={range.end}
                  onChange={(end) => update(day, ranges.map((r, i) => (i === index ? { ...r, end } : r)))}
                />
                {ranges.length > 1 && (
                  <button
                    type="button"
                    className="text-sm text-red-700 underline"
                    onClick={() => update(day, ranges.filter((_, i) => i !== index))}
                  >
                    {t("providers.removeRange")}
                  </button>
                )}
              </div>
            ))}
            {ranges.length > 0 && (
              <button
                type="button"
                className="mt-2 pl-8 text-sm font-medium text-brand-700 underline"
                onClick={() => update(day, [...ranges, { start: ranges.at(-1)!.end, end: "19:00" }])}
              >
                {t("providers.addRange")}
              </button>
            )}
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={save}
        disabled={saving}
        className="mt-2 w-full rounded-xl bg-brand-700 px-4 py-3 font-medium text-white disabled:opacity-60"
      >
        {t("providers.saveHours")}
      </button>
    </div>
  );
}

function TimeInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="time"
      step={300}
      aria-label={label}
      className="rounded-lg border border-slate-300 bg-white px-3 py-2"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}


import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type Agenda,
  type AgendaAppointment,
  type AppointmentStatus,
  useAgenda,
} from "../../../api/agenda";
import { useCan } from "../../../auth/permissions";
import { useAuth } from "../../../auth/AuthProvider";
import { FormError } from "../../../components/form";
import { formatLocale } from "../../../i18n/format";
import { addDays, dayLabel, mondayOf, todayIn } from "../../../i18n/zoned";
import { useCurrentTenant } from "../../TenantLayout";
import { AgendaGrid } from "./AgendaGrid";
import { AgendaList } from "./AgendaList";
import { AppointmentPanel } from "./AppointmentPanel";
import { BookingForm } from "./BookingForm";
import { STATUS_CLASS } from "./AppointmentCard";

type View = "day" | "week";

const STATUSES = Object.keys(STATUS_CLASS) as AppointmentStatus[];

/** Agenda do dia ou da semana: colunas no computador, lista no celular. */
export function AgendaPage() {
  const { t, i18n } = useTranslation();
  const { slug } = useAuth();
  const tenant = useCurrentTenant();
  const [view, setView] = useState<View>("day");
  const [day, setDay] = useState(() => todayIn(tenant.timezone));
  const [providerId, setProviderId] = useState("");
  const [selected, setSelected] = useState<AgendaAppointment | null>(null);
  const [booking, setBooking] = useState(false);
  const can = useCan();

  const start = view === "week" ? mondayOf(day) : day;
  const days = view === "week" ? 7 : 1;
  const agenda = useAgenda(slug, start, days, providerId || undefined);
  const locale = formatLocale(i18n.language, tenant.country);
  const dates = Array.from({ length: days }, (_, i) => addDays(start, i));
  const period =
    view === "day"
      ? dayLabel(start, locale)
      : t("agenda.weekOf", { from: dayLabel(start, locale), to: dayLabel(dates[6], locale) });

  return (
    <section className="flex flex-col gap-4">
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h1 className="text-2xl font-bold text-brand-900">{t("agenda.title")}</h1>
          {can("agenda.manage") && !booking && (
            <button
              type="button"
              onClick={() => setBooking(true)}
              className="rounded-xl bg-brand-700 px-4 py-2 font-medium text-white"
            >
              {t("booking.new")}
            </button>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <NavButton label={t("agenda.previous")} onClick={() => setDay(addDays(day, -days))}>
            ‹
          </NavButton>
          <NavButton onClick={() => setDay(todayIn(tenant.timezone))}>{t("agenda.today")}</NavButton>
          <NavButton label={t("agenda.next")} onClick={() => setDay(addDays(day, days))}>
            ›
          </NavButton>
          <span className="font-medium capitalize">{period}</span>
          <div
            role="group"
            aria-label={t("agenda.view")}
            className="ml-auto flex overflow-hidden rounded-lg border border-slate-300"
          >
            {(["day", "week"] as View[]).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={`px-3 py-2 text-sm ${view === v ? "bg-brand-700 text-white" : "bg-white"}`}
              >
                {t(`agenda.${v}`)}
              </button>
            ))}
          </div>
        </div>

        {agenda.data?.scope === "all" && (
          <ProviderFilter agenda={agenda.data} value={providerId} onChange={setProviderId} />
        )}
        <Legend />
      </div>

      {booking && <BookingForm day={day} onDone={() => setBooking(false)} />}
      {selected && agenda.data && (
        <AppointmentPanel
          item={selected}
          agenda={agenda.data}
          locale={locale}
          onClose={() => setSelected(null)}
        />
      )}

      {agenda.isPending && <p role="status">{t("auth.loading")}</p>}
      {agenda.isError && <FormError error={agenda.error} />}
      {agenda.data?.own_provider_missing && (
        <p role="alert" className="rounded-2xl bg-amber-50 p-4 text-amber-900">
          {t("agenda.notLinked")}
        </p>
      )}
      {agenda.data && !agenda.data.own_provider_missing && agenda.data.providers.length === 0 && (
        <p className="rounded-2xl bg-white p-4 text-slate-600">{t("agenda.noProviders")}</p>
      )}
      {agenda.data && agenda.data.providers.length > 0 && (
        <>
          <AgendaList agenda={agenda.data} dates={dates} locale={locale} onSelect={setSelected} />
          <AgendaGrid
            agenda={agenda.data}
            dates={dates}
            locale={locale}
            columnsBy={view === "day" ? "provider" : "day"}
            onSelect={setSelected}
          />
        </>
      )}
    </section>
  );
}

function NavButton({
  label,
  onClick,
  children,
}: {
  label?: string;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="rounded-lg border border-slate-300 px-3 py-2 font-medium"
    >
      {children}
    </button>
  );
}

/** Filtro por profissional (para quem vê todos). Guarda a lista completa para não sumir com o
 * filtro aplicado (a API devolve só o profissional filtrado). */
function ProviderFilter({
  agenda,
  value,
  onChange,
}: {
  agenda: Agenda;
  value: string;
  onChange: (id: string) => void;
}) {
  const { t } = useTranslation();
  const [known] = useState(() => agenda.providers);
  const providers = known.length >= agenda.providers.length ? known : agenda.providers;
  if (providers.length < 2) return null;
  return (
    <label className="mt-3 block text-sm">
      <span className="mr-2 font-medium">{t("agenda.provider")}</span>
      <select
        className="rounded-lg border border-slate-300 bg-white px-2 py-2"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{t("agenda.allProviders")}</option>
        {providers.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function Legend() {
  const { t } = useTranslation();
  return (
    <ul aria-label={t("agenda.legend")} className="mt-3 flex flex-wrap gap-2 text-xs">
      {STATUSES.map((s) => (
        <li key={s} className={`rounded-full border-l-4 px-2 py-1 ${STATUS_CLASS[s]}`}>
          {t(`agenda.status.${s}`)}
        </li>
      ))}
    </ul>
  );
}

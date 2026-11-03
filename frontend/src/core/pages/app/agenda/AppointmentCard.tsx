import { useTranslation } from "react-i18next";

import type { Agenda, AgendaAppointment, AppointmentStatus } from "../../../api/agenda";
import { timeLabel } from "../../../i18n/zoned";
import { PROVIDER_COLOR_CLASS } from "../../../layout/colors";

/** Cores por status (classes completas, para o Tailwind gerar). */
export const STATUS_CLASS: Record<AppointmentStatus, string> = {
  scheduled: "border-sky-500 bg-sky-50 text-sky-950",
  confirmed: "border-emerald-600 bg-emerald-50 text-emerald-950",
  completed: "border-slate-400 bg-slate-100 text-slate-700",
  no_show: "border-red-600 bg-red-50 text-red-900",
  cancelled: "border-slate-300 bg-white text-slate-400 line-through",
};

export function providerOf(agenda: Agenda, id: string | null) {
  return agenda.providers.find((p) => p.id === id);
}

export function AppointmentCard({
  item,
  agenda,
  locale,
  showProvider = true,
  onSelect,
}: {
  item: AgendaAppointment;
  agenda: Agenda;
  locale: string;
  /** Desligado quando a coluna já é do profissional. */
  showProvider?: boolean;
  onSelect?: (item: AgendaAppointment) => void;
}) {
  const { t } = useTranslation();
  const provider = providerOf(agenda, item.provider_id);
  const from = timeLabel(item.starts_at, agenda.timezone, locale);
  const to = timeLabel(item.ends_at, agenda.timezone, locale);

  return (
    <button
      type="button"
      onClick={() => onSelect?.(item)}
      className={`block h-full w-full overflow-hidden rounded-lg border-l-4 px-2 py-1 text-left text-sm ${STATUS_CLASS[item.status]}`}
    >
      <p className="font-medium">
        {t("agenda.timeRange", { from, to })} {item.customer_name}
      </p>
      <p className="truncate">
        {item.offering_name}
        {showProvider && provider && agenda.providers.length > 1 && (
          <span className="ml-2 inline-flex items-center gap-1 text-xs">
            <span className={`inline-block h-2 w-2 rounded-full ${PROVIDER_COLOR_CLASS[provider.color]}`} />
            {provider.name}
          </span>
        )}
      </p>
      <p className="text-xs">
        {t(`agenda.status.${item.status}`)}
        {item.source === "public" && ` · ${t("agenda.online")}`}
        {item.customer_phone_display && ` · ${item.customer_phone_display}`}
      </p>
    </button>
  );
}

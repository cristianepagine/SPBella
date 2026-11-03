import { type FormEvent, type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import {
  type BookingConfirmation,
  type PublicOffering,
  useBook,
  useBookingCatalog,
  usePublicAvailability,
} from "../../api/booking";
import { ApiError } from "../../api/client";
import {
  CheckboxField,
  FormError,
  SubmitButton,
  TextField,
} from "../../components/form";
import { useTurnstile } from "../../components/Turnstile";
import { type Language } from "../../i18n";
import { formatLocale } from "../../i18n/format";
import {
  addDays,
  dayLabel,
  localDate,
  timeLabel,
  todayIn,
} from "../../i18n/zoned";
import { salonPath } from "../../paths";
import { useCurrentTenant } from "../TenantLayout";

const DAYS_PER_PAGE = 7;

type Slot = { starts_at: string; provider_ids: string[] };

/**
 * Agendamento pelo cliente final: serviço → profissional (ou sem preferência) → dia → horário →
 * nome, telefone e consentimento. A vertical pode mostrar mais sobre cada serviço
 * (`offeringDetail`, ex.: o preço no salão).
 */
export function BookingFlow({
  offeringDetail,
}: {
  offeringDetail?: (offering: PublicOffering) => ReactNode;
}) {
  const { t, i18n } = useTranslation();
  const tenant = useCurrentTenant();
  const catalog = useBookingCatalog(tenant.slug);
  const [offeringId, setOfferingId] = useState<string>();
  const [providerId, setProviderId] = useState<string | null>(); // null = sem preferência
  const [day, setDay] = useState<string>();
  const [slot, setSlot] = useState<Slot>();
  const [done, setDone] = useState<BookingConfirmation>();
  const [lost, setLost] = useState(false); // outra pessoa pegou o horário escolhido
  const display = formatLocale(i18n.language, tenant.country);

  if (catalog.isPending) return <p role="status">{t("tenant.loading")}</p>;
  if (catalog.isError) return <FormError error={catalog.error} />;
  const { offerings, providers } = catalog.data;

  if (done) {
    return (
      <Done
        confirmation={done}
        display={display}
        onAgain={() => {
          setDone(undefined);
          setSlot(undefined);
        }}
      />
    );
  }
  if (offerings.length === 0)
    return <p className="text-slate-600">{t("publicBooking.noServices")}</p>;

  const offering = offerings.find((o) => o.id === offeringId);
  const able = providers.filter(
    (p) => offeringId && p.offering_ids.includes(offeringId),
  );
  const providerName = (id: string) =>
    providers.find((p) => p.id === id)?.name ?? "";

  return (
    <div className="space-y-6">
      <Step title={t("publicBooking.chooseService")}>
        <div className="grid gap-2">
          {offerings.map((o) => (
            <Choice
              key={o.id}
              selected={o.id === offeringId}
              onClick={() => {
                setOfferingId(o.id);
                setProviderId(undefined);
                setSlot(undefined);
              }}
            >
              <span className="font-medium">{o.name}</span>
              <span className="text-sm opacity-80">
                {t("publicBooking.duration", { count: o.duration_min })}
                {offeringDetail && <> · {offeringDetail(o)}</>}
              </span>
            </Choice>
          ))}
        </div>
      </Step>

      {offering && (
        <Step title={t("publicBooking.chooseProvider")}>
          <div className="grid gap-2 sm:grid-cols-2">
            {able.length > 1 && (
              <Choice
                selected={providerId === null}
                onClick={() => {
                  setProviderId(null);
                  setSlot(undefined);
                }}
              >
                <span className="font-medium">{t("publicBooking.anyProvider")}</span>
              </Choice>
            )}
            {able.map((p) => (
              <Choice
                key={p.id}
                selected={p.id === providerId}
                onClick={() => {
                  setProviderId(p.id);
                  setSlot(undefined);
                }}
              >
                <span className="font-medium">{p.name}</span>
              </Choice>
            ))}
          </div>
        </Step>
      )}

      {offering && providerId !== undefined && (
        <Step title={t("publicBooking.chooseDay")}>
          <DayPicker
            maxDaysAhead={catalog.data.max_days_ahead}
            value={day}
            onChange={(value) => {
              setDay(value);
              setSlot(undefined);
            }}
            display={display}
          />
        </Step>
      )}

      {offering && providerId !== undefined && day && (
        <Step title={t("publicBooking.chooseTime")}>
          {lost && (
            <p role="alert" className="mb-3 rounded-xl bg-amber-50 px-4 py-3 text-amber-900">
              {t("errors.slot_unavailable")}
            </p>
          )}
          <Times
            offeringId={offering.id}
            providerId={providerId ?? undefined}
            day={day}
            value={slot}
            onChange={(value) => {
              setSlot(value);
              setLost(false);
            }}
          />
        </Step>
      )}

      {offering && slot && (
        <Step title={t("publicBooking.yourDetails")}>
          <p className="mb-4 rounded-xl bg-brand-50 px-4 py-3 text-slate-800">
            {t("publicBooking.summary", {
              service: offering.name,
              day: dayLabel(day!, display),
              time: timeLabel(slot.starts_at, tenant.timezone, display),
              provider: providerId
                ? providerName(providerId)
                : t("publicBooking.anyProvider"),
            })}
          </p>
          <DetailsForm
            offeringId={offering.id}
            providerId={providerId ?? null}
            startsAt={slot.starts_at}
            policyVersion={catalog.data.privacy_policy_version}
            onBooked={setDone}
            onLost={() => {
              setLost(true);
              setSlot(undefined);
            }}
          />
        </Step>
      )}
    </div>
  );
}

function Step({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title}>
      <h2 className="mb-3 text-lg font-semibold text-brand-900">{title}</h2>
      {children}
    </section>
  );
}

function Choice({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={`flex flex-col items-start rounded-xl border px-4 py-3 text-left ${
        selected
          ? "border-brand-700 bg-brand-700 text-white"
          : "border-slate-300 bg-white"
      }`}
    >
      {children}
    </button>
  );
}

function DayPicker({
  maxDaysAhead,
  value,
  onChange,
  display,
}: {
  maxDaysAhead: number;
  value?: string;
  onChange: (day: string) => void;
  display: string;
}) {
  const { t } = useTranslation();
  const tenant = useCurrentTenant();
  const today = todayIn(tenant.timezone);
  const [page, setPage] = useState(0);
  const total = maxDaysAhead + 1;
  const first = page * DAYS_PER_PAGE;
  const days = Array.from(
    { length: Math.min(DAYS_PER_PAGE, total - first) },
    (_, i) => addDays(today, first + i),
  );

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {days.map((d) => (
          <button
            key={d}
            type="button"
            aria-pressed={d === value}
            onClick={() => onChange(d)}
            className={`rounded-lg border px-3 py-2 text-sm ${
              d === value
                ? "border-brand-700 bg-brand-700 text-white"
                : "border-slate-300 bg-white"
            }`}
          >
            {d === today ? t("publicBooking.today") : dayLabel(d, display)}
          </button>
        ))}
      </div>
      <div className="mt-2 flex justify-between text-sm">
        <button
          type="button"
          className="px-2 py-2 font-medium text-brand-700 disabled:invisible"
          disabled={page === 0}
          onClick={() => setPage(page - 1)}
        >
          {t("publicBooking.previousDays")}
        </button>
        <button
          type="button"
          className="px-2 py-2 font-medium text-brand-700 disabled:invisible"
          disabled={first + DAYS_PER_PAGE >= total}
          onClick={() => setPage(page + 1)}
        >
          {t("publicBooking.nextDays")}
        </button>
      </div>
    </div>
  );
}

function Times({
  offeringId,
  providerId,
  day,
  value,
  onChange,
}: {
  offeringId: string;
  providerId?: string;
  day: string;
  value?: Slot;
  onChange: (slot: Slot) => void;
}) {
  const { t, i18n } = useTranslation();
  const tenant = useCurrentTenant();
  const display = formatLocale(i18n.language, tenant.country);
  const free = usePublicAvailability(tenant.slug, offeringId, day, providerId);

  if (free.isPending) return <p role="status">{t("tenant.loading")}</p>;
  if (free.isError) return <FormError error={free.error} />;
  if (free.data.slots.length === 0)
    return <p className="text-slate-600">{t("publicBooking.noTimes")}</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {free.data.slots.map((s) => (
        <button
          key={s.starts_at}
          type="button"
          aria-pressed={s.starts_at === value?.starts_at}
          onClick={() => onChange(s)}
          className={`rounded-lg border px-3 py-2 text-sm ${
            s.starts_at === value?.starts_at
              ? "border-brand-700 bg-brand-700 text-white"
              : "border-slate-300 bg-white"
          }`}
        >
          {timeLabel(s.starts_at, tenant.timezone, display)}
        </button>
      ))}
    </div>
  );
}

function DetailsForm({
  offeringId,
  providerId,
  startsAt,
  policyVersion,
  onBooked,
  onLost,
}: {
  offeringId: string;
  providerId: string | null;
  startsAt: string;
  policyVersion: string;
  onBooked: (confirmation: BookingConfirmation) => void;
  onLost: () => void;
}) {
  const { t, i18n } = useTranslation();
  const tenant = useCurrentTenant();
  const book = useBook(tenant.slug);
  const turnstile = useTurnstile();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [service, setService] = useState(false);
  const [reminders, setReminders] = useState(true);
  const [marketing, setMarketing] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const confirmation = await book.mutateAsync({
        offering_id: offeringId,
        provider_id: providerId,
        starts_at: startsAt,
        name,
        phone,
        email: email || null,
        locale: i18n.language as Language,
        consents: [
          ...(service ? (["service"] as const) : []),
          ...(reminders ? (["reminders"] as const) : []),
          ...(marketing ? (["marketing"] as const) : []),
        ],
        turnstile_token: turnstile.token,
      });
      onBooked(confirmation);
    } catch (e) {
      turnstile.reset();
      if (e instanceof ApiError && e.code === "slot_unavailable") onLost();
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <FormError error={book.error} />
      <TextField
        label={t("publicBooking.name")}
        autoComplete="name"
        required
        maxLength={120}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <TextField
        label={t("publicBooking.phone")}
        hint={t("publicBooking.phoneHint")}
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        required
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
      />
      <TextField
        label={t("publicBooking.email")}
        type="email"
        inputMode="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <CheckboxField
        label={t("publicBooking.consentService", { salon: tenant.name })}
        checked={service}
        onChange={setService}
      />
      <CheckboxField
        label={t("publicBooking.consentReminders")}
        checked={reminders}
        onChange={setReminders}
      />
      <CheckboxField
        label={t("publicBooking.consentMarketing")}
        checked={marketing}
        onChange={setMarketing}
      />
      <p className="mb-2 text-sm text-slate-600">
        <Link
          to={salonPath.privacy(tenant.slug)}
          className="font-medium text-brand-700 underline"
        >
          {t("publicBooking.privacyLink")}
        </Link>{" "}
        <span className="text-slate-400">
          ({t("publicBooking.policyVersion", { version: policyVersion })})
        </span>
      </p>
      {turnstile.widget}
      <SubmitButton
        busy={book.isPending}
        disabled={!service || !name.trim() || !phone.trim() || !turnstile.ready}
      >
        {t("publicBooking.confirm")}
      </SubmitButton>
    </form>
  );
}

function Done({
  confirmation,
  display,
  onAgain,
}: {
  confirmation: BookingConfirmation;
  display: string;
  onAgain: () => void;
}) {
  const { t } = useTranslation();
  const tenant = useCurrentTenant();
  return (
    <div
      role="status"
      className="rounded-xl bg-emerald-50 px-4 py-4 text-emerald-900"
    >
      <h2 className="text-lg font-semibold">{t("publicBooking.doneTitle")}</h2>
      <p className="mt-2">
        {t("publicBooking.doneText", {
          service: confirmation.offering_name,
          provider: confirmation.provider_name,
          day: dayLabel(
            localDate(confirmation.starts_at, tenant.timezone),
            display,
          ),
          time: timeLabel(confirmation.starts_at, tenant.timezone, display),
        })}
      </p>
      <button
        type="button"
        onClick={onAgain}
        className="mt-4 font-medium text-emerald-800 underline"
      >
        {t("publicBooking.again")}
      </button>
    </div>
  );
}

import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { BookingFlow } from "../../core/pages/booking/BookingFlow";
import { WhatsAppContact } from "../../core/pages/booking/WhatsAppContact";
import { formatLocale, formatMoney } from "../../core/i18n/format";
import { useCurrentTenant } from "../../core/pages/TenantLayout";

/** Página pública do salão: serviços com preço e agendamento online (SAL-11). */
export function PublicHomePage() {
  const { t, i18n } = useTranslation();
  const tenant = useCurrentTenant();
  const display = formatLocale(i18n.language, tenant.country);

  useEffect(() => {
    document.title = t("salon.publicTitle", { salon: tenant.name });
  }, [t, tenant.name]);

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-bold text-brand-900">{tenant.name}</h1>
      <p className="mb-6 mt-1 text-slate-600">{t("salon.publicIntro")}</p>
      <WhatsAppContact />
      <BookingFlow
        offeringDetail={(o) =>
          typeof o.extras?.price_minor === "number"
            ? formatMoney(o.extras?.price_minor, tenant.currency, display)
            : null
        }
      />
      <Link
        to="login"
        className="mt-8 inline-block text-sm text-slate-500 underline"
      >
        {t("auth.staffLogin")}
      </Link>
    </section>
  );
}

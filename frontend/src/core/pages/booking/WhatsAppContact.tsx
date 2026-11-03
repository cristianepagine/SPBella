import { useTranslation } from "react-i18next";

import { useBookingCatalog } from "../../api/booking";
import { whatsappLink } from "../../whatsapp";
import { useCurrentTenant } from "../TenantLayout";

/** Botão "falar no WhatsApp" da página pública. Só aparece se o dono cadastrou o número. */
export function WhatsAppContact() {
  const { t } = useTranslation();
  const tenant = useCurrentTenant();
  const phone = useBookingCatalog(tenant.slug).data?.whatsapp_phone;

  if (!phone) return null;
  return (
    <a
      href={whatsappLink(t("publicBooking.whatsappMessage", { salon: tenant.name }), phone)}
      target="_blank"
      rel="noreferrer"
      className="mb-6 block rounded-xl border border-emerald-600 px-4 py-3 text-center font-medium text-emerald-800"
    >
      {t("publicBooking.whatsappButton")}
    </a>
  );
}

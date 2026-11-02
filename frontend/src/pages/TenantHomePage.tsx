import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useCurrentTenant } from "./TenantLayout";

export function TenantHomePage() {
  const { t } = useTranslation();
  const tenant = useCurrentTenant();

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-bold text-brand-900">{tenant.name}</h1>
      <p className="mt-2 text-slate-600">{t("tenant.comingSoon")}</p>
      <Link to="login" className="mt-6 inline-block font-medium text-brand-700 underline">
        {t("auth.staffLogin")}
      </Link>
    </section>
  );
}

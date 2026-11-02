import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";

import { ApiError } from "../api/client";
import { useTenant } from "../api/tenant";
import { applySalonLanguage } from "../i18n";

export function TenantHomePage() {
  const { slug = "" } = useParams();
  const { t } = useTranslation();
  const tenant = useTenant(slug);

  useEffect(() => {
    if (tenant.data) applySalonLanguage(tenant.data.locale);
  }, [tenant.data]);

  if (tenant.isPending) {
    return <p role="status">{t("tenant.loading")}</p>;
  }

  if (tenant.isError) {
    const code = tenant.error instanceof ApiError ? tenant.error.code : "unknown";
    return (
      <section className="rounded-2xl bg-white p-6 text-center shadow-sm" role="alert">
        <p className="font-medium">{t(`errors.${code}`, { defaultValue: t("errors.unknown") })}</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-bold text-brand-900">{tenant.data.name}</h1>
      <p className="mt-2 text-slate-600">{t("tenant.comingSoon")}</p>
    </section>
  );
}

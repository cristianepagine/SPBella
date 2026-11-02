import { createContext, useContext, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Outlet, useParams } from "react-router";

import { ApiError } from "../api/client";
import type { components } from "../api/schema";
import { useTenant } from "../api/tenant";
import { AuthProvider } from "../auth/AuthProvider";
import { applySalonLanguage } from "../i18n";

type Tenant = components["schemas"]["TenantPublicInfo"];

/** Carrega o salão do slug da URL e oferece login para as páginas dentro dele. */
export function TenantLayout() {
  const { slug = "" } = useParams();
  const { t } = useTranslation();
  const tenant = useTenant(slug);

  useEffect(() => {
    if (tenant.data) applySalonLanguage(tenant.data.locale);
  }, [tenant.data]);

  if (tenant.isPending) return <p role="status">{t("tenant.loading")}</p>;

  if (tenant.isError) {
    const code = tenant.error instanceof ApiError ? tenant.error.code : "unknown";
    return (
      <section className="rounded-2xl bg-white p-6 text-center shadow-sm" role="alert">
        <p className="font-medium">{t(`errors.${code}`, { defaultValue: t("errors.unknown") })}</p>
      </section>
    );
  }

  return (
    <TenantContext.Provider value={tenant.data}>
      <AuthProvider slug={slug}>
        <Outlet />
      </AuthProvider>
    </TenantContext.Provider>
  );
}

// Contexto React (e não o do Outlet, que não atravessa as rotas de proteção intermediárias).
const TenantContext = createContext<Tenant | null>(null);

export function useCurrentTenant(): Tenant {
  const tenant = useContext(TenantContext);
  if (!tenant) throw new Error("useCurrentTenant fora do TenantLayout");
  return tenant;
}

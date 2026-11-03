import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Card } from "../components/form";
import { salonPath } from "../paths";
import { useCurrentTenant } from "./TenantLayout";

const SECTIONS = ["who", "what", "why", "share", "keep", "rights"] as const;

/** Política de privacidade da página pública. O estabelecimento é o controlador dos dados. */
export function PrivacyPage() {
  const { t } = useTranslation();
  const tenant = useCurrentTenant();

  return (
    <Card title={t("privacy.title")}>
      {SECTIONS.map((section) => (
        <section key={section} className="mb-4">
          <h2 className="mb-1 font-semibold text-brand-900">
            {t(`privacy.${section}Title`)}
          </h2>
          <p className="text-slate-700">
            {t(`privacy.${section}`, { salon: tenant.name })}
          </p>
        </section>
      ))}
      <Link
        to={salonPath.home(tenant.slug)}
        className="font-medium text-brand-700 underline"
      >
        {t("privacy.back")}
      </Link>
    </Card>
  );
}

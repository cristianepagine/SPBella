import { useTranslation } from "react-i18next";
import { Link, Outlet } from "react-router";

import { salonPath } from "../paths";
import { useAuth } from "./AuthProvider";
import { type Permission, useCan } from "./permissions";

/** Área que exige uma permissão. Quem não tem vê um aviso (o servidor também responde 403). */
export function RequirePermission({ permission }: { permission: Permission }) {
  const can = useCan();
  return can(permission) ? <Outlet /> : <ForbiddenPage />;
}

export function ForbiddenPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  return (
    <section className="rounded-2xl bg-white p-6 text-center shadow-sm" role="alert">
      <h1 className="text-xl font-bold">{t("forbidden.title")}</h1>
      <p className="mt-2 text-slate-600">{t("forbidden.text")}</p>
      <Link to={salonPath.app(slug)} className="mt-4 inline-block font-medium text-brand-700 underline">
        {t("forbidden.back")}
      </Link>
    </section>
  );
}

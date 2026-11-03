import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { useAuth } from "../auth/AuthProvider";
import { salonPath } from "../paths";
import { useCurrentTenant } from "./TenantLayout";

/** Primeira tela depois do login. A agenda entra na história 7. */
export function DashboardPage() {
  const { t } = useTranslation();
  const { slug, state, logout } = useAuth();
  const tenant = useCurrentTenant();
  const navigate = useNavigate();

  if (state.status !== "authenticated") return null;

  async function signOut() {
    await logout();
    navigate(salonPath.login(slug), { replace: true });
  }

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm">
      <p className="text-sm text-slate-500">{tenant.name}</p>
      <h1 className="text-2xl font-bold text-brand-900">
        {t("auth.hello", { name: state.user.name })}
      </h1>
      <p className="mt-2 text-slate-600">{t("auth.dashboardIntro")}</p>
      <div className="mt-6 flex flex-col gap-3">
        <Link
          to={salonPath.changePassword(slug)}
          className="rounded-xl border border-slate-300 px-4 py-3 text-center font-medium"
        >
          {t("auth.changePasswordLink")}
        </Link>
        <button
          type="button"
          onClick={() => void signOut()}
          className="rounded-xl bg-slate-800 px-4 py-3 font-medium text-white"
        >
          {t("auth.logout")}
        </button>
      </div>
    </section>
  );
}

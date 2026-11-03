import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router";

import { useAuth } from "../auth/AuthProvider";
import { useCan } from "../auth/permissions";
import { useCurrentTenant } from "../pages/TenantLayout";
import { salonPath } from "../paths";
import { NavContext, type NavItem } from "./nav";

/** Moldura das telas da equipe: nome do salão, quem está logado, menu do perfil e "Sair". */
export function StaffLayout({ nav }: { nav: NavItem[] }) {
  const { t } = useTranslation();
  const { slug, state, logout } = useAuth();
  const tenant = useCurrentTenant();
  const can = useCan();
  const navigate = useNavigate();

  if (state.status !== "authenticated") return null;
  const items = nav
    .filter((item) => !item.permission || can(item.permission))
    .sort((a, b) => a.order - b.order);

  async function signOut() {
    await logout();
    navigate(salonPath.login(slug), { replace: true });
  }

  return (
    <NavContext.Provider value={items}>
      <header className="mb-4 rounded-2xl bg-white p-4 shadow-sm print:hidden">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-bold text-brand-900">{tenant.name}</p>
            <p className="truncate text-sm text-slate-500">
              {state.user.name} · {t(`roles.${state.user.role}`)}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void signOut()}
            className="shrink-0 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium"
          >
            {t("auth.logout")}
          </button>
        </div>
        <nav aria-label={t("nav.label")} className="-mx-1 mt-3 flex gap-2 overflow-x-auto px-1">
          {items.map((item) => (
            <NavLink
              key={item.id}
              to={item.to(slug)}
              end={item.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium ${
                  isActive ? "bg-brand-700 text-white" : "bg-brand-50 text-brand-900"
                }`
              }
            >
              {t(item.labelKey)}
            </NavLink>
          ))}
        </nav>
      </header>
      <Outlet />
    </NavContext.Provider>
  );
}

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useAuth } from "../../auth/AuthProvider";
import { useNavItems } from "../../layout/nav";
import { salonPath } from "../../paths";

/** Início da equipe: cada perfil vê a sua apresentação e os atalhos que pode usar. */
export function StaffHomePage() {
  const { t } = useTranslation();
  const { slug, state } = useAuth();
  const shortcuts = useNavItems().filter((item) => item.id !== "home");

  if (state.status !== "authenticated") return null;

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-bold text-brand-900">
        {t("auth.hello", { name: state.user.name })}
      </h1>
      <p className="mt-2 text-slate-600">{t(`home.intro.${state.user.role}`)}</p>

      {shortcuts.length > 0 && (
        <ul className="mt-6 grid gap-3">
          {shortcuts.map((item) => (
            <li key={item.id}>
              <Link
                to={item.to(slug)}
                className="block rounded-xl border border-slate-200 px-4 py-3 font-medium"
              >
                {t(item.labelKey)}
              </Link>
            </li>
          ))}
        </ul>
      )}

      <Link
        to={salonPath.changePassword(slug)}
        className="mt-6 inline-block text-sm font-medium text-brand-700 underline"
      >
        {t("auth.changePasswordLink")}
      </Link>
    </section>
  );
}

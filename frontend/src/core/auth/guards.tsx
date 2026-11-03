import { useTranslation } from "react-i18next";
import { Navigate, Outlet, useLocation } from "react-router";

import { salonPath } from "../paths";
import { useAuth } from "./AuthProvider";

/** Exige login. Deixa passar quem ainda precisa trocar a senha provisória. */
export function RequireLogin() {
  const { slug, state } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();

  if (state.status === "loading") return <p role="status">{t("auth.loading")}</p>;
  if (state.status === "anonymous") {
    return <Navigate to={salonPath.login(slug)} replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

/** Exige login E senha provisória já trocada (o back-end também barra, com 403). */
export function RequireFullAccess() {
  const { slug, state } = useAuth();
  if (state.status === "authenticated" && state.user.must_change_password) {
    return <Navigate to={salonPath.changePassword(slug)} replace />;
  }
  return <Outlet />;
}

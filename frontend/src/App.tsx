import { Route, Routes } from "react-router";

import { RequireFullAccess, RequireLogin } from "./core/auth/guards";
import { RequirePermission } from "./core/auth/RequirePermission";
import { LanguageSwitcher } from "./core/components/LanguageSwitcher";
import { CORE_NAV, type NavItem } from "./core/layout/nav";
import { StaffLayout } from "./core/layout/StaffLayout";
import { StaffHomePage } from "./core/pages/app/HomePage";
import { TeamPage } from "./core/pages/app/TeamPage";
import { ChangePasswordPage } from "./core/pages/auth/ChangePasswordPage";
import { ForgotPasswordPage } from "./core/pages/auth/ForgotPasswordPage";
import { LoginPage } from "./core/pages/auth/LoginPage";
import { ResetPasswordPage } from "./core/pages/auth/ResetPasswordPage";
import { HomePage } from "./core/pages/HomePage";
import { NotFoundPage } from "./core/pages/NotFoundPage";
import { TenantLayout } from "./core/pages/TenantLayout";
import { PublicHomePage } from "./salon/pages/PublicHomePage";

/** Menu da equipe: itens do core + os da vertical (serviços, agenda... nas próximas histórias). */
const NAV: NavItem[] = [...CORE_NAV];

/** Composição: rotas do core + páginas da vertical (salão). */
export function App() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col px-4 py-4 md:max-w-3xl">
      <header className="mb-4 flex justify-end">
        <LanguageSwitcher />
      </header>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/:slug" element={<TenantLayout />}>
            <Route index element={<PublicHomePage />} />
            <Route path="login" element={<LoginPage />} />
            <Route path="forgot-password" element={<ForgotPasswordPage />} />
            <Route path="reset-password" element={<ResetPasswordPage />} />
            <Route element={<RequireLogin />}>
              <Route path="change-password" element={<ChangePasswordPage />} />
              <Route element={<RequireFullAccess />}>
                <Route path="app" element={<StaffLayout nav={NAV} />}>
                  <Route index element={<StaffHomePage />} />
                  <Route element={<RequirePermission permission="team.manage" />}>
                    <Route path="team" element={<TeamPage />} />
                  </Route>
                  <Route path="*" element={<NotFoundPage />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  );
}

import { Route, Routes } from "react-router";

import { RequireFullAccess, RequireLogin } from "./core/auth/guards";
import { LanguageSwitcher } from "./core/components/LanguageSwitcher";
import { ChangePasswordPage } from "./core/pages/auth/ChangePasswordPage";
import { ForgotPasswordPage } from "./core/pages/auth/ForgotPasswordPage";
import { LoginPage } from "./core/pages/auth/LoginPage";
import { ResetPasswordPage } from "./core/pages/auth/ResetPasswordPage";
import { DashboardPage } from "./core/pages/DashboardPage";
import { HomePage } from "./core/pages/HomePage";
import { NotFoundPage } from "./core/pages/NotFoundPage";
import { TenantLayout } from "./core/pages/TenantLayout";
import { PublicHomePage } from "./salon/pages/PublicHomePage";

/** Composição: rotas do core + páginas da vertical (salão). */
export function App() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col px-4 py-4">
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
                <Route path="app" element={<DashboardPage />} />
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

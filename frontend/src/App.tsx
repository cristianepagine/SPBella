import { Route, Routes } from "react-router";

import { RequireFullAccess, RequireLogin } from "./auth/guards";
import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { ChangePasswordPage } from "./pages/auth/ChangePasswordPage";
import { ForgotPasswordPage } from "./pages/auth/ForgotPasswordPage";
import { LoginPage } from "./pages/auth/LoginPage";
import { ResetPasswordPage } from "./pages/auth/ResetPasswordPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { TenantHomePage } from "./pages/TenantHomePage";
import { TenantLayout } from "./pages/TenantLayout";

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
            <Route index element={<TenantHomePage />} />
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

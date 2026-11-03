import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { Route, Routes } from "react-router";

import { RequireFullAccess, RequireLogin } from "./core/auth/guards";
import { RequirePermission } from "./core/auth/RequirePermission";
import { LanguageSwitcher } from "./core/components/LanguageSwitcher";
import { CORE_NAV, type NavItem } from "./core/layout/nav";
import { ChangePasswordPage } from "./core/pages/auth/ChangePasswordPage";
import { ForgotPasswordPage } from "./core/pages/auth/ForgotPasswordPage";
import { LoginPage } from "./core/pages/auth/LoginPage";
import { ResetPasswordPage } from "./core/pages/auth/ResetPasswordPage";
import { HomePage } from "./core/pages/HomePage";
import { NotFoundPage } from "./core/pages/NotFoundPage";
import { PrivacyPage } from "./core/pages/PrivacyPage";
import { TenantLayout } from "./core/pages/TenantLayout";
import { SALON_NAV } from "./spbella/nav";
import { PublicHomePage } from "./spbella/pages/PublicHomePage";

// Área da equipe em pedaços separados: a página pública (o que o cliente abre no 4G) não baixa
// o código da agenda, dos clientes etc.
const StaffLayout = lazy(() => import("./core/layout/StaffLayout").then((m) => ({ default: m.StaffLayout })));
const CustomerPage = lazy(() => import("./core/pages/app/customers/CustomerPage").then((m) => ({ default: m.CustomerPage })));
const CustomersPage = lazy(() => import("./core/pages/app/customers/CustomersPage").then((m) => ({ default: m.CustomersPage })));
const NewCustomerPage = lazy(() => import("./core/pages/app/customers/NewCustomerPage").then((m) => ({ default: m.NewCustomerPage })));
const AgendaPage = lazy(() => import("./core/pages/app/agenda/AgendaPage").then((m) => ({ default: m.AgendaPage })));
const StaffHomePage = lazy(() => import("./core/pages/app/HomePage").then((m) => ({ default: m.StaffHomePage })));
const ProviderPage = lazy(() => import("./core/pages/app/providers/ProviderPage").then((m) => ({ default: m.ProviderPage })));
const ProvidersPage = lazy(() => import("./core/pages/app/providers/ProvidersPage").then((m) => ({ default: m.ProvidersPage })));
const SettingsPage = lazy(() => import("./core/pages/app/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const TeamPage = lazy(() => import("./core/pages/app/TeamPage").then((m) => ({ default: m.TeamPage })));
const ServicesPage = lazy(() => import("./spbella/pages/ServicesPage").then((m) => ({ default: m.ServicesPage })));

/** Menu da equipe: itens do core + os da vertical (serviços, agenda... nas próximas histórias). */
const NAV: NavItem[] = [...CORE_NAV, ...SALON_NAV];

/** Composição: rotas do core + páginas da vertical (salão). */
export function App() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col px-4 py-4 md:max-w-3xl">
      <header className="mb-4 flex justify-end">
        <LanguageSwitcher />
      </header>
      <main className="flex-1">
        <Suspense fallback={<p role="status">{t("auth.loading")}</p>}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/:slug" element={<TenantLayout />}>
              <Route index element={<PublicHomePage />} />
              <Route path="privacy" element={<PrivacyPage />} />
              <Route path="login" element={<LoginPage />} />
              <Route path="forgot-password" element={<ForgotPasswordPage />} />
              <Route path="reset-password" element={<ResetPasswordPage />} />
              <Route element={<RequireLogin />}>
                <Route path="change-password" element={<ChangePasswordPage />} />
                <Route element={<RequireFullAccess />}>
                  <Route path="app" element={<StaffLayout nav={NAV} />}>
                    <Route index element={<StaffHomePage />} />
                    <Route element={<RequirePermission permission="agenda.view_own" />}>
                      <Route path="agenda" element={<AgendaPage />} />
                    </Route>
                    <Route element={<RequirePermission permission="customers.manage" />}>
                      <Route path="customers" element={<CustomersPage />} />
                      <Route path="customers/new" element={<NewCustomerPage />} />
                      <Route path="customers/:customerId" element={<CustomerPage />} />
                    </Route>
                    <Route element={<RequirePermission permission="catalog.manage" />}>
                      <Route path="services" element={<ServicesPage />} />
                    </Route>
                    <Route element={<RequirePermission permission="providers.manage" />}>
                      <Route path="providers" element={<ProvidersPage />} />
                      <Route path="providers/:providerId" element={<ProviderPage />} />
                    </Route>
                    <Route element={<RequirePermission permission="team.manage" />}>
                      <Route path="team" element={<TeamPage />} />
                    </Route>
                    <Route element={<RequirePermission permission="settings.manage" />}>
                      <Route path="settings" element={<SettingsPage />} />
                    </Route>
                    <Route path="*" element={<NotFoundPage />} />
                  </Route>
                </Route>
              </Route>
              <Route path="*" element={<NotFoundPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

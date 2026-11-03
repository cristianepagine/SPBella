import { Route, Routes } from "react-router";

import { RequireFullAccess, RequireLogin } from "./core/auth/guards";
import { RequirePermission } from "./core/auth/RequirePermission";
import { LanguageSwitcher } from "./core/components/LanguageSwitcher";
import { CORE_NAV, type NavItem } from "./core/layout/nav";
import { StaffLayout } from "./core/layout/StaffLayout";
import { CustomerPage } from "./core/pages/app/customers/CustomerPage";
import { CustomersPage } from "./core/pages/app/customers/CustomersPage";
import { NewCustomerPage } from "./core/pages/app/customers/NewCustomerPage";
import { AgendaPage } from "./core/pages/app/agenda/AgendaPage";
import { StaffHomePage } from "./core/pages/app/HomePage";
import { ProviderPage } from "./core/pages/app/providers/ProviderPage";
import { ProvidersPage } from "./core/pages/app/providers/ProvidersPage";
import { SettingsPage } from "./core/pages/app/SettingsPage";
import { TeamPage } from "./core/pages/app/TeamPage";
import { ChangePasswordPage } from "./core/pages/auth/ChangePasswordPage";
import { ForgotPasswordPage } from "./core/pages/auth/ForgotPasswordPage";
import { LoginPage } from "./core/pages/auth/LoginPage";
import { ResetPasswordPage } from "./core/pages/auth/ResetPasswordPage";
import { HomePage } from "./core/pages/HomePage";
import { NotFoundPage } from "./core/pages/NotFoundPage";
import { TenantLayout } from "./core/pages/TenantLayout";
import { SALON_NAV } from "./salon/nav";
import { PublicHomePage } from "./salon/pages/PublicHomePage";
import { ServicesPage } from "./salon/pages/ServicesPage";

/** Menu da equipe: itens do core + os da vertical (serviços, agenda... nas próximas histórias). */
const NAV: NavItem[] = [...CORE_NAV, ...SALON_NAV];

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
      </main>
    </div>
  );
}

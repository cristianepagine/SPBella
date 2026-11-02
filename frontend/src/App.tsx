import { Route, Routes } from "react-router";

import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { TenantHomePage } from "./pages/TenantHomePage";

export function App() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col px-4 py-4">
      <header className="mb-4 flex justify-end">
        <LanguageSwitcher />
      </header>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/:slug" element={<TenantHomePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  );
}

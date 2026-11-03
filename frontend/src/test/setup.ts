import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { setupI18n } from "../core/i18n";
import { salonLocales } from "../salon/locales";

setupI18n(salonLocales);

afterEach(() => {
  cleanup();
});

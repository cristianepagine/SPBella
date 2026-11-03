import "@testing-library/jest-dom/vitest";

import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

import { setupI18n } from "../core/i18n";
import { salonLocales } from "../spbella/locales";

setupI18n(salonLocales);

// A área da equipe carrega sob demanda (React.lazy): no primeiro uso, o módulo leva um tempo.
configure({ asyncUtilTimeout: 3000 });

afterEach(() => {
  cleanup();
});

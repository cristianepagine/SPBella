import { expect, it } from "vitest";

// Conteúdo de todos os arquivos do core (o Vite lê como texto).
const sources = import.meta.glob<string>("./**/*.{ts,tsx}", {
  query: "?raw",
  import: "default",
  eager: true,
});

const IMPORTS_A_VERTICAL = /(from|import)\s+["'][^"']*\bsalon\//;

it("o core não importa nada de uma vertical (é o template dos próximos sistemas)", () => {
  const offenders = Object.entries(sources)
    .filter(([, source]) => IMPORTS_A_VERTICAL.test(source))
    .map(([path]) => path);

  expect(offenders).toEqual([]);
});

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../../../App";
import { json, mockApi, salon, session } from "../../../test/api";
import { renderWithProviders } from "../../../test/render";
import { resetSessions } from "../../auth/session";
import i18n, { changeLanguage, clearLanguagePreference } from "../../i18n";

afterEach(() => {
  vi.restoreAllMocks();
  resetSessions();
  clearLanguagePreference();
  changeLanguage("pt-BR");
  clearLanguagePreference();
});

const settings = (overrides = {}) => ({
  name: "Studio Alpha",
  locale: "pt-BR",
  timezone: "America/Sao_Paulo",
  currency: "BRL",
  country: "BR",
  timezone_options: ["America/Sao_Paulo", "America/Manaus"],
  ...overrides,
});

const asOwner = (extra = {}, user = {}) => ({
  "GET /t/alpha": json(salon()),
  "POST /t/alpha/auth/refresh": json(session(user)),
  ...extra,
});

describe("configurações do salão", () => {
  it("salva nome, idioma padrão e fuso", async () => {
    const requests = mockApi(
      asOwner({
        "GET /t/alpha/settings": json(settings()),
        "PATCH /t/alpha/settings": async (request: Request) =>
          json(settings(await request.json())),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/settings" });

    const name = await screen.findByLabelText("Nome do salão");
    await userEvent.clear(name);
    await userEvent.type(name, "Studio Alpha Centro");
    await userEvent.selectOptions(screen.getByLabelText("Idioma padrão"), "es");
    await userEvent.selectOptions(screen.getByLabelText("Fuso horário da agenda"), "America/Manaus");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(await screen.findByText("Pronto! As configurações foram salvas.")).toBeInTheDocument();
    const patch = requests.find((r) => r.method === "PATCH")!;
    expect(await patch.json()).toEqual({
      name: "Studio Alpha Centro",
      locale: "es",
      timezone: "America/Manaus",
    });
  });

  it("mostra a moeda sem deixar mudar, com exemplo de preço no formato do país", async () => {
    mockApi(
      asOwner({
        "GET /t/alpha": json(salon({ country: "PY", currency: "PYG", locale: "es" })),
        "GET /t/alpha/settings": json(
          settings({ currency: "PYG", country: "PY", timezone: "America/Asuncion",
            timezone_options: ["America/Asuncion"] }),  // prettier-ignore
        ),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/settings" });

    expect(await screen.findByText("Guaraní (Gs.)")).toBeInTheDocument(); // salão em espanhol
    expect(screen.queryByLabelText("Moneda")).toBeNull(); // não é um campo editável
    expect(screen.getByText(/Ejemplo: un servicio de Gs\.\s150\.000/)).toBeInTheDocument();
  });

  it("aparece no menu só para quem pode", async () => {
    mockApi(asOwner({}, { role: "reception" }));

    renderWithProviders(<App />, { route: "/alpha/app" });

    const nav = await screen.findByRole("navigation", { name: "Menu" });
    expect(within(nav).queryByRole("link", { name: "Configurações" })).toBeNull();
  });
});

describe("idioma de cada pessoa", () => {
  it("troca na hora, sem recarregar, e salva na conta", async () => {
    const requests = mockApi(
      asOwner({
        "PATCH /t/alpha/auth/me": async (request: Request) =>
          json({ ...session().user, ...(await request.json()) }),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app" });
    const nav = await screen.findByRole("navigation", { name: "Menu" });
    expect(within(nav).getByRole("link", { name: "Equipe" })).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Idioma"), "es");

    expect(await within(nav).findByRole("link", { name: "Equipo" })).toBeInTheDocument();
    const saved = requests.find((r) => r.method === "PATCH" && r.url.endsWith("/auth/me"))!;
    expect(await saved.json()).toEqual({ locale: "es" });
    // sem recarregar: o salão e a sessão foram buscados uma única vez
    expect(requests.filter((r) => r.url.endsWith("/t/alpha"))).toHaveLength(1);
    expect(requests.filter((r) => r.url.endsWith("/auth/refresh"))).toHaveLength(1);
  });

  it("usa o idioma salvo na conta ao entrar, em qualquer aparelho", async () => {
    mockApi(asOwner({}, { locale: "es" }));

    renderWithProviders(<App />, { route: "/alpha/app" });

    const nav = await screen.findByRole("navigation", { name: "Menú" });
    expect(within(nav).getByRole("link", { name: "Equipo" })).toBeInTheDocument();
    expect(i18n.language).toBe("es");
  });
});

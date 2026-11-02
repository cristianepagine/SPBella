import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { changeLanguage, clearLanguagePreference } from "./i18n";
import { renderWithProviders } from "./test/render";

function mockFetch(response: Response | Error) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
    if (response instanceof Error) throw response;
    return response.clone();
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  changeLanguage("pt-BR");
});

describe("tela inicial", () => {
  it("mostra que o sistema está funcionando quando a API responde", async () => {
    mockFetch(Response.json({ status: "ok", version: "0.1.0" }));

    renderWithProviders(<App />);

    expect(await screen.findByText("Tudo certo! O sistema está funcionando.")).toBeInTheDocument();
    expect(screen.getByText("Versão 0.1.0")).toBeInTheDocument();
  });

  it("explica em linguagem simples quando não há conexão", async () => {
    mockFetch(new TypeError("Failed to fetch"));

    renderWithProviders(<App />);

    expect(await screen.findByText(/Não conseguimos falar com o servidor/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });

  it("troca para espanhol", async () => {
    mockFetch(Response.json({ status: "ok", version: "0.1.0" }));
    renderWithProviders(<App />);

    await userEvent.selectOptions(screen.getByLabelText("Idioma"), "es");

    expect(await screen.findByText("¡Todo bien! El sistema está funcionando.")).toBeInTheDocument();
  });

  it("mostra página não encontrada", () => {
    mockFetch(Response.json({ status: "ok", version: "0.1.0" }));

    renderWithProviders(<App />, { route: "/a/b/c" });

    expect(screen.getByText("Página não encontrada")).toBeInTheDocument();
  });
});

const salon = (overrides = {}) => ({
  slug: "salon-asuncion",
  name: "Salón Asunción",
  country: "PY",
  locale: "es",
  timezone: "America/Asuncion",
  currency: "PYG",
  ...overrides,
});

describe("página do salão", () => {
  afterEach(() => clearLanguagePreference());

  it("mostra o nome do salão", async () => {
    mockFetch(Response.json(salon({ locale: "pt-BR", name: "Studio Bella" })));

    renderWithProviders(<App />, { route: "/studio-bella" });

    expect(await screen.findByRole("heading", { name: "Studio Bella" })).toBeInTheDocument();
  });

  it("usa o idioma do salão quando o usuário nunca escolheu um", async () => {
    clearLanguagePreference();
    mockFetch(Response.json(salon()));

    renderWithProviders(<App />, { route: "/salon-asuncion" });

    expect(await screen.findByText(/Muy pronto vas a poder reservar/)).toBeInTheDocument();
  });

  it("respeita o idioma escolhido pelo usuário", async () => {
    changeLanguage("pt-BR");
    mockFetch(Response.json(salon()));

    renderWithProviders(<App />, { route: "/salon-asuncion" });

    expect(await screen.findByRole("heading", { name: "Salón Asunción" })).toBeInTheDocument();
    expect(screen.getByText(/Em breve você vai poder marcar/)).toBeInTheDocument();
  });

  it("explica quando o salão não existe", async () => {
    mockFetch(
      Response.json(
        { error: { code: "tenant_not_found", message: "Salão não encontrado" } },
        { status: 404 },
      ),
    );

    renderWithProviders(<App />, { route: "/nao-existe" });

    expect(await screen.findByText(/Não encontramos esse salão/)).toBeInTheDocument();
  });
});

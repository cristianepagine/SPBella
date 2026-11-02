import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { resetSessions } from "./auth/session";
import { changeLanguage, clearLanguagePreference } from "./i18n";
import { apiError, json, mockApi, salon } from "./test/api";
import { renderWithProviders } from "./test/render";

afterEach(() => {
  vi.restoreAllMocks();
  resetSessions();
  changeLanguage("pt-BR");
});

describe("tela inicial", () => {
  it("mostra que o sistema está funcionando quando a API responde", async () => {
    mockApi({ "GET /health": json({ status: "ok", version: "0.3.0" }) });

    renderWithProviders(<App />);

    expect(await screen.findByText("Tudo certo! O sistema está funcionando.")).toBeInTheDocument();
    expect(screen.getByText("Versão 0.3.0")).toBeInTheDocument();
  });

  it("explica em linguagem simples quando não há conexão", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    renderWithProviders(<App />);

    expect(await screen.findByText(/Não conseguimos falar com o servidor/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });

  it("troca para espanhol", async () => {
    mockApi({ "GET /health": json({ status: "ok", version: "0.3.0" }) });
    renderWithProviders(<App />);

    await userEvent.selectOptions(screen.getByLabelText("Idioma"), "es");

    expect(await screen.findByText("¡Todo bien! El sistema está funcionando.")).toBeInTheDocument();
  });

  it("mostra página não encontrada", async () => {
    mockApi({
      "GET /t/alpha": json(salon()),
      "POST /t/alpha/auth/refresh": apiError(401, "refresh_invalid"),
    });

    renderWithProviders(<App />, { route: "/alpha/nao-existe" });

    expect(await screen.findByText("Página não encontrada")).toBeInTheDocument();
  });
});

describe("página do salão", () => {
  afterEach(() => clearLanguagePreference());

  const refreshFails = { "POST /t/alpha/auth/refresh": apiError(401, "refresh_invalid") };

  it("mostra o nome do salão e o acesso da equipe", async () => {
    mockApi({ "GET /t/alpha": json(salon()), ...refreshFails });

    renderWithProviders(<App />, { route: "/alpha" });

    expect(await screen.findByRole("heading", { name: "Studio Alpha" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Área do salão: entrar" })).toBeInTheDocument();
  });

  it("usa o idioma do salão quando o usuário nunca escolheu um", async () => {
    clearLanguagePreference();
    mockApi({ "GET /t/alpha": json(salon({ locale: "es", name: "Salón Asunción" })), ...refreshFails });

    renderWithProviders(<App />, { route: "/alpha" });

    expect(await screen.findByText(/Muy pronto vas a poder reservar/)).toBeInTheDocument();
  });

  it("respeita o idioma escolhido pelo usuário", async () => {
    changeLanguage("pt-BR");
    mockApi({ "GET /t/alpha": json(salon({ locale: "es", name: "Salón Asunción" })), ...refreshFails });

    renderWithProviders(<App />, { route: "/alpha" });

    expect(await screen.findByRole("heading", { name: "Salón Asunción" })).toBeInTheDocument();
    expect(screen.getByText(/Em breve você vai poder marcar/)).toBeInTheDocument();
  });

  it("explica quando o salão não existe", async () => {
    mockApi({ "GET /t/nao-existe": apiError(404, "tenant_not_found") });

    renderWithProviders(<App />, { route: "/nao-existe" });

    expect(await screen.findByText(/Não encontramos esse salão/)).toBeInTheDocument();
  });
});

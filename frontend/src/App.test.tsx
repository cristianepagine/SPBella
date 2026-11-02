import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { changeLanguage } from "./i18n";
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

    renderWithProviders(<App />, { route: "/nao-existe" });

    expect(screen.getByText("Página não encontrada")).toBeInTheDocument();
  });
});

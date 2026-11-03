import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import { resetSessions } from "../../core/auth/session";
import { json, mockApi, salon, session } from "../../test/api";
import { renderWithProviders } from "../../test/render";

afterEach(() => {
  vi.restoreAllMocks();
  resetSessions();
});

const service = (overrides = {}) => ({
  id: "55555555-5555-5555-5555-555555555555",
  name: "Corte feminino",
  duration_min: 60,
  price_minor: 8000,
  currency: "BRL",
  is_active: true,
  updated_at: "2026-11-03T12:00:00Z",
  ...overrides,
});

const loggedAs = (role: "owner" | "reception", extra = {}, tenant = salon()) => ({
  "GET /t/alpha": json(tenant),
  "POST /t/alpha/auth/refresh": json(session({ role })),
  ...extra,
});

describe("serviços", () => {
  it("o dono vê os serviços com duração e preço na moeda do salão", async () => {
    mockApi(
      loggedAs("owner", {
        "GET /t/alpha/services": json([service(), service({ id: "2", name: "Barba",
          duration_min: 30, price_minor: 3500, is_active: false })]),  // prettier-ignore
      }),
    );

    renderWithProviders(<App />, { route: "/alpha/app/services" });

    expect(await screen.findByText("Corte feminino")).toBeInTheDocument();
    expect(screen.getByText(/60 min · R\$\s80,00/)).toBeInTheDocument();
    expect(screen.getByText(/Desativado: não aparece para agendar/)).toBeInTheDocument();
  });

  it("no Paraguai, o preço aparece em guaranis", async () => {
    mockApi(
      loggedAs(
        "owner",
        { "GET /t/alpha/services": json([service({ name: "Corte de dama", price_minor: 80000,
          currency: "PYG" })]) },  // prettier-ignore
        salon({ country: "PY", currency: "PYG", locale: "es" }),
      ),
    );

    renderWithProviders(<App />, { route: "/alpha/app/services" });

    expect(await screen.findByText(/60 min · Gs\.\s80\.000/)).toBeInTheDocument();
  });

  it("cadastra um serviço lendo o preço como a pessoa digita", async () => {
    const requests = mockApi(
      loggedAs("owner", {
        "GET /t/alpha/services": json([]),
        "POST /t/alpha/services": json(service(), 201),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/services" });

    await userEvent.click(await screen.findByRole("button", { name: "Novo serviço" }));
    await userEvent.type(screen.getByLabelText("Nome do serviço"), "Hidratação");
    await userEvent.selectOptions(screen.getByLabelText("Duração"), "45");
    await userEvent.type(screen.getByLabelText("Preço (BRL)"), "75,90");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    const sent = requests.find((r) => r.method === "POST" && r.url.endsWith("/services"))!;
    expect(await sent.json()).toEqual({ name: "Hidratação", duration_min: 45, price_minor: 7590 });
  });

  it("explica quando o preço não é um número", async () => {
    const requests = mockApi(loggedAs("owner", { "GET /t/alpha/services": json([]) }));
    renderWithProviders(<App />, { route: "/alpha/app/services" });

    await userEvent.click(await screen.findByRole("button", { name: "Novo serviço" }));
    await userEvent.type(screen.getByLabelText("Nome do serviço"), "Hidratação");
    await userEvent.type(screen.getByLabelText("Preço (BRL)"), "caro");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/só com números/);
    expect(requests.some((r) => r.method === "POST" && r.url.endsWith("/services"))).toBe(false);
  });

  it("edita mostrando o preço atual para corrigir", async () => {
    const requests = mockApi(
      loggedAs("owner", {
        "GET /t/alpha/services": json([service()]),
        "PATCH /t/alpha/services/55555555-5555-5555-5555-555555555555": json(service()),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/services" });

    await userEvent.click(await screen.findByRole("button", { name: "Editar" }));
    const price = screen.getByLabelText("Preço (BRL)");
    expect(price).toHaveValue("80,00");
    await userEvent.clear(price);
    await userEvent.type(price, "85");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    const patch = requests.find((r) => r.method === "PATCH")!;
    expect(await patch.json()).toEqual({ name: "Corte feminino", duration_min: 60, price_minor: 8500 });
  });

  it("desativa com um toque", async () => {
    const requests = mockApi(
      loggedAs("owner", {
        "GET /t/alpha/services": json([service()]),
        "PATCH /t/alpha/services/55555555-5555-5555-5555-555555555555": json(
          service({ is_active: false }),
        ),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/services" });

    await userEvent.click(await screen.findByRole("button", { name: "Desativar" }));

    const patch = requests.find((r) => r.method === "PATCH")!;
    expect(await patch.json()).toEqual({ is_active: false });
  });

  it("aparece no menu do dono, entre Clientes e Equipe; não aparece para a recepção", async () => {
    mockApi(loggedAs("owner"));
    const { unmount } = renderWithProviders(<App />, { route: "/alpha/app" });

    const nav = await screen.findByRole("navigation", { name: "Menu" });
    expect(within(nav).getAllByRole("link").map((a) => a.textContent)).toEqual([
      "Início", "Clientes", "Serviços", "Equipe", "Configurações",
    ]);  // prettier-ignore
    unmount();
    resetSessions();
    vi.restoreAllMocks();

    mockApi(loggedAs("reception"));
    renderWithProviders(<App />, { route: "/alpha/app" });
    const receptionNav = await screen.findByRole("navigation", { name: "Menu" });
    expect(within(receptionNav).queryByRole("link", { name: "Serviços" })).toBeNull();
  });
});

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../../../App";
import { json, mockApi, salon, session } from "../../../../test/api";
import { renderWithProviders } from "../../../../test/render";
import { resetSessions } from "../../../auth/session";

// "Agora" fixo: terça, 09/03/2027, 12:00 em São Paulo (15:00 UTC).
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2027-03-09T15:00:00Z"));
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  resetSessions();
});

const PAULA = "p1";
const DIEGO = "p2";

const agenda = (overrides = {}) => ({
  start_date: "2027-03-09",
  days: 1,
  timezone: "America/Sao_Paulo",
  scope: "all",
  own_provider_missing: false,
  providers: [
    { id: PAULA, name: "Paula", color: "sky", working_hours: [{ weekday: 1, start: "09:00", end: "18:00" }] },
    { id: DIEGO, name: "Diego", color: "amber", working_hours: [{ weekday: 1, start: "10:00", end: "16:00" }] },
  ],
  appointments: [
    {
      id: "a1", provider_id: PAULA, offering_id: "o1", offering_name: "Corte feminino",
      customer_id: "c1", customer_name: "Maria Oliveira", customer_phone_display: "+55 11 98111-0001",
      starts_at: "2027-03-09T13:00:00Z", ends_at: "2027-03-09T14:00:00Z", status: "confirmed",
      source: "public",
    },
    {
      id: "a2", provider_id: DIEGO, offering_id: "o2", offering_name: "Barba",
      customer_id: "c2", customer_name: "Carlos Mendes", customer_phone_display: "+55 11 98111-0003",
      starts_at: "2027-03-09T17:30:00Z", ends_at: "2027-03-09T18:00:00Z", status: "no_show",
      source: "staff",
    },
  ],
  time_off: [],
  ...overrides,
}); // prettier-ignore

function setup(role: "owner" | "reception" | "professional" = "reception", data = agenda()) {
  return mockApi({
    "GET /t/alpha": json(salon()),
    "POST /t/alpha/auth/refresh": json(session({ role })),
    "GET /t/alpha/agenda": json(data),
  });
}

describe("agenda", () => {
  it("abre no dia de hoje do salão e mostra os horários no fuso dele", async () => {
    const requests = setup();

    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    const list = await screen.findByRole("region", { name: "Agenda em lista" });
    expect(within(list).getByText("10:00–11:00 Maria Oliveira")).toBeInTheDocument(); // 13h UTC
    expect(within(list).getByText(/14:30–15:00 Carlos Mendes/)).toBeInTheDocument();
    const query = new URL(requests.find((r) => r.url.includes("/agenda"))!.url).searchParams;
    expect(query.get("start")).toBe("2027-03-09");
    expect(query.get("days")).toBe("1");
  });

  it("mostra status com cor e texto, e quem marcou pela página", async () => {
    setup();

    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    const list = await screen.findByRole("region", { name: "Agenda em lista" });
    expect(within(list).getByText(/Confirmado · marcado pela página/)).toBeInTheDocument();
    const noShow = within(list).getByText(/Faltou/).closest("button")!;
    expect(noShow.className).toContain("border-red-600");
    expect(screen.getByRole("list", { name: "Legenda" })).toHaveTextContent("Cancelado");
  });

  it("no computador, um profissional por coluna", async () => {
    setup();

    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    const grid = await screen.findByRole("region", { name: "Agenda em colunas" });
    expect(within(grid).getByText("Paula")).toBeInTheDocument();
    expect(within(grid).getByText("Diego")).toBeInTheDocument();
    expect(within(grid).getByText("10:00–11:00 Maria Oliveira")).toBeInTheDocument();
  });

  it("na semana, pede a semana desde a segunda e mostra um dia por coluna", async () => {
    const requests = setup("reception", agenda({ start_date: "2027-03-08", days: 7 }));
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await userEvent.click(await screen.findByRole("button", { name: "Semana" }));

    const grid = await screen.findByRole("region", { name: "Agenda em colunas" });
    expect(within(grid).getByText("seg., 08/03")).toBeInTheDocument();
    expect(within(grid).getByText("dom., 14/03")).toBeInTheDocument();
    const last = new URL(requests.filter((r) => r.url.includes("/agenda")).at(-1)!.url).searchParams;
    expect(last.get("start")).toBe("2027-03-08");
    expect(last.get("days")).toBe("7");
  });

  it("anda para o próximo dia e volta para hoje", async () => {
    const requests = setup();
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await userEvent.click(await screen.findByRole("button", { name: "Próximo" }));
    await userEvent.click(screen.getByRole("button", { name: "Hoje" }));

    const starts = requests
      .filter((r) => r.url.includes("/agenda"))
      .map((r) => new URL(r.url).searchParams.get("start"));
    expect(starts).toEqual(["2027-03-09", "2027-03-10", "2027-03-09"]);
  });

  it("avisa o profissional sem conta ligada", async () => {
    setup("professional", agenda({ scope: "own", own_provider_missing: true, providers: [], appointments: [] }));

    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    expect(await screen.findByRole("alert")).toHaveTextContent(/não está ligada a um profissional/);
  });

  it("o profissional não vê telefone nem o filtro de profissionais", async () => {
    setup(
      "professional",
      agenda({
        scope: "own",
        providers: [agenda().providers[0]],
        appointments: [{ ...agenda().appointments[0], customer_phone_display: null }],
      }),
    );

    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    const list = await screen.findByRole("region", { name: "Agenda em lista" });
    expect(within(list).getByText("10:00–11:00 Maria Oliveira")).toBeInTheDocument();
    expect(screen.queryByText(/98111/)).toBeNull();
    expect(screen.queryByLabelText("Profissional")).toBeNull();
  });

  it("aparece no menu de todos os perfis", async () => {
    setup("professional");

    renderWithProviders(<App />, { route: "/alpha/app" });

    const nav = await screen.findByRole("navigation", { name: "Menu" });
    expect(within(nav).getByRole("link", { name: "Agenda" })).toBeInTheDocument();
  });
});

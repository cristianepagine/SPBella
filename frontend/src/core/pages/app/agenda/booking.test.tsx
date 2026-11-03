import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../../../App";
import { apiError, json, mockApi, salon, session } from "../../../../test/api";
import { renderWithProviders } from "../../../../test/render";
import { resetSessions } from "../../../auth/session";

// "Agora": terça, 09/03/2027, 12:00 em São Paulo (15:00 UTC).
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2027-03-09T15:00:00Z"));
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  resetSessions();
});

const provider = {
  id: "p1", name: "Paula", color: "sky", is_active: true, user_id: null,
  offering_ids: ["o1"], working_hours: [{ weekday: 1, start: "09:00", end: "18:00" }],
}; // prettier-ignore

const appointment = (overrides = {}) => ({
  id: "a1", provider_id: "p1", offering_id: "o1", offering_name: "Corte feminino",
  customer_id: "c1", customer_name: "Maria Oliveira", customer_phone_display: "+55 11 98111-0001",
  starts_at: "2027-03-09T17:00:00Z", ends_at: "2027-03-09T18:00:00Z", status: "scheduled",
  source: "staff", ...overrides,
}); // prettier-ignore

const agenda = (appointments = [appointment()]) => ({
  start_date: "2027-03-09", days: 1, timezone: "America/Sao_Paulo", scope: "all",
  own_provider_missing: false,
  providers: [{ id: "p1", name: "Paula", color: "sky", working_hours: provider.working_hours }],
  appointments, time_off: [],
}); // prettier-ignore

function setup(extra = {}, role: "reception" | "professional" = "reception") {
  return mockApi({
    "GET /t/alpha": json(salon()),
    "POST /t/alpha/auth/refresh": json(session({ role })),
    "GET /t/alpha/agenda": json(agenda()),
    "GET /t/alpha/providers": json([provider]),
    "GET /t/alpha/offerings": json([
      { id: "o1", name: "Corte feminino", duration_min: 60, is_active: true },
    ]),
    "GET /t/alpha/customers": json({
      items: [{ id: "c1", name: "Maria Oliveira", phone: "+5511981110001",
        phone_display: "+55 11 98111-0001" }],  // prettier-ignore
      total: 1,
    }),
    ...extra,
  });
}

async function fillBooking() {
  await userEvent.click(await screen.findByRole("button", { name: "Novo agendamento" }));
  const form = screen.getByRole("heading", { name: "Novo agendamento" }).parentElement!;
  await userEvent.type(within(form).getByLabelText("Cliente"), "maria");
  await userEvent.click(await within(form).findByRole("button", { name: /Maria Oliveira/ }));
  const time = within(form).getByLabelText("Horário");
  await userEvent.clear(time);
  await userEvent.type(time, "10:00");
}

describe("marcar horário", () => {
  it("marca com o horário do salão convertido para UTC", async () => {
    const requests = setup({ "POST /t/alpha/appointments": json(appointment(), 201) });
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await fillBooking();
    await userEvent.click(screen.getByRole("button", { name: "Agendar" }));

    const sent = requests.find((r) => r.method === "POST" && r.url.endsWith("/appointments"))!;
    expect(await sent.json()).toEqual({
      customer_id: "c1",
      provider_id: "p1",
      offering_id: "o1",
      starts_at: "2027-03-09T13:00:00.000Z", // 10:00 em São Paulo
      allow_outside_hours: false,
    });
  });

  it("horário ocupado: explica e não oferece passar por cima", async () => {
    setup({ "POST /t/alpha/appointments": apiError(409, "slot_taken") });
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await fillBooking();
    await userEvent.click(screen.getByRole("button", { name: "Agendar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/já está ocupado/);
    expect(screen.queryByRole("button", { name: /mesmo assim/ })).toBeNull();
  });

  it("fora da jornada: oferece o encaixe e reenvia com permissão", async () => {
    let calls = 0;
    const requests = setup({
      "POST /t/alpha/appointments": () =>
        ++calls === 1 ? apiError(409, "outside_working_hours") : json(appointment(), 201),
    });
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await fillBooking();
    await userEvent.click(screen.getByRole("button", { name: "Agendar" }));
    await userEvent.click(await screen.findByRole("button", { name: "Agendar mesmo assim (encaixe)" }));

    const posts = requests.filter((r) => r.method === "POST" && r.url.endsWith("/appointments"));
    expect((await posts[1].json()).allow_outside_hours).toBe(true);
  });

  it("o profissional não vê o botão de marcar", async () => {
    setup({}, "professional");

    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await screen.findByRole("region", { name: "Agenda em lista" });
    expect(screen.queryByRole("button", { name: "Novo agendamento" })).toBeNull();
  });
});

describe("detalhe do agendamento", () => {
  async function openFirst() {
    const list = await screen.findByRole("region", { name: "Agenda em lista" });
    await userEvent.click(within(list).getByRole("button", { name: /Maria Oliveira/ }));
  }

  it("confirma com um toque; atendido e faltou só depois do horário", async () => {
    const requests = setup({
      "POST /t/alpha/appointments/a1/status": json(appointment({ status: "confirmed" })),
    });
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });
    await openFirst();

    // 14:00 de hoje ainda não chegou (agora é 12:00)
    expect(screen.queryByRole("button", { name: "Faltou" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    const sent = requests.find((r) => r.url.endsWith("/a1/status"))!;
    expect(await sent.json()).toEqual({ status: "confirmed" });
  });

  it("depois do horário, pode marcar falta", async () => {
    setup({ "GET /t/alpha/agenda": json(agenda([appointment({ starts_at: "2027-03-09T13:00:00Z",
      ends_at: "2027-03-09T14:00:00Z" })])) });  // prettier-ignore
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await openFirst();

    expect(screen.getByRole("button", { name: "Faltou" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Atendido" })).toBeInTheDocument();
  });

  it("move para outro horário", async () => {
    const requests = setup({ "PATCH /t/alpha/appointments/a1": json(appointment()) });
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });
    await openFirst();

    await userEvent.click(screen.getByRole("button", { name: "Mover" }));
    const panel = screen.getByRole("heading", { name: "Maria Oliveira" }).parentElement!;
    const time = within(panel).getByLabelText("Horário");
    await userEvent.clear(time);
    await userEvent.type(time, "16:00");
    await userEvent.click(within(panel).getByRole("button", { name: "Salvar novo horário" }));

    const patch = requests.find((r) => r.method === "PATCH")!;
    expect(await patch.json()).toEqual({
      starts_at: "2027-03-09T19:00:00.000Z",
      provider_id: "p1",
      allow_outside_hours: false,
    });
  });

  it("um cancelado pode ser reativado", async () => {
    setup({ "GET /t/alpha/agenda": json(agenda([appointment({ status: "cancelled" })])) });
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await openFirst();

    expect(screen.getByRole("button", { name: "Reativar" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mover" })).toBeNull();
  });
});

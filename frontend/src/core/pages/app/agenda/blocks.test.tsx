import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../../../App";
import { json, mockApi, salon, session } from "../../../../test/api";
import { renderWithProviders } from "../../../../test/render";
import { resetSessions } from "../../../auth/session";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2027-03-09T15:00:00Z")); // terça, 12:00 em São Paulo
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  resetSessions();
});

const providers = [{ id: "p1", name: "Paula", color: "sky", working_hours: [{ weekday: 1, start: "09:00", end: "18:00" }] }];

const agenda = (time_off: unknown[] = []) => ({
  start_date: "2027-03-09", days: 1, timezone: "America/Sao_Paulo", scope: "all",
  own_provider_missing: false, providers, appointments: [], time_off,
}); // prettier-ignore

function setup(extra = {}, role: "owner" | "reception" = "owner", blocks: unknown[] = []) {
  return mockApi({
    "GET /t/alpha": json(salon()),
    "POST /t/alpha/auth/refresh": json(session({ role })),
    "GET /t/alpha/agenda": json(agenda(blocks)),
    ...extra,
  });
}

const created = (conflicts: unknown[] = []) => ({
  id: "b1", provider_id: null, starts_at: "2027-03-10T03:00:00Z", ends_at: "2027-03-11T03:00:00Z",
  reason: "Feriado", conflicts,
}); // prettier-ignore

describe("bloqueios", () => {
  it("bloqueia o salão inteiro por um dia", async () => {
    const requests = setup({ "POST /t/alpha/blocks": json(created(), 201) });
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await userEvent.click(await screen.findByRole("button", { name: "Bloquear horário" }));
    const form = screen.getByRole("heading", { name: "Bloquear horário" }).parentElement!;
    await userEvent.type(within(form).getByLabelText("Motivo (opcional)"), "Feriado");
    await userEvent.click(within(form).getByRole("button", { name: "Bloquear" }));

    const sent = requests.find((r) => r.method === "POST" && r.url.endsWith("/blocks"))!;
    expect(await sent.json()).toEqual({
      provider_id: null, start_date: "2027-03-09", end_date: null, reason: "Feriado",
    }); // prettier-ignore
  });

  it("bloqueia algumas horas de um profissional", async () => {
    const requests = setup({ "POST /t/alpha/blocks": json(created(), 201) });
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await userEvent.click(await screen.findByRole("button", { name: "Bloquear horário" }));
    const form = screen.getByRole("heading", { name: "Bloquear horário" }).parentElement!;
    await userEvent.selectOptions(within(form).getByLabelText("Quem"), "p1");
    await userEvent.selectOptions(within(form).getByLabelText("Tipo"), "hours");
    await userEvent.click(within(form).getByRole("button", { name: "Bloquear" }));

    const sent = requests.find((r) => r.method === "POST" && r.url.endsWith("/blocks"))!;
    expect(await sent.json()).toEqual({
      provider_id: "p1", start_date: "2027-03-09", start_time: "12:00", end_time: "13:00",
      reason: null,
    }); // prettier-ignore
  });

  it("avisa quem já estava marcado, sem cancelar ninguém", async () => {
    setup({
      "POST /t/alpha/blocks": json(
        created([{ appointment_id: "a1", provider_id: "p1", customer_name: "Maria Oliveira",
          starts_at: "2027-03-09T17:00:00Z" }]), 201),  // prettier-ignore
    });
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await userEvent.click(await screen.findByRole("button", { name: "Bloquear horário" }));
    await userEvent.click(screen.getByRole("button", { name: "Bloquear" }));

    const warning = await screen.findByText(/já havia 1 cliente marcado/);
    expect(warning.parentElement).toHaveTextContent("Maria Oliveira · 14:00");
    expect(screen.getByText(/Nada foi cancelado/)).toBeInTheDocument();
  });

  it("mostra o bloqueio na agenda e deixa o dono desbloquear", async () => {
    const requests = setup({ "DELETE /t/alpha/blocks/b2": new Response(null, { status: 204 }) }, "owner", [
      { id: "b2", provider_id: "p1", starts_at: "2027-03-09T17:00:00Z", ends_at: "2027-03-09T19:00:00Z",
        reason: "Médico" },
    ]);  // prettier-ignore
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    const list = await screen.findByRole("region", { name: "Agenda em lista" });
    expect(within(list).getByText(/Folga: Paula · 14:00–16:00 · Médico/)).toBeInTheDocument();
    const grid = screen.getByRole("region", { name: "Agenda em colunas" });
    expect(within(grid).getByText("Médico")).toBeInTheDocument();
    await userEvent.click(within(list).getByRole("button", { name: "Desbloquear" }));

    expect(requests.some((r) => r.method === "DELETE" && r.url.endsWith("/blocks/b2"))).toBe(true);
  });

  it("a recepção não bloqueia", async () => {
    setup({}, "reception");

    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await screen.findByRole("region", { name: "Agenda em lista" });
    expect(screen.queryByRole("button", { name: "Bloquear horário" })).toBeNull();
  });
});

describe("horários livres no agendamento", () => {
  it("mostra os horários livres e escolhe com um toque", async () => {
    setup(
      {
        "GET /t/alpha/providers": json([{ ...providers[0], is_active: true, user_id: null, offering_ids: ["o1"] }]),
        "GET /t/alpha/offerings": json([{ id: "o1", name: "Corte", duration_min: 60, is_active: true }]),
        "GET /t/alpha/availability": json({
          date: "2027-03-09", timezone: "America/Sao_Paulo", offering_id: "o1", duration_min: 60,
          slots: [{ starts_at: "2027-03-09T12:00:00Z", provider_ids: ["p1"] },
                  { starts_at: "2027-03-09T17:30:00Z", provider_ids: ["p1"] }],
        }),
      },
      "reception",
    );  // prettier-ignore
    renderWithProviders(<App />, { route: "/alpha/app/agenda" });

    await userEvent.click(await screen.findByRole("button", { name: "Novo agendamento" }));
    const form = screen.getByRole("heading", { name: "Novo agendamento" }).parentElement!;
    await userEvent.click(await within(form).findByRole("button", { name: "14:30" }));

    expect(within(form).getByLabelText("Horário")).toHaveValue("14:30");
    expect(within(form).getByRole("button", { name: "09:00" })).toHaveAttribute("aria-pressed", "false");
  });
});

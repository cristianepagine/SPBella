import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../../../../App";
import { json, mockApi, salon, session } from "../../../../test/api";
import { renderWithProviders } from "../../../../test/render";
import { resetSessions } from "../../../auth/session";

afterEach(() => {
  vi.restoreAllMocks();
  resetSessions();
});

const ID = "66666666-6666-6666-6666-666666666666";
const CORTE = "77777777-7777-7777-7777-777777777771";
const BARBA = "77777777-7777-7777-7777-777777777772";

const provider = (overrides = {}) => ({
  id: ID,
  name: "Paula Souza",
  color: "sky",
  is_active: true,
  user_id: null,
  offering_ids: [CORTE],
  working_hours: [
    { weekday: 1, start: "09:00", end: "12:00" },
    { weekday: 1, start: "13:00", end: "19:00" },
  ],
  ...overrides,
});

const base = (extra = {}) => ({
  "GET /t/alpha": json(salon()),
  "POST /t/alpha/auth/refresh": json(session()),
  "GET /t/alpha/providers": json([provider()]),
  "GET /t/alpha/team": json([]),
  "GET /t/alpha/offerings": json([
    { id: CORTE, name: "Corte feminino", duration_min: 60, is_active: true },
    { id: BARBA, name: "Barba", duration_min: 30, is_active: true },
  ]),
  [`GET /t/alpha/providers/${ID}/time-off`]: json([]),
  ...extra,
});

describe("profissionais", () => {
  it("lista com resumo da jornada e dos serviços", async () => {
    mockApi(base());

    renderWithProviders(<App />, { route: "/alpha/app/providers" });

    expect(await screen.findByText("Paula Souza")).toBeInTheDocument();
    expect(screen.getByText("Trabalha 1 dias por semana · faz 1 serviços")).toBeInTheDocument();
  });

  it("cadastra só com o nome e abre a ficha para configurar", async () => {
    const requests = mockApi(base({ "POST /t/alpha/providers": json(provider(), 201) }));
    renderWithProviders(<App />, { route: "/alpha/app/providers" });

    await userEvent.type(await screen.findByLabelText("Nome"), "Paula Souza");
    await userEvent.click(screen.getByRole("button", { name: "Cadastrar e configurar" }));

    expect(await screen.findByRole("heading", { name: "Jornada semanal" })).toBeInTheDocument();
    const sent = requests.find((r) => r.method === "POST" && r.url.endsWith("/providers"))!;
    expect(await sent.json()).toEqual({ name: "Paula Souza" });
  });

  it("monta a jornada: liga um dia, ajusta o horário e salva a semana inteira", async () => {
    const requests = mockApi(
      base({ [`PUT /t/alpha/providers/${ID}/working-hours`]: json(provider()) }),
    );
    renderWithProviders(<App />, { route: `/alpha/app/providers/${ID}` });

    // terça já tem 2 faixas (almoço no meio); liga a quarta e muda o fim para 17:00
    expect(await screen.findByLabelText("Início de Terça")).toHaveValue("09:00");
    expect(screen.getByLabelText("Início do 2º horário de Terça")).toHaveValue("13:00");
    await userEvent.click(screen.getByLabelText("Quarta"));
    const end = screen.getByLabelText("Fim de Quarta");
    await userEvent.clear(end);
    await userEvent.type(end, "17:00");
    await userEvent.click(screen.getByRole("button", { name: "Salvar jornada" }));

    const put = requests.find((r) => r.method === "PUT" && r.url.endsWith("/working-hours"))!;
    expect(await put.json()).toEqual({
      ranges: [
        { weekday: 1, start: "09:00", end: "12:00" },
        { weekday: 1, start: "13:00", end: "19:00" },
        { weekday: 2, start: "09:00", end: "17:00" },
      ],
    });
  });

  it("marca os serviços que a pessoa faz", async () => {
    const requests = mockApi(
      base({ [`PUT /t/alpha/providers/${ID}/offerings`]: json(provider()) }),
    );
    renderWithProviders(<App />, { route: `/alpha/app/providers/${ID}` });

    await userEvent.click(await screen.findByLabelText("Barba"));

    const put = requests.find((r) => r.url.endsWith("/offerings") && r.method === "PUT")!;
    expect((await put.json()).offering_ids.sort()).toEqual([CORTE, BARBA].sort());
  });

  it("marca uma folga de um dia só", async () => {
    const requests = mockApi(
      base({
        [`POST /t/alpha/providers/${ID}/time-off`]: json(
          { id: "t1", start_date: "2027-01-10", end_date: "2027-01-10", reason: null,
            starts_at: "2027-01-10T03:00:00Z", ends_at: "2027-01-11T03:00:00Z" }, 201,
        ),  // prettier-ignore
      }),
    );
    renderWithProviders(<App />, { route: `/alpha/app/providers/${ID}` });

    await userEvent.type(await screen.findByLabelText("Primeiro dia"), "2027-01-10");
    await userEvent.click(screen.getByRole("button", { name: "Marcar folga" }));

    const sent = requests.find((r) => r.url.endsWith("/time-off") && r.method === "POST")!;
    expect(await sent.json()).toEqual({
      start_date: "2027-01-10",
      end_date: "2027-01-10",
      reason: null,
    });
  });

  it("mostra as folgas pelo dia local, sem errar por causa do fuso", async () => {
    mockApi(
      base({
        [`GET /t/alpha/providers/${ID}/time-off`]: json([
          { id: "t1", start_date: "2027-12-24", end_date: "2027-12-26", reason: "Natal",
            starts_at: "2027-12-24T03:00:00Z", ends_at: "2027-12-27T03:00:00Z" },
        ]),  // prettier-ignore
      }),
    );
    renderWithProviders(<App />, { route: `/alpha/app/providers/${ID}` });

    const folgas = (await screen.findByRole("heading", { name: "Folgas e férias" })).parentElement!;
    expect(
      await within(folgas).findByText(/24 de dez\. de 2027 a 26 de dez\. de 2027/),
    ).toBeInTheDocument();
    expect(within(folgas).getByText(/Natal/)).toBeInTheDocument();
  });
});

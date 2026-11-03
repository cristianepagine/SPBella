import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import { resetSessions } from "../../core/auth/session";
import { apiError, json, mockApi, salon } from "../../test/api";
import { renderWithProviders } from "../../test/render";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2027-03-09T15:00:00Z")); // terça, 12:00 em São Paulo
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  resetSessions();
});

const catalog = {
  offerings: [
    { id: "o1", name: "Corte feminino", duration_min: 60, extras: { price_minor: 8000 } },
    { id: "o2", name: "Barba", duration_min: 30, extras: { price_minor: 3500 } },
  ],
  providers: [
    { id: "p1", name: "Paula", color: "sky", offering_ids: ["o1"] },
    { id: "p2", name: "Rita", color: "rose", offering_ids: ["o1", "o2"] },
  ],
  min_notice_min: 60,
  max_days_ahead: 30,
  privacy_policy_version: "2026-11-02",
};

const free = {
  date: "2027-03-10", timezone: "America/Sao_Paulo", offering_id: "o1", duration_min: 60,
  slots: [{ starts_at: "2027-03-10T12:00:00Z", provider_ids: ["p1", "p2"] },
          { starts_at: "2027-03-10T13:00:00Z", provider_ids: ["p2"] }],
}; // prettier-ignore

function setup(extra = {}) {
  return mockApi({
    "GET /t/alpha": json(salon()),
    "GET /t/alpha/booking/catalog": json(catalog),
    "GET /t/alpha/booking/availability": json(free),
    ...extra,
  });
}

async function chooseUntilDetails() {
  await userEvent.click(await screen.findByRole("button", { name: /Corte feminino/ }));
  await userEvent.click(screen.getByRole("button", { name: "Sem preferência" }));
  await userEvent.click(screen.getByRole("button", { name: /10\/03/ }));
  await userEvent.click(await screen.findByRole("button", { name: "09:00" }));
  const details = screen.getByRole("region", { name: "5. Seus dados" });
  await userEvent.type(within(details).getByLabelText("Seu nome"), "Maria");
  await userEvent.type(within(details).getByLabelText("Celular (WhatsApp)"), "11 98888-7777");
  return details;
}

describe("página pública de agendamento", () => {
  it("mostra o botão de WhatsApp com o número do salão", async () => {
    setup({ "GET /t/alpha/booking/catalog": json({ ...catalog, whatsapp_phone: "+5511988887777" }) });
    renderWithProviders(<App />, { route: "/alpha" });

    const button = await screen.findByRole("link", { name: "Falar no WhatsApp" });
    const href = button.getAttribute("href")!;
    expect(href.startsWith("https://wa.me/5511988887777?text=")).toBe(true);
    expect(decodeURIComponent(href)).toContain("Studio Alpha");
  });

  it("sem número cadastrado, não mostra o botão", async () => {
    setup({ "GET /t/alpha/booking/catalog": json({ ...catalog, whatsapp_phone: null }) });
    renderWithProviders(<App />, { route: "/alpha" });

    await screen.findByRole("button", { name: /Corte feminino/ });
    expect(screen.queryByRole("link", { name: "Falar no WhatsApp" })).not.toBeInTheDocument();
  });

  it("mostra serviços com preço e só os profissionais que fazem o serviço", async () => {
    setup();
    renderWithProviders(<App />, { route: "/alpha" });

    expect(await screen.findByRole("button", { name: /Barba.*30 min.*R\$\s?35,00/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Barba/ }));

    const who = screen.getByRole("region", { name: "2. Com quem?" });
    expect(within(who).getByRole("button", { name: "Rita" })).toBeInTheDocument();
    expect(within(who).queryByRole("button", { name: "Paula" })).toBeNull();
    expect(within(who).queryByRole("button", { name: "Sem preferência" })).toBeNull();
  });

  it("marca sem conta, com consentimento, e confirma", async () => {
    const requests = setup({
      "POST /t/alpha/booking": json(
        { appointment_id: "a1", offering_name: "Corte feminino", provider_name: "Rita",
          starts_at: "2027-03-10T12:00:00Z", ends_at: "2027-03-10T13:00:00Z" }, 201), // prettier-ignore
    });
    renderWithProviders(<App />, { route: "/alpha" });

    const details = await chooseUntilDetails();
    const confirm = within(details).getByRole("button", { name: "Confirmar agendamento" });
    expect(confirm).toBeDisabled(); // sem a autorização de uso dos dados
    await userEvent.click(within(details).getByLabelText(/Autorizo Studio Alpha/));
    await userEvent.click(confirm);

    expect(await screen.findByText("Horário marcado!")).toBeInTheDocument();
    expect(screen.getByText(/Corte feminino com Rita, .*10\/03 às 09:00/)).toBeInTheDocument();
    const sent = requests.find((r) => r.method === "POST" && r.url.endsWith("/booking"))!;
    expect(await sent.json()).toEqual({
      offering_id: "o1", provider_id: null, starts_at: "2027-03-10T12:00:00Z", name: "Maria",
      phone: "11 98888-7777", email: null, locale: "pt-BR", consents: ["service", "reminders"],
      turnstile_token: null,
    }); // prettier-ignore
  });

  it("avisa quando outra pessoa pegou o horário", async () => {
    setup({ "POST /t/alpha/booking": apiError(409, "slot_unavailable") });
    renderWithProviders(<App />, { route: "/alpha" });

    const details = await chooseUntilDetails();
    await userEvent.click(within(details).getByLabelText(/Autorizo/));
    await userEvent.click(within(details).getByRole("button", { name: "Confirmar agendamento" }));

    expect(await screen.findByText(/acabou de ser ocupado/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "09:00" })).toHaveAttribute("aria-pressed", "false");
  });

  it("dia sem horário livre", async () => {
    setup({ "GET /t/alpha/booking/availability": json({ ...free, slots: [] }) });
    renderWithProviders(<App />, { route: "/alpha" });

    await userEvent.click(await screen.findByRole("button", { name: /Corte feminino/ }));
    await userEvent.click(screen.getByRole("button", { name: "Paula" }));
    await userEvent.click(screen.getByRole("button", { name: "Hoje" }));

    expect(await screen.findByText(/Nenhum horário livre/)).toBeInTheDocument();
  });

  it("tem a política de privacidade com o nome do salão", async () => {
    setup();
    renderWithProviders(<App />, { route: "/alpha/privacy" });

    expect(await screen.findByRole("heading", { name: "Privacidade" })).toBeInTheDocument();
    expect(screen.getByText(/Studio Alpha é responsável pelos dados/)).toBeInTheDocument();
  });
});

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../../../../App";
import { apiError, json, mockApi, salon, session } from "../../../../test/api";
import { renderWithProviders } from "../../../../test/render";
import { resetSessions } from "../../../auth/session";

afterEach(() => {
  vi.restoreAllMocks();
  resetSessions();
});

const ID = "44444444-4444-4444-4444-444444444444";

const customer = (overrides = {}) => ({
  id: ID,
  name: "Maria Silva",
  phone: "+5511988887777",
  phone_display: "+55 11 98888-7777",
  email: "maria@exemplo.com",
  locale: null,
  created_at: "2026-11-03T12:00:00Z",
  updated_at: "2026-11-03T12:00:00Z",
  consents: [
    { purpose: "service", granted_at: "2026-11-03T12:00:00Z", source: "staff", policy_version: "1" },
  ],
  ...overrides,
});

const loggedAs = (role: "owner" | "reception" | "professional", extra = {}) => ({
  "GET /t/alpha": json(salon()),
  "POST /t/alpha/auth/refresh": json(session({ role, name: `Pessoa ${role}` })),
  ...extra,
});

const audit = [
  {
    id: "a2", occurred_at: "2026-11-03T13:31:00Z", action: "customer.updated",
    entity_type: "customer", entity_id: ID, actor_type: "user",
    actor: { id: "u1", name: "Rita Recepção" }, fields: ["email", "phone"],
  },
  {
    id: "a1", occurred_at: "2026-11-03T13:30:00Z", action: "consent.granted",
    entity_type: "customer", entity_id: ID, actor_type: "user",
    actor: { id: "u1", name: "Rita Recepção" }, fields: ["reminders", "service"],
  },
]; // prettier-ignore

describe("clientes", () => {
  it("aparece no menu para recepção e dono, não para profissional", async () => {
    mockApi(loggedAs("professional"));

    renderWithProviders(<App />, { route: "/alpha/app" });

    const nav = await screen.findByRole("navigation", { name: "Menu" });
    expect(within(nav).queryByRole("link", { name: "Clientes" })).toBeNull();
  });

  it("lista os clientes", async () => {
    mockApi(
      loggedAs("reception", {
        "GET /t/alpha/customers": json({ items: [customer()], total: 1 }),
      }),
    );

    renderWithProviders(<App />, { route: "/alpha/app/customers" });

    expect(await screen.findByText("Maria Silva")).toBeInTheDocument();
    expect(screen.getByText("+55 11 98888-7777")).toBeInTheDocument();
  });

  it("cadastra com o consentimento marcado e abre a ficha", async () => {
    const requests = mockApi(
      loggedAs("reception", {
        "POST /t/alpha/customers": json(customer(), 201),
        [`GET /t/alpha/customers/${ID}`]: json(customer()),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/customers/new" });

    await userEvent.type(await screen.findByLabelText("Nome"), "Maria Silva");
    await userEvent.type(screen.getByLabelText(/^Telefone/), "(11) 98888-7777");
    await userEvent.click(screen.getByLabelText(/para o atendimento \(obrigatório\)/));
    await userEvent.click(screen.getByLabelText(/confirmações e lembretes/));
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(await screen.findByRole("heading", { name: "Maria Silva" })).toBeInTheDocument();
    const sent = requests.find((r) => r.method === "POST" && r.url.endsWith("/customers"))!;
    expect(await sent.json()).toEqual({
      name: "Maria Silva",
      phone: "(11) 98888-7777",
      email: null,
      locale: null,
      consents: ["service", "reminders"],
    });
  });

  it("explica em linguagem simples o que está errado", async () => {
    mockApi(
      loggedAs("reception", {
        "POST /t/alpha/customers": apiError(422, "validation_error", [
          { field: "consents", code: "consent_required" },
        ]),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/customers/new" });

    await userEvent.type(await screen.findByLabelText("Nome"), "Sem Consentimento");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "o cliente precisa concordar com o uso dos dados para o atendimento",
    );
  });

  it("na ficha, envia só o que mudou", async () => {
    const requests = mockApi(
      loggedAs("reception", {
        [`GET /t/alpha/customers/${ID}`]: json(customer()),
        [`PATCH /t/alpha/customers/${ID}`]: json(customer({ email: null })),
      }),
    );
    renderWithProviders(<App />, { route: `/alpha/app/customers/${ID}` });

    await userEvent.clear(await screen.findByLabelText("E-mail (opcional)"));
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    const patch = requests.find((r) => r.method === "PATCH")!;
    expect(await patch.json()).toEqual({ email: null });
  });

  it("retira um consentimento com um toque", async () => {
    const requests = mockApi(
      loggedAs("reception", {
        [`GET /t/alpha/customers/${ID}`]: json(customer()),
        [`POST /t/alpha/customers/${ID}/consents`]: json(customer({ consents: [] })),
      }),
    );
    renderWithProviders(<App />, { route: `/alpha/app/customers/${ID}` });

    await userEvent.click(await screen.findByLabelText(/para o atendimento \(obrigatório\)/));

    const sent = requests.find((r) => r.url.endsWith("/consents"))!;
    expect(await sent.json()).toEqual({ purpose: "service", granted: false });
    expect(await screen.findByText(/retirou a concordância/)).toBeInTheDocument();
  });
});

describe("busca", () => {
  it("busca pelo que a pessoa digita, sem buscar a cada tecla", async () => {
    const requests = mockApi(
      loggedAs("reception", {
        "GET /t/alpha/customers": (request: Request) => {
          const q = new URL(request.url).searchParams.get("q");
          return json(
            q
              ? { items: [customer({ name: "João Conceição" })], total: 1 }
              : { items: [customer()], total: 1 },
          );
        },
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/customers" });

    await userEvent.type(await screen.findByLabelText("Buscar cliente"), "joao");

    expect(await screen.findByText("João Conceição")).toBeInTheDocument();
    const searches = requests
      .map((r) => new URL(r.url).searchParams.get("q"))
      .filter((q) => q !== null);
    expect(searches).toEqual(["joao"]); // uma busca só, depois de parar de digitar
  });

  it("diz quando não encontra ninguém", async () => {
    mockApi(
      loggedAs("reception", {
        "GET /t/alpha/customers": (request: Request) =>
          json(
            new URL(request.url).searchParams.get("q")
              ? { items: [], total: 0 }
              : { items: [customer()], total: 1 },
          ),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/customers" });

    await userEvent.type(await screen.findByLabelText("Buscar cliente"), "zzz");

    expect(await screen.findByText("Nenhum cliente encontrado para “zzz”.")).toBeInTheDocument();
  });

  it("no cadastro, avisa que o telefone já existe e leva à ficha", async () => {
    mockApi(
      loggedAs("reception", {
        "GET /t/alpha/customers": (request: Request) => {
          const q = new URL(request.url).searchParams.get("q");
          return json(q === "11988887777" ? { items: [customer()], total: 1 } : { items: [], total: 0 });
        },
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/customers/new" });

    await userEvent.type(await screen.findByLabelText(/^Telefone/), "(11) 98888-7777");

    expect(await screen.findByText("Já existe cliente com este telefone:")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Maria Silva" })).toHaveAttribute(
      "href",
      `/alpha/app/customers/${ID}`,
    );
  });
});

describe("histórico (auditoria)", () => {
  it("o dono vê quem alterou o quê e quando, no fuso do salão", async () => {
    mockApi(
      loggedAs("owner", {
        [`GET /t/alpha/customers/${ID}`]: json(customer()),
        "GET /t/alpha/audit": json(audit),
      }),
    );

    renderWithProviders(<App />, { route: `/alpha/app/customers/${ID}` });

    expect(await screen.findByText("Alterou: e-mail, telefone")).toBeInTheDocument();
    expect(
      screen.getByText("Registrou consentimento: lembretes, atendimento"),
    ).toBeInTheDocument();
    expect(screen.getByText("03/11/2026, 10:31 · Rita Recepção")).toBeInTheDocument();
  });

  it("a recepção não vê o histórico (e nem pede ao servidor)", async () => {
    const requests = mockApi(
      loggedAs("reception", { [`GET /t/alpha/customers/${ID}`]: json(customer()) }),
    );

    renderWithProviders(<App />, { route: `/alpha/app/customers/${ID}` });

    await screen.findByRole("heading", { name: "Maria Silva" });
    expect(screen.queryByRole("heading", { name: "Histórico" })).toBeNull();
    expect(requests.some((r) => r.url.includes("/audit"))).toBe(false);
  });
});

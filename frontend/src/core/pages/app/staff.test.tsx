import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../../../App";
import { apiError, json, mockApi, salon, session } from "../../../test/api";
import { renderWithProviders } from "../../../test/render";
import { resetSessions } from "../../auth/session";

afterEach(() => {
  vi.restoreAllMocks();
  resetSessions();
});

const loggedAs = (role: "owner" | "reception" | "professional", extra = {}) => ({
  "GET /t/alpha": json(salon()),
  "POST /t/alpha/auth/refresh": json(session({ role, name: `Pessoa ${role}` })),
  ...extra,
});

const member = (overrides = {}) => ({
  id: "22222222-2222-2222-2222-222222222222",
  name: "Carla Souza",
  email: "carla@alpha.test",
  role: "reception",
  is_active: true,
  must_change_password: false,
  last_login_at: null,
  created_at: "2026-11-01T12:00:00Z",
  ...overrides,
});

const me = member({
  id: "11111111-1111-1111-1111-111111111111",
  name: "Pessoa owner",
  role: "owner",
});

describe("cada perfil vê o seu menu e o seu início", () => {
  it("dono vê a Equipe no menu", async () => {
    mockApi(loggedAs("owner"));

    renderWithProviders(<App />, { route: "/alpha/app" });

    const nav = await screen.findByRole("navigation", { name: "Menu" });
    expect(within(nav).getByRole("link", { name: "Equipe" })).toBeInTheDocument();
    expect(screen.getByText(/Aqui você administra tudo/)).toBeInTheDocument();
    expect(screen.getByText("Pessoa owner · Dono(a)")).toBeInTheDocument();
  });

  it("recepção não vê a Equipe", async () => {
    mockApi(loggedAs("reception"));

    renderWithProviders(<App />, { route: "/alpha/app" });

    const nav = await screen.findByRole("navigation", { name: "Menu" });
    expect(within(nav).queryByRole("link", { name: "Equipe" })).toBeNull();
    expect(screen.getByText(/cuida da agenda e dos clientes/)).toBeInTheDocument();
  });

  it("profissional vê só a própria agenda", async () => {
    mockApi(loggedAs("professional"));

    renderWithProviders(<App />, { route: "/alpha/app" });

    expect(await screen.findByText(/Aqui você vê a sua agenda/)).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Menu" });
    expect(within(nav).getAllByRole("link").map((a) => a.textContent)).toEqual(["Início", "Agenda"]);
  });

  it("quem abre uma área proibida pelo endereço vê o aviso", async () => {
    const requests = mockApi(loggedAs("professional"));

    renderWithProviders(<App />, { route: "/alpha/app/team" });

    expect(await screen.findByRole("heading", { name: "Sem acesso" })).toBeInTheDocument();
    expect(requests.some((r) => r.url.endsWith("/team"))).toBe(false); // nem chama a API
  });
});

describe("equipe", () => {
  it("lista a equipe e cadastra uma pessoa, mostrando a senha provisória uma vez", async () => {
    let team = [me, member()];
    const requests = mockApi(
      loggedAs("owner", {
        "GET /t/alpha/team": () => json(team),
        "POST /t/alpha/team": async (request: Request) => {
          const body = await request.json();
          const created = member({ id: "33333333-3333-3333-3333-333333333333", ...body,
            must_change_password: true });  // prettier-ignore
          team = [...team, created];
          return json({ member: created, temporary_password: "Xy7-provisoria" }, 201);
        },
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/team" });

    expect(await screen.findByText("Carla Souza")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Nome"), "Paulo Lima");
    await userEvent.type(screen.getByLabelText("E-mail"), "paulo@alpha.test");
    await userEvent.selectOptions(screen.getByLabelText("Perfil"), "professional");
    await userEvent.click(screen.getByRole("button", { name: "Cadastrar" }));

    expect(await screen.findByText("Xy7-provisoria")).toBeInTheDocument();
    expect(await screen.findByText("Paulo Lima")).toBeInTheDocument();
    const sent = requests.find((r) => r.method === "POST" && r.url.endsWith("/team"))!;
    expect(await sent.json()).toEqual({
      name: "Paulo Lima",
      email: "paulo@alpha.test",
      role: "professional",
    });
    await userEvent.click(screen.getByRole("button", { name: "Já anotei" }));
    expect(screen.queryByText("Xy7-provisoria")).toBeNull();
  });

  it("explica quando o e-mail já existe", async () => {
    mockApi(
      loggedAs("owner", {
        "GET /t/alpha/team": json([me]),
        "POST /t/alpha/team": apiError(409, "email_taken"),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/team" });

    await userEvent.type(await screen.findByLabelText("Nome"), "Repetida");
    await userEvent.type(screen.getByLabelText("E-mail"), "carla@alpha.test");
    await userEvent.click(screen.getByRole("button", { name: "Cadastrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Já existe alguém com esse e-mail na equipe.",
    );
  });

  it("desativa uma pessoa, mas não mostra ações para si mesmo", async () => {
    const requests = mockApi(
      loggedAs("owner", {
        "GET /t/alpha/team": json([me, member()]),
        "PATCH /t/alpha/team/22222222-2222-2222-2222-222222222222": json(
          member({ is_active: false }),
        ),
      }),
    );
    renderWithProviders(<App />, { route: "/alpha/app/team" });

    const buttons = await screen.findAllByRole("button", { name: "Desativar" });
    expect(buttons).toHaveLength(1); // só a Carla; a própria pessoa não tem o botão
    await userEvent.click(buttons[0]);

    const patch = requests.find((r) => r.method === "PATCH")!;
    expect(await patch.json()).toEqual({ is_active: false });
  });
});

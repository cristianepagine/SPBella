import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, call } from "../api/client";
import { App } from "../../App";
import { changeLanguage } from "../i18n/index";
import { apiError, json, mockApi, salon, session } from "../../test/api";
import { renderWithProviders } from "../../test/render";
import { getAccessToken, refreshSession, resetSessions, setSession } from "./session";

const noSession = { "POST /t/alpha/auth/refresh": apiError(401, "refresh_invalid") };
const tenant = { "GET /t/alpha": json(salon()) };

afterEach(() => {
  vi.restoreAllMocks();
  resetSessions();
  changeLanguage("pt-BR");
  window.history.replaceState(null, "", "/");
});

async function fillLogin(email = "ana@alpha.test", password = "senha-forte-123") {
  await userEvent.type(await screen.findByLabelText("E-mail"), email);
  await userEvent.type(screen.getByLabelText("Senha"), password);
  await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
}

describe("login", () => {
  it("entra e mostra o painel", async () => {
    const requests = mockApi({
      ...tenant,
      ...noSession,
      "POST /t/alpha/auth/login": json(session()),
    });

    renderWithProviders(<App />, { route: "/alpha/login" });
    await fillLogin();

    expect(await screen.findByRole("heading", { name: "Olá, Ana Demo!" })).toBeInTheDocument();
    const loginRequest = requests.find((r) => r.url.endsWith("/auth/login"))!;
    expect(await loginRequest.json()).toEqual({
      email: "ana@alpha.test",
      password: "senha-forte-123",
      turnstile_token: null,
    });
    expect(loginRequest.credentials).toBe("include");
  });

  it("explica quando e-mail ou senha estão errados", async () => {
    mockApi({
      ...tenant,
      ...noSession,
      "POST /t/alpha/auth/login": apiError(401, "invalid_credentials"),
    });

    renderWithProviders(<App />, { route: "/alpha/login" });
    await fillLogin();

    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou senha incorretos.");
  });

  it("avisa quando há tentativas demais", async () => {
    mockApi({
      ...tenant,
      ...noSession,
      "POST /t/alpha/auth/login": apiError(429, "too_many_requests"),
    });

    renderWithProviders(<App />, { route: "/alpha/login" });
    await fillLogin();

    expect(await screen.findByRole("alert")).toHaveTextContent(/Muitas tentativas/);
  });

  it("leva ao login quem tenta abrir o painel sem sessão", async () => {
    mockApi({ ...tenant, ...noSession });

    renderWithProviders(<App />, { route: "/alpha/app" });

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
  });

  it("recupera a sessão pelo cookie ao abrir o app", async () => {
    mockApi({ ...tenant, "POST /t/alpha/auth/refresh": json(session()) });

    renderWithProviders(<App />, { route: "/alpha/app" });

    expect(await screen.findByRole("heading", { name: "Olá, Ana Demo!" })).toBeInTheDocument();
  });

  it("sai e volta ao login", async () => {
    let loggedOut = false;
    const requests = mockApi({
      ...tenant,
      "POST /t/alpha/auth/refresh": () =>
        loggedOut ? apiError(401, "refresh_invalid") : json(session()),
      "POST /t/alpha/auth/logout": () => {
        loggedOut = true;
        return new Response(null, { status: 204 });
      },
    });
    renderWithProviders(<App />, { route: "/alpha/app" });

    await userEvent.click(await screen.findByRole("button", { name: "Sair" }));

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(requests.some((r) => r.url.endsWith("/auth/logout"))).toBe(true);
  });
});

describe("senha provisória", () => {
  it("obriga a trocar a senha antes de usar o sistema", async () => {
    const requests = mockApi({
      ...tenant,
      ...noSession,
      "POST /t/alpha/auth/login": json(session({ must_change_password: true })),
      "POST /t/alpha/auth/change-password": json(session({}, "access-2")),
    });
    renderWithProviders(<App />, { route: "/alpha/login" });
    await fillLogin("ana@alpha.test", "provisoria1");

    await userEvent.type(await screen.findByLabelText("Senha provisória"), "provisoria1");
    await userEvent.type(screen.getByLabelText("Senha nova"), "nova-senha-forte-1");
    await userEvent.click(screen.getByRole("button", { name: "Salvar senha nova" }));

    expect(await screen.findByRole("heading", { name: "Olá, Ana Demo!" })).toBeInTheDocument();
    const change = requests.find((r) => r.url.endsWith("/auth/change-password"))!;
    expect(change.headers.get("Authorization")).toBe("Bearer access-1");
  });

  it("explica por que a senha nova foi recusada", async () => {
    mockApi({
      ...tenant,
      "POST /t/alpha/auth/refresh": json(session({ must_change_password: true })),
      "POST /t/alpha/auth/change-password": apiError(422, "weak_password", [
        { field: "new_password", code: "contains_email" },
      ]),
    });
    renderWithProviders(<App />, { route: "/alpha/change-password" });

    await userEvent.type(await screen.findByLabelText("Senha provisória"), "provisoria1");
    await userEvent.type(screen.getByLabelText("Senha nova"), "ana12345678");
    await userEvent.click(screen.getByRole("button", { name: "Salvar senha nova" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A senha não pode conter o seu e-mail.",
    );
  });
});

describe("esqueci a senha", () => {
  it("confirma o envio sem revelar se o e-mail existe", async () => {
    const requests = mockApi({
      ...tenant,
      ...noSession,
      "POST /t/alpha/auth/forgot-password": new Response(null, { status: 202 }),
    });
    renderWithProviders(<App />, { route: "/alpha/forgot-password" });

    await userEvent.type(await screen.findByLabelText("E-mail"), "qualquer@alpha.test");
    await userEvent.click(screen.getByRole("button", { name: "Enviar link" }));

    expect(await screen.findByRole("status")).toHaveTextContent(/Se esse e-mail tiver conta/);
    const sent = requests.find((r) => r.url.endsWith("/forgot-password"))!;
    expect(await sent.json()).toEqual({ email: "qualquer@alpha.test", turnstile_token: null });
  });

  it("cria a senha nova pelo link e tira o token da barra de endereço", async () => {
    window.history.replaceState(null, "", "/alpha/reset-password#token=abc123");
    const requests = mockApi({
      ...tenant,
      ...noSession,
      "POST /t/alpha/auth/reset-password": new Response(null, { status: 204 }),
    });
    renderWithProviders(<App />, { route: "/alpha/reset-password" });

    await userEvent.type(await screen.findByLabelText("Senha nova"), "senha-nova-forte-9");
    expect(window.location.hash).toBe("");
    await userEvent.click(screen.getByRole("button", { name: "Salvar senha nova" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Senha nova salva!");
    const reset = requests.find((r) => r.url.endsWith("/reset-password"))!;
    expect(await reset.json()).toMatchObject({ token: "abc123", new_password: "senha-nova-forte-9" });
  });

  it("explica quando o link venceu", async () => {
    window.history.replaceState(null, "", "/alpha/reset-password#token=velho");
    mockApi({
      ...tenant,
      ...noSession,
      "POST /t/alpha/auth/reset-password": apiError(400, "invalid_reset_token"),
    });
    renderWithProviders(<App />, { route: "/alpha/reset-password" });

    await userEvent.type(await screen.findByLabelText("Senha nova"), "senha-nova-forte-9");
    await userEvent.click(screen.getByRole("button", { name: "Salvar senha nova" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Este link venceu/);
  });

  it("avisa quando o link está incompleto", async () => {
    mockApi({ ...tenant, ...noSession });

    renderWithProviders(<App />, { route: "/alpha/reset-password" });

    expect(await screen.findByRole("alert")).toHaveTextContent(/Este link está incompleto/);
  });
});

describe("renovação automática da sessão", () => {
  it("renova o access token vencido e repete o pedido uma vez", async () => {
    setSession("alpha", session({}, "vencido"));
    let meCalls = 0;
    const requests = mockApi({
      "GET /t/alpha/auth/me": () =>
        ++meCalls === 1 ? apiError(401, "not_authenticated") : json(session().user),
      "POST /t/alpha/auth/refresh": json(session({}, "novo")),
    });

    const me = await call(() =>
      api.GET("/t/{slug}/auth/me", { params: { path: { slug: "alpha" } } }),
    );

    expect(me.name).toBe("Ana Demo");
    const meRequests = requests.filter((r) => r.url.endsWith("/auth/me"));
    expect(meRequests.map((r) => r.headers.get("Authorization"))).toEqual([
      "Bearer vencido",
      "Bearer novo",
    ]);
  });

  it("pedidos de renovação simultâneos viram um só", async () => {
    const requests = mockApi({ "POST /t/alpha/auth/refresh": json(session()) });

    await Promise.all([refreshSession("alpha"), refreshSession("alpha"), refreshSession("alpha")]);

    expect(requests.filter((r) => r.url.endsWith("/refresh"))).toHaveLength(1);
  });

  it("tenta de novo uma vez quando outra aba acabou de renovar", async () => {
    let calls = 0;
    mockApi({
      "POST /t/alpha/auth/refresh": () =>
        ++calls === 1 ? apiError(401, "refresh_superseded") : json(session()),
    });

    const result = await refreshSession("alpha");

    expect(result?.user.name).toBe("Ana Demo");
    expect(calls).toBe(2);
  });

  it("sem sessão, não insiste", async () => {
    const requests = mockApi({ "POST /t/alpha/auth/refresh": apiError(401, "refresh_invalid") });

    expect(await refreshSession("alpha")).toBeNull();
    expect(requests).toHaveLength(1);
  });

  it("uma renovação atrasada não desfaz um login feito no meio do caminho", async () => {
    let answer: (response: Response) => void = () => {};
    mockApi({
      "POST /t/alpha/auth/refresh": () => new Promise<Response>((resolve) => (answer = resolve)),
    });

    const pending = refreshSession("alpha");
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    setSession("alpha", session({}, "do-login"));
    answer(apiError(401, "refresh_invalid"));
    await pending;

    expect(getAccessToken("alpha")).toBe("do-login");
  });
});

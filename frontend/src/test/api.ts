import { vi } from "vitest";

import type { Session } from "../core/auth/session";

type Handler = Response | ((request: Request) => Response | Promise<Response>);

export const json = (body: unknown, status = 200) => Response.json(body, { status });

export const apiError = (status: number, code: string, fields?: unknown) =>
  json({ error: { code, message: code, ...(fields ? { fields } : {}) } }, status);

/**
 * Simula a API. Chave: "MÉTODO /caminho". Rotas não listadas respondem 404.
 * Devolve a lista de pedidos feitos, para conferir corpo e cabeçalhos.
 */
export function mockApi(routes: Record<string, Handler>) {
  const requests: Request[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const request = input instanceof Request ? input : new Request(input, init);
    requests.push(request.clone());
    const handler = routes[`${request.method} ${new URL(request.url).pathname}`];
    if (!handler) return apiError(404, "not_found");
    return typeof handler === "function" ? handler(request) : handler.clone();
  });
  return requests;
}

export const salon = (overrides: Record<string, unknown> = {}) => ({
  slug: "alpha",
  name: "Studio Alpha",
  country: "BR",
  locale: "pt-BR",
  timezone: "America/Sao_Paulo",
  currency: "BRL",
  ...overrides,
});

export const session = (user: Record<string, unknown> = {}, token = "access-1"): Session => ({
  access_token: token,
  token_type: "bearer",
  expires_in: 900,
  user: {
    id: "11111111-1111-1111-1111-111111111111",
    name: "Ana Demo",
    email: "ana@alpha.test",
    role: "owner",
    must_change_password: false,
    permissions: [...PERMISSIONS[(user.role as keyof typeof PERMISSIONS) ?? "owner"]],
    ...user,
  } as Session["user"],
});

/** Mesma matriz do servidor (backend/app/core/accounts/permissions.py). */
export const PERMISSIONS = {
  owner: [
    "agenda.manage",
    "agenda.view_all",
    "agenda.view_own",
    "audit.view",
    "catalog.manage",
    "customers.manage",
    "providers.manage",
    "reports.view",
    "settings.manage",
    "team.manage",
    "time_off.manage",
  ],
  reception: ["agenda.manage", "agenda.view_all", "agenda.view_own", "customers.manage"],
  professional: ["agenda.view_own"],
} as const;

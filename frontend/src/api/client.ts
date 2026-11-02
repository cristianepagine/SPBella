import createClient from "openapi-fetch";

import { getAccessToken, refreshSession } from "../auth/session";
import { API_URL } from "../config";
import type { components, paths } from "./schema";

// Rotas de login que não usam (nem renovam) o access token.
const PUBLIC_AUTH_ROUTE = /\/auth\/(login|refresh|logout|forgot-password|reset-password)$/;

function salonSlug(url: string): string | null {
  return new URL(url).pathname.match(/^\/t\/([^/]+)/)?.[1] ?? null;
}

function withToken(request: Request, slug: string | null): Request {
  const token = slug ? getAccessToken(slug) : null;
  if (!token) return request;
  const headers = new Headers(request.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return new Request(request, { headers });
}

/** Envia o access token e, se ele tiver vencido (401), renova a sessão e repete uma vez. */
async function fetchWithSession(request: Request): Promise<Response> {
  const slug = salonSlug(request.url);
  const canRetry =
    slug !== null && getAccessToken(slug) !== null && !PUBLIC_AUTH_ROUTE.test(request.url);
  const copy = canRetry ? request.clone() : null;

  // Lê o fetch global a cada chamada (e não só na criação), o que permite simulá-lo nos testes.
  const response = await globalThis.fetch(withToken(request, slug));
  if (response.status !== 401 || !copy || !slug) return response;

  const renewed = await refreshSession(slug);
  return renewed ? globalThis.fetch(withToken(copy, slug)) : response;
}

/** Tipos gerados de docs/api/openapi.json (npm run gen:api). Não edite schema.d.ts à mão. */
export const api = createClient<paths>({
  baseUrl: API_URL,
  credentials: "include", // necessário para o cookie de refresh (API em outro subdomínio)
  fetch: fetchWithSession,
});

export type ApiErrorBody = components["schemas"]["ErrorResponse"]["error"];

/** Erro lançado pelas chamadas; `code` é a chave de tradução em errors.<code>. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly requestId?: string,
    readonly fields: { field: string; code: string }[] = [],
  ) {
    super(code);
  }
}

export function toApiError(status: number, body: unknown): ApiError {
  const error = (body as { error?: ApiErrorBody } | undefined)?.error;
  return new ApiError(
    status,
    error?.code ?? "unknown",
    error?.request_id ?? undefined,
    error?.fields ?? [],
  );
}

type FetchResult<T> = { data?: T; error?: unknown; response: Response };

/** Executa uma chamada do openapi-fetch e devolve os dados, ou lança ApiError. */
export async function call<T>(request: () => Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await request();
  } catch {
    throw new ApiError(0, "network_error");
  }
  if (!result.response.ok) throw toApiError(result.response.status, result.error);
  return result.data as T;
}

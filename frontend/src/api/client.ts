import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/** Tipos gerados de docs/api/openapi.json (npm run gen:api). Não edite schema.d.ts à mão. */
export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  // Lê o fetch global a cada chamada (e não só na criação), o que permite simulá-lo nos testes.
  fetch: (request) => globalThis.fetch(request),
});

export type ApiErrorBody = components["schemas"]["ErrorResponse"]["error"];

/** Erro lançado pelas chamadas; `code` é a chave de tradução em errors.<code>. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly requestId?: string,
  ) {
    super(code);
  }
}

export function toApiError(status: number, body: unknown): ApiError {
  const error = (body as { error?: ApiErrorBody } | undefined)?.error;
  return new ApiError(status, error?.code ?? "unknown", error?.request_id ?? undefined);
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
  if (result.data === undefined) throw toApiError(result.response.status, result.error);
  return result.data;
}

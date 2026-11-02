/**
 * Sessão de login.
 *
 * - O access token fica SÓ na memória (some ao fechar a aba). Nunca em localStorage: lá
 *   qualquer script injetado conseguiria ler.
 * - O refresh token é um cookie httpOnly que o JavaScript nem enxerga; o navegador o envia
 *   sozinho para /t/{slug}/auth/refresh.
 */

import type { components } from "../api/schema";
import { API_URL } from "../config";

export type Session = components["schemas"]["SessionOut"];
export type SessionUser = components["schemas"]["UserOut"];

type Listener = (session: Session | null) => void;

const tokens = new Map<string, string>();
const listeners = new Map<string, Set<Listener>>();
const inFlight = new Map<string, Promise<Session | null>>();
// Muda a cada login/logout. Uma renovação que termina depois de uma mudança é descartada
// (ex.: a pessoa entrou enquanto a tentativa de recuperar a sessão ainda estava no ar).
let version = 0;

export function getAccessToken(slug: string): string | null {
  return tokens.get(slug) ?? null;
}

/** Guarda (ou apaga, com null) a sessão do salão e avisa quem está ouvindo. */
export function setSession(slug: string, session: Session | null): void {
  version += 1;
  if (session) tokens.set(slug, session.access_token);
  else tokens.delete(slug);
  listeners.get(slug)?.forEach((listener) => listener(session));
}

export function onSessionChange(slug: string, listener: Listener): () => void {
  const set = listeners.get(slug) ?? new Set();
  set.add(listener);
  listeners.set(slug, set);
  return () => set.delete(listener);
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function requestRefresh(slug: string): Promise<Response> {
  return fetch(`${API_URL}/t/${encodeURIComponent(slug)}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
}

async function errorCode(response: Response): Promise<string | undefined> {
  try {
    return ((await response.clone().json()) as { error?: { code?: string } }).error?.code;
  } catch {
    return undefined;
  }
}

/**
 * Pede um access token novo usando o cookie. Chamadas simultâneas compartilham o mesmo pedido.
 * Se outra aba acabou de renovar (`refresh_superseded`), tenta mais uma vez, já com o cookie novo.
 */
export function refreshSession(slug: string): Promise<Session | null> {
  const pending = inFlight.get(slug);
  if (pending) return pending;

  const startedAt = version;
  const promise = (async () => {
    try {
      let response = await requestRefresh(slug);
      if (response.status === 401 && (await errorCode(response)) === "refresh_superseded") {
        await wait(300);
        response = await requestRefresh(slug);
      }
      const session = response.ok ? ((await response.json()) as Session) : null;
      if (version !== startedAt) return getAccessToken(slug) ? session : null;
      setSession(slug, session);
      return session;
    } catch {
      return null; // sem internet: mantém o que havia; a próxima ação tenta de novo
    } finally {
      inFlight.delete(slug);
    }
  })();
  inFlight.set(slug, promise);
  return promise;
}

/** Só para testes. */
export function resetSessions(): void {
  version += 1;
  tokens.clear();
  listeners.clear();
  inFlight.clear();
}

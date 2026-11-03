export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Chave pública do Cloudflare Turnstile. Sem ela (desenvolvimento), o widget não aparece e a
 * API, também sem a chave secreta, não exige a verificação. */
export const TURNSTILE_SITE_KEY: string | undefined = import.meta.env.VITE_TURNSTILE_SITE_KEY;

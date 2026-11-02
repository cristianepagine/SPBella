import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { TURNSTILE_SITE_KEY } from "../config";

type TurnstileApi = {
  render: (element: HTMLElement, options: Record<string, unknown>) => string;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
let scriptPromise: Promise<void> | null = null;

function loadScript(): Promise<void> {
  scriptPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("turnstile"));
    document.head.appendChild(script);
  });
  return scriptPromise;
}

function TurnstileWidget({ onToken }: { onToken: (token: string | null) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const { i18n } = useTranslation();

  useEffect(() => {
    let widgetId: string | undefined;
    let cancelled = false;
    void loadScript().then(() => {
      if (cancelled || !ref.current || !window.turnstile) return;
      widgetId = window.turnstile.render(ref.current, {
        sitekey: TURNSTILE_SITE_KEY,
        language: i18n.language === "es" ? "es" : "pt-br",
        callback: (token: string) => onToken(token),
        "expired-callback": () => onToken(null),
        "error-callback": () => onToken(null),
      });
    });
    return () => {
      cancelled = true;
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
    };
  }, [onToken, i18n.language]);

  return <div ref={ref} className="my-2 min-h-[65px]" />;
}

/**
 * Verificação anti-robô dos formulários públicos.
 * `ready` diz se já dá para enviar; `reset()` pede um token novo (cada token vale uma vez).
 */
export function useTurnstile() {
  const [token, setToken] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);
  const onToken = useCallback((value: string | null) => setToken(value), []);

  const reset = useCallback(() => {
    setToken(null);
    setGeneration((g) => g + 1);
  }, []);

  const widget = TURNSTILE_SITE_KEY ? <TurnstileWidget key={generation} onToken={onToken} /> : null;
  return { token, ready: !TURNSTILE_SITE_KEY || token !== null, widget, reset };
}

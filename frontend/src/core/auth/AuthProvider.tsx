import { useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { api, call } from "../api/client";
import { applyUserLanguage, onLanguageChosen } from "../i18n";
import { onSessionChange, refreshSession, type Session, type SessionUser, setSession } from "./session";

type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; user: SessionUser };

type LoginInput = { email: string; password: string; turnstileToken: string | null };

type AuthContextValue = {
  slug: string;
  state: AuthState;
  login: (input: LoginInput) => Promise<SessionUser>;
  logout: () => Promise<void>;
  /** Para rotas que devolvem uma sessão nova (ex.: troca de senha). */
  startSession: (session: Session) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ slug, children }: { slug: string; children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const queryClient = useQueryClient();

  useEffect(() => {
    const stop = onSessionChange(slug, (session) => {
      if (session?.user.locale) applyUserLanguage(session.user.locale); // idioma da conta
      setState(session ? { status: "authenticated", user: session.user } : { status: "anonymous" });
    });
    // Ao abrir o app, tenta recuperar a sessão pelo cookie (sem pedir senha de novo).
    void refreshSession(slug).then((session) => {
      if (!session) setState({ status: "anonymous" });
    });
    return stop;
  }, [slug]);

  // Quem está logado e troca o idioma no seletor: salva na conta (vale em outros aparelhos).
  const loggedIn = state.status === "authenticated";
  useEffect(() => {
    if (!loggedIn) return;
    return onLanguageChosen((locale) => {
      void call(() =>
        api.PATCH("/t/{slug}/auth/me", { params: { path: { slug } }, body: { locale } }),
      ).then(
        (user) => setState({ status: "authenticated", user }),
        () => undefined, // sem internet: a troca vale neste aparelho; tenta de novo na próxima
      );
    });
  }, [loggedIn, slug]);

  const startSession = useCallback((session: Session) => setSession(slug, session), [slug]);

  const login = useCallback(
    async ({ email, password, turnstileToken }: LoginInput) => {
      const session = await call(() =>
        api.POST("/t/{slug}/auth/login", {
          params: { path: { slug } },
          body: { email, password, turnstile_token: turnstileToken },
        }),
      );
      setSession(slug, session);
      return session.user;
    },
    [slug],
  );

  const logout = useCallback(async () => {
    try {
      await api.POST("/t/{slug}/auth/logout", { params: { path: { slug } } });
    } finally {
      setSession(slug, null);
      // Nada do usuário anterior fica em cache (os dados públicos do salão podem ficar).
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== "tenant" });
    }
  }, [slug, queryClient]);

  return (
    <AuthContext.Provider value={{ slug, state, login, logout, startSession }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth fora do AuthProvider");
  return context;
}

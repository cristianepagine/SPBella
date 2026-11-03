import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { api, call } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
import { Card, FormError, SubmitButton, TextField } from "../../components/form";
import { useTurnstile } from "../../components/Turnstile";
import { salonPath } from "../../paths";

/** Lê o token do link (#token=...) e o tira da barra de endereço, para não ficar no histórico. */
function takeTokenFromUrl(): string | null {
  const token = new URLSearchParams(window.location.hash.slice(1)).get("token");
  if (token) {
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }
  return token;
}

export function ResetPasswordPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const turnstile = useTurnstile();
  const [token] = useState(takeTokenFromUrl);
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const toLogin = (
    <Link
      to={salonPath.login(slug)}
      className="mt-4 block text-center font-medium text-brand-700 underline"
    >
      {t("auth.backToLogin")}
    </Link>
  );

  if (!token) {
    return (
      <Card title={t("auth.resetTitle")}>
        <p role="alert">{t("auth.resetMissingToken")}</p>
        {toLogin}
      </Card>
    );
  }

  if (done) {
    return (
      <Card title={t("auth.resetTitle")}>
        <p role="status">{t("auth.resetDone")}</p>
        {toLogin}
      </Card>
    );
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await call(() =>
        api.POST("/t/{slug}/auth/reset-password", {
          params: { path: { slug } },
          body: { token: token!, new_password: newPassword, turnstile_token: turnstile.token },
        }),
      );
      setDone(true);
    } catch (e) {
      setError(e);
      turnstile.reset();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title={t("auth.resetTitle")}>
      <form onSubmit={submit} noValidate>
        <FormError error={error} />
        <TextField
          label={t("auth.newPassword")}
          hint={t("auth.newPasswordHint")}
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />
        {turnstile.widget}
        <SubmitButton busy={busy} disabled={!turnstile.ready}>
          {t("auth.submitChange")}
        </SubmitButton>
      </form>
    </Card>
  );
}

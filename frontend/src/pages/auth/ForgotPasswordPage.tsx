import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { api, call } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
import { Card, FormError, SubmitButton, TextField } from "../../components/form";
import { useTurnstile } from "../../components/Turnstile";
import { salonPath } from "../../paths";

export function ForgotPasswordPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const turnstile = useTurnstile();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await call(() =>
        api.POST("/t/{slug}/auth/forgot-password", {
          params: { path: { slug } },
          body: { email, turnstile_token: turnstile.token },
        }),
      );
      setSent(true);
    } catch (e) {
      setError(e);
      turnstile.reset();
    } finally {
      setBusy(false);
    }
  }

  const back = (
    <Link
      to={salonPath.login(slug)}
      className="mt-4 block text-center font-medium text-brand-700 underline"
    >
      {t("auth.backToLogin")}
    </Link>
  );

  if (sent) {
    return (
      <Card title={t("auth.forgotTitle")}>
        <p role="status" className="text-slate-700">
          {t("auth.forgotSent")}
        </p>
        {back}
      </Card>
    );
  }

  return (
    <Card title={t("auth.forgotTitle")}>
      <p className="mb-4 text-slate-600">{t("auth.forgotIntro")}</p>
      <form onSubmit={submit} noValidate>
        <FormError error={error} />
        <TextField
          label={t("auth.email")}
          type="email"
          inputMode="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        {turnstile.widget}
        <SubmitButton busy={busy} disabled={!turnstile.ready}>
          {t("auth.submitForgot")}
        </SubmitButton>
      </form>
      {back}
    </Card>
  );
}

import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useLocation, useNavigate } from "react-router";

import { useAuth } from "../../auth/AuthProvider";
import { Card, FormError, SubmitButton, TextField } from "../../components/form";
import { useTurnstile } from "../../components/Turnstile";
import { salonPath } from "../../paths";

export function LoginPage() {
  const { t } = useTranslation();
  const { slug, state, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const turnstile = useTurnstile();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (state.status === "authenticated") return <Navigate to={salonPath.app(slug)} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login({ email, password, turnstileToken: turnstile.token });
      const from = (location.state as { from?: string } | null)?.from;
      if (user.must_change_password) navigate(salonPath.changePassword(slug));
      else if (from) navigate(from, { replace: true });
      else navigate(salonPath.app(slug), { replace: true });
    } catch (e) {
      setError(e);
      turnstile.reset();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title={t("auth.loginTitle")}>
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
        <TextField
          label={t("auth.password")}
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {turnstile.widget}
        <SubmitButton busy={busy} disabled={!turnstile.ready}>
          {busy ? t("auth.loggingIn") : t("auth.submitLogin")}
        </SubmitButton>
      </form>
      <Link
        to={salonPath.forgotPassword(slug)}
        className="mt-4 block text-center font-medium text-brand-700 underline"
      >
        {t("auth.forgotLink")}
      </Link>
    </Card>
  );
}

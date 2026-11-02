import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { api, call } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
import { Card, FormError, SubmitButton, TextField } from "../../components/form";
import { salonPath } from "../../paths";

export function ChangePasswordPage() {
  const { t } = useTranslation();
  const { slug, state, startSession } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const mustChange = state.status === "authenticated" && state.user.must_change_password;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await call(() =>
        api.POST("/t/{slug}/auth/change-password", {
          params: { path: { slug } },
          body: { current_password: currentPassword, new_password: newPassword },
        }),
      );
      startSession(session);
      navigate(salonPath.app(slug), { replace: true });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title={t("auth.changeTitle")}>
      <p className="mb-4 text-slate-600">
        {mustChange ? t("auth.changeIntroTemporary") : t("auth.changeIntro")}
      </p>
      <form onSubmit={submit} noValidate>
        <FormError error={error} />
        <TextField
          label={mustChange ? t("auth.temporaryPassword") : t("auth.currentPassword")}
          type="password"
          autoComplete="current-password"
          required
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
        />
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
        <SubmitButton busy={busy}>{t("auth.submitChange")}</SubmitButton>
      </form>
    </Card>
  );
}

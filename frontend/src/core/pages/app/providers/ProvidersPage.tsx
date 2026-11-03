import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { useCreateProvider, useProviders } from "../../../api/providers";
import { useAuth } from "../../../auth/AuthProvider";
import { Card, FormError, SubmitButton, TextField } from "../../../components/form";
import { PROVIDER_COLOR_CLASS } from "../../../layout/colors";
import { salonPath } from "../../../paths";

/** Profissionais (só o dono): quem atende, com jornada, serviços e folgas na ficha de cada um. */
export function ProvidersPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const providers = useProviders(slug);

  return (
    <div className="flex flex-col gap-4">
      <NewProvider />
      <Card title={t("providers.title")}>
        {providers.isPending && <p role="status">{t("auth.loading")}</p>}
        {providers.isError && <FormError error={providers.error} />}
        {providers.data?.length === 0 && <p className="text-slate-600">{t("providers.empty")}</p>}
        <ul className="divide-y divide-slate-100">
          {providers.data?.map((provider) => (
            <li key={provider.id}>
              <Link
                to={salonPath.provider(slug, provider.id)}
                className={`flex items-center gap-3 py-3 ${provider.is_active ? "" : "text-slate-400"}`}
              >
                <span className={`h-4 w-4 shrink-0 rounded-full ${PROVIDER_COLOR_CLASS[provider.color]}`} />
                <span className="flex-1">
                  <span className="block font-medium">{provider.name}</span>
                  <span className="block text-sm text-slate-500">
                    {provider.is_active
                      ? t("providers.summary", {
                          days: new Set(provider.working_hours.map((h) => h.weekday)).size,
                          services: provider.offering_ids.length,
                        })
                      : t("providers.inactive")}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function NewProvider() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const navigate = useNavigate();
  const create = useCreateProvider(slug);
  const [name, setName] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const created = await create.mutateAsync({ name }).catch(() => null);
    if (created) navigate(salonPath.provider(slug, created.id));
  }

  return (
    <Card title={t("providers.new")}>
      <form onSubmit={submit} noValidate>
        <FormError error={create.error} />
        <TextField
          label={t("providers.name")}
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <SubmitButton busy={create.isPending}>{t("providers.add")}</SubmitButton>
      </form>
    </Card>
  );
}

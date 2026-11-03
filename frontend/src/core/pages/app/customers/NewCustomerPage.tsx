import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { type ConsentPurpose, useCreateCustomer } from "../../../api/customers";
import { useAuth } from "../../../auth/AuthProvider";
import {
  Card,
  CheckboxField,
  FormError,
  SubmitButton,
  TextField,
} from "../../../components/form";
import { salonPath } from "../../../paths";
import { LocaleSelect, PURPOSES } from "./shared";

/** Cadastro de cliente. A recepção marca com o que o cliente concordou (LGPD). */
export function NewCustomerPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const navigate = useNavigate();
  const create = useCreateCustomer(slug);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [locale, setLocale] = useState<"pt-BR" | "es" | null>(null);
  const [consents, setConsents] = useState<ConsentPurpose[]>([]);

  function toggle(purpose: ConsentPurpose, on: boolean) {
    setConsents((current) => (on ? [...current, purpose] : current.filter((p) => p !== purpose)));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const created = await create
      .mutateAsync({ name, phone, email: email || null, locale, consents })
      .catch(() => null);
    if (created) navigate(salonPath.customer(slug, created.id), { replace: true });
  }

  return (
    <Card title={t("customers.new")}>
      <form onSubmit={submit} noValidate>
        <FormError error={create.error} />
        <TextField
          label={t("customers.fields.name")}
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <TextField
          label={t("customers.fields.phone")}
          hint={t("customers.phoneHint")}
          type="tel"
          inputMode="tel"
          autoComplete="off"
          required
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        <TextField
          label={t("customers.fields.emailOptional")}
          type="email"
          inputMode="email"
          autoComplete="off"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <LocaleSelect value={locale} onChange={setLocale} />

        <fieldset className="mb-4 rounded-xl border border-slate-200 p-4">
          <legend className="px-1 font-medium">{t("consent.title")}</legend>
          <p className="mb-3 text-sm text-slate-600">{t("consent.intro")}</p>
          {PURPOSES.map((purpose) => (
            <CheckboxField
              key={purpose}
              label={t(`consent.ask.${purpose}`)}
              checked={consents.includes(purpose)}
              onChange={(on) => toggle(purpose, on)}
            />
          ))}
        </fieldset>

        <SubmitButton busy={create.isPending}>{t("customers.save")}</SubmitButton>
      </form>
    </Card>
  );
}

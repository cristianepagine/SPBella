import type { InputHTMLAttributes, ReactNode } from "react";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";

export function TextField({
  label,
  hint,
  ...input
}: { label: string; hint?: string } & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className="mb-4">
      <label htmlFor={id} className="mb-1 block font-medium text-slate-800">
        {label}
      </label>
      <input
        id={id}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-base focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
        {...input}
      />
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-sm text-slate-500">
          {hint}
        </p>
      )}
    </div>
  );
}

export function SubmitButton({ busy, children, ...rest }: { busy?: boolean; children: ReactNode } & {
  disabled?: boolean;
}) {
  return (
    <button
      type="submit"
      className="mt-2 w-full rounded-xl bg-brand-700 px-4 py-3 font-medium text-white active:bg-brand-900 disabled:opacity-60"
      disabled={busy || rest.disabled}
    >
      {children}
    </button>
  );
}

/** Mostra o erro da API traduzido. Senha fraca ganha o motivo específico. */
export function FormError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;

  const apiError = error instanceof ApiError ? error : new ApiError(0, "unknown");
  const reason = apiError.fields[0]?.code;
  const general = t(`errors.${apiError.code}`, { defaultValue: t("errors.unknown") });
  let message = general;
  if (apiError.code === "weak_password" && reason) {
    message = t(`errors.weakPassword.${reason}`, { defaultValue: t("errors.weak_password") });
  } else if (apiError.code === "validation_error" && reason) {
    // ex.: errors.fields.invalid_phone; sem tradução específica, fica a mensagem geral
    message = t(`errors.fields.${reason}`, { defaultValue: general });
  }

  return (
    <p role="alert" className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-red-800">
      {message}
    </p>
  );
}

export function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm">
      <h1 className="mb-4 text-2xl font-bold text-brand-900">{title}</h1>
      {children}
    </section>
  );
}

export function SelectField({
  label,
  hint,
  value,
  onChange,
  options,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  const id = useId();
  return (
    <div className="mb-4">
      <label htmlFor={id} className="mb-1 block font-medium text-slate-800">
        {label}
      </label>
      <select
        id={id}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-sm text-slate-500">
          {hint}
        </p>
      )}
    </div>
  );
}

export function CheckboxField({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="mb-3 flex items-start gap-3">
      <input
        type="checkbox"
        className="mt-1 h-5 w-5 shrink-0 accent-brand-700"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

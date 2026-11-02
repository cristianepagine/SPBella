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
  const reason = apiError.code === "weak_password" ? apiError.fields[0]?.code : undefined;
  const message = reason
    ? t(`errors.weakPassword.${reason}`, { defaultValue: t("errors.weak_password") })
    : t(`errors.${apiError.code}`, { defaultValue: t("errors.unknown") });

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

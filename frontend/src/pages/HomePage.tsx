import { useTranslation } from "react-i18next";

import { useHealth } from "../api/health";

export function HomePage() {
  const { t } = useTranslation();
  const health = useHealth();

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-bold text-brand-900">{t("app.name")}</h1>
      <p className="mt-1 text-slate-600">{t("app.tagline")}</p>

      <div className="mt-6" role="status">
        {health.isPending && <p>{t("status.checking")}</p>}
        {health.isSuccess && (
          <>
            <p className="font-medium text-emerald-700">{t("status.ok")}</p>
            <p className="mt-1 text-sm text-slate-500">
              {t("status.version", { version: health.data.version })}
            </p>
          </>
        )}
        {health.isError && (
          <>
            <p className="font-medium text-red-700">{t("status.offline")}</p>
            <button
              type="button"
              className="mt-4 w-full rounded-xl bg-brand-700 px-4 py-3 font-medium text-white active:bg-brand-900"
              onClick={() => void health.refetch()}
            >
              {t("status.retry")}
            </button>
          </>
        )}
      </div>
    </section>
  );
}

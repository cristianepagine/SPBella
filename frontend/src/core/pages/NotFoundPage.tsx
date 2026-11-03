import { useTranslation } from "react-i18next";
import { Link } from "react-router";

export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <section className="rounded-2xl bg-white p-6 text-center shadow-sm">
      <h1 className="text-xl font-bold">{t("notFound.title")}</h1>
      <Link className="mt-4 inline-block font-medium text-brand-700 underline" to="/">
        {t("notFound.back")}
      </Link>
    </section>
  );
}

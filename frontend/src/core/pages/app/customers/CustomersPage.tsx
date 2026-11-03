import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { PAGE_SIZE, useCustomers } from "../../../api/customers";
import { useDebounced } from "../../../hooks/useDebounced";
import { useAuth } from "../../../auth/AuthProvider";
import { Card, FormError } from "../../../components/form";
import { salonPath } from "../../../paths";

/** Clientes em ordem alfabética, com busca por nome (sem acento) ou por telefone. */
export function CustomersPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const query = useDebounced(search);
  const customers = useCustomers(slug, page, query);
  const total = customers.data?.total ?? 0;

  return (
    <Card title={t("customers.title")}>
      <Link
        to={salonPath.newCustomer(slug)}
        className="mb-4 block rounded-xl bg-brand-700 px-4 py-3 text-center font-medium text-white"
      >
        {t("customers.new")}
      </Link>

      <label className="mb-4 block">
        <span className="mb-1 block font-medium text-slate-800">{t("customers.search")}</span>
        <input
          type="search"
          inputMode="search"
          autoComplete="off"
          className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3"
          placeholder={t("customers.searchPlaceholder")}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
        />
      </label>

      {customers.isPending && <p role="status">{t("auth.loading")}</p>}
      {customers.isError && <FormError error={customers.error} />}
      {customers.data && customers.data.items.length === 0 && (
        <p className="text-slate-600">
          {query.trim() ? t("customers.noResults", { q: query.trim() }) : t("customers.empty")}
        </p>
      )}
      {customers.data && customers.data.items.length > 0 && (
        <>
          <ul className="divide-y divide-slate-100">
            {customers.data.items.map((customer) => (
              <li key={customer.id}>
                <Link to={salonPath.customer(slug, customer.id)} className="block py-3">
                  <span className="block font-medium">{customer.name}</span>
                  <span className="block text-sm text-slate-500">{customer.phone_display}</span>
                </Link>
              </li>
            ))}
          </ul>
          {total > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between gap-2 text-sm">
              <button
                type="button"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-40"
              >
                {t("customers.previous")}
              </button>
              <span className="text-slate-500">
                {t("customers.pageOf", { page: page + 1, pages: Math.ceil(total / PAGE_SIZE) })}
              </span>
              <button
                type="button"
                disabled={(page + 1) * PAGE_SIZE >= total}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-40"
              >
                {t("customers.next")}
              </button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}

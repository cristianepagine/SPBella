import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, call } from "./client";
import type { components } from "./schema";

export type Customer = components["schemas"]["CustomerOut"];
export type CustomerSummary = components["schemas"]["CustomerSummary"];
export type NewCustomer = components["schemas"]["NewCustomer"];
export type CustomerChanges = components["schemas"]["CustomerChanges"];
export type ConsentPurpose = components["schemas"]["ConsentChange"]["purpose"];
export type AuditEntry = components["schemas"]["AuditEntryOut"];

export const PAGE_SIZE = 20;

export function useCustomers(slug: string, page: number, search = "") {
  const q = search.trim();
  return useQuery({
    queryKey: ["customers", slug, page, q],
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/customers", {
          params: {
            path: { slug },
            query: { limit: PAGE_SIZE, offset: page * PAGE_SIZE, ...(q ? { q } : {}) },
          },
        }),
      ),
    placeholderData: (previous) => previous, // mantém a lista na tela enquanto busca
  });
}

/** Clientes com este telefone (para avisar de cadastro repetido). Só busca com 8+ dígitos. */
export function useCustomersWithPhone(slug: string, phone: string) {
  const digits = phone.replace(/\D/g, "");
  return useQuery({
    queryKey: ["customers-phone", slug, digits],
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/customers", {
          params: { path: { slug }, query: { q: digits, limit: 5 } },
        }),
      ),
    enabled: digits.length >= 8,
  });
}

export function useCustomer(slug: string, id: string) {
  return useQuery({
    queryKey: ["customer", slug, id],
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/customers/{customer_id}", {
          params: { path: { slug, customer_id: id } },
        }),
      ),
    // Cada consulta da ficha entra no log de auditoria: não buscar de novo sem necessidade.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

function useCustomerCache(slug: string) {
  const queryClient = useQueryClient();
  return (customer: Customer) => {
    queryClient.setQueryData(["customer", slug, customer.id], customer);
    void queryClient.invalidateQueries({ queryKey: ["customers", slug] });
    void queryClient.invalidateQueries({ queryKey: ["audit", slug, customer.id] });
  };
}

export function useCreateCustomer(slug: string) {
  const store = useCustomerCache(slug);
  return useMutation({
    mutationFn: (body: NewCustomer) =>
      call(() => api.POST("/t/{slug}/customers", { params: { path: { slug } }, body })),
    onSuccess: store,
  });
}

export function useUpdateCustomer(slug: string, id: string) {
  const store = useCustomerCache(slug);
  return useMutation({
    mutationFn: (body: CustomerChanges) =>
      call(() =>
        api.PATCH("/t/{slug}/customers/{customer_id}", {
          params: { path: { slug, customer_id: id } },
          body,
        }),
      ),
    onSuccess: store,
  });
}

export function useChangeConsent(slug: string, id: string) {
  const store = useCustomerCache(slug);
  return useMutation({
    mutationFn: (body: { purpose: ConsentPurpose; granted: boolean }) =>
      call(() =>
        api.POST("/t/{slug}/customers/{customer_id}/consents", {
          params: { path: { slug, customer_id: id } },
          body,
        }),
      ),
    onSuccess: store,
  });
}

export function useAudit(slug: string, entityId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["audit", slug, entityId],
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/audit", {
          params: { path: { slug }, query: { entity_id: entityId, limit: 100 } },
        }),
      ),
    enabled,
  });
}

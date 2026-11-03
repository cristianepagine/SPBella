import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Language } from "../i18n";
import { api, call } from "./client";
import type { components } from "./schema";

export type TenantSettings = components["schemas"]["TenantSettings"];

export function useSettings(slug: string) {
  return useQuery({
    queryKey: ["settings", slug],
    queryFn: () => call(() => api.GET("/t/{slug}/settings", { params: { path: { slug } } })),
  });
}

export function useSaveSettings(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; locale?: Language; timezone?: string }) =>
      call(() => api.PATCH("/t/{slug}/settings", { params: { path: { slug } }, body })),
    onSuccess: (saved) => {
      queryClient.setQueryData(["settings", slug], saved);
      // nome, idioma e fuso também aparecem no cabeçalho e na página pública
      void queryClient.invalidateQueries({ queryKey: ["tenant", slug] });
    },
  });
}

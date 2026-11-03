import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, call } from "../../core/api/client";
import type { components } from "../../core/api/schema";

export type Service = components["schemas"]["ServiceOut"];

const key = (slug: string) => ["services", slug];

export function useServices(slug: string) {
  return useQuery({
    queryKey: key(slug),
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/services", {
          params: { path: { slug }, query: { include_inactive: true } },
        }),
      ),
  });
}

export function useCreateService(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; duration_min: number; price_minor: number }) =>
      call(() => api.POST("/t/{slug}/services", { params: { path: { slug } }, body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(slug) }),
  });
}

export function useChangeService(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: string;
      name?: string;
      duration_min?: number;
      price_minor?: number;
      is_active?: boolean;
    }) =>
      call(() =>
        api.PATCH("/t/{slug}/services/{service_id}", {
          params: { path: { slug, service_id: id } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(slug) }),
  });
}

import { useQuery } from "@tanstack/react-query";

import { api, ApiError, call } from "./client";

export function useTenant(slug: string) {
  return useQuery({
    queryKey: ["tenant", slug],
    queryFn: () => call(() => api.GET("/t/{slug}", { params: { path: { slug } } })),
    staleTime: 5 * 60_000,
    // Salão inexistente não melhora tentando de novo.
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 1,
  });
}

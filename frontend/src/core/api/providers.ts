import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, call } from "./client";
import type { components } from "./schema";

export type Provider = components["schemas"]["ProviderOut"];
export type WorkingRange = components["schemas"]["WorkingRange"];
export type ProviderColor = Provider["color"];
export type TimeOff = components["schemas"]["TimeOffOut"];
export type Offering = components["schemas"]["OfferingOut"];

const listKey = (slug: string) => ["providers", slug];

export function useProviders(slug: string) {
  return useQuery({
    queryKey: listKey(slug),
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/providers", {
          params: { path: { slug }, query: { include_inactive: true } },
        }),
      ),
  });
}

export function useOfferings(slug: string) {
  return useQuery({
    queryKey: ["offerings", slug],
    queryFn: () => call(() => api.GET("/t/{slug}/offerings", { params: { path: { slug } } })),
  });
}

function useRefresh(slug: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: listKey(slug) });
}

export function useCreateProvider(slug: string) {
  const refresh = useRefresh(slug);
  return useMutation({
    mutationFn: (body: { name: string }) =>
      call(() => api.POST("/t/{slug}/providers", { params: { path: { slug } }, body })),
    onSuccess: refresh,
  });
}

export function useChangeProvider(slug: string, id: string) {
  const refresh = useRefresh(slug);
  return useMutation({
    mutationFn: (body: components["schemas"]["ProviderChanges"]) =>
      call(() =>
        api.PATCH("/t/{slug}/providers/{provider_id}", {
          params: { path: { slug, provider_id: id } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

export function useSetWorkingHours(slug: string, id: string) {
  const refresh = useRefresh(slug);
  return useMutation({
    mutationFn: (ranges: WorkingRange[]) =>
      call(() =>
        api.PUT("/t/{slug}/providers/{provider_id}/working-hours", {
          params: { path: { slug, provider_id: id } },
          body: { ranges },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useSetProviderOfferings(slug: string, id: string) {
  const refresh = useRefresh(slug);
  return useMutation({
    mutationFn: (offering_ids: string[]) =>
      call(() =>
        api.PUT("/t/{slug}/providers/{provider_id}/offerings", {
          params: { path: { slug, provider_id: id } },
          body: { offering_ids },
        }),
      ),
    onSuccess: refresh,
  });
}

const timeOffKey = (slug: string, id: string) => ["time-off", slug, id];

export function useTimeOff(slug: string, id: string) {
  return useQuery({
    queryKey: timeOffKey(slug, id),
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/providers/{provider_id}/time-off", {
          params: { path: { slug, provider_id: id } },
        }),
      ),
  });
}

export function useAddTimeOff(slug: string, id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { start_date: string; end_date: string; reason?: string | null }) =>
      call(() =>
        api.POST("/t/{slug}/providers/{provider_id}/time-off", {
          params: { path: { slug, provider_id: id } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: timeOffKey(slug, id) }),
  });
}

export function useDeleteTimeOff(slug: string, id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (timeOffId: string) =>
      call(() =>
        api.DELETE("/t/{slug}/providers/{provider_id}/time-off/{time_off_id}", {
          params: { path: { slug, provider_id: id, time_off_id: timeOffId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: timeOffKey(slug, id) }),
  });
}

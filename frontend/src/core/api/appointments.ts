import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AppointmentStatus } from "./agenda";
import { api, call } from "./client";
import type { components } from "./schema";

function useRefreshAgenda(slug: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["agenda", slug] }),
      queryClient.invalidateQueries({ queryKey: ["availability", slug] }),
    ]);
}

export type NewAppointment = components["schemas"]["NewAppointment"];

export function useCreateAppointment(slug: string) {
  const refresh = useRefreshAgenda(slug);
  return useMutation({
    mutationFn: (body: NewAppointment) =>
      call(() => api.POST("/t/{slug}/appointments", { params: { path: { slug } }, body })),
    onSuccess: refresh,
  });
}

export function useMoveAppointment(slug: string) {
  const refresh = useRefreshAgenda(slug);
  return useMutation({
    mutationFn: ({
      id,
      allow_outside_hours = false,
      ...body
    }: {
      id: string;
      starts_at?: string;
      provider_id?: string;
      allow_outside_hours?: boolean;
    }) =>
      call(() =>
        api.PATCH("/t/{slug}/appointments/{appointment_id}", {
          params: { path: { slug, appointment_id: id } },
          body: { ...body, allow_outside_hours },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useChangeAppointmentStatus(slug: string) {
  const refresh = useRefreshAgenda(slug);
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: AppointmentStatus }) =>
      call(() =>
        api.POST("/t/{slug}/appointments/{appointment_id}/status", {
          params: { path: { slug, appointment_id: id } },
          body: { status },
        }),
      ),
    onSuccess: refresh,
  });
}

export type Availability = components["schemas"]["AvailabilityOut"];

export function useAvailability(slug: string, offeringId?: string, day?: string, providerId?: string) {
  return useQuery({
    queryKey: ["availability", slug, offeringId, day, providerId ?? null],
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/availability", {
          params: {
            path: { slug },
            query: {
              offering_id: offeringId!,
              date: day!,
              ...(providerId ? { provider_id: providerId } : {}),
            },
          },
        }),
      ),
    enabled: Boolean(offeringId && day),
  });
}

export type NewBlock = components["schemas"]["NewBlock"];
export type CreatedBlock = components["schemas"]["BlockOut"];

export function useCreateBlock(slug: string) {
  const refresh = useRefreshAgenda(slug);
  return useMutation({
    mutationFn: (body: NewBlock) =>
      call(() => api.POST("/t/{slug}/blocks", { params: { path: { slug } }, body })),
    onSuccess: refresh,
  });
}

export function useDeleteBlock(slug: string) {
  const refresh = useRefreshAgenda(slug);
  return useMutation({
    mutationFn: (id: string) =>
      call(() =>
        api.DELETE("/t/{slug}/blocks/{block_id}", { params: { path: { slug, block_id: id } } }),
      ),
    onSuccess: refresh,
  });
}

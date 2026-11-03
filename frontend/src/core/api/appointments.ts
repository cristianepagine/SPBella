import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { AppointmentStatus } from "./agenda";
import { api, call } from "./client";
import type { components } from "./schema";

function useRefreshAgenda(slug: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["agenda", slug] });
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

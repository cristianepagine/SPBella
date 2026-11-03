import { useQuery } from "@tanstack/react-query";

import { api, call } from "./client";
import type { components } from "./schema";

export type Agenda = components["schemas"]["AgendaOut"];
export type AgendaAppointment = components["schemas"]["AgendaAppointment"];
export type AgendaProvider = components["schemas"]["AgendaProvider"];
export type AppointmentStatus = AgendaAppointment["status"];

export function useAgenda(slug: string, start: string, days: number, providerId?: string) {
  return useQuery({
    queryKey: ["agenda", slug, start, days, providerId ?? null],
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/agenda", {
          params: {
            path: { slug },
            query: { start, days, ...(providerId ? { provider_id: providerId } : {}) },
          },
        }),
      ),
    placeholderData: (previous) => previous, // não pisca ao trocar de dia
  });
}

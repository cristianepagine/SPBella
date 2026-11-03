import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, call } from "./client";
import type { components } from "./schema";

/** Página pública de agendamento (sem login). */
export type BookingCatalog = components["schemas"]["Catalog"];
export type PublicOffering = components["schemas"]["PublicOffering"];
export type PublicBooking = components["schemas"]["PublicBooking"];
export type BookingConfirmation = components["schemas"]["BookingConfirmation"];

export function useBookingCatalog(slug: string) {
  return useQuery({
    queryKey: ["booking-catalog", slug],
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/booking/catalog", { params: { path: { slug } } }),
      ),
    staleTime: 5 * 60_000,
  });
}

export function usePublicAvailability(
  slug: string,
  offeringId?: string,
  day?: string,
  providerId?: string,
) {
  return useQuery({
    queryKey: [
      "booking-availability",
      slug,
      offeringId,
      day,
      providerId ?? null,
    ],
    queryFn: () =>
      call(() =>
        api.GET("/t/{slug}/booking/availability", {
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

export function useBook(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PublicBooking) =>
      call(() =>
        api.POST("/t/{slug}/booking", { params: { path: { slug } }, body }),
      ),
    // marcou ou perdeu o horário para outra pessoa: os horários livres mudaram
    onSettled: () =>
      queryClient.invalidateQueries({
        queryKey: ["booking-availability", slug],
      }),
  });
}

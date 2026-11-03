import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Role } from "../auth/permissions";
import { api, call } from "./client";
import type { components } from "./schema";

export type TeamMember = components["schemas"]["TeamMember"];
export type MemberWithPassword = components["schemas"]["MemberWithPassword"];

const key = (slug: string) => ["team", slug];

export function useTeam(slug: string) {
  return useQuery({
    queryKey: key(slug),
    queryFn: () => call(() => api.GET("/t/{slug}/team", { params: { path: { slug } } })),
  });
}

export function useAddMember(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; email: string; role: Role }) =>
      call(() => api.POST("/t/{slug}/team", { params: { path: { slug } }, body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(slug) }),
  });
}

export function useChangeMember(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; role?: Role; is_active?: boolean }) =>
      call(() =>
        api.PATCH("/t/{slug}/team/{member_id}", {
          params: { path: { slug, member_id: id } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(slug) }),
  });
}

export function useResetMemberPassword(slug: string) {
  return useMutation({
    mutationFn: (id: string) =>
      call(() =>
        api.POST("/t/{slug}/team/{member_id}/reset-password", {
          params: { path: { slug, member_id: id } },
        }),
      ),
  });
}

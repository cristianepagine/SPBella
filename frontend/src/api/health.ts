import { useQuery } from "@tanstack/react-query";

import { api, ApiError, toApiError } from "./client";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      try {
        const result = await api.GET("/health");
        if (!result.data) throw toApiError(result.response.status, result.error);
        return result.data;
      } catch (e) {
        if (e instanceof ApiError) throw e;
        throw new ApiError(0, "network_error");
      }
    },
  });
}

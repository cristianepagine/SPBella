import { useQuery } from "@tanstack/react-query";

import { api, call } from "./client";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => call(() => api.GET("/health")),
  });
}

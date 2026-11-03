import type { components } from "../api/schema";
import { useAuth } from "./AuthProvider";

export type Permission = components["schemas"]["Permission"];
export type Role = components["schemas"]["UserOut"]["role"];

/**
 * `can("team.manage")`: o usuário logado tem a permissão? Serve só para mostrar ou esconder
 * coisas na tela; quem decide de verdade é o servidor (403).
 */
export function useCan(): (permission: Permission) => boolean {
  const { state } = useAuth();
  const permissions = state.status === "authenticated" ? state.user.permissions : [];
  return (permission) => permissions.includes(permission);
}

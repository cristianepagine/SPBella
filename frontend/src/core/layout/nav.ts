import { createContext, useContext } from "react";

import type { Permission } from "../auth/permissions";
import { salonPath } from "../paths";

/** Item do menu da equipe. Sem `permission`, aparece para todo mundo logado. */
export type NavItem = {
  id: string;
  labelKey: string;
  to: (slug: string) => string;
  permission?: Permission;
  /** Só fica "ativo" no endereço exato (para o Início não acender em todas as páginas). */
  end?: boolean;
};

/** Itens do core. A vertical acrescenta os seus em App.tsx. */
export const CORE_NAV: NavItem[] = [
  { id: "home", labelKey: "nav.home", to: salonPath.app, end: true },
  {
    id: "customers",
    labelKey: "nav.customers",
    to: salonPath.customers,
    permission: "customers.manage",
  },
  { id: "team", labelKey: "nav.team", to: salonPath.team, permission: "team.manage" },
  {
    id: "settings",
    labelKey: "nav.settings",
    to: salonPath.settings,
    permission: "settings.manage",
  },
];

export const NavContext = createContext<NavItem[]>(CORE_NAV);

export function useNavItems(): NavItem[] {
  return useContext(NavContext);
}

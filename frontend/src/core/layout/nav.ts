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
  /** Posição no menu (menor primeiro). O core usa 0, 20, 80, 90; a vertical encaixa os seus. */
  order: number;
};

/** Itens do core. A vertical acrescenta os seus em App.tsx. */
export const CORE_NAV: NavItem[] = [
  { id: "home", labelKey: "nav.home", to: salonPath.app, end: true, order: 0 },
  {
    id: "agenda",
    labelKey: "nav.agenda",
    to: salonPath.agenda,
    permission: "agenda.view_own",
    order: 10,
  },
  {
    id: "customers",
    labelKey: "nav.customers",
    to: salonPath.customers,
    permission: "customers.manage",
    order: 20,
  },
  {
    id: "providers",
    labelKey: "nav.providers",
    to: salonPath.providers,
    permission: "providers.manage",
    order: 40,
  },
  { id: "team", labelKey: "nav.team", to: salonPath.team, permission: "team.manage", order: 80 },
  {
    id: "settings",
    labelKey: "nav.settings",
    to: salonPath.settings,
    permission: "settings.manage",
    order: 90,
  },
];

export const NavContext = createContext<NavItem[]>(CORE_NAV);

export function useNavItems(): NavItem[] {
  return useContext(NavContext);
}

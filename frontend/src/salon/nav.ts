import type { NavItem } from "../core/layout/nav";

export const salonServicesPath = (slug: string) => `/${slug}/app/services`;

/** Itens do menu da equipe que só existem no salão. */
export const SALON_NAV: NavItem[] = [
  {
    id: "services",
    labelKey: "nav.services",
    to: salonServicesPath,
    permission: "catalog.manage",
    order: 30,
  },
];

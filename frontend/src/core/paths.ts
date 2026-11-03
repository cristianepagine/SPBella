/** Endereços das páginas de um tenant (salão). Sempre absolutos (evita surpresas com rotas aninhadas). */
export const salonPath = {
  home: (slug: string) => `/${slug}`,
  login: (slug: string) => `/${slug}/login`,
  app: (slug: string) => `/${slug}/app`,
  team: (slug: string) => `/${slug}/app/team`,
  settings: (slug: string) => `/${slug}/app/settings`,
  customers: (slug: string) => `/${slug}/app/customers`,
  newCustomer: (slug: string) => `/${slug}/app/customers/new`,
  customer: (slug: string, id: string) => `/${slug}/app/customers/${id}`,
  providers: (slug: string) => `/${slug}/app/providers`,
  provider: (slug: string, id: string) => `/${slug}/app/providers/${id}`,
  changePassword: (slug: string) => `/${slug}/change-password`,
  forgotPassword: (slug: string) => `/${slug}/forgot-password`,
};

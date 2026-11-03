/** Endereços das páginas de um tenant (salão). Sempre absolutos (evita surpresas com rotas aninhadas). */
export const salonPath = {
  home: (slug: string) => `/${slug}`,
  login: (slug: string) => `/${slug}/login`,
  app: (slug: string) => `/${slug}/app`,
  team: (slug: string) => `/${slug}/app/team`,
  settings: (slug: string) => `/${slug}/app/settings`,
  changePassword: (slug: string) => `/${slug}/change-password`,
  forgotPassword: (slug: string) => `/${slug}/forgot-password`,
};

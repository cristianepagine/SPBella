import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import es from "./locales/es.json";
import ptBR from "./locales/pt-BR.json";

export const SUPPORTED_LANGUAGES = ["pt-BR", "es"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

const STORAGE_KEY = "spbella.language";

function savedLanguage(): Language | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "pt-BR" || saved === "es") return saved;
  } catch {
    // modo privado ou armazenamento bloqueado: segue sem preferência salva
  }
  return null;
}

/** Idioma salvo pelo usuário; senão, o do navegador (es-* → es); senão, português. */
export function detectLanguage(): Language {
  return savedLanguage() ?? (navigator.language?.toLowerCase().startsWith("es") ? "es" : "pt-BR");
}

function apply(language: Language): void {
  document.documentElement.lang = language;
  void i18n.changeLanguage(language);
}

/** Troca feita pelo usuário: vale também para as próximas visitas. */
export function changeLanguage(language: Language): void {
  try {
    localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // sem problema: a escolha vale só para esta visita
  }
  apply(language);
}

/** Idioma padrão do salão: só é aplicado se o usuário nunca escolheu um. */
export function applySalonLanguage(language: Language): void {
  if (savedLanguage() === null && i18n.language !== language) apply(language);
}

export function clearLanguagePreference(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // nada a limpar
  }
}

type Messages = { [key: string]: string | Messages };
export type LocaleOverrides = Record<Language, Messages>;

function merge(base: Messages, overrides: Messages): Messages {
  const result: Messages = { ...base };
  for (const [key, value] of Object.entries(overrides)) {
    const current = result[key];
    result[key] =
      typeof value === "object" && typeof current === "object" ? merge(current, value) : value;
  }
  return result;
}

/**
 * Inicia as traduções: textos do core (neutros, servem a qualquer negócio) + os da vertical,
 * que acrescentam chaves e trocam o vocabulário (ex.: "equipe" → "salão").
 */
export function setupI18n(vertical: LocaleOverrides): void {
  void i18n.use(initReactI18next).init({
    resources: {
      "pt-BR": { translation: merge(ptBR, vertical["pt-BR"]) },
      es: { translation: merge(es, vertical.es) },
    },
    lng: detectLanguage(),
    fallbackLng: "pt-BR",
    interpolation: { escapeValue: false }, // o React já escapa
  });
  document.documentElement.lang = i18n.language;
}

export default i18n;

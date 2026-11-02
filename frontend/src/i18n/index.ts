import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import es from "./locales/es.json";
import ptBR from "./locales/pt-BR.json";

export const SUPPORTED_LANGUAGES = ["pt-BR", "es"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

const STORAGE_KEY = "spbella.language";

/** Idioma salvo pelo usuário; senão, o do navegador (es-* → es); senão, português. */
export function detectLanguage(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "pt-BR" || saved === "es") return saved;
  } catch {
    // modo privado ou armazenamento bloqueado: segue sem preferência salva
  }
  return navigator.language?.toLowerCase().startsWith("es") ? "es" : "pt-BR";
}

export function changeLanguage(language: Language): void {
  try {
    localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // sem problema: a escolha vale só para esta visita
  }
  document.documentElement.lang = language;
  void i18n.changeLanguage(language);
}

void i18n.use(initReactI18next).init({
  resources: { "pt-BR": { translation: ptBR }, es: { translation: es } },
  lng: detectLanguage(),
  fallbackLng: "pt-BR",
  interpolation: { escapeValue: false }, // o React já escapa
});

document.documentElement.lang = i18n.language;

export default i18n;

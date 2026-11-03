import type { LocaleOverrides } from "../../core/i18n";
import es from "./es.json";
import ptBR from "./pt-BR.json";

/** Vocabulário e textos próprios do salão (sobrescrevem os textos neutros do core). */
export const salonLocales: LocaleOverrides = { "pt-BR": ptBR, es };

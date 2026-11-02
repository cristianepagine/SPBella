// Garante que pt-BR.json e es.json têm exatamente as mesmas chaves.
import { readFileSync } from "node:fs";

const load = (lang) =>
  JSON.parse(readFileSync(new URL(`../src/i18n/locales/${lang}.json`, import.meta.url), "utf8"));

const keys = (obj, prefix = "") =>
  Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );

const pt = new Set(keys(load("pt-BR")));
const es = new Set(keys(load("es")));
const missingInEs = [...pt].filter((k) => !es.has(k));
const missingInPt = [...es].filter((k) => !pt.has(k));

if (missingInEs.length || missingInPt.length) {
  if (missingInEs.length) console.error("Faltando em es.json:", missingInEs.join(", "));
  if (missingInPt.length) console.error("Faltando em pt-BR.json:", missingInPt.join(", "));
  process.exit(1);
}
console.log(`Traduções OK (${pt.size} chaves).`);

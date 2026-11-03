// Garante que pt-BR.json e es.json têm exatamente as mesmas chaves, no core e na vertical.
import { readFileSync } from "node:fs";

const DIRS = ["../src/core/i18n/locales", "../src/spbella/locales"];

const load = (dir, lang) =>
  JSON.parse(readFileSync(new URL(`${dir}/${lang}.json`, import.meta.url), "utf8"));

const keys = (obj, prefix = "") =>
  Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );

let failed = false;
for (const dir of DIRS) {
  const pt = new Set(keys(load(dir, "pt-BR")));
  const es = new Set(keys(load(dir, "es")));
  const missingInEs = [...pt].filter((k) => !es.has(k));
  const missingInPt = [...es].filter((k) => !pt.has(k));
  const where = dir.replace("../src/", "");
  if (missingInEs.length) console.error(`${where}: faltando em es.json:`, missingInEs.join(", "));
  if (missingInPt.length) console.error(`${where}: faltando em pt-BR.json:`, missingInPt.join(", "));
  if (missingInEs.length || missingInPt.length) failed = true;
  else console.log(`${where}: traduções OK (${pt.size} chaves).`);
}
if (failed) process.exit(1);

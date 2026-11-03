/**
 * SAL-03: "todos os textos vêm de arquivos de tradução".
 *
 * 1. Toda chave usada no código (t("..."), labelKey: "...") existe em pt-BR E em es.
 * 2. Nenhuma tela tem texto para o usuário escrito direto no JSX nem em atributos visíveis.
 */
import { describe, expect, it } from "vitest";

import coreEs from "./core/i18n/locales/es.json";
import corePt from "./core/i18n/locales/pt-BR.json";
import salonEs from "./salon/locales/es.json";
import salonPt from "./salon/locales/pt-BR.json";

const sources = import.meta.glob<string>(["./**/*.tsx", "./**/*.ts", "!./**/*.test.*", "!./test/**"], {
  query: "?raw",
  import: "default",
  eager: true,
});

type Tree = { [key: string]: string | Tree };

function has(tree: Tree, key: string): boolean {
  let node: string | Tree | undefined = tree;
  for (const part of key.split(".")) {
    if (typeof node !== "object") return false;
    node = node[part];
  }
  return typeof node === "string";
}

const catalogs = {
  "pt-BR": [corePt, salonPt] as Tree[],
  es: [coreEs, salonEs] as Tree[],
};

function usedKeys(): Map<string, string> {
  const found = new Map<string, string>();
  const patterns = [/\bt\(\s*"([a-zA-Z0-9_.]+)"/g, /labelKey:\s*"([a-zA-Z0-9_.]+)"/g];
  for (const [file, source] of Object.entries(sources)) {
    for (const pattern of patterns) {
      for (const match of source.matchAll(pattern)) found.set(match[1], file);
    }
  }
  return found;
}

describe("traduções", () => {
  it("encontra as chaves usadas no código", () => {
    expect(usedKeys().size).toBeGreaterThan(50);
  });

  it.each(Object.keys(catalogs))("toda chave usada existe em %s", (lang) => {
    const missing = [...usedKeys()]
      .filter(([key]) => !catalogs[lang as keyof typeof catalogs].some((tree) => has(tree, key)))
      .map(([key, file]) => `${key} (${file})`);

    expect(missing).toEqual([]);
  });

  it("nenhuma tela tem texto escrito direto no código", () => {
    // texto entre tags (ex.: <p>Olá</p>) e atributos que a pessoa vê ou o leitor de tela lê
    const jsxText = />\s*([^<>{}\n]*[A-Za-zÀ-ÿ]{2,}[^<>{}\n]*?)\s*</g;
    const visibleAttr = /\b(placeholder|title|alt|aria-label)="([^"]*[A-Za-zÀ-ÿ][^"]*)"/g;

    const offenders: string[] = [];
    for (const [file, source] of Object.entries(sources)) {
      if (!file.endsWith(".tsx")) continue;
      // só o que está dentro de JSX: descarta comentários e tipos genéricos (Promise<...>)
      const code = source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
      for (const match of code.matchAll(jsxText)) {
        const text = match[1].trim();
        if (/^[\w.]+$/.test(text) && !/\s/.test(text) && /[a-z][A-Z]|^[A-Z]/.test(text)) continue;
        if (/=>|[;=]|\)\s*$|^\w+\s*\(/.test(text)) continue; // código, não texto
        offenders.push(`${file}: "${text}"`);
      }
      for (const match of code.matchAll(visibleAttr)) offenders.push(`${file}: ${match[1]}="${match[2]}"`);
    }

    expect(offenders).toEqual([]);
  });
});

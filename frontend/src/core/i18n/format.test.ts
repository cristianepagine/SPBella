import { describe, expect, it } from "vitest";

import {
  currencyDigits,
  formatDateTime,
  formatLocale,
  formatMoney,
  timeZoneLabel,
} from "./format";

const clean = (text: string) => text.replace(/\s/g, " "); // Intl usa espaços especiais

describe("dinheiro", () => {
  it("real tem centavos; guarani não", () => {
    expect(currencyDigits("BRL")).toBe(2);
    expect(currencyDigits("PYG")).toBe(0);
  });

  it("formata pela moeda e pelo idioma", () => {
    expect(clean(formatMoney(4590, "BRL", "pt-BR"))).toBe("R$ 45,90");
    expect(clean(formatMoney(150000, "PYG", "es-PY"))).toBe("Gs. 150.000");
  });

  it("usa a convenção do país do estabelecimento", () => {
    expect(formatLocale("es", "PY")).toBe("es-PY");
    expect(formatLocale("pt-BR", "BR")).toBe("pt-BR");
    expect(formatLocale("es", "BR")).toBe("es-BR"); // pessoa em espanhol num salão brasileiro
    expect(formatLocale("pt-BR", "PY")).toBe("pt-PY"); // e em português num salão paraguaio
  });
});

describe("datas", () => {
  it("mostra no fuso do estabelecimento, não no do aparelho", () => {
    const utc = "2026-11-03T13:30:00Z";

    expect(formatDateTime(utc, "America/Sao_Paulo", "pt-BR")).toBe("03/11/2026, 10:30");
    expect(formatDateTime(utc, "America/Manaus", "pt-BR")).toBe("03/11/2026, 09:30");
    expect(formatDateTime(utc, "America/Asuncion", "es-PY")).toBe("3/11/26, 10:30");
  });

  it("descreve o fuso com cidade e diferença para UTC", () => {
    const at = new Date("2026-11-03T12:00:00Z");

    expect(timeZoneLabel("America/Sao_Paulo", "pt-BR", at)).toBe("Sao Paulo (UTC-03:00)");
    expect(timeZoneLabel("America/Rio_Branco", "pt-BR", at)).toBe("Rio Branco (UTC-05:00)");
  });
});

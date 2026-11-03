/**
 * Formatação de dinheiro e data pelo estabelecimento.
 *
 * - Dinheiro chega da API como inteiro na menor unidade da moeda (`*_minor`): centavos em BRL,
 *   guaranis inteiros em PYG (que não tem centavos). Quantas casas cada moeda tem vem do Intl.
 * - Datas chegam em UTC e são mostradas no fuso do estabelecimento, não no do aparelho.
 */

/**
 * Idioma da pessoa + país do estabelecimento: números, moeda e datas seguem a convenção do
 * país (no Paraguai, "Gs. 150.000"), no idioma de quem está usando.
 */
export function formatLocale(language: string, country: string): string {
  return `${language.split("-")[0]}-${country}`;
}

export function currencyDigits(currency: string): number {
  return new Intl.NumberFormat("en", { style: "currency", currency }).resolvedOptions()
    .maximumFractionDigits as number;
}

export function formatMoney(minor: number, currency: string, locale: string): string {
  const value = minor / 10 ** currencyDigits(currency);
  return new Intl.NumberFormat(locale, { style: "currency", currency }).format(value);
}

export function formatDateTime(utc: string | Date, timeZone: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "short",
    timeStyle: "short",
    hourCycle: "h23", // agenda em 24 h nos dois países (sem "a. m./p. m.")
    timeZone,
  }).format(typeof utc === "string" ? new Date(utc) : utc);
}

/** "São Paulo (UTC−03:00)" para mostrar um fuso IANA em lista. */
export function timeZoneLabel(timeZone: string, locale: string, at = new Date()): string {
  const city = timeZone.split("/").at(-1)!.replaceAll("_", " ");
  const offset = new Intl.DateTimeFormat(locale, { timeZone, timeZoneName: "longOffset" })
    .formatToParts(at)
    .find((part) => part.type === "timeZoneName")?.value;
  return offset ? `${city} (${offset.replace("GMT", "UTC")})` : city;
}

/**
 * Lê um valor digitado ("45,90", "45.90", "1.234,56", "150.000") e devolve na menor unidade
 * da moeda (4590, 123456, 150000). Devolve null se não for um valor válido.
 */
export function parseMoney(text: string, currency: string): number | null {
  const digits = currencyDigits(currency);
  const clean = text.replace(/[^\d.,]/g, "");
  if (!/\d/.test(clean)) return null;
  if (digits === 0) return Number(clean.replace(/[.,]/g, ""));

  // O último "," ou "." seguido de 1 ou 2 dígitos é a vírgula decimal; o resto é milhar.
  const decimal = clean.match(/[.,](\d{1,2})$/);
  const whole = (decimal ? clean.slice(0, -decimal[0].length) : clean).replace(/[.,]/g, "");
  if (whole === "" && !decimal) return null;
  const cents = decimal ? decimal[1].padEnd(digits, "0") : "0".repeat(digits);
  return Number(whole || "0") * 10 ** digits + Number(cents);
}

/** Valor para um campo de edição, sem símbolo e sem separador de milhar ("45,90", "150000"). */
export function moneyInputValue(minor: number, currency: string, locale: string): string {
  const digits = currencyDigits(currency);
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    useGrouping: false,
  }).format(minor / 10 ** digits);
}

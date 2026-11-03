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

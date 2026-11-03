import type { ProviderColor } from "../api/providers";

/** Classes completas (o Tailwind só gera as que aparecem escritas no código). */
export const PROVIDER_COLOR_CLASS: Record<ProviderColor, string> = {
  rose: "bg-rose-500",
  violet: "bg-violet-500",
  sky: "bg-sky-500",
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  orange: "bg-orange-500",
  teal: "bg-teal-500",
  fuchsia: "bg-fuchsia-500",
  lime: "bg-lime-500",
  slate: "bg-slate-500",
};

export const PROVIDER_COLORS = Object.keys(PROVIDER_COLOR_CLASS) as ProviderColor[];

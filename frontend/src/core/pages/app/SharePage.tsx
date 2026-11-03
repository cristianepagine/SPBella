import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Card } from "../../components/form";
import { QrCode } from "../../components/QrCode";
import { salonPath } from "../../paths";
import { whatsappLink } from "../../whatsapp";
import { useCurrentTenant } from "../TenantLayout";

/** Divulgar a página pública (só o dono): link para copiar, WhatsApp e cartaz com QR code. */
export function SharePage() {
  const { t } = useTranslation();
  const tenant = useCurrentTenant();
  const link = `${window.location.origin}${salonPath.home(tenant.slug)}`;
  const input = useRef<HTMLInputElement>(null);
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(link);
      setCopy("copied");
    } catch {
      // Sem acesso à área de transferência: deixa selecionado para a pessoa copiar.
      input.current?.select();
      setCopy("failed");
    }
  }

  return (
    <div className="space-y-4">
      <div className="print:hidden">
        <Card title={t("share.title")}>
          <p className="mb-4 text-slate-600">{t("share.intro")}</p>
          <label htmlFor="share-link" className="mb-1 block font-medium text-slate-800">
            {t("share.linkLabel")}
          </label>
          <input
            id="share-link"
            ref={input}
            readOnly
            value={link}
            onFocus={(e) => e.target.select()}
            className="mb-3 w-full rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-base"
          />
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={() => void copyLink()}
              className="flex-1 rounded-xl bg-brand-700 px-4 py-3 font-medium text-white active:bg-brand-900"
            >
              {t("share.copy")}
            </button>
            <a
              href={whatsappLink(t("share.message", { salon: tenant.name, link }))}
              target="_blank"
              rel="noreferrer"
              className="flex-1 rounded-xl border border-slate-300 px-4 py-3 text-center font-medium"
            >
              {t("share.sendWhatsapp")}
            </a>
          </div>
          {copy !== "idle" && (
            <p role="status" className="mt-3 text-sm text-slate-700">
              {t(copy === "copied" ? "share.copied" : "share.copyFailed")}
            </p>
          )}
          <p className="mt-3 text-sm text-slate-500">{t("share.instagramHint")}</p>
        </Card>
      </div>

      <section className="rounded-2xl bg-white p-6 text-center shadow-sm print:shadow-none">
        <h2 className="text-2xl font-bold text-brand-900 print:text-4xl">{tenant.name}</h2>
        <p className="mt-1 text-slate-600 print:mt-4 print:text-2xl">{t("share.posterCall")}</p>
        <QrCode
          value={link}
          label={t("share.qrLabel", { link })}
          className="mx-auto my-4 w-56 print:my-8 print:w-96"
        />
        <p className="break-all text-sm text-slate-600 print:text-lg">{link}</p>
        <button
          type="button"
          onClick={() => window.print()}
          className="mt-4 w-full rounded-xl bg-brand-700 px-4 py-3 font-medium text-white active:bg-brand-900 print:hidden"
        >
          {t("share.print")}
        </button>
      </section>
    </div>
  );
}

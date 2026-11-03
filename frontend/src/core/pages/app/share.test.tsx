import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import jsQR from "jsqr";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../../../App";
import { json, mockApi, salon, session } from "../../../test/api";
import { renderWithProviders } from "../../../test/render";
import { resetSessions } from "../../auth/session";
import { QR_QUIET_ZONE, qrMatrix } from "../../components/QrCode";
import { whatsappLink } from "../../whatsapp";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  resetSessions();
});

const asRole = (role: "owner" | "reception") => ({
  "GET /t/alpha": json(salon()),
  "POST /t/alpha/auth/refresh": json(session({ role })),
});

const LINK = `${window.location.origin}/alpha`;

/** Desenha a matriz em pixels e lê de volta, como a câmera do celular faria. */
function scan(value: string): string | undefined {
  const matrix = qrMatrix(value);
  const scale = 4;
  const side = (matrix.length + QR_QUIET_ZONE * 2) * scale;
  const pixels = new Uint8ClampedArray(side * side * 4).fill(255);
  matrix.forEach((cells, row) =>
    cells.forEach((dark, col) => {
      if (!dark) return;
      for (let y = 0; y < scale; y++) {
        for (let x = 0; x < scale; x++) {
          const at = (((row + QR_QUIET_ZONE) * scale + y) * side + (col + QR_QUIET_ZONE) * scale + x) * 4;
          pixels.fill(0, at, at + 3);
        }
      }
    }),
  );
  return jsQR(pixels, side, side)?.data;
}

describe("QR code", () => {
  it.each([
    "http://localhost:5173/alpha",
    "https://agenda.exemplo.com.br/salao-de-beleza-da-maria-aparecida-centro",
  ])("a câmera lê o mesmo link: %s", (link) => {
    expect(scan(link)).toBe(link);
  });
});

describe("link do WhatsApp", () => {
  it("usa só os dígitos do telefone e codifica a mensagem", () => {
    expect(whatsappLink("Oi & tchau", "+5511988887777")).toBe(
      "https://wa.me/5511988887777?text=Oi%20%26%20tchau",
    );
  });

  it("sem telefone, a pessoa escolhe o contato", () => {
    expect(whatsappLink("Oi")).toBe("https://wa.me/?text=Oi");
  });
});

describe("divulgar", () => {
  it("o dono vê o link, envia pelo WhatsApp e tem o QR code", async () => {
    mockApi(asRole("owner"));
    renderWithProviders(<App />, { route: "/alpha/app/share" });

    expect(await screen.findByLabelText("Link da sua página")).toHaveValue(LINK);
    const send = screen.getByRole("link", { name: "Enviar pelo WhatsApp" });
    const href = send.getAttribute("href")!;
    expect(href.startsWith("https://wa.me/?text=")).toBe(true);
    const message = decodeURIComponent(href.split("text=")[1]);
    expect(message).toContain("Studio Alpha");
    expect(message).toContain(LINK);
    expect(screen.getByRole("img", { name: `QR code para ${LINK}` })).toBeInTheDocument();
  });

  it("copia o link", async () => {
    mockApi(asRole("owner"));
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    renderWithProviders(<App />, { route: "/alpha/app/share" });

    await user.click(await screen.findByRole("button", { name: "Copiar link" }));

    expect(writeText).toHaveBeenCalledWith(LINK);
    expect(await screen.findByText("Link copiado!")).toBeInTheDocument();
  });

  it("sem acesso à área de transferência, seleciona o link e avisa", async () => {
    mockApi(asRole("owner"));
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("negado"));
    renderWithProviders(<App />, { route: "/alpha/app/share" });

    await user.click(await screen.findByRole("button", { name: "Copiar link" }));

    expect(await screen.findByText(/Não deu para copiar/)).toBeInTheDocument();
    const input = screen.getByLabelText<HTMLInputElement>("Link da sua página");
    expect(input.selectionEnd! - input.selectionStart!).toBe(LINK.length);
  });

  it("imprime o cartaz", async () => {
    mockApi(asRole("owner"));
    const print = vi.fn();
    vi.stubGlobal("print", print);
    renderWithProviders(<App />, { route: "/alpha/app/share" });

    await userEvent.click(await screen.findByRole("button", { name: "Imprimir cartaz" }));

    expect(print).toHaveBeenCalledOnce();
  });

  it("aparece no menu do dono", async () => {
    mockApi(asRole("owner"));
    renderWithProviders(<App />, { route: "/alpha/app" });

    const nav = await screen.findByRole("navigation", { name: "Menu" });
    expect(within(nav).getByRole("link", { name: "Divulgar" })).toBeInTheDocument();
  });

  it("a recepção não vê no menu nem abre pelo endereço", async () => {
    mockApi(asRole("reception"));
    renderWithProviders(<App />, { route: "/alpha/app/share" });

    expect(await screen.findByRole("link", { name: "Início" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Divulgar" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Link da sua página")).not.toBeInTheDocument();
  });
});

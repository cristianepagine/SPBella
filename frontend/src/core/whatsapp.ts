/** Link que abre o WhatsApp com a mensagem pronta. Sem telefone, a pessoa escolhe o contato. */
export function whatsappLink(text: string, phoneE164?: string): string {
  const number = phoneE164 ? phoneE164.replace(/\D/g, "") : "";
  return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}

# Backlog

Cada história só é considerada pronta com: testes, migração (quando mexe no banco), seed de
demonstração (quando cria dados), **API documentada** (`openapi.json` + [guia](api/README.md) +
[changelog](api/CHANGELOG.md)), textos em pt-BR e es, e README atualizado.

## MVP

| # | História | Status |
|---|---|---|
| 1 | Esqueleto: estrutura do repositório, Docker Compose, healthcheck, CI, `.env.example`, documentação da API | ✅ Feita |
| 2 | Multitenancy: tabela de tenants, resolução por slug, sessão com `SET LOCAL ROLE` + `search_path`, CLI `tenants create` / `tenants migrate --all`, testes de isolamento A×B | ⏭️ Próxima |
| 3 | Login: argon2, access token de 15 min, refresh em cookie httpOnly com rotação, perfis verificados no back-end, "esqueci a senha", Turnstile e rate limit | |
| 4 | Configurações do salão: nome, fuso, moeda (BRL/PYG), idioma, regras de agendamento | |
| 5 | Serviços e profissionais: duração, preço, quem faz o quê, horário semanal, folgas e bloqueios | |
| 6 | Clientes com consentimento registrado | |
| 7 | Agenda interna: dia/semana por profissional; criar, remarcar, cancelar; status | |
| 8 | Página pública de agendamento com Turnstile, rate limit e link para cancelar/remarcar | |
| 9 | Fila em Postgres + lembretes por e-mail + botão "Enviar no WhatsApp" (`wa.me`) | |
| 10 | Registro manual de pagamento e resumo do dia/mês | |
| 11 | LGPD: log de auditoria, exportar e excluir/anonimizar titular | |
| 12 | PWA instalável, revisão final de i18n, seed de demonstração completo | |
| — | Deploy: compose de produção, Cloudflare Tunnel, backup diário criptografado para R2 com teste de restauração | |

## Depois do MVP (não implementar sem aprovação)

- **Backup contínuo (WAL-G → R2, PITR).** Recomendado logo após o MVP: o backup diário pode perder até 24 h.
- **WhatsApp pela API oficial.** ⚠️ A Meta cobra por mensagem; exige número verificado e templates aprovados.
- Cobrança automática e sinal via Pix (BR: Mercado Pago / Asaas / Efí; PY: Bancard / Pagopar).
- Comissões dos profissionais.
- Pacotes e programa de fidelidade.
- Estoque de produtos.
- Lista de espera.
- Sincronização com Google Agenda.
- Notificações push no PWA.
- Confirmação do agendamento público por SMS/WhatsApp (contra agendamentos falsos). ⚠️ Custa por mensagem.
- Cadastro self-service do salão com assinatura paga.
- Nota fiscal: NFS-e (BR) e SIFEN (PY).
- Múltiplas unidades por salão.
- Subdomínio por salão (`studio-ana.<dominio>`), via Cloudflare Worker.
- Swagger protegido por login em produção.
- Uso offline com gravação (hoje o offline será só leitura).

# Backlog — Agenda Salão

Cada história só é considerada pronta com: testes, migração (quando mexe no banco), seed de
demonstração (quando cria dados), **API documentada** (`openapi.json` + [guia](api/README.md) +
[changelog](api/CHANGELOG.md)), textos em pt-BR e es, e README atualizado.

Ordem: SAL-01 a SAL-04 primeiro, isolados no **core** (ver [template.md](template.md)).

## MVP

| ID | Épico | História | Critério de aceite | Status |
|---|---|---|---|---|
| SAL-01 | Base | Como Cristiane, crio um novo cliente (tenant) por comando | Um comando cria schema, aplica migrações, cria o dono e carrega serviços de exemplo em menos de 1 minuto | 🟡 Feita, exceto os **serviços de exemplo**, que entram com a tabela de serviços (SAL-05) pelo gancho `seed_tenant`, já pronto e testado |
| SAL-02 | Base | Como usuário, entro com e-mail e senha e vejo só o que meu perfil permite | Dono, recepção e profissional têm telas e rotas distintas; acesso indevido retorna 403 (testado) | 🟡 Login, perfis e 403 prontos. Faltam o menu e as telas por perfil |
| SAL-03 | Base | Como dono, uso o sistema em PT ou ES | Todos os textos vêm de arquivos de tradução; troca de idioma sem recarregar | 🟡 Textos e troca prontos. Falta a tela de configurações do salão (idioma, fuso, moeda) |
| SAL-04 | Base | Como dono, vejo quem alterou dados de clientes | Log de auditoria com usuário, ação e data; consentimento registrado no cadastro do cliente | |
| SAL-05 | Cadastros | Como dono, cadastro serviços com nome, preço e duração | Serviço pode ser ativado ou desativado; preço na moeda do tenant | |
| SAL-06 | Cadastros | Como dono, cadastro profissionais com jornada semanal, folgas e serviços que realizam | Cada profissional tem horários próprios; dois profissionais podem ter jornadas diferentes | |
| SAL-07 | Cadastros | Como recepção, cadastro e busco clientes por nome ou telefone | Busca em menos de 1 segundo com 5 mil clientes; telefone validado | |
| SAL-08 | Agenda | Como recepção, vejo a agenda do dia e da semana por profissional | Visão em colunas no computador e em lista no celular; cores por status | |
| SAL-09 | Agenda | Como recepção, crio, movo, cancelo e marco falta em um agendamento | Tentativa de horário ocupado é recusada com mensagem clara, mesmo com duas pessoas agendando ao mesmo tempo (teste de concorrência) | |
| SAL-10 | Agenda | Como dono, bloqueio horários (almoço, férias, feriado) | Bloqueio remove o horário da agenda pública | |
| SAL-11 | Online | Como cliente final, agendo pela página pública do salão | Escolho serviço, profissional (ou sem preferência), dia e hora; página abre em menos de 2 s no 4G; protegida por Turnstile | |
| SAL-12 | Online | Como dono, divulgo o link no Instagram e no WhatsApp | Link curto por tenant, botão de WhatsApp na página e QR code para imprimir | |
| SAL-13 | Online | Como cliente final, cancelo ou remarco pelo link recebido | Link com token expira após o horário; respeita antecedência mínima definida pelo dono | |
| SAL-14 | Lembretes | Como dono, o cliente recebe confirmação e lembrete por e-mail | Lembrete enviado 24 h antes (configurável); falha de envio registrada e reenviada | ⚠️ precisa do domínio (SES) |
| SAL-15 | Lembretes | Como recepção, envio lembrete por WhatsApp com um toque | Botão abre wa.me com mensagem pronta (nome, serviço, data, hora) no idioma do cliente | |
| SAL-16 | Relatórios | Como dono, vejo atendimentos, faltas e serviços mais vendidos por período e profissional | Exporta para Excel; números conferem com a agenda | |
| — | Deploy | Compose de produção, Cloudflare Tunnel, backup diário criptografado para R2 com teste de restauração | | |

## V2 (não implementar sem aprovação)

| ID | História | Observação |
|---|---|---|
| SAL-17 | Exportação em PDF | PDF com logotipo do salão |
| SAL-18 | Histórico de atendimentos e observações por cliente | Visível para dono e recepção |
| SAL-19 | Sinal ou pagamento antecipado por Pix | Depende de provedor de pagamento; definir antes |
| SAL-20 | WhatsApp automático pela API oficial | ⚠️ A Meta cobra por mensagem. Canal plugado em `NotificationChannel`; custo repassado (plano `whatsapp_api`) |

## Outras ideias registradas (fora do MVP)

- **Backup contínuo (WAL-G → R2, PITR).** Recomendado logo após o MVP: o backup diário pode perder até 24 h.
- **Papel com login por tenant + PgBouncer.** Fecha o limite de `SET ROLE` descrito em
  [arquitetura.md](arquitetura.md#isolamento-entre-salões-história-2). Custo: um pool por tenant.
- **Cadastro da equipe pelo dono** (convidar recepção e profissionais). Proposto para entrar junto com SAL-06.
- **Limite de tentativas compartilhado** (no Postgres), se a API passar a rodar em mais de um processo.
- **Suspender, reativar e excluir tenant pela CLI** (hoje: só criar; suspender é um UPDATE manual).
- Comissões dos profissionais (fora do escopo por decisão comercial).
- Pacotes e fidelidade, estoque, lista de espera, Google Agenda, notificações push.
- Cadastro self-service do salão com assinatura paga.
- Nota fiscal: NFS-e (BR) e SIFEN (PY).
- Múltiplas unidades por salão; subdomínio por salão (Cloudflare Worker).
- Uso offline com gravação (hoje o offline será só leitura).

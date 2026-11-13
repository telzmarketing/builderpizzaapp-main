# Controle de atendimento WhatsApp: UI e contrato

Escopo: Agente WhatsApp e painel de atendimento de Operações. Sem deploy,
alterações de banco, worker, áudio, credenciais ou transporte de mensagens.

## Pontos auditados

- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`: havia ações de assumir/pausar,
  mas o compositor e `sendReply` continuavam aceitando envio humano com IA ativa.
- `client/components/admin/OperationsContactPanel.tsx`, usado por
  `client/pages/admin/Orders.tsx`: enviava diretamente sem ação de assumir ou
  indicação explícita do controle. Também apagava o rascunho antes da resposta.
- `client/lib/api.ts`: ambas as telas já consumiam a API canônica
  `/api/agente-whatsapp`; não é necessário criar outro canal ou endpoint.

## Contrato preservado

| Ação | API existente | Dados |
| --- | --- | --- |
| Consultar controle | `GET /api/agente-whatsapp/sessions/{id}` | `session.status`, `session.ai_enabled`, `session.automation_blocked` |
| Assumir | `PATCH /api/agente-whatsapp/sessions/{id}` | `status: human`, `ai_enabled: false`, `automation_blocked: true` |
| Devolver à IA | Mesmo PATCH | `status: open`, `ai_enabled: true`, `automation_blocked: false` |
| Responder como humano | `POST /api/agente-whatsapp/sessions/{id}/messages` | `direction: outbound`, `sender_type: human`, `provider_status: queued` |

Implementação da API: `backend/routes/agente_whatsapp.py`, delegando para
`backend/services/agente_whatsapp_service.py`. Esses arquivos não fazem parte
desta alteração de UI/contrato.

## Condição de envio e apresentação

O compositor humano só é liberado após confirmação da sessão pela API e quando
`status === human && ai_enabled === false`. Somente pausar a IA, ficar na fila
de atendimento ou encerrar a conversa não equivale a assumir.

As duas telas usam o mesmo indicador e os mesmos comandos:

- Aberta, IA habilitada e automação desbloqueada: **IA ativa**.
- Humano com IA desabilitada: **Humano assumiu · IA desativada**.
- Fila: **Aguardando humano assumir**.
- Pausa ou combinação inconsistente: **IA pausada · assuma para responder**.
- Encerrada: **Conversa encerrada**.

O indicador descreve o controle da sessão; não certifica a saúde do provedor de IA.
Assumir exige confirmação do PATCH; falhas não liberam o compositor. As telas
preservam o rascunho quando o envio falha. O cliente consulta novamente a sessão
antes do POST, detectando devolução à IA feita por outra tela. Operações atualiza
a conversa selecionada periodicamente e mostra o status retornado da mensagem;
`queued` não significa entrega no celular.

## Limite e integração com backend

A consulta antes do envio reduz estado desatualizado na interface, mas não
substitui validação no servidor. O backend deve rejeitar envio humano fora da
condição acima (HTTP 409), aplicando a regra dentro da operação de gravação.
A exclusão entre resposta automática e envio humano concorrentes também depende
do serviço/worker; esta alteração não modifica essa implementação.

Não há exigência nova de que apenas um usuário específico responda: o contrato
atual confirma controle humano da sessão, sem criar propriedade por operador.

## Validação

- Testes de estados bloqueados, falha de consulta, mudança de controle entre
  envios e payloads dos comandos em `client/lib/whatsappAttendance.spec.ts`.
- Renderização dos indicadores, instruções e bloqueio durante confirmação em
  `client/components/admin/WhatsAppAttendanceControls.spec.tsx`.
- Testes de integração real com WhatsApp, áudio e resposta automática estão fora
  desta entrega e não são comprovados por esses testes de UI/contrato.

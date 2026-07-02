# Agente WhatsApp Audio IA - Fase 0

Data: 2026-07-01

Status: executada como fase documental/arquitetural. Nenhum codigo funcional foi implementado.

## 1. Objetivo

Fechar os contratos, flags, criterios de aceite e decisoes de arquitetura necessarios para iniciar a Fase 1 do plano `PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md` com seguranca.

Esta fase nao altera comportamento de loja, checkout, pedidos, pagamentos, Marketing, CRM, Agente WhatsApp, Gateway ou banco de dados.

## 2. Escopo executado

- Contrato normalizado de mensagem recebida.
- Contrato normalizado de midia/audio.
- Contrato de download de midia.
- Contrato de envio de audio/voice note.
- Contrato de status de envio, entrega e leitura.
- Contrato de vinculo de campanha.
- Chaves de idempotencia.
- Feature flags iniciais.
- Limites padrao.
- Criterios de aceite para liberar a Fase 1.
- Decisoes pendentes que nao bloqueiam a Fase 1.

## 3. Estado atual usado como base

Arquivos existentes confirmados:

- `backend/routes/agente_whatsapp.py`
- `backend/services/agente_whatsapp_service.py`
- `backend/services/agente_whatsapp_ai_service.py`
- `backend/services/agente_whatsapp_outbox_service.py`
- `backend/models/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `backend/routes/whatsapp_marketing.py`
- `backend/services/whatsapp_gateway_service.py`
- `backend/services/whatsapp_gateway_runtime_client.py`
- `backend/services/whatsapp_gateway_provider.py`
- `server/whatsapp-gateway-runtime.mjs`
- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`
- `client/pages/admin/marketing/MarketingWhatsApp.tsx`
- `client/lib/api.ts`

Fatos tecnicos confirmados:

- `AgenteWhatsAppService` ja persiste mensagens inbound com `message_type`, `body`, `media_url` e `provider_message_id`.
- O runtime Baileys detecta audio inbound, mas nao baixa/normaliza audio nem preserva quoted message no contrato atual.
- A biblioteca Baileys suporta envio de audio/voice note, mas `server/whatsapp-gateway-runtime.mjs` ainda nao monta payload de audio/PTT.
- `WhatsAppGatewayService` ja envia texto e midia, mas ainda nao possui contrato explicito para audio e download.
- Marketing WhatsApp grava disparos em `whatsapp_messages` com `wamid`, `campaign_id`, `template_id`, `phone`, `body_sent`, `media_type`, `media_url` e `status`.
- O Agente e o Gateway ainda nao possuem tabela de delivery/snapshot canonica para campanha.

## 4. Contrato normalizado de mensagem recebida

Nome conceitual: `NormalizedWhatsAppInboundMessageV1`.

Este contrato deve ser produzido pela camada de transporte/Gateway e consumido pelo backend do Agente.

```json
{
  "event_id": "baileys:instance-id:provider-message-id",
  "event_type": "message_received",
  "provider": "baileys",
  "tenant_id": "default",
  "company_id": "default",
  "instance_id": "whatsapp_gateway_instance_id",
  "received_at": "2026-07-01T12:00:00Z",
  "message": {
    "provider_message_id": "3A123",
    "remote_jid": "5511999999999@s.whatsapp.net",
    "phone": "5511999999999",
    "push_name": "Cliente",
    "from_me": false,
    "direction": "inbound",
    "message_type": "audio",
    "text": null,
    "timestamp": "2026-07-01T12:00:00Z",
    "quoted_provider_message_id": "3A111",
    "quoted_text": "Hoje, pizza grande por R$ 39,90.",
    "media": {
      "provider_media_id": "media-id-or-null",
      "media_url": null,
      "media_key": "provider-media-key-or-null",
      "mime_type": "audio/ogg; codecs=opus",
      "file_name": null,
      "caption": null,
      "duration_ms": 12000,
      "size_bytes": 180000,
      "sha256": "optional"
    },
    "raw_payload": {}
  }
}
```

Campos obrigatorios para persistir mensagem:

- `provider`
- `message.provider_message_id`
- `message.phone`
- `message.direction`
- `message.message_type`
- `received_at`

Campos obrigatorios para audio:

- `message.media.mime_type` quando o provider disponibilizar.
- `message.media.provider_media_id`, `message.media.media_url` ou `message.media.media_key`.
- `message.media.duration_ms` quando o provider disponibilizar.

Campos desejados para campanha:

- `message.quoted_provider_message_id`
- `message.quoted_text`

Regra:

- Se `message_type = "audio"` e nenhum identificador de midia estiver presente, a mensagem deve ser persistida como audio pendente de intervencao, sem tentar STT.

## 5. Contrato de download de midia

Nome conceitual: `WhatsAppMediaDownloadRequestV1`.

```json
{
  "provider": "baileys",
  "instance_id": "whatsapp_gateway_instance_id",
  "provider_message_id": "3A123",
  "provider_media_id": "media-id-or-null",
  "media_key": "provider-media-key-or-null",
  "media_url": "provider-url-or-null",
  "expected_mime_type": "audio/ogg; codecs=opus",
  "max_size_bytes": 15728640,
  "max_duration_ms": 180000
}
```

Resposta normalizada:

```json
{
  "ok": true,
  "storage_key": "whatsapp/audio/inbound/2026/07/message-id.ogg",
  "public_url": null,
  "mime_type": "audio/ogg; codecs=opus",
  "size_bytes": 180000,
  "duration_ms": 12000,
  "checksum_sha256": "hash",
  "error": null
}
```

Regras:

- O download nao deve ocorrer dentro do tempo critico do webhook.
- O arquivo nao deve ser salvo em base64 no PostgreSQL.
- O storage inicial pode ser local, mas audio de cliente deve ser tratado como dado pessoal.
- Para piloto, o arquivo pode ser salvo localmente em diretorio segregado; para producao, preferir endpoint autenticado ou URL assinada.

## 6. Contrato de envio de audio/voice note

Nome conceitual: `WhatsAppSendAudioMessageV1`.

```json
{
  "provider": "baileys",
  "instance_id": "whatsapp_gateway_instance_id",
  "phone": "5511999999999",
  "audio_url": "https://dominio/secure-media/generated.ogg",
  "storage_key": "whatsapp/audio/outbound/2026/07/message-id.ogg",
  "mime_type": "audio/ogg; codecs=opus",
  "ptt": true,
  "caption": null,
  "reply_to_provider_message_id": "3A123",
  "idempotency_key": "agente_whatsapp_audio_reply:message-id"
}
```

Resposta normalizada:

```json
{
  "ok": true,
  "provider": "baileys",
  "provider_message_id": "3A124",
  "remote_jid": "5511999999999@s.whatsapp.net",
  "status": "sent",
  "error": null
}
```

Regra Baileys recomendada no runtime:

```ts
socket.sendMessage(jid, {
  audio: { url: audioUrl },
  mimetype: "audio/ogg; codecs=opus",
  ptt: true
});
```

Observacao:

- O runtime atual do projeto ainda nao implementa esse payload.
- A Fase 6 deve implementar o envio no runtime e expor o contrato pelo backend Gateway.

## 7. Contrato de status

Nome conceitual: `WhatsAppProviderStatusEventV1`.

```json
{
  "event_type": "message_status",
  "provider": "baileys",
  "instance_id": "whatsapp_gateway_instance_id",
  "provider_message_id": "3A124",
  "status": "delivered",
  "status_at": "2026-07-01T12:01:00Z",
  "raw_payload": {}
}
```

Status normalizados:

- `queued`
- `sent`
- `delivered`
- `read`
- `failed`
- `dead`

Regra:

- Status fora de ordem nao deve apagar status mais avancado.
- Status sem `provider_message_id` deve ser logado e ignorado.

## 8. Contrato de vinculo de campanha

Prioridade 1: resposta direta.

```text
inbound.quoted_provider_message_id
-> whatsapp_campaign_deliveries.provider_message_id
-> campaign_delivery_id
-> campaign_id
```

Prioridade 2: campanha recente.

```text
phone_normalized
-> deliveries enviadas nas ultimas 72 horas
-> priorizar ultimas 24 horas
-> se existir uma candidata segura, vincular
```

Prioridade 3: ambiguidade.

```text
2 ou mais candidatas relevantes
-> nao escolher arbitrariamente
-> salvar candidatas no contexto
-> agente pergunta qual promocao o cliente deseja
```

Campos minimos do delivery canonico:

- `id`
- `campaign_id`
- `template_id`
- `customer_id`
- `phone_normalized`
- `provider`
- `provider_message_id`
- `message_text_snapshot`
- `media_type`
- `media_url`
- `status`
- `sent_at`
- `delivered_at`
- `read_at`
- `replied_at`
- `provider_payload_json`

## 9. Idempotencia

Inbound:

```text
tenant_id + company_id + provider + provider_message_id
```

Enquanto `agente_whatsapp_messages` nao tiver `tenant_id/company_id`, usar:

```text
provider + provider_message_id
```

Outbound texto/audio:

```text
agente_whatsapp:<message_id>
agente_whatsapp_audio_reply:<source_message_id>
```

Jobs:

```text
job_type + message_id
```

Regras:

- Webhook repetido deve retornar sucesso operacional sem criar segunda mensagem.
- Job repetido deve identificar item existente.
- Resposta da IA deve ser gerada apenas uma vez por mensagem inbound, exceto retry manual explicito.
- Fallback textual de audio deve usar chave propria para nao duplicar voz e texto sem regra.

## 10. Feature flags

Flags propostas para `backend/config.py` em fase futura:

| Flag | Default inicial | Uso |
|---|---:|---|
| `WHATSAPP_AUDIO_INPUT_ENABLED` | `false` | Habilita processamento STT de audio recebido |
| `WHATSAPP_AUDIO_OUTPUT_ENABLED` | `false` | Habilita TTS e envio de audio |
| `WHATSAPP_GATEWAY_AUDIO_BAILEYS_ENABLED` | `false` | Habilita envio audio/PTT no runtime Baileys |
| `WHATSAPP_CAMPAIGN_CONTEXT_ENABLED` | `false` | Habilita contexto de campanha na resposta |
| `WHATSAPP_AI_AUTO_REPLY_ENABLED` | `false` | Habilita resposta automatica da IA |
| `WHATSAPP_AUDIO_TEXT_FALLBACK_ENABLED` | `true` | Envia texto quando audio falhar |
| `WHATSAPP_AUDIO_LOW_CONFIDENCE_HANDOFF_ENABLED` | `true` | Transfere/pausa quando transcricao for duvidosa |
| `WHATSAPP_AUDIO_RETENTION_CLEANUP_ENABLED` | `false` | Habilita limpeza por retencao |

Regra:

- Em producao, audio input deve ser ativado antes de audio output.
- Auto reply nao deve ser ligado antes de idempotencia e humano/IA estarem validados.

## 11. Limites padrao aprovados para implementacao inicial

| Configuracao | Valor inicial |
|---|---:|
| Duracao maxima de audio recebido | 180 segundos |
| Duracao maxima de resposta por voz | 45 segundos |
| Janela de contexto de campanha | 72 horas |
| Janela prioritaria de campanha | 24 horas |
| Tamanho maximo inicial do audio recebido | 15 MB |
| Tamanho maximo inicial do audio gerado | 10 MB |
| Idioma principal | `pt-BR` |
| STT principal | `gpt-4o-mini-transcribe` |
| STT contingencia | `gpt-4o-transcribe` |
| TTS principal | `gpt-4o-mini-tts` |
| Voz TTS inicial | `marin` |
| Formato preferencial | `audio/ogg; codecs=opus` |

## 12. Criterios de aceite da Fase 0

- [x] Contrato de mensagem recebida definido.
- [x] Contrato de media/download definido.
- [x] Contrato de envio de audio/voice note definido.
- [x] Contrato de status definido.
- [x] Estrategia de vinculo de campanha definida.
- [x] Idempotencia inicial definida.
- [x] Feature flags iniciais definidas.
- [x] Limites iniciais definidos.
- [x] Separacao Marketing/Gateway/Agente preservada.
- [x] Nenhuma implementacao funcional realizada.

## 13. Decisoes fechadas nesta fase

- Campanhas e disparos permanecem no modulo Marketing.
- Agente WhatsApp concentra Conversas e Configuracoes.
- Gateway permanece transporte, sem regra de IA.
- Baileys pode ser usado para responder clientes com audio, mas o runtime do projeto precisa implementar audio/PTT.
- A Fase 1 deve priorizar delivery/snapshot de campanha antes de STT/TTS.
- O webhook deve persistir rapido e delegar processamento pesado para job/worker.
- Fallback textual deve ficar ligado no inicio.

## 14. Pendencias que nao bloqueiam a Fase 1

- Decidir storage final de audio para producao: local protegido, endpoint autenticado ou URL assinada/S3.
- Confirmar no ambiente da VPS se `ffmpeg` sera necessario para conversao OGG/Opus.
- Validar no SDK OpenAI instalado o suporte exato aos modelos STT/TTS.
- Confirmar se `tenant_id/company_id` deve ser adicionado tambem nas tabelas do Agente ou se o escopo `default` permanece no piloto.
- Definir se o painel deve ocultar ou migrar as areas antigas de campanha/stories do Agente em fase de UX.

## 15. Riscos remanescentes

| Risco | Tratamento planejado |
|---|---|
| Provider nao envia quoted id | Usar janela de campanha e ambiguidade explicita |
| Audio em formato incompativel | Validar dispositivos e usar conversao se necessario |
| Duplicidade de resposta | Idempotencia por provider id, message id e job type |
| Vazamento de audio | Storage protegido, RBAC, retencao e logs sem segredo |
| IA responder oferta errada | Snapshot canonico da campanha e regras anti-invencao |
| Humano e IA responderem juntos | Verificar `ai_enabled`, `automation_blocked` e `status` antes de enviar |

## 16. Liberacao para Fase 1

A Fase 1 pode iniciar com as seguintes condicoes:

- Implementar apenas persistencia e vinculo de campanhas.
- Criar migrations aditivas.
- Nao implementar STT/TTS ainda.
- Nao alterar Gateway Baileys ainda, salvo se for necessario para preservar `provider_message_id`/delivery.
- Manter Marketing como origem dos disparos.
- Registrar backfill de `whatsapp_messages` para delivery canonico.

Resultado da Fase 0: aprovada para seguir para Fase 1, desde que a implementacao respeite estes contratos.

# Plano de Execucao - Agente WhatsApp Com Audio Por IA

Documento criado em 2026-07-01.

Escopo desta execucao: auditoria tecnica e plano. Nenhuma funcionalidade foi implementada.

Arquivos relevantes analisados: 57 arquivos entre backend, frontend, runtime Node, migrations, configuracao, dependencias e base de conhecimento. O codigo real prevaleceu sobre a documentacao.

Estado do Git antes do plano:
- Branch: `main`.
- Sincronia: `git rev-list --left-right --count origin/main...HEAD` retornou `0 0`.
- Alteracoes locais preexistentes e fora do escopo: `.claude/settings.local.json`, `.claude/settings.json` e `.claude/worktrees/*`.

## 1. Resumo executivo

O objetivo futuro e transformar o Agente WhatsApp atual em um atendimento capaz de receber audio do cliente, transcrever com IA, usar o texto no motor de atendimento, montar contexto operacional e de campanha, responder em texto ou voz, enviar audio pelo WhatsApp, registrar rastreabilidade, custos, falhas e conversoes.

A base atual ja possui uma estrutura forte para isso:
- Agente WhatsApp com sessoes, mensagens, eventos, contexto, ferramentas, IA, canal e outbox.
- WhatsApp Gateway com provider Baileys, runtime Node, instancias, envio de texto/midia e eventos inbound.
- Marketing WhatsApp com campanhas, templates, listas, disparo, status de envio e sincronizacao parcial com o Agente.
- Abstracao de IA para resposta textual com OpenAI/Claude.
- Uploads locais servidos por `/uploads` e `/api/uploads`.
- Painel `CRM / Agente WhatsApp` com conversas, configuracoes, IA, outbox, assumir atendimento e devolver para IA.

O suporte a audio ainda e parcial. O sistema reconhece `message_type = "audio"` em alguns webhooks, mas nao executa o ciclo completo: download seguro da midia, storage de audio, transcricao, avaliacao de baixa qualidade, contexto de campanha, TTS, envio de audio/PTT, player no painel, retry especifico, custo, retencao e metricas.

Decisao central recomendada: implementar audio por IA como extensao nativa do pipeline existente do Agente WhatsApp, sem criar outro chatbot e sem mover campanhas do Marketing para o Agente. Marketing continua responsavel por campanhas/disparos; Agente continua responsavel por conversa, contexto, IA, atendimento humano e resposta.

Principais riscos:
- A biblioteca Baileys suporta envio de audio/voice note, mas o runtime atual do projeto ainda nao implementa o payload correto; hoje ele trata `media_type` diferente de `video` e `document` como imagem.
- Marketing aceita midia apenas como `image` ou `video` no disparo atual.
- O webhook nao deve aguardar STT, contexto, IA, TTS e envio.
- Provider oficial, Baileys, Evolution e UAZAPI precisam de contrato normalizado para audio e mensagem citada.
- Audio e voz sao dados pessoais e exigem retencao, acesso e LGPD bem definidos.

## 2. Estado atual confirmado

| Area | Arquivo/tabela atual | O que existe | Completude | Evidencia no codigo |
|---|---|---|---|---|
| Registro das rotas | `backend/main.py` | Importa e inclui `agente_whatsapp_routes`, `whatsapp_gateway_routes` e `whatsapp_marketing_routes` com e sem `/api` | Completo para exposicao atual | `backend/main.py`, imports e `app.include_router(...)` |
| Startup do Agente | `backend/main.py` | Inicia worker `run_agente_whatsapp_outbox_worker` no lifespan | Parcial para audio, completo para outbox atual | `backend/main.py`, bloco do worker |
| Agente WhatsApp rotas | `backend/routes/agente_whatsapp.py` | Webhooks Meta/Evolution, dashboard, conversas, sessoes, mensagens, IA, tools, canal, outbox, campanhas e stories | Alto para texto/outbox; parcial para audio | `router = APIRouter(prefix="/agente-whatsapp")` |
| Sessoes do Agente | `agente_whatsapp_sessions` / `AgenteWhatsAppSession` | Cliente, telefone, provider, status, origem, intent, admin, flags de IA | Reaproveitavel | `backend/models/agente_whatsapp.py` |
| Mensagens do Agente | `agente_whatsapp_messages` / `AgenteWhatsAppMessage` | `message_type`, `body`, `media_url`, `provider_message_id`, status, payload bruto | Parcial para audio | `backend/models/agente_whatsapp.py` |
| IA do Agente | `agente_whatsapp_ai_settings` / `AgenteWhatsAppAISettings` | Provider, modelo, prompt, regras, tom, chaves OpenAI/Anthropic | Bom para texto; falta audio | `backend/models/agente_whatsapp.py`, `backend/services/agente_whatsapp_ai_service.py` |
| Canal do Agente | `agente_whatsapp_channel_settings` | `active_provider` e `whatsapp_gateway_instance_id` | Reaproveitavel; precisa garantir envio pelo canal ativo | `backend/models/agente_whatsapp.py` |
| Outbox | `agente_whatsapp_outbox` / `AgenteWhatsAppOutboxService` | Enfileira outbound, retenta, dead items, provider states, alertas internos | Bom para texto/midia; precisa audio e idempotencia de resposta | `backend/services/agente_whatsapp_outbox_service.py` |
| Webhook Meta | `AgenteWhatsAppService.process_meta_webhook` | Persiste inbound, status e detecta `audio` como tipo | Parcial; nao baixa/transcreve midia | `backend/services/agente_whatsapp_service.py` |
| Webhook Evolution | `AgenteWhatsAppService.process_evolution_webhook` | Persiste inbound e detecta `audioMessage` | Parcial; nao baixa/transcreve midia | `backend/services/agente_whatsapp_service.py` |
| Evento Baileys | `AgenteWhatsAppService.process_baileys_runtime_event` | Recebe evento normalizado do runtime | Parcial; usa `media_url` se vier pronto | `backend/services/agente_whatsapp_service.py` |
| Runtime Baileys | `server/whatsapp-gateway-runtime.mjs` | Conecta instancias, detecta inbound text/media/audio, envia texto e midia | Parcial; a biblioteca Baileys suporta audio, mas o runtime atual ainda nao monta payload de audio/PTT | `extractInboundMessage`, `sendMediaMessage` |
| Gateway service | `WhatsAppGatewayService` | Instancias, QR, status, envio texto, envio midia, runtime events | Reaproveitavel; precisa contrato de download/audio | `backend/services/whatsapp_gateway_service.py` |
| Interface de provider | `WhatsAppGatewayProvider` | Contrato de envio texto/midia e retorno `provider_message_id` | Parcial para audio | `backend/services/whatsapp_gateway_provider.py` |
| Marketing WhatsApp | `backend/routes/whatsapp_marketing.py` | Templates, listas, campanhas, disparo, status, config, sync com Agente | Reaproveitavel; delivery/snapshot precisa melhorar | `WhatsAppTemplate`, `WhatsAppMessage`, `WhatsAppCampaign` |
| Campaign delivery atual | `whatsapp_messages` | Registro de disparo por telefone/campanha, `wamid`, status, media | Parcial; sem quoted id, snapshot completo, replied_at, indices fortes | `WhatsAppMessage` dentro de `whatsapp_marketing.py` |
| Chatbot web | `backend/models/chatbot.py`, `backend/services/chatbot_service.py` | Chatbot do site com settings, conversa, mensagem, FAQ, handoff | Referencia util; nao deve virar Agente WhatsApp | `ChatbotSettings`, `ChatbotConversation` |
| IA provider | `backend/services/ai/base.py`, `openai_provider.py`, `claude_provider.py`, `factory.py` | `AIProvider.generate()` para texto | Parcial; falta STT/TTS na abstracao | `AIProvider`, `OpenAIProvider.generate` |
| Uploads | `backend/routes/upload.py` | Upload admin aceita imagem/video e salva em `uploads/` | Parcial; nao aceita audio | `_ALLOWED_TYPES = _IMAGE_TYPES | _VIDEO_TYPES` |
| Static files | `backend/main.py` | Monta `/uploads` e `/api/uploads` | Reaproveitavel; acesso e retencao precisam revisao | `app.mount("/uploads", ...)` |
| Frontend Agente | `client/pages/admin/crm/CrmAgenteWhatsApp.tsx` | Conversas, filtros, mensagens, assumir, pausar, devolver IA, outbox/configs | Parcial; sem player/transcricao/audio controls | render de mensagens usa `body || message_type` |
| API client | `client/lib/api.ts` | Tipos e funcoes do Agente para sessions, messages, IA, outbox, configs | Parcial; falta campos de audio/campanha/transcricao | `ApiAgenteWhatsAppMessage` |
| Marketing frontend | `client/pages/admin/marketing/MarketingWhatsApp.tsx` | Campanhas, templates, disparo, monitoramento, config | Bom para campanhas; nao deve ser movido | tabs e payload de midia image/video |
| Dependencias backend | `backend/requirements.txt` | `openai>=1.50.0`, `anthropic>=0.40.0`, FastAPI, SQLAlchemy, Alembic | OpenAI presente; suporte STT/TTS precisa validacao em implementacao | arquivo de requisitos |
| Dependencias Node | `package.json` | `@whiskeysockets/baileys`, Express, Vite, React | Baileys presente | `dependencies` |
| Base de conhecimento | `KNOWLEDGE_BASE.md` | Inventario historico e validacoes | Parcial/desatualizado para Agente/Gateway atual | Secao 16 nao lista todos os arquivos atuais |

## 3. Divergencias entre codigo e base de conhecimento

Documentacao correta:
- A base registra que o backend usa routes, services, models, schemas, migrations e que mudancas de schema devem usar Alembic.
- A base confirma que alteracoes documentais podem ser validadas apenas por diff/Markdown.
- A base registra ruido local recorrente em `.claude/*`.

Documentacao desatualizada ou incompleta:
- A secao de inventario do backend nao lista todos os arquivos atuais de `agente_whatsapp`, `whatsapp_gateway`, outbox, provider states, internal alerts e channel settings.
- A base historica cita o Chatbot como centro de atendimento, mas o codigo atual possui um Agente WhatsApp proprio com modelos, schemas, rotas e services separados.
- A base nao descreve o runtime Node `server/whatsapp-gateway-runtime.mjs`.
- A base nao descreve a sincronizacao parcial `Marketing WhatsApp -> Agente WhatsApp` feita por `_sync_marketing_message_to_agent`.

Funcionalidades parcialmente implementadas:
- Audio inbound e reconhecido como tipo, mas nao ha download seguro, storage, STT, transcricao, retry e exibicao.
- Outbox envia midia, mas o runtime Baileys do projeto ainda nao monta payload de audio/PTT, embora a biblioteca Baileys suporte esse tipo de envio.
- Campanha e disparo existem, mas o vinculo de resposta por `quoted_provider_message_id -> provider_message_id -> delivery -> campaign` ainda nao existe.
- IA do Agente existe para resposta textual, mas nao separa STT, raciocinio e TTS.

Arquivos citados no prompt e encontrados:
- `backend/main.py`
- `backend/routes/chatbot.py`
- `backend/routes/admin_chatbot.py`
- `backend/routes/whatsapp_marketing.py`
- `backend/routes/campaigns.py`
- `backend/routes/automations.py`
- `backend/routes/marketing_workflow.py`
- `backend/routes/webhooks.py`
- `backend/services/chatbot_service.py`
- `backend/services/context_builder.py`
- `backend/services/campaign_service.py`
- `backend/services/automation_service.py`
- `backend/services/customer_ai_service.py`
- `backend/services/ai/base.py`
- `backend/services/ai/factory.py`
- `backend/services/ai/openai_provider.py`
- `backend/services/ai/claude_provider.py`
- `backend/models/chatbot.py`
- `backend/models/campaign.py`
- `backend/models/customer.py`
- `backend/models/crm.py`
- `client/pages/admin/marketing/MarketingWhatsApp.tsx`
- `client/lib/api.ts`
- `client/lib/chatbotApi.ts`

Arquivos/areas adicionais encontrados e relevantes:
- `backend/routes/agente_whatsapp.py`
- `backend/routes/whatsapp_gateway.py`
- `backend/models/agente_whatsapp.py`
- `backend/models/whatsapp_gateway.py`
- `backend/schemas/agente_whatsapp.py`
- `backend/schemas/whatsapp_gateway.py`
- `backend/services/agente_whatsapp_service.py`
- `backend/services/agente_whatsapp_ai_service.py`
- `backend/services/agente_whatsapp_outbox_service.py`
- `backend/services/agente_whatsapp_worker.py`
- `backend/services/whatsapp_gateway_service.py`
- `backend/services/whatsapp_gateway_runtime_client.py`
- `backend/services/whatsapp_gateway_provider.py`
- `backend/services/whatsapp_gateway_baileys_provider.py`
- `server/whatsapp-gateway-runtime.mjs`
- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`

## 4. Lacunas encontradas

Gateway:
- Falta contrato normalizado para download de midia.
- Falta implementar envio de audio/PTT no runtime Baileys do projeto; a biblioteca Baileys pode ser usada para responder clientes com audio.
- Falta preservacao de mensagem citada no evento inbound.
- Falta retorno padronizado de `media_mime_type`, duracao, tamanho e storage key.
- Falta tratamento equivalente para audio nos providers oficiais/nao oficiais.

Webhook:
- O webhook persiste mensagem, mas nao dispara job de processamento inbound.
- Falta idempotencia composta por `provider`, `provider_message_id` e escopo de loja/tenant quando houver multiempresa.
- Falta chave para evitar duas respostas de IA para a mesma mensagem.
- Falta status `processing`, `processed`, `failed`, `needs_human` na mensagem/processamento.

Midia:
- Upload atual bloqueia audio.
- Nao ha validacao real de MIME de audio.
- Nao ha limite proprio para duracao e tamanho.
- Nao ha retencao/exclusao.
- Nao ha estrategia para arquivos temporarios e audio orfao.

Campanhas:
- `whatsapp_messages` funciona como delivery parcial, mas falta snapshot completo do texto/midia/regras.
- Falta `quoted_provider_message_id` no inbound para vinculo direto.
- Falta `campaign_delivery_id` em `agente_whatsapp_messages`.
- Falta calculo formal de ambiguidade para campanhas recentes.
- Falta metrica de resposta por audio e conversao por campanha.

Conversas:
- Mensagens de audio aparecem como texto do tipo, sem player.
- Nao ha transcricao visivel.
- Nao ha status de STT/TTS por mensagem.
- Nao ha retry de transcricao/TTS por mensagem.
- Nao ha bloqueio de corrida quando humano assume durante processamento.

Chatbot/IA:
- `AIProvider` so tem `generate()` textual.
- Nao ha metodos `transcribe_audio()` e `generate_speech()`.
- `AgenteWhatsAppAIService.respond()` recebe texto e gera texto; nao conhece audio.
- Nao ha avaliacao de baixa qualidade sem campo de confianca.

Contexto:
- O Agente usa ferramentas e contexto proprio, mas falta um builder especifico para campanha de origem.
- `backend/services/context_builder.py` e do chatbot/atendimento web e precisa ser avaliado antes de reaproveitar.
- Falta selecionar/resumir contexto para nao estourar tokens.

STT:
- Falta servico de transcricao.
- Falta modelo principal `gpt-4o-mini-transcribe`.
- Falta contingencia `gpt-4o-transcribe`.
- Falta criterio objetivo de baixa qualidade.

TTS:
- Falta servico de voz.
- Falta modelo `gpt-4o-mini-tts`.
- Falta voz `marin`, idioma pt-BR e formato preferencial Opus.
- Falta conversao OGG/Opus se o provider exigir.

Armazenamento:
- Storage local existe, mas publico.
- Falta decisao entre URL publica temporaria, URL assinada ou endpoint autenticado para painel.
- Falta retencao por tipo de audio.

Fila:
- Existe outbox outbound; nao existe fila inbound para STT/contexto/IA/TTS.
- Webhook nao deve esperar IA.
- Precisa decidir se um novo job table interno basta ou se exige fila externa.

Painel:
- O Agente hoje tem muitas abas/areas alem de Conversas e Configuracoes; o plano deve convergir para essas duas sem mover campanhas para o Agente.
- Falta player de audio, transcricao, campanha de origem, retry, custos, flags de baixa qualidade e controles de resposta por audio.

Seguranca:
- Falta politica especifica de voz como dado pessoal.
- Falta RBAC granular para ouvir audio/transcricao.
- Falta protecao contra replay de webhook.
- Falta mascaramento de logs de provider.

Metricas:
- Existem metricas basicas do Agente/outbox, mas nao de STT, TTS, custo, duracao, fallback, campanha identificada/inferida/ambigua.

Testes:
- Nao foi encontrado suite especifica para audio WhatsApp, STT/TTS, quoted message, campanha por janela ou player.

## 5. Arquitetura proposta

Fluxo geral de audio inbound:

```text
WhatsApp
-> Provider/Gateway
-> Evento normalizado de entrada
-> Persistencia rapida e idempotente
-> Job inbound
-> Download/validacao/storage de audio
-> STT
-> Qualidade da transcricao
-> Contexto operacional + contexto de campanha
-> Agente WhatsApp IA textual
-> Persistencia da resposta textual
-> Politica de saida: texto/audio
-> TTS se aplicavel
-> Outbox
-> Provider/Gateway
-> WhatsApp
-> Status, metricas, custos e conversao
```

Fluxo de campanha para conversa:

```text
Marketing WhatsApp
-> WhatsApp campaign delivery
-> provider_message_id / wamid
-> cliente responde
-> quoted_provider_message_id quando existir
-> Agente WhatsApp Message
-> campaign_delivery_id / campaign_id
-> Contexto da campanha
-> Resposta do agente sem inventar oferta
```

Separacao de responsabilidades:
- Marketing: campanhas, templates, listas, segmentacoes, midias, agendamento, intervalos, provider, disparo, status e metricas de campanha.
- Agente WhatsApp: conversas, historico, interpretacao de texto/audio, contexto, IA, humano, resposta e conversao.
- Gateway: transporte normalizado de WhatsApp. Nao contem regra de negocio nem prompt de IA.
- IA: STT gera texto, modelo do Agente decide resposta textual, TTS gera audio da resposta.
- Storage: armazena arquivos, metadados e retencao. Nao salva base64 no PostgreSQL.

## 6. Decisoes arquiteturais

| Decisao | Alternativas consideradas | Recomendacao | Justificativa | Impactos | Riscos |
|---|---|---|---|---|---|
| Onde fica campanha/disparo | Mover para Agente, duplicar, manter em Marketing | Manter em Marketing | Ja existe `MarketingWhatsApp` e `whatsapp_marketing.py`; prompt exige separacao | Agente consulta delivery/contexto | Exige limpar/ocultar areas de campanha hoje presentes no Agente |
| Onde fica conversa/audio | Chatbot web, novo modulo, Agente atual | Agente atual | Ja tem sessions/messages/outbox/IA/humano | Menos retrabalho | Precisa ampliar modelo sem quebrar texto |
| Como identificar campanha | So quoted, so janela, IA inferindo | Quoted primeiro, janela depois, ambiguidade explicita | Evita inventar oferta/preco | Requer delivery snapshot e indices | Providers podem nao enviar quoted id |
| Modelo de delivery | Criar tabela nova, ampliar `whatsapp_messages`, usar JSON | Evoluir `whatsapp_messages` ou criar `whatsapp_campaign_deliveries` com backfill | Nome atual ja existe mas e parcial; delivery dedicada melhora semantica | Migration e backfill | Duplicacao se nao migrar com cuidado |
| Audio metadata | Tudo em `agente_whatsapp_messages`, tabela de artifacts, JSON | Campos principais na mensagem + tabela `agente_whatsapp_audio_artifacts` se houver multiplos arquivos | Consulta rapida e auditavel | Mais schema | Manter consistencia entre mensagem e artifact |
| STT/TTS provider | Chamar OpenAI direto em rota, ampliar AIProvider, criar service separado | Criar services de audio usando configuracao do Agente e SDK oficial; nao chamar em rota | Mantem arquitetura services | Exige schemas/configs | SDK pode exigir ajuste de versao no futuro |
| Fila inbound | Processar no webhook, usar outbox, criar job table, Redis/Celery | Criar job table interna primeiro | Infra atual ja usa worker de outbox; evita componente novo | Simples para VPS atual | Pode precisar fila externa se volume crescer |
| Resposta em audio | Sempre audio, nunca audio, espelhar cliente | Configuravel com default "quando cliente enviar audio" | Experiencia natural e segura | Precisa UI/config | Custo e latencia maiores |
| Fallback | Falha bloqueia resposta, envia texto automatico, aguarda humano | Preservar texto e enviar texto se fallback habilitado | Evita cliente sem resposta | Pode enviar texto quando esperado audio | Duplicidade se idempotencia falhar |
| Storage | Base64 no banco, `uploads/`, S3/privado | Iniciar com storage local segregado e metadados; prever S3/privado | A infraestrutura atual ja serve uploads | Precisa restricao e retencao | `/uploads` publico pode ser inadequado para voz |
| Gateway Baileys | Acoplar IA no Node, ampliar runtime, novo servico | Ampliar runtime apenas para transporte/download/audio | Mantem desacoplamento | Testes de contrato | Baileys muda API com frequencia |

## 7. Modelo de dados

Tabelas atuais reaproveitadas:
- `agente_whatsapp_sessions`: conversa, cliente, telefone, provider, status, humano/IA.
- `agente_whatsapp_messages`: historico textual/midia, status e payload bruto.
- `agente_whatsapp_outbox`: fila de envio outbound.
- `agente_whatsapp_events`: auditoria e processamento.
- `agente_whatsapp_context`: contexto resumido da conversa.
- `agente_whatsapp_tool_calls`: rastreabilidade das ferramentas.
- `agente_whatsapp_metrics`: base para metricas diarias.
- `agente_whatsapp_ai_settings`: configuracao de IA textual e chaves.
- `agente_whatsapp_channel_settings`: provider ativo e instancia Gateway.
- `whatsapp_campaigns`, `whatsapp_templates`, `whatsapp_messages`, `whatsapp_contact_lists`: origem de campanhas e disparos do Marketing.
- `whatsapp_gateway_instances`, `whatsapp_gateway_logs`: transporte.

Campos atuais reaproveitados:
- `agente_whatsapp_messages.message_type`
- `agente_whatsapp_messages.body`
- `agente_whatsapp_messages.media_url`
- `agente_whatsapp_messages.provider_message_id`
- `agente_whatsapp_messages.provider_status`
- `agente_whatsapp_messages.raw_payload_json`
- `whatsapp_messages.wamid`
- `whatsapp_messages.campaign_id`
- `whatsapp_messages.template_id`
- `whatsapp_messages.phone`
- `whatsapp_messages.body_sent`
- `whatsapp_messages.media_type`
- `whatsapp_messages.media_url`
- `whatsapp_messages.status`

NOVOS CAMPOS PROPOSTOS em `agente_whatsapp_messages`:
- `provider`: provider normalizado da mensagem, quando nao bastar `session.provider`.
- `quoted_provider_message_id`: id da mensagem citada pelo cliente.
- `campaign_id`: campanha vinculada.
- `campaign_delivery_id`: delivery/disparo especifico vinculado.
- `media_storage_key`: caminho interno/localizador do audio salvo.
- `media_mime_type`: MIME validado.
- `media_duration_ms`: duracao do audio.
- `media_size_bytes`: tamanho.
- `transcription_status`: `none`, `pending`, `processing`, `done`, `failed`, `low_confidence`, `needs_human`.
- `transcription_text`: texto final usado pelo agente.
- `transcription_language`: exemplo `pt-BR`.
- `transcription_provider`: exemplo `openai`.
- `transcription_model`: exemplo `gpt-4o-mini-transcribe`.
- `transcription_error`: erro sanitizado.
- `transcription_quality_json`: sinais de qualidade, sem depender de campo de confianca inexistente.
- `tts_status`: `none`, `pending`, `processing`, `done`, `failed`, `fallback_text_sent`.
- `tts_text`: texto convertido em voz.
- `tts_storage_key`: arquivo gerado.
- `tts_voice`: exemplo `marin`.
- `tts_provider`: exemplo `openai`.
- `tts_model`: exemplo `gpt-4o-mini-tts`.
- `tts_duration_ms`: duracao gerada.
- `tts_error`: erro sanitizado.
- `processing_status`: estado do pipeline inbound/outbound.
- `idempotency_key`: chave unica de processamento.
- `processed_at`: conclusao do pipeline.

NOVA TABELA PROPOSTA: `whatsapp_campaign_deliveries`
- Objetivo: transformar o disparo em entidade auditavel e vinculavel a conversa.
- Relacionamentos: `campaign_id -> whatsapp_campaigns.id`, `template_id -> whatsapp_templates.id`, `customer_id -> customers.id`, `conversation_id -> agente_whatsapp_sessions.id` opcional.
- Campos principais: `id`, `campaign_id`, `template_id`, `customer_id`, `contact_id`, `phone_normalized`, `provider`, `provider_message_id`, `message_text_snapshot`, `media_type`, `media_url`, `media_storage_key`, `coupon_snapshot_json`, `product_snapshot_json`, `rules_snapshot_json`, `provider_payload_json`, `status`, `sent_at`, `delivered_at`, `read_at`, `replied_at`, `failed_at`, `created_at`, `updated_at`.
- Unique recomendado: `(provider, provider_message_id)` quando `provider_message_id IS NOT NULL`.
- Indices: `phone_normalized`, `campaign_id`, `sent_at DESC`, `status`, `provider_message_id`.
- Backfill: criar deliveries a partir de `whatsapp_messages` existentes, preservando `body_sent`, `wamid`, `campaign_id`, `template_id`, `phone`, `status`, `sent_at`, `media_type`, `media_url`.

CONFIGURACAO IMPLEMENTADA: `site_config.content.agente_whatsapp_audio`
- Objetivo: manter politica de audio editavel no painel sem nova tabela para um singleton operacional.
- Fallback: variaveis `.env` seguem como padrao quando nao houver configuracao persistida.
- Campos atuais: `enabled`, `response_mode`, `tts_model`, `tts_voice`, `tts_format`, `max_chars`, `send_as_ptt`, `updated_at`.
- Evolucao futura: avaliar tabela propria apenas se audio precisar de tenant/company, historico de alteracoes ou politicas de retencao por empresa.

NOVA TABELA PROPOSTA: `agente_whatsapp_processing_jobs`
- Objetivo: fila interna para processamento inbound sem prender webhook.
- Campos: `id`, `message_id`, `session_id`, `job_type`, `status`, `attempts`, `max_attempts`, `idempotency_key`, `payload_json`, `error`, `next_attempt_at`, `locked_at`, `started_at`, `finished_at`, `created_at`, `updated_at`.
- Job types: `audio_transcription`, `agent_response`, `tts_generation`, `campaign_linking`, `retention_cleanup`.
- Unique: `(job_type, idempotency_key)`.
- Indice: `(status, next_attempt_at)`.

NOVA TABELA PROPOSTA: `agente_whatsapp_audio_artifacts`
- Objetivo: auditar arquivos original/transcrito/gerado sem inflar a mensagem quando houver multiplos artifacts.
- Campos: `id`, `message_id`, `artifact_type`, `storage_key`, `public_url`, `mime_type`, `size_bytes`, `duration_ms`, `checksum`, `provider`, `model`, `status`, `error`, `retention_until`, `created_at`, `deleted_at`.
- Artifact types: `inbound_original`, `inbound_normalized`, `tts_generated`.

Estrategia JSON:
- Usar JSON apenas para payload bruto, snapshots variaveis e sinais de qualidade.
- Evitar JSON para filtros frequentes como status, provider, campaign_id, phone, datas e ids.

Estrategia de rollback:
- Criar campos/tabelas como aditivos.
- Nao remover colunas atuais.
- Feature flags desligam o fluxo novo sem afetar texto.
- Migrations de downgrade devem remover apenas objetos novos quando nao houver dados criticos a preservar; em producao, rollback operacional deve preferir desativacao por flag.

## 8. Contratos e endpoints

Webhook de entrada normalizado:

```json
{
  "event_type": "message_received",
  "provider": "baileys",
  "instance_id": "string",
  "message": {
    "provider_message_id": "string",
    "remote_jid": "string",
    "phone": "5511999999999",
    "from_me": false,
    "message_type": "audio",
    "body": null,
    "media": {
      "provider_media_id": "string",
      "url": "string",
      "mime_type": "audio/ogg",
      "duration_ms": 12000,
      "size_bytes": 123456
    },
    "quoted_provider_message_id": "string-or-null",
    "timestamp": "iso",
    "raw_payload": {}
  }
}
```

Mensagens do Agente:
- `GET /agente-whatsapp/sessions/{session_id}/messages`: deve retornar campos de audio, transcricao, tts e campanha.
- `POST /agente-whatsapp/sessions/{session_id}/messages`: deve continuar aceitando texto e futuramente aceitar audio humano, sempre via service.
- `POST /agente-whatsapp/messages/{message_id}/retry-transcription` NOVO ENDPOINT PROPOSTO.
- `POST /agente-whatsapp/messages/{message_id}/retry-tts` NOVO ENDPOINT PROPOSTO.
- `POST /agente-whatsapp/messages/{message_id}/send-text-fallback` NOVO ENDPOINT PROPOSTO.

Configuracoes:
- `GET /agente-whatsapp/audio/settings` NOVO ENDPOINT PROPOSTO.
- `PUT /agente-whatsapp/audio/settings` NOVO ENDPOINT PROPOSTO.
- Deve mascarar chaves e nao expor segredo no frontend.

Campanhas:
- `GET /agente-whatsapp/sessions/{session_id}/campaign-context` endpoint implementado.
- `POST /agente-whatsapp/messages/{message_id}/resolve-campaign-context` endpoint implementado para reprocessar contexto quando necessario.

Gateway:
- `POST /instances/{instance_id}/messages/audio` NOVO CONTRATO PROPOSTO no runtime.
- `GET /instances/{instance_id}/media/{provider_media_id}` ou comando interno equivalente NOVO CONTRATO PROPOSTO para download.
- Retorno deve incluir `provider_message_id`, `remote_jid`, status e erro normalizado.

Takeover humano:
- Reaproveitar `PATCH /agente-whatsapp/sessions/{session_id}` com `status`, `ai_enabled`, `automation_blocked`.
- Garantir que jobs pendentes verifiquem o estado atual antes de responder.

## 9. Alteracoes no backend

| Arquivo existente ou novo | Tipo de alteracao | Responsabilidade | Dependencias | Risco | Etapa |
|---|---|---|---|---|---|
| `backend/models/agente_whatsapp.py` | Alterar | Campos de audio, campanha, processamento e artifacts/jobs | Alembic | Medio | 1, 3, 6 |
| `backend/schemas/agente_whatsapp.py` | Alterar | Expor campos novos de mensagem, settings, retry e contexto | Models | Medio | 1, 3, 7 |
| `backend/migrations/versions/*` | Novo | Migrations aditivas e backfill | Database | Alto | 1, 3, 8 |
| `backend/routes/agente_whatsapp.py` | Alterar | Endpoints de audio settings, retry, campaign context | Services | Medio | 2, 3, 7 |
| `backend/services/agente_whatsapp_service.py` | Alterar | Persistencia idempotente, quoted id, campaign link, jobs | Models/Gateway | Alto | 2, 4 |
| `backend/services/agente_whatsapp_ai_service.py` | Alterar | Aceitar transcricao como entrada, bloqueios, resposta textual, politica de saida | Audio services | Alto | 5, 6 |
| `backend/services/agente_whatsapp_outbox_service.py` | Alterar | Enviar audio, fallback texto, retry e idempotencia outbound | Gateway | Alto | 6 |
| `backend/services/agente_whatsapp_audio_service.py` | NOVO ARQUIVO PROPOSTO | Orquestrar download, validacao, STT, TTS e storage | OpenAI, storage | Alto | 3, 6 |
| `backend/services/agente_whatsapp_processing_service.py` | NOVO ARQUIVO PROPOSTO | Worker/jobs inbound | DB | Medio | 3 |
| `backend/services/agente_whatsapp_campaign_context_service.py` | NOVO ARQUIVO PROPOSTO | Vinculo direto/janela/ambiguidade e snapshot | Marketing tables | Medio | 4 |
| `backend/services/ai/base.py` | Alterar | Contratos opcionais para STT/TTS ou interfaces separadas | Providers | Medio | 3, 6 |
| `backend/services/ai/openai_provider.py` | Alterar | Implementar STT/TTS via SDK oficial | `openai` | Alto | 3, 6 |
| `backend/services/whatsapp_gateway_provider.py` | Alterar | Contrato de audio e download | Runtime | Medio | 2, 6 |
| `backend/services/whatsapp_gateway_runtime_client.py` | Alterar | Chamar endpoints audio/download do runtime | Runtime Node | Medio | 2, 6 |
| `backend/services/whatsapp_gateway_service.py` | Alterar | `send_audio_message`, `download_media`, logs | Provider | Medio | 2, 6 |
| `server/whatsapp-gateway-runtime.mjs` | Alterar | Detectar quoted id, baixar media, enviar audio/PTT | Baileys | Alto | 2, 6 |
| `backend/routes/whatsapp_marketing.py` | Alterar | Criar/atualizar delivery snapshot e reply metrics | Campaign delivery | Medio | 1, 8 |
| `backend/routes/upload.py` | Alterar ou criar rota separada | Aceitar audio com limites e MIME real | Storage | Medio | 3, 7 |
| `backend/config.py` | Alterar | Flags e limites de audio | Deploy | Baixo | 7, 9 |
| `backend/main.py` | Alterar | Iniciar worker inbound somente se flag ativa | Processing service | Medio | 3, 9 |
| `backend/core/events.py` | Avaliar | Eventos de conversa/pedido/conversao | Metrics | Baixo | 8 |

## 10. Alteracoes no frontend

| Arquivo existente ou novo | Tipo de alteracao | Responsabilidade | Dependencias | Risco | Etapa |
|---|---|---|---|---|---|
| `client/pages/admin/crm/CrmAgenteWhatsApp.tsx` | Alterar | Manter apenas Conversas/Configuracoes, render audio, transcricao, campanha, retry, resposta audio | API | Alto | 7 |
| `client/lib/api.ts` | Alterar | Tipos de audio, campanha, settings, retry, metrics | Backend schemas | Medio | 3, 7, 8 |
| `client/components/admin/MediaUpload.tsx` | Alterar ou criar variante | Suportar audio quando aplicavel | Upload backend | Medio | 7 |
| `client/pages/admin/crm/CrmAgenteWhatsApp.tsx` | Implementado inline | Player, transcricao e retry de audio nas mensagens | URL/storage | Medio | 7 |
| `client/components/admin/WhatsAppCampaignContextCard.tsx` | NOVO ARQUIVO PROPOSTO | Resumo da campanha, produto, preco, cupom, validade | Campaign context endpoint | Medio | 7 |
| `client/pages/admin/crm/CrmAgenteWhatsApp.tsx` | Implementado inline | Configuracoes de audio e voz | Audio settings API | Medio | 7 |
| `client/config/adminNavigation.ts` | Avaliar | Garantir Agente WhatsApp com Conversas/Configuracoes somente no modulo | UX | Baixo | 7 |
| `client/config/adminPageMeta.ts` | Avaliar | Titulo/metadados corretos | UX | Baixo | 7 |
| `client/pages/admin/marketing/MarketingWhatsApp.tsx` | Alterar minimo | Exibir delivery metrics e preservar disparador em Marketing | Backend delivery | Medio | 8 |
| `client/lib/chatbotApi.ts` | Nao alterar salvo necessidade | Chatbot web separado do Agente | Nenhuma | Baixo | Fora do escopo principal |

## 11. Plano de execucao em etapas

### Roadmap executivo por fases

| Fase | Nome | Objetivo operacional | Entregavel principal | Depende de | Libera | Validacao minima |
|---|---|---|---|---|---|---|
| 0 | Auditoria e contratos | Fechar a verdade tecnica antes de alterar codigo | Executada em `docs/agente-whatsapp-audio-ia-fase-0.md` | Documento atual | Fase 1 | Contratos, flags, limites e aceite documentados |
| 1 | Campanhas e deliveries | Tornar o disparo rastreavel ate a conversa | Executada em `docs/agente-whatsapp-audio-ia-fase-1.md` | Fase 0 | Fases 2 e 4 | Delivery/snapshot, backfill e vinculo com Agente implementados |
| 2 | Entrada e idempotencia | Receber mensagens sem duplicar conversa/resposta | Executada em `docs/agente-whatsapp-audio-ia-fase-2.md`: idempotencia e job inbound | Fase 1 executada | Fase 3 | Webhook duplicado nao duplica mensagem |
| 3 | Audio inbound e STT | Entender audio recebido do cliente | Executada em `docs/agente-whatsapp-audio-ia-fase-3.md`: download, storage, validacao, transcricao e fallback | Fase 2 executada | Fases 4 e 5 | Audio real vira transcricao persistida |
| 4 | Contexto de campanha | Responder audio/texto sabendo a oferta de origem | Executada em `docs/agente-whatsapp-audio-ia-fase-4.md`: contexto direto, janela e ambiguidade | Fases 1 e 3 executadas | Fase 5 | Resposta usa snapshot e nao inventa preco |
| 5 | Resposta textual IA | Fazer o agente responder com seguranca | Executada em `docs/agente-whatsapp-audio-ia-fase-5.md`: resposta textual, guardrails, humano/IA e anti-duplicidade | Fases 2, 3 e 4 executadas | Fase 6 | Audio do cliente gera resposta textual correta |
| 6 | Voz IA e envio Baileys | Responder clientes com audio/voice note | Executada em `docs/agente-whatsapp-audio-ia-fase-6.md`: TTS, arquivo de voz, envio audio/PTT e fallback texto | Fase 5 executada | Fase 7 | Audio da IA chega reproduzivel no WhatsApp |
| 7 | Painel e configuracoes | Dar operacao ao administrador | Executada em `docs/agente-whatsapp-audio-ia-fase-7.md`: configuracoes de audio, player, transcricao e retry | Fases 3, 4 e 6 executadas | Fase 8 | Operador ve audio, texto, campanha e controles |
| 8 | Metricas e conversoes | Medir custo, falha e venda | Executada em `docs/agente-whatsapp-audio-ia-fase-8.md`: metricas STT/TTS/campanha/conversa/pedido | Fase 7 executada | Fase 9 | Dashboard/auditoria conferem com eventos |
| 9 | Producao e robustez | Rodar com seguranca em ambiente real | Executada em `docs/agente-whatsapp-audio-ia-fase-9.md`: flags, readiness, cleanup LGPD e checklist VPS | Fases 0 a 8 executadas | Expansao gradual | Flags desligam audio sem quebrar texto |
| 10 | Piloto e deploy assistido | Levar o pacote para VPS com controle | Executada em `docs/agente-whatsapp-audio-ia-fase-10.md`: workflow Alembic, handoff VPS e flags de piloto | Fase 9 executada | Piloto real | Deploy aplica migration antes do restart |
| 11 | Expansao gradual | Controlar liberacao por piloto, horario e volume | Executada em `docs/agente-whatsapp-audio-ia-fase-11.md`: rollout por env, limites diarios e readiness | Fase 10 executada | Escala controlada | Telefone fora do piloto nao aciona audio |
| 12 | UI de rollout | Permitir controle operacional do rollout no painel | Executada em `docs/agente-whatsapp-audio-ia-fase-12.md`: GET/PUT de rollout, site_config e painel | Fase 11 executada | Piloto sem editar env | Admin altera modo, piloto, horario e limites |

Sequencia recomendada de execucao:

```text
0 Auditoria e contratos
-> 1 Campanhas e deliveries
-> 2 Entrada e idempotencia
-> 3 Audio inbound e STT
-> 4 Contexto de campanha
-> 5 Resposta textual IA
-> 6 Voz IA e envio Baileys
-> 7 Painel e configuracoes
-> 8 Metricas e conversoes
-> 9 Producao e robustez
```

Marcos de decisao:
- Depois da Fase 0: aprovar contratos, flags, storage e idempotencia.
- Depois da Fase 1: confirmar se `whatsapp_messages` sera evoluida ou se `whatsapp_campaign_deliveries` sera a fonte canonica.
- Depois da Fase 3: decidir se storage local com protecao basta para piloto ou se audio exige URL privada/assinada desde o inicio.
- Depois da Fase 6: validar em Android, iPhone, WhatsApp Web e WhatsApp Desktop antes de liberar cliente real.
- Depois da Fase 9: executar handoff de piloto/deploy assistido.
- Depois da Fase 10: expandir por loja/horario/volume, mantendo fallback textual ligado.
- Depois da Fase 11: criar UI de rollout ou segmentacao multiempresa apenas se o piloto exigir.
- Depois da Fase 12: criar segmentacao multiempresa somente se houver mais de uma loja usando audio em paralelo.

Regra de avanco:
- Nenhuma fase deve iniciar se a anterior ainda tiver risco aberto que possa gerar duplicidade de mensagem, resposta errada, vazamento de audio ou quebra do atendimento textual.
- Implementacoes de banco devem ser sempre aditivas, com migration Alembic e rollback operacional por feature flag.
- O Marketing continua dono de campanhas/disparos; o Agente continua dono de conversas/configuracoes.

### Etapa 0 - Auditoria e contratos

Objetivo:
- Congelar decisoes tecnicas antes de implementar e confirmar contratos reais do Gateway, Agente, Marketing e IA.

Escopo:
- Inventario final dos arquivos, tabelas, rotas, payloads e estados.
- Contrato normalizado para mensagem recebida, audio, mensagem citada, download, envio e status.
- Criterios de aceite por provider.

Arquivos afetados:
- Apenas documentacao: este arquivo e, se autorizado depois, contrato tecnico em `docs/`.

Banco/migration:
- Nenhuma.

Dependencias:
- Nenhuma nova.

Passos tecnicos:
- Revisar payload real Meta, Evolution, UAZAPI e Baileys.
- Confirmar se `store_id`, `tenant_id` ou `company_id` deve entrar em unicos.
- Definir limites iniciais: input 180s, output 45s, janela campanha 72h, prioridade 24h.
- Definir flags.

Testes:
- Checklist manual de payloads e cenarios.

Criterios de aceite:
- Contratos aprovados antes de migration.
- Nenhuma regra de IA dentro do Gateway.

Riscos:
- Provider sem quoted id.

Rollback:
- Nao aplicavel.

O que nao sera feito:
- Nenhuma implementacao funcional.

### Etapa 1 - Persistencia e vinculo de campanhas

Objetivo:
- Criar base confiavel para saber qual campanha originou a conversa.

Escopo:
- Delivery/snapshot de campanha.
- `provider_message_id` confiavel.
- `quoted_provider_message_id`.
- Backfill de `whatsapp_messages`.

Arquivos afetados:
- `backend/models/agente_whatsapp.py`
- `backend/routes/whatsapp_marketing.py`
- `backend/schemas/agente_whatsapp.py`
- NOVA MIGRATION PROPOSTA `*_whatsapp_campaign_deliveries.py`
- NOVA MIGRATION PROPOSTA `*_agente_whatsapp_message_campaign_refs.py`

Banco/migration:
- Criar `whatsapp_campaign_deliveries`.
- Adicionar campos de campanha/quoted em `agente_whatsapp_messages`.
- Indices e unique por provider/id.

Dependencias:
- Nenhuma externa.

Passos tecnicos:
- Em todo disparo de Marketing, gravar delivery com snapshot.
- Mapear `wamid` atual para `provider_message_id`.
- Atualizar sync com Agente para salvar `campaign_delivery_id`.
- Criar servico de resolucao por quoted id e por janela.

Testes:
- Unitario de vinculo direto.
- Unitario de janela 24/72h.
- Ambiguidade com duas campanhas recentes.
- Backfill sem perder historico.

Criterios de aceite:
- Uma resposta direta a campanha encontra a campanha pelo id do provider.
- Uma resposta sem quote encontra a ultima campanha se houver apenas uma candidata segura.
- Com varias candidatas, marca ambiguidade e nao inventa oferta.

Riscos:
- Historico antigo sem `wamid` nao tera vinculo direto.

Rollback:
- Desativar flag de contexto de campanha.
- Manter delivery como historico sem uso pelo Agente.

O que nao sera feito:
- Audio, STT ou TTS.

### Etapa 2 - Entrada de mensagens e conversas

Objetivo:
- Normalizar inbound de texto/midia/audio e garantir idempotencia antes do processamento pesado.

Escopo:
- Provider/Gateway normalizado.
- Quoted message no payload.
- Persistencia rapida.
- Jobs inbound.
- Verificacao de humano/IA antes de responder.

Arquivos afetados:
- `server/whatsapp-gateway-runtime.mjs`
- `backend/services/whatsapp_gateway_service.py`
- `backend/services/whatsapp_gateway_runtime_client.py`
- `backend/services/agente_whatsapp_service.py`
- NOVO ARQUIVO PROPOSTO `backend/services/agente_whatsapp_processing_service.py`

Banco/migration:
- Criado `agente_whatsapp_processing_jobs` em `20260701_whatsapp_audio_phase2_inbound_jobs.py`.
- Adicionados `idempotency_key`, `processing_status` e `processed_at`.

Dependencias:
- Nenhuma externa inicial.

Passos tecnicos:
- Webhook persiste mensagem e agenda job.
- Jobs verificam duplicidade antes de executar.
- Provider states e internal alerts devem cobrir falhas de inbound.
- Sessions existentes devem respeitar canal ativo quando aplicavel.

Testes:
- Webhook duplicado.
- Status fora de ordem.
- Inbound enquanto humano assumiu.
- Reinicio durante job pendente.

Criterios de aceite:
- Webhook retorna rapido.
- Mensagem duplicada nao cria nova conversa nem nova resposta.
- Mensagem inbound aparece na conversa.

Riscos:
- Corrida entre status da sessao e job.

Rollback:
- Desligar worker inbound.
- Manter persistencia textual atual.

O que nao sera feito:
- Transcricao e TTS.

### Etapa 3 - Recepcao e transcricao de audio

Objetivo:
- Baixar, validar, armazenar e transcrever audio recebido.

Escopo:
- Download seguro.
- Validacao MIME, tamanho e duracao.
- Storage de original/normalizado.
- STT principal e fallback.
- Transcricao visivel no backend.

Arquivos afetados:
- NOVO ARQUIVO PROPOSTO `backend/services/agente_whatsapp_audio_service.py`
- `backend/services/ai/openai_provider.py`
- `backend/services/ai/base.py` ou NOVA interface de audio
- `backend/routes/upload.py` ou rota propria de media interna
- `backend/models/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`

Banco/migration:
- Campos de transcricao em `agente_whatsapp_messages` criados em `20260701_whatsapp_audio_phase3_audio_stt.py`.
- Criado `agente_whatsapp_audio_artifacts`.

Dependencias:
- `openai>=1.50.0` ja existe; validar suporte do SDK antes da implementacao.
- Avaliar `ffmpeg` no servidor apenas se for necessaria conversao para OGG/Opus.

Passos tecnicos:
- Aceitar tipos iniciais: `audio/ogg`, `audio/opus`, `audio/mpeg`, `audio/mp4`, `audio/webm`.
- Rejeitar audio acima dos limites configurados.
- Transcrever com `gpt-4o-mini-transcribe`.
- Usar `gpt-4o-transcribe` se baixa qualidade.
- Detectar baixa qualidade sem inventar score: texto vazio, texto curto para duracao, repeticoes anormais, caracteres incoerentes, termos criticos duvidosos, validacao contra catalogo/contexto.
- Se duvidoso, pedir confirmacao ou transferir para humano conforme config.

Testes:
- Audio valido.
- MIME invalido.
- Audio longo.
- STT falha e fallback funciona.
- Baixa qualidade vira `needs_human` ou pergunta de confirmacao.

Criterios de aceite:
- Audio recebido gera transcricao persistida.
- Falha nao bloqueia conversa.
- Segredo de provider nao aparece em log.

Riscos:
- Formato de audio do WhatsApp varia por provider.

Rollback:
- Desligar `WHATSAPP_AUDIO_INPUT_ENABLED`.
- Audio continua registrado como mensagem de tipo audio, sem transcricao.

O que nao sera feito:
- Responder em audio.

### Etapa 4 - Contexto da campanha

Objetivo:
- Fornecer ao Agente o contexto correto da campanha ao responder texto ou audio.

Escopo:
- Vinculo direto por quote.
- Vinculo por janela.
- Ambiguidade.
- Snapshot de oferta.
- Inclusao no prompt/contexto.

Arquivos afetados:
- Criado `backend/services/agente_whatsapp_campaign_context_service.py`
- Alterado `backend/services/agente_whatsapp_ai_service.py`
- Alterado `backend/services/agente_whatsapp_tools.py`
- Alterado `backend/routes/agente_whatsapp.py`

Banco/migration:
- Reusar deliveries e campos da Etapa 1.

Dependencias:
- Etapa 1 concluida.

Passos tecnicos:
- `quoted_provider_message_id` resolve delivery.
- Sem quote, buscar deliveries do telefone na janela 72h.
- Priorizar 24h.
- Se houver empate relevante, passar candidatas e instruir IA a perguntar.
- Incluir status da campanha, validade, produto, preco, cupom e midia.
- Nunca permitir que o modelo invente oferta se snapshot nao existir.

Testes:
- Campanha unica recente.
- Duas campanhas recentes.
- Campanha expirada.
- Produto/promocao removida do catalogo depois do disparo.

Criterios de aceite:
- O agente responde com base no snapshot, nao no template atual alterado.
- Ambiguidade nao vira oferta inventada.

Riscos:
- Campanhas antigas sem snapshot limitado.

Rollback:
- Desligar `WHATSAPP_CAMPAIGN_CONTEXT_ENABLED`.

O que nao sera feito:
- Dashboard comercial completo.

### Etapa 5 - Resposta textual pelo agente

Objetivo:
- Fazer a transcricao entrar no fluxo de resposta textual do Agente com guardrails.

Escopo:
- Integrar transcricao como mensagem do cliente.
- Montar contexto.
- Gerar resposta textual.
- Prevenir resposta duplicada.
- Respeitar humano/IA.

Arquivos afetados:
- `backend/services/agente_whatsapp_ai_service.py`
- `backend/services/agente_whatsapp_service.py`
- `backend/services/agente_whatsapp_processing_service.py`
- `backend/services/agente_whatsapp_worker.py`
- `backend/services/agente_whatsapp_outbox_service.py`
- `backend/routes/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `client/lib/api.ts`

Banco/migration:
- Migration `20260701_whatsapp_audio_phase5_agent_response.py`.
- Campo `agente_whatsapp_messages.response_to_message_id`.
- Backfill de jobs `agent_response` para mensagens inbound elegiveis.

Dependencias:
- Etapas 2, 3 e 4.

Passos tecnicos:
- Job de agente recebe texto transcrito.
- Antes de responder, verificar `session.ai_enabled`, `automation_blocked` e `status`.
- Registrar `manager_review` e tool trace.
- Se dado critico estiver duvidoso, pedir confirmacao em vez de executar acao.
- Para links, PIX, cupons, enderecos e codigos, garantir texto mesmo quando saida por audio estiver ativa.

Testes:
- IA pausada nao responde.
- Humano assumiu durante processamento.
- Transcricao duvidosa exige confirmacao.
- Resposta duplicada nao ocorre.

Criterios de aceite:
- Cliente que envia audio recebe resposta textual correta quando audio output esta desligado.

Riscos:
- Prompt muito grande com campanha + historico + catalogo.

Rollback:
- Desligar `WHATSAPP_AI_AUTO_REPLY_ENABLED`.
- Manter atendimento humano e texto manual.

O que nao sera feito:
- TTS e envio de voz.

### Etapa 6 - Geracao e envio de voz

Objetivo:
- Converter resposta textual em audio e enviar como mensagem de voz quando configurado.

Escopo:
- TTS `gpt-4o-mini-tts`.
- Voz `marin`.
- Formato preferencial Opus.
- Limite de 45s.
- Fallback texto.
- Envio audio/PTT no Gateway.

Arquivos afetados:
- `backend/services/agente_whatsapp_audio_service.py`
- `backend/services/agente_whatsapp_processing_service.py`
- `backend/services/agente_whatsapp_worker.py`
- `backend/services/agente_whatsapp_outbox_service.py`
- `backend/services/whatsapp_gateway_service.py`
- `backend/services/whatsapp_gateway_runtime_client.py`
- `backend/services/whatsapp_gateway_provider.py`
- `backend/services/whatsapp_gateway_baileys_provider.py`
- `backend/services/ai/base.py`
- `backend/services/ai/openai_provider.py`
- `backend/routes/agente_whatsapp.py`
- `backend/routes/whatsapp_marketing.py`
- `backend/schemas/agente_whatsapp.py`
- `backend/config.py`
- `client/lib/api.ts`
- `server/whatsapp-gateway-runtime.mjs`

Banco/migration:
- Sem migration nova.
- Reusa `agente_whatsapp_audio_artifacts` com `artifact_type='tts'`.
- Reusa `agente_whatsapp_processing_jobs` com `job_type='tts_generation'`.
- Reusa mensagem outbound `audio` com `response_to_message_id` apontando para a resposta textual.

Dependencias:
- OpenAI SDK atual validado.
- Possivel `ffmpeg` no VPS se a saida precisar conversao.

Passos tecnicos:
- Aplicar politica `audio_response_mode`: `never`, `mirror_customer_audio`, `always`, `manual_only`.
- Resumir resposta se exceder limite.
- Gerar audio.
- Se provider aceitar PTT, enviar como voice note.
- Se TTS ou envio falhar, manter texto e enviar fallback se habilitado.
- Usar idempotencia por mensagem de resposta para nao enviar audio e texto duplicados sem regra.

Testes:
- Cliente manda texto, recebe texto.
- Cliente manda audio, recebe audio no modo espelho.
- Falha TTS envia texto.
- Falha gateway envia texto ou fica em retry conforme config.
- WhatsApp Android/iPhone/Web/Desktop.

Criterios de aceite:
- Audio da IA chega como mensagem reproduzivel no WhatsApp.
- Texto critico tambem e enviado em texto.

Riscos:
- Formato aceito pelo WhatsApp/provider pode exigir OGG/Opus especifico.

Rollback:
- Desligar `WHATSAPP_AUDIO_OUTPUT_ENABLED`.
- Resposta textual continua.

O que nao sera feito:
- Campanhas de audio em massa no Marketing.

### Etapa 7 - Configuracoes e experiencia do painel

Objetivo:
- Tornar audio operavel por administradores sem quebrar o layout admin.

Escopo:
- Agente com apenas Conversas e Configuracoes.
- Player de audio.
- Transcricao expandir/ocultar.
- Campanha de origem.
- Status STT/TTS.
- Retry.
- Responder com audio.
- Configuracoes de audio e voz.

Arquivos afetados:
- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`
- `client/lib/api.ts`
- NOVO ARQUIVO PROPOSTO `client/components/admin/AudioMessagePlayer.tsx`
- NOVO ARQUIVO PROPOSTO `client/components/admin/WhatsAppCampaignContextCard.tsx`
- NOVO ARQUIVO PROPOSTO `client/components/admin/AudioSettingsPanel.tsx`
- `client/config/adminNavigation.ts`
- `client/config/adminPageMeta.ts`

Banco/migration:
- Nenhuma nova alem de settings ja criadas.

Dependencias:
- Backend das etapas anteriores.

Passos tecnicos:
- Renderizar audio inbound/outbound.
- Mostrar transcricao, qualidade e erros.
- Mostrar campanha vinculada ou ambigua.
- Botao retry de STT/TTS.
- Botao assumir/devolver continua.
- Configurar modos de resposta por audio.
- Garantir responsividade.

Testes:
- Estados loading/erro/vazio.
- Player em desktop/mobile.
- Permissoes.
- Texto sem sobreposicao.
- Conversa com campanha e sem campanha.

Criterios de aceite:
- Operador entende o que foi falado, de onde veio a campanha e consegue assumir/retry.

Riscos:
- Tela atual densa; risco visual alto.

Rollback:
- Ocultar componentes de audio por flag frontend/backend.

O que nao sera feito:
- Redesign do shell global.

### Etapa 8 - Metricas, custos e conversoes

Objetivo:
- Medir operacao e resultado comercial do audio por IA.

Escopo:
- STT/TTS custo, duracao, falhas, latencia.
- Campanha -> conversa -> pedido.
- Conversoes e receita.
- Auditoria por mensagem.

Arquivos afetados:
- `backend/models/agente_whatsapp.py`
- `backend/services/agente_whatsapp_service.py`
- `backend/services/agente_whatsapp_analytics_service.py`
- `backend/services/agente_whatsapp_audio_service.py`
- `backend/services/agente_whatsapp_outbox_service.py`
- `backend/routes/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `client/lib/api.ts`
- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`
- `client/pages/admin/marketing/MarketingWhatsApp.tsx`

Banco/migration:
- Sem migration nova nesta fase.
- Metricas derivadas de mensagens, jobs, artifacts, outbox, campanhas e pedidos.
- Latencia STT passa a ser gravada em `transcription_quality_json` para novos audios.

Dependencias:
- Etapas 1 a 7.

Passos tecnicos:
- Registrar tokens/custos estimados por provider/model.
- Registrar tempo de download, STT, IA, TTS, envio.
- Registrar campanha identificada direta/inferida/ambigua.
- Vincular pedidos gerados a campanha quando a conversa resultar em pedido.

Testes:
- Metricas atualizam em sucesso.
- Falhas tambem geram metricas.
- Pedido gerado vincula campanha.

Criterios de aceite:
- Admin consegue auditar uma conversa e entender custo/falha/conversao.

Riscos:
- Custo real depende do billing externo; usar estimativa documentada.

Rollback:
- Desligar dashboards novos mantendo logs.

O que nao sera feito:
- BI avancado fora do Agente/Marketing.

### Etapa 9 - Robustez e producao

Objetivo:
- Preparar operacao real em VPS com seguranca, LGPD, observabilidade, carga, rollout e rollback.

Escopo:
- Feature flags.
- Logs e alertas.
- Retencao e cleanup.
- RBAC.
- Webhook secret/replay.
- Teste em dispositivos.
- Documentacao operacional.

Arquivos afetados:
- `backend/config.py`
- `backend/main.py`
- `backend/routes/lgpd.py` e RBAC se necessario
- `backend/routes/agente_whatsapp.py`
- `backend/services/agente_whatsapp_retention_service.py`
- `backend/services/agente_whatsapp_worker.py`
- `backend/services/whatsapp_gateway_service.py`
- `client/lib/api.ts`
- `docs/agente-whatsapp-audio-ia-fase-9.md`
- systemd/runtime configs na VPS em deploy futuro

Banco/migration:
- Sem migration nova nesta fase.
- Retencao implementada sobre `agente_whatsapp_audio_artifacts` com status `deleted` e remocao fisica segura por diretorio configurado.

Dependencias:
- Todas as etapas anteriores.

Passos tecnicos:
- Implementado endpoint de readiness operacional.
- Implementado cleanup de audio com `dry_run=true` por padrao.
- Conectadas flags de STT/TTS/fallback/baixa confianca/Gateway audio.
- Documentado checklist VPS em `docs/agente-whatsapp-audio-ia-fase-9.md`.
- Validar Android, iPhone, Web e Desktop em piloto real.
- Confirmar logs sem segredos na VPS.

Testes:
- Build, typecheck, testes backend, testes de contrato gateway.
- Testes manuais ponta a ponta.
- Teste de reinicio do worker.

Criterios de aceite:
- Desativar audio nao derruba texto, Marketing, checkout ou pedidos.

Riscos:
- VPS sem codec/ffmpeg se conversao for necessaria.

Rollback:
- Flags, pausar worker, manter texto e atendimento humano.

O que nao sera feito:
- Migrar toda infraestrutura para fila externa sem evidencia de necessidade.

### Etapa 10 - Piloto e deploy assistido

Objetivo:
- Levar o pacote de Audio/IA para VPS com migrations, flags conservadoras e validacao operacional antes de clientes reais.

Escopo:
- Workflow de deploy com Alembic antes do build/restart.
- Handoff de piloto controlado.
- Flags iniciais seguras.
- Checklist de readiness, jobs, outbox, gateway e cleanup dry-run.

Arquivos afetados:
- `.github/workflows/deploy.yml`
- `docs/agente-whatsapp-audio-ia-fase-10.md`

Banco/migration:
- Sem migration nova nesta fase.
- O deploy mira a revision `20260701_whatsapp_audio_phase5_agent_response`.

Dependencias:
- Fase 9 executada.
- Push para `main` antes do deploy automatizado.

Passos tecnicos:
- Rodar Alembic `current`, `heads` e `upgrade 20260701_whatsapp_audio_phase5_agent_response`.
- Reiniciar API, web e gateway.
- Validar `/health`, gateway health, readiness de audio, processing summary e outbox alerts.
- Comecar com auto reply/TTS/audio Baileys desligados para cliente real.

Testes:
- `git diff --check`
- Validacao local ja coberta pelas fases anteriores.
- Validacao real deve ocorrer na VPS apos push/deploy.

Criterios de aceite:
- Deploy nao reinicia servicos antes de aplicar migrations.
- Piloto pode iniciar com audio input sem resposta automatica.
- Rollback por flags permanece disponivel.

Riscos:
- Deploy real ainda depende de push, secrets do GitHub e estado atual da VPS.

Rollback:
- Reverter flags de audio para falso e manter texto/atendimento humano.

O que nao sera feito:
- Executar deploy real nesta etapa local.
- Liberar audio para todos os clientes sem piloto.

### Etapa 11 - Expansao gradual

Objetivo:
- Controlar liberacao do Audio/IA por piloto, janela horaria e volume diario.

Escopo:
- Modo de rollout por env: `all`, `pilot` ou `off`.
- Lista de telefones piloto.
- Janela horaria operacional.
- Limites diarios de audio recebido, resposta automatica e TTS.
- Readiness expondo status e uso do rollout.

Arquivos afetados:
- `backend/config.py`
- `backend/routes/agente_whatsapp.py`
- `backend/services/agente_whatsapp_processing_service.py`
- `backend/services/agente_whatsapp_rollout_service.py`
- `docs/agente-whatsapp-audio-ia-fase-11.md`

Banco/migration:
- Sem migration nova.
- Contadores diarios sao derivados de `agente_whatsapp_messages`.

Dependencias:
- Fase 10 executada.

Passos tecnicos:
- Configurar `WHATSAPP_AUDIO_ROLLOUT_MODE`.
- Definir telefones piloto se modo `pilot`.
- Definir `WHATSAPP_AUDIO_ROLLOUT_HOURS` se houver janela operacional.
- Definir limites diarios para controlar custo e volume.
- Validar readiness antes de liberar clientes reais.

Testes:
- `git diff --check`
- `npm.cmd run typecheck`
- `npm.cmd test`

Criterios de aceite:
- Telefone fora do piloto nao aciona audio quando modo `pilot`.
- Fora da janela horaria, audio nao avanca para automacao.
- Limite diario impede crescimento inesperado.
- Atendimento textual e humano continuam funcionando.

Riscos:
- Sem UI, alteracao de rollout depende de env/restart.

Rollback:
- `WHATSAPP_AUDIO_ROLLOUT_MODE=off`.

O que nao sera feito:
- Tela administrativa de rollout.
- Segmentacao multiempresa avancada.

### Etapa 12 - UI de rollout

Objetivo:
- Permitir que o administrador controle o rollout de audio/IA pelo painel, sem depender de edicao direta de variaveis de ambiente.

Escopo:
- Configuracao persistida em `site_config.content.agente_whatsapp_audio_rollout`.
- Endpoints de leitura e atualizacao do rollout.
- Painel com modo, telefones piloto, janela horaria, limites diarios e uso do dia.
- `.env` permanece como fallback inicial.

Arquivos afetados:
- `backend/services/agente_whatsapp_rollout_service.py`
- `backend/routes/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `client/lib/api.ts`
- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`
- `docs/agente-whatsapp-audio-ia-fase-12.md`

Banco/migration:
- Sem migration nova.
- Reusa `site_config`.

Dependencias:
- Fase 11 executada.

Passos tecnicos:
- Adicionar `GET /agente-whatsapp/audio/rollout`.
- Adicionar `PUT /agente-whatsapp/audio/rollout`.
- Fazer o serviço de rollout ler `site_config` antes do fallback de ambiente.
- Adicionar tipos no API client.
- Adicionar bloco de configuracao na aba Configuracoes do Agente WhatsApp.

Testes:
- `git diff --check`
- `npm.cmd run typecheck`
- `npm.cmd test`
- `npm.cmd run build`

Criterios de aceite:
- Admin consegue alterar modo `all`, `pilot` ou `off`.
- Admin consegue editar telefones piloto, janela horaria e limites diarios.
- Readiness e processamento respeitam a configuracao persistida.
- Sem migration nova e sem quebrar o fallback por env.

Riscos:
- Alteracoes operacionais mal configuradas podem bloquear respostas; manter modo `off` como rollback imediato.

Rollback:
- Alterar modo para `off` pelo painel ou remover o bloco `agente_whatsapp_audio_rollout` de `site_config`.

O que nao sera feito:
- Segmentacao multiempresa avancada.
- Controle por usuario/perfil alem do admin atual.

## 12. Ordem de migrations

1. Migration de delivery de campanhas:
   - Criar `whatsapp_campaign_deliveries`.
   - Backfill de `whatsapp_messages`.
   - Indices e unique por provider/message id.

2. Migration de referencias de campanha em mensagens:
   - Adicionar `quoted_provider_message_id`, `campaign_id`, `campaign_delivery_id`.
   - Adicionar indices.

3. Migration de processamento:
   - Criar `agente_whatsapp_processing_jobs`.
   - Adicionar `processing_status`, `idempotency_key`, `processed_at`.

4. Migration de audio/transcricao:
   - Adicionar campos de midia/transcricao em `agente_whatsapp_messages`.
   - Criar `agente_whatsapp_audio_artifacts`.

5. Configuracoes de audio:
   - Implementado em `site_config.content.agente_whatsapp_audio`.
   - Sem migration nova enquanto a configuracao for singleton.

6. Migration de TTS/outbound:
   - Adicionar campos `tts_*` se nao incluidos na migration de audio.
   - Ajustar indices de status.

7. Migration de metricas:
   - Ampliar `agente_whatsapp_metrics` ou criar `agente_whatsapp_audio_metrics`.
   - Criar indices por data/campanha/provider/model.

8. Migration de auditoria/retencao opcional:
   - Registrar acesso/delecao de audio se a politica LGPD exigir tabela separada.

## 13. Estrategia de rollout

Feature flags propostas:
- `WHATSAPP_AUDIO_INPUT_ENABLED`
- `WHATSAPP_AUDIO_OUTPUT_ENABLED`
- `WHATSAPP_CAMPAIGN_CONTEXT_ENABLED`
- `WHATSAPP_AI_AUTO_REPLY_ENABLED`
- `WHATSAPP_AUDIO_TEXT_FALLBACK_ENABLED`
- `WHATSAPP_AUDIO_LOW_CONFIDENCE_HANDOFF_ENABLED`
- `WHATSAPP_AUDIO_RETENTION_CLEANUP_ENABLED`
- `WHATSAPP_GATEWAY_AUDIO_BAILEYS_ENABLED`

Sequencia:
1. Local: contratos, migrations, testes unitarios.
2. Staging: Gateway com instancia de teste.
3. Piloto: uma loja, apenas transcricao inbound.
4. Piloto: resposta textual automatica usando transcricao.
5. Piloto: contexto de campanha habilitado.
6. Piloto: audio outbound apenas para admins/telefones de teste.
7. Producao parcial: modo espelho para clientes reais.
8. Expansao gradual por volume/horario.

Guardrails:
- Ativar audio input antes de audio output.
- Ativar campanha contextual antes de IA auto reply com campanhas.
- Manter fallback textual ligado no inicio.
- Limitar duracao de entrada e saida.
- Pausar provider automaticamente em falhas consecutivas.

## 14. Estrategia de rollback

Entrada de audio:
- Desligar `WHATSAPP_AUDIO_INPUT_ENABLED`.
- Webhook registra audio como mensagem simples sem STT.

Transcricao:
- Pausar `agente_whatsapp_processing_jobs` do tipo `audio_transcription`.
- Manter mensagens e atendimento humano.

Resposta automatica:
- Desligar `WHATSAPP_AI_AUTO_REPLY_ENABLED`.
- Conversas ficam abertas ou `waiting_human`.

TTS:
- Desligar `WHATSAPP_AUDIO_OUTPUT_ENABLED`.
- Enviar texto com fallback.

Contexto de campanha:
- Desligar `WHATSAPP_CAMPAIGN_CONTEXT_ENABLED`.
- Agente nao usa oferta no prompt, mas Marketing continua disparando.

Gateway audio:
- Desligar `WHATSAPP_GATEWAY_AUDIO_BAILEYS_ENABLED`.
- `send_media_message` texto/imagem/video continua.

Novo worker inbound:
- Desativar no `backend/config.py`.
- Nao remover dados ja processados.

Migrations:
- Rollback operacional por flag e preferivel.
- Downgrade fisico so em ambiente controlado, pois tabelas novas guardam auditoria e historico.

## 15. Matriz de riscos

| Risco | Probabilidade | Impacto | Prevencao | Deteccao | Resposta |
|---|---:|---:|---|---|---|
| Enviar audio duplicado | Media | Alto | Idempotency key por mensagem/resposta | Outbox duplicado, provider ids repetidos | Bloquear segundo envio e marcar duplicado |
| Provider nao entrega quoted id | Alta | Medio | Fallback por janela e ambiguidade | Payload sem quoted | Perguntar ao cliente quando ambiguo |
| Audio sai em formato incompativel | Media | Alto | Testes Android/iPhone/Web/Desktop | Falha gateway ou audio nao reproduz | Converter formato ou fallback texto |
| Webhook lento/timeouts | Media | Alto | Persistir rapido e processar job | Latencia webhook | Pausar processamento inline |
| Transcricao errada muda pedido | Media | Alto | Confirmar dados criticos e baixa qualidade | Sinais de incoerencia | Pedir confirmacao ou humano |
| IA inventa promocao/preco | Media | Alto | Snapshot e prompt proibindo invencao | Auditoria de resposta | Bloquear ferramenta/transferir humano |
| Vazamento de audio publico | Media | Alto | URL privada/retencao/RBAC | Auditoria de acesso | Revogar URLs e excluir arquivos |
| Custo de STT/TTS cresce | Media | Medio | Limites, flags, metricas | Dashboard de custo | Reduzir modos ou desativar audio output |
| Runtime Baileys quebra por update | Media | Alto | Contrato e testes; auto update controlado | Health/logs | Rollback package/runtime |
| Campanha errada por janela | Media | Medio | Ambiguidade explicita | Multiplas candidatas | Perguntar qual promocao |
| Humano e IA respondem juntos | Media | Alto | Lock/status antes de enviar | Mensagens simultaneas | Cancelar job e marcar waiting_human |
| Logs com segredo/payload sensivel | Baixa | Alto | Sanitizacao | Revisao de logs | Rotacionar segredo e limpar logs |
| Arquivos orfaos | Media | Medio | Artifact table e cleanup | Storage sem registro | Job de limpeza |

## 16. Dependencias sugeridas

Dependencias atuais verificadas:
- Backend ja possui `openai>=1.50.0` e `anthropic>=0.40.0`.
- Node ja possui `@whiskeysockets/baileys`.
- Nao existe `pyproject.toml` nem `requirements.txt` na raiz; requisitos backend estao em `backend/requirements.txt`.

Novas dependencias propostas:

| Nome | Motivo | Alternativas | Impacto | Licenca | Onde sera usada | Realmente necessaria? |
|---|---|---|---|---|---|---|
| `ffmpeg` no sistema operacional | Converter/normalizar audio para OGG/Opus se provider/TTS exigir | Usar formato nativo retornado pelo SDK se compativel | Operacional na VPS | LGPL/GPL conforme build | Worker audio/backend ou runtime | Somente se testes mostrarem incompatibilidade |
| Biblioteca Python de sniffing MIME, por exemplo `python-magic` | Validar MIME real, nao apenas extensao/header | Validacao basica por `filetype`, ffprobe, ou assinatura manual limitada | Nova dependencia backend | MIT/BSD conforme pacote escolhido | Upload/download de audio | Recomendada se audio virar producao |
| Nenhuma dependencia npm nova inicialmente | Baileys ja existe e HTML audio nativo resolve player | Player custom | Menor impacto | N/A | Frontend/runtime | Nao necessaria no inicio |

Observacao: nao alterar versoes nesta tarefa. Antes da implementacao, validar no ambiente local/VPS se a versao instalada do SDK OpenAI suporta `gpt-4o-mini-transcribe`, `gpt-4o-transcribe` e `gpt-4o-mini-tts` com o formato desejado.

## 17. Perguntas e decisoes pendentes

1. Escopo multiempresa:
   - Opcoes: chave unica so por provider/message id; ou incluir tenant/store/company.
   - Recomendacao: incluir escopo de tenant/company quando consolidado, pois `whatsapp_gateway_instances` ja possui `tenant_id` e `company_id`.
   - Consequencia: evita colisao entre lojas.

2. Storage publico ou privado:
   - Opcoes: continuar `/uploads`; criar endpoint autenticado; S3/URLs assinadas.
   - Recomendacao: para voz, endpoint autenticado ou URL assinada; usar `/uploads` apenas em piloto controlado.
   - Consequencia: LGPD mais forte, mas maior complexidade.

3. Fila interna ou externa:
   - Opcoes: tabela de jobs; Redis/Celery; fila do provider.
   - Recomendacao: tabela de jobs primeiro, porque a infra atual ja usa DB/outbox e VPS simples.
   - Consequencia: menos infra; avaliar fila externa se volume crescer.

4. Audio oficial Meta Cloud:
   - Opcoes: suportar Baileys primeiro; suportar todos providers na mesma fase.
   - Recomendacao: contrato multi-provider, implementacao piloto Baileys, depois oficial.
   - Consequencia: menor risco inicial sem fechar arquitetura.

5. Resposta por voz padrao:
   - Opcoes: nunca, sempre, espelhar cliente, manual.
   - Recomendacao: espelhar cliente por padrao com fallback texto ligado.
   - Consequencia: experiencia natural com custo controlado.

6. Baixa qualidade de transcricao:
   - Opcoes: sempre fallback de modelo; sempre humano; heuristica.
   - Recomendacao: heuristica + fallback em casos de duvida + confirmacao para dados criticos.
   - Consequencia: menor risco operacional.

7. Agente WhatsApp com abas:
   - Opcoes: manter varias abas atuais; reduzir para Conversas/Configuracoes; mover campanhas/stories.
   - Recomendacao: convergir Agente para Conversas/Configuracoes e manter disparador/campanhas em Marketing.
   - Consequencia: exige ajuste de UI sem remover dados.

8. Snapshot de produtos/ofertas:
   - Opcoes: referenciar produto atual; salvar snapshot no delivery.
   - Recomendacao: snapshot no delivery.
   - Consequencia: historico correto mesmo se produto/preco mudar.

## 18. Checklist para autorizacao da implementacao

Etapa 0:
- [ ] Contrato normalizado de inbound aprovado.
- [ ] Contrato Gateway audio/download aprovado.
- [ ] Decisao de storage aprovada.
- [ ] Feature flags aprovadas.

Etapa 1:
- [ ] Modelo de `whatsapp_campaign_deliveries` aprovado.
- [ ] Estrategia de backfill aprovada.
- [ ] Regras de ambiguidade aprovadas.

Etapa 2:
- [ ] Chave de idempotencia aprovada.
- [ ] Job table interna aprovada.
- [ ] Estados humano/IA revisados.

Etapa 3:
- [ ] Tipos MIME e limites aprovados.
- [ ] Modelos STT aprovados.
- [ ] Politica de baixa qualidade aprovada.
- [ ] Retencao de audio original aprovada.

Etapa 4:
- [ ] Campos de contexto de campanha aprovados.
- [ ] Prompt/regras anti-invencao aprovados.
- [ ] Tratamento de campanha expirada aprovado.

Etapa 5:
- [ ] Guardrails de dados criticos aprovados.
- [ ] Politica de resposta automatica aprovada.
- [ ] Bloqueio humano/IA aprovado.

Etapa 6:
- [ ] Modelo TTS, voz e formato aprovados.
- [ ] Compatibilidade WhatsApp testada.
- [ ] Fallback textual aprovado.

Etapa 7:
- [ ] Layout com apenas Conversas/Configuracoes aprovado.
- [ ] Player/transcricao/campanha aprovados.
- [ ] Permissoes/RBAC aprovadas.

Etapa 8:
- [ ] Metricas de custo aprovadas.
- [ ] Vinculo campanha -> conversa -> pedido aprovado.
- [ ] Auditoria aprovada.

Etapa 9:
- [x] Rollout local/staging/piloto documentado.
- [x] Rollback por flags implementado.
- [x] LGPD/retencao revisados com cleanup dry-run.
- [x] Deploy VPS documentado.

Etapa 10:
- [x] Workflow de deploy com Alembic antes do restart.
- [x] Handoff de piloto documentado.
- [x] Flags conservadoras de piloto definidas.
- [x] Criterios de aceite e rollback documentados.

Etapa 11:
- [x] Modo de rollout implementado.
- [x] Telefones piloto implementados.
- [x] Janela horaria e limites diarios implementados.
- [x] Readiness mostra status do rollout.

Etapa 12:
- [x] Configuracao de rollout persistida em `site_config`.
- [x] Endpoints GET/PUT de rollout implementados.
- [x] Painel de rollout implementado na aba Configuracoes.
- [x] Fallback por env preservado.

Confirmacao final:
- [ ] Nenhuma implementacao funcional deve iniciar antes da aprovacao explicita da etapa correspondente.

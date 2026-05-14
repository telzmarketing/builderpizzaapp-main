# AGENTE WHATSAPP - Fase 19

## Objetivo

Criar configuracao propria da IA do AGENTE WHATSAPP, separada da IA do chatbot da loja, para definir provider, modelo, prompt, regras comerciais, tom de voz e chaves de API.

## Entrega

- Nova tabela `agente_whatsapp_ai_settings`.
- Migration `20260514_agente_whatsapp_ai_settings`.
- Sincronizacao runtime em `backend/main.py`.
- Endpoints administrativos:
  - `GET /api/agente-whatsapp/ai/settings`
  - `PUT /api/agente-whatsapp/ai/settings`
  - `GET /api/agente-whatsapp/ai/settings/status`
  - `PUT /api/agente-whatsapp/ai/settings/keys`
  - `POST /api/agente-whatsapp/ai/settings/test`
- Painel CRM > Agente WhatsApp com secao `Configuracoes da IA`.
- Chaves de API nao sao expostas ao frontend; somente preview mascarado e status.

## Regras Implementadas

- O AGENTE WHATSAPP tem configuracao de IA independente do chatbot do site.
- Providers suportados:
  - `internal`
  - `openai`
  - `claude`
- O modo `internal` continua usando o runtime seguro deterministico.
- Providers externos usam as chaves salvas no banco ou fallback de variaveis de ambiente.
- O prompt final e composto por:
  - prompt principal
  - objetivo
  - tom de voz
  - regras comerciais
  - instrucoes de transferencia humana
  - limitacoes e proibicoes
- A IA continua obrigada a usar ferramentas reais antes de afirmar dados operacionais.

## Limites Atuais

- A Fase 19 configura e testa provider/prompt.
- A resposta operacional da Fase 17 ainda preserva o runtime deterministico seguro para nao criar resposta sem tool calling.
- A evolucao para usar provider externo no fluxo automatico deve manter tool calling e guardrails antes de qualquer envio real.

## Criterio de Aceite

- O administrador consegue configurar provider, modelo, prompt, regras e chaves no modulo AGENTE WHATSAPP.
- O sistema consegue testar a conexao da IA pelo endpoint proprio.
- O chatbot da loja permanece separado e sem alteracao de configuracao.

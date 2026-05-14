# AGENTE WHATSAPP - Fase 1

Data: 2026-05-13
Status: Implementacao da base de identidade do cliente

## Objetivo

Criar a fundacao para o WhatsApp usar telefone como identidade principal, sem quebrar o cadastro, login, CRM, pedidos ou checkout atuais.

## Escopo implementado

- Criacao das tabelas `customer_auth`, `customer_channels` e `customer_preferences`.
- Backfill dos clientes atuais para canais `email`, `phone` e `whatsapp`.
- Service `CustomerIdentityService` para normalizar telefone, localizar cliente por canal e criar lead WhatsApp.
- Endpoint admin para consultar identidade por telefone.
- Endpoint admin para criar/localizar lead WhatsApp.
- Cadastro atual passa a completar um lead WhatsApp existente em vez de criar duplicidade.
- Login atual continua usando email/telefone e senha.
- Clientes novos do site continuam tendo email/senha.

## Decisoes de compatibilidade

O campo `customers.email` continua obrigatorio nesta fase. Para leads criados pelo WhatsApp, o sistema usa um email tecnico interno no dominio `lead.whatsapp.local` ate o cliente informar email real.

Essa decisao evita uma alteracao perigosa na constraint atual de `customers.email`, preservando login, CRM, listagens e schemas existentes.

## Rotas adicionadas

- `GET /api/customers/identity/by-phone?phone=...&channel=whatsapp`
- `POST /api/customers/identity/whatsapp-lead`

As rotas exigem autenticacao admin nesta fase. O webhook publico do WhatsApp sera tratado na Fase 3 usando o service interno, nao expondo criacao aberta de clientes.

## Criterios de aceite

- Lead por telefone pode ser criado sem email/senha informados pelo cliente.
- Cliente completo continua usando email/senha.
- Cliente parcial/lead nao quebra listagem de clientes.
- Cadastro pelo site com mesmo telefone de um lead completa o perfil existente.
- Duplicidade por telefone WhatsApp e evitada por `customer_channels`.
- Checkout, conta, CRM e pedidos permanecem compatíveis.

## Fora de escopo

- Webhook inbound do WhatsApp.
- Conversa IA.
- Criacao de pedidos pelo WhatsApp.
- Redis/workers.
- Painel operacional do Agente WhatsApp.
- Stories WhatsApp.

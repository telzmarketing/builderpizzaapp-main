# Campanhas Estratégicas — Fase 0

Status: decisão arquitetural aprovada; Fase 1 implementada parcialmente, com os
gates operacionais avançados listados abaixo ainda bloqueados.

Data: 2026-11-25

## Objetivo

Definir o limite funcional e os contratos que deverão orientar o submódulo
Campanhas Estratégicas sem quebrar campanhas de tráfego, banners, promoções,
checkout, pedidos ou integrações operacionais existentes.

## Decisões arquiteturais

### 1. Domínio separado

Campanha estratégica é um domínio comercial distinto de:

- `TrafficCampaign`, usado para tráfego e atribuição;
- `Campaign`, usado pelo fluxo atual de banners/promoções;
- campanhas de WhatsApp e email;
- `PromotionLandingPage`, usada para landing promocional de produto.

Não será reutilizado o campo `Order.campaign_id` para representar campanha
estratégica, pois o contrato atual aponta para `traffic_campaigns`.

A implementação deverá introduzir uma referência explícita de campanha
estratégica nos contratos necessários, mantendo compatibilidade com os campos
atuais de tráfego e UTM.

### 2. Checkout único

Produtos, promoções, kits, opções, quote, pagamento e pedido continuarão sendo
resolvidos pelos serviços existentes. A campanha somente fornecerá o contexto
comercial e as restrições da oferta.

Não será criado checkout, cálculo de preço, catálogo, pedido ou pagamento
paralelo.

### 3. Preço e composição

O backend será a autoridade para:

- produto e opções autorizadas;
- composição da oferta;
- preço original;
- preço promocional;
- descontos;
- disponibilidade;
- limite por cliente;
- condições de entrega e retirada.

O pedido deverá preservar snapshot de campanha, oferta, preço, composição e
regras comerciais. Alterações posteriores não poderão modificar o histórico.

### 4. Estados da campanha

O vocabulário aprovado para o novo domínio é:

`draft`, `scheduled`, `active`, `paused`, `sold_out`, `ended`, `archived`.

Transições inválidas serão rejeitadas no backend. Publicação da landing page
será independente do rascunho e usará versão publicada imutável.

### 5. Venda, reserva e capacidade

- Venda imediata cria pedido pelo checkout canônico.
- Pré-venda permite pagamento antes da janela operacional, mas conserva a
  data efetiva de produção/entrega.
- Reserva é uma retenção lógica, com expiração e idempotência.
- Reserva não gera baixa física de estoque nem CMV definitivo.
- Capacidade será controlada por tenant, data, janela, modalidade e unidade.
- A última vaga deverá ser protegida por transação, lock e constraint.
- Pedido futuro não será liberado imediatamente ao KDS.
- A liberação para produção ocorrerá por job idempotente na janela operacional.

### 6. Financeiro

Recebimento antecipado, contas a receber, receita reconhecida, taxa,
reembolso e estorno permanecerão semanticamente distintos.

Todo efeito financeiro deverá ser idempotente e vinculado ao pedido, pagamento,
tenant e origem da operação. O orçamento de marketing não poderá gerar um
lançamento duplicado no Financeiro.

### 7. Tenant, RBAC e segurança

Toda entidade nova e toda operação comercial serão tenant-scoped. As ações
administrativas deverão ser separadas por permissão:

- visualizar;
- criar/editar;
- editar identidade visual;
- alterar preço/oferta;
- publicar;
- gerenciar reserva/capacidade;
- consultar clientes;
- consultar resultados financeiros;
- registrar investimento;
- gerenciar rastreamento.

Rotas públicas somente exporão conteúdo publicado e dados mínimos necessários
para conversão.

### 8. Publicação e rollback

O rascunho será editável. A publicação criará uma versão imutável e será
atômica. Restauração deverá:

- suspender novas vendas da versão problemática;
- preservar pedidos, pagamentos e reservas já existentes;
- restaurar a versão publicada anterior;
- desligar integrações externas defeituosas;
- manter o checkout convencional disponível.

### 9. Métricas e integrações externas

Eventos de visualização, clique, carrinho, checkout, reserva, compra e
pagamento serão deduplicados. Falha de Meta, Google, WhatsApp ou analytics não
poderá impedir quote, checkout ou pagamento.

Compra confirmada somente será contabilizada após confirmação definida pelo
contrato de pagamento. Reserva não paga e pagamento recusado não serão
contabilizados como venda.

## Escopo aprovado para a Fase 1

1. Contrato de campanha estratégica e tenant.
2. Oferta estratégica vinculada a produto, promoção ou kit existente.
3. Slug e estados com transições server-side.
4. Versionamento de rascunho/publicação.
5. Quote de uma oferta usando o `OrderService` existente.
6. Snapshot comercial no pedido.
7. RBAC mínimo para CRUD e publicação.
8. Testes de isolamento, preço server-side, idempotência e publicação.

## Fora do escopo da Fase 1

- dashboard completo de ROAS/ROI;
- integração direta com APIs externas de anúncios;
- reservas concorrentes e capacidade avançada;
- notificações personalizadas por campanha;
- liberação futura ao KDS;
- orçamento financeiro completo;
- editor visual completo com todos os componentes multimídia.

Esses itens somente entram após o contrato básico de oferta e checkout estar
validado.

## Gates obrigatórios antes da Fase 1

- [x] Confirmar migration/relacionamento para campanha estratégica sem quebrar
      `TrafficCampaign`, `Campaign` e `Order.campaign_id`.
- [x] Confirmar snapshot de preço, composição, oferta e regras no pedido.
- [x] Confirmar que o quote rejeita preço enviado pelo frontend.
- [x] Confirmar tenant e RBAC em todas as rotas administrativas.
- [ ] Confirmar publicação atômica e versão restaurável.
- [ ] Confirmar idempotência de criação de pedido e efeitos financeiros.
- [ ] Definir contrato de data/hora com timezone do tenant.
- [x] Definir política de alteração, pausa, encerramento e esgotamento.
- [x] Definir evidência mínima de regressão do checkout convencional.

## Riscos ainda bloqueadores

1. A capacidade e as reservas ainda não possuem contrato confirmado para esta
   funcionalidade.
2. A liberação de pedidos programados ao KDS precisa de contrato explícito e
   job idempotente.
3. A publicação versionada e a restauração ainda precisam ser implementadas.
4. O relacionamento atual de campanha no pedido é de tráfego, não de campanha
   estratégica.
5. A oferta estratégica ainda exige correspondência com o quote canônico; a
   aplicação de um preço promocional diferente será uma etapa posterior e não
   pode ser feita por override do frontend.

## Critério de saída da Fase 0

A Fase 0 está concluída como decisão arquitetural. A Fase 1 está autorizada
somente para modelar e testar o contrato básico descrito acima; qualquer
implementação de capacidade, reserva, Financeiro, KDS ou dashboard deve aguardar
os respectivos contratos específicos.

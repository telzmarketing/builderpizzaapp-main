# Campanhas Estratégicas — Fase 7

## Entrega

- Configuração opcional de orçamento planejado e vínculo com uma campanha de tráfego existente.
- Indicadores tenant-scoped em `GET /api/strategic-campaigns/{campaign_id}/metrics`.
- Funil de visualização, clique de oferta, início de checkout, sessões e pedidos pagos.
- Receita calculada somente por pedidos canônicos da campanha estratégica com pagamento aprovado ou pago.
- Gasto calculado somente quando há `traffic_campaign_id` e dados reais em `ad_daily_metrics`.
- ROAS e conversão retornam `null` quando a fonte necessária não existe; não há zero fictício.
- Painel administrativo para configuração e leitura dos indicadores.

## Segurança e integridade

- Todas as consultas administrativas filtram `tenant_id` pelo ator autenticado.
- Pedidos cancelados, estornados e arquivados não entram na receita.
- Eventos públicos são associados à campanha pelo `campaign_id` persistido no metadata do evento.
- A atribuição financeira continua no `Order.strategic_campaign_id`; UTM isolada não cria receita atribuída.
- Falhas ou ausência de sincronização de mídia não bloqueiam checkout e são exibidas como aviso.

## Pendências bloqueadas para próxima etapa

- Integrações de escrita com Meta/Google/TikTok, sincronização agendada e reconciliação externa.
- ROI com CMV/margem líquida; receita bruta não deve ser tratada como lucro.
- Orçamento financeiro efetivamente comprometido; nesta fase o orçamento planejado é configuração de marketing.
- Teste autenticado em banco PostgreSQL com migration aplicada e validação de tenant cruzado.

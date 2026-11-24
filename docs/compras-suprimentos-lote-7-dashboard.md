# Compras e Suprimentos — Lote 7: Dashboard e BI

Foi criada uma camada analítica tenant-scoped para compras em `GET /api/gestao/purchases/dashboard`. Ela conta cada requisição, cotação, pedido e recebimento pela respectiva tabela canônica, considera somente recebimentos `posted` para estoque e conta obrigações financeiras sem somar novamente suas parcelas.

O painel `BI de Compras` está em Gestão → Estoque → Operação, com período, loading, erro, estado vazio, alertas e cards de requisições, cotações, pedidos, recebimentos, estoque e financeiro.

CMV, vendas e BI comercial não são misturados aos indicadores de aquisição. Não foram criadas tabelas analíticas paralelas nem alterações persistidas durante a consulta.
# Controles adicionais

O endpoint exige as permissoes `inventory.view` e `finance.view`, limita o periodo a 366 dias e considera no financeiro apenas obrigacoes vinculadas a documentos fiscais de recebimento.

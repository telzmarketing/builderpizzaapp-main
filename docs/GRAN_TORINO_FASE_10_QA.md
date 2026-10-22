# Gran Torino — Fase 10: QA de inteligência gerencial

## Escopo auditado

Esta revisão cobre os contratos de BI já disponíveis e a base usada pela última
fase: dashboard por período, vendas, clientes, produtos, marketing, operações,
funil, insights, recomendações e visão mobile. O BI deve apenas derivar dados
das tabelas canônicas e receber o tenant do contexto autenticado do painel.

## Critérios de aceite

- Todos os endpoints de BI devem exigir autenticação administrativa e contexto
  de tenant confiável.
- Consultas de pedidos, pagamentos, clientes, produtos, entregas, eventos e
  tráfego devem filtrar o tenant atual.
- Receita efetivada deve considerar pagamentos aprovados/pagos e excluir
  pedidos cancelados ou estornados quando aplicável.
- Períodos inválidos e limites fora do contrato devem ser rejeitados pelo
  schema/query validation.
- Respostas vazias devem retornar coleções e valores numéricos válidos, sem
  erro de serialização.
- Insights e recomendações devem permanecer derivados e identificáveis, sem
  alterar pedidos, clientes, campanhas ou estoque.
- A validação PostgreSQL deve ser separada da validação estática/local.

## Evidência executada

Comando:

```text
python -m pytest -q tests/test_wave6_bi_marketing_intelligence_tenant.py tests/test_bi_migrated_postgresql.py --disable-warnings --maxfail=1
```

Resultado observado em 22/10/2026:

```text
6 passed, 1 skipped
```

Os seis testes aprovados verificam o vínculo do serviço ao tenant autenticado,
o isolamento das consultas operacionais e de marketing, a propriedade dos
insights/produtos e os contratos migrados. O teste PostgreSQL foi ignorado por
dependência de banco disponível no ambiente local.

## Riscos e gates restantes

- A execução local não prova concorrência, índices ou plano de consulta em
  PostgreSQL 15.
- O teste ignorado deve ser executado contra um banco criado exclusivamente por
  Alembic antes de liberar a fase para produção.
- Ainda são necessários testes HTTP com dois tenants e perfis sem permissão,
  além de conferência de dados reais entre receita, pagamentos, CMV e estoque.
- Previsões e alertas só podem ser apresentados como decisão gerencial depois
  de definir janela histórica mínima, qualidade dos dados e tratamento de
  ausência de amostra.
- A publicação continua dependente de build, migration aplicada, health check e
  validação ponta a ponta no ambiente alvo.

## Conclusão QA

A base de BI atende aos contratos de isolamento e agregação verificados
localmente. A Fase 10 pode ser considerada implementada no código apenas após
o agente responsável concluir a integração final; a liberação operacional exige
os gates PostgreSQL e HTTP descritos acima.

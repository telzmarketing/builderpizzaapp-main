# Campanhas Estratégicas — Runbook de Release C10

Status: preparado, não executado

Data: 2026-11-26

Target Alembic: `20261126_strategic_campaign_publish_rbac_c9`

## 1. Objetivo e limites

Este runbook prepara uma release imutável pelo mecanismo oficial do projeto. Não autoriza nem registra deploy, commit, push, migration em produção ou downgrade de banco.

O candidato deve usar SHA completo e reproduzível. Não usar working tree, `git pull`, cópia manual, Alembic isolado ou build sobre a release ativa.

## 2. Critérios de entrada bloqueantes

- escopo revisado e candidato fechado;
- commit/push somente após autorização específica e CI verde no SHA completo;
- no mínimo `55 passed` backend e `17 passed` frontend, typecheck e builds do pipeline no mesmo SHA;
- head único `20261126_strategic_campaign_publish_rbac_c9`;
- upgrade ensaiado em PostgreSQL real vazio e com dados representativos;
- concorrência de capacidade/reservas comprovada com conexões independentes;
- E2E autenticado de RBAC, tenant, publicação, landing e checkout canônico;
- pagamento, scheduler, KDS físico, impressão, estoque, CMV, financeiro e CRM/notificações validados quando aplicáveis;
- backup/restore ensaiados;
- par de schema classificado como rollback-safe ou forward-only;
- janela, piloto, responsáveis, métricas e autorização de produção aprovados.

## 3. Release imutável

Modelo, não executado:

```bash
TARGET_SHA='<SHA-COMPLETO-APROVADO>'
ALEMBIC_TARGET='20261126_strategic_campaign_publish_rbac_c9'

sudo env \
  TELZ_ALEMBIC_TARGET="$ALEMBIC_TARGET" \
  /usr/local/sbin/telz-deploy-from-origin "$TARGET_SHA" /opt/telz
```

Antes da promoção, confirmar SHA, manifesto, hashes, dependências, head único e target do pipeline. A compatibilidade do schema deve estar registrada no mecanismo de update/rollback; migrations aditivas, sozinhas, não provam rollback seguro.

## 4. Gates após materialização

- `current` aponta para a release imutável e SHA esperados;
- banco está exatamente no target;
- API/web, health local e HTTPS público estão saudáveis;
- logs não mostram erros de migration, import, scheduler ou inicialização;
- autenticação, RBAC de publicação e isolamento tenant funcionam;
- landing corresponde ao snapshot publicado;
- capacidade/reserva e checkout/pedido são canônicos e idempotentes;
- pedido programado pago chega uma vez ao KDS no momento correto;
- cancelamento/expiração devolve capacidade uma vez;
- métricas reconciliam com pedidos, pagamentos, mídia e custos disponíveis.

Falha em qualquer gate bloqueia a abertura do tráfego da funcionalidade.

## 5. Observação e critérios de abortar

Monitorar erros HTTP, conflitos/capacidade, reservas, duplicidade de pedidos/KDS, divergência entre oferta/quote/cobrança/pedido, scheduler, pagamento, estoque, CMV, impressão, CRM/notificações e latência.

Abortar diante de overselling, vazamento entre tenants, publicação indevida, preço/cobrança divergente, pedido/KDS duplicado, perda de capacidade, schema inconsistente ou indisponibilidade.

## 6. Rollback e recuperação segura

- Não usar `alembic downgrade` automaticamente em produção.
- Não apagar campanhas, reservas, pedidos, auditoria ou métricas.
- Não reativar código incompatível com o schema ou com estados já gravados.
- Preservar backup, manifesto, logs, revisão do banco e release com falha.

Se o par estiver explicitamente aprovado como rollback-safe, usar apenas release anterior já materializada e SHA completo:

```bash
sudo /usr/local/sbin/rollback-telz /opt/telz '<SHA-COMPLETO-ANTERIOR-COMPATÍVEL>'
```

O rollback oficial troca o código e preserva o schema conforme sua política. Repetir health, autenticação e verificações de integridade. O comando não foi executado neste checkpoint.

Se o par não estiver aprovado ou for forward-only, manter rollback automático bloqueado. Interromper ativação, preservar dados e optar, em janela aprovada, por hotfix forward-only em nova release imutável ou restore explícito do backup compatível. Suspender novas vendas/reservas da campanha por mecanismo administrativo seguro, sem excluir pedidos; reconciliar reservas, pagamentos, KDS, estoque, CMV e financeiro.

## 7. Evidências de saída

Exigir SHA/manifesto, CI/builds, ensaio PostgreSQL/concorrência, revisão Alembic antes/depois, backup/restore, classificação de rollback, health local/HTTPS, evidência autenticada multi-tenant, fluxo comercial/operacional e observação sem bloqueadores.

## 8. Estado deste checkpoint

- Documentação C10: preparada.
- Head esperado: confirmado localmente.
- Backend: `55 passed`; frontend: `17 passed`; typecheck e build client: aprovados.
- PostgreSQL real/concorrência e integrações físicas/externas: pendentes.
- Commit, push e deploy: não executados.
- Produção: inalterada por este checkpoint.

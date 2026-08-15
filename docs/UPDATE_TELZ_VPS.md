# Atualizacao Telz na VPS

Atualizado em: 2026-08-09

Use este procedimento para uma atualizacao incremental de uma instalacao
existente em `/opt/telz`. `installer/install.sh` continua reservado para a
primeira instalacao ou reconstrucao planejada.

## 1. Preflight

O checkout e os processos pertencem a `telz:telz`. Operacoes Git devem executar
como esse usuario; nao configure `/opt/telz` como `safe.directory` global do
`root`.

```bash
sudo -u telz -H git -C /opt/telz status --short
sudo -u telz -H git -C /opt/telz rev-parse HEAD
sudo -u telz -H git -C /opt/telz fetch --prune origin main
```

O atualizador rejeita qualquer arquivo alterado ou nao rastreado. Preserve
`backend/.env`, uploads e backups fora do worktree; nao use `reset --hard` para
contornar o gate.

## 2. Executar

O target canonico deste checkout e:

```text
20260818_platform_operations
```

Execute:

```bash
sudo install -m 0755 -o root -g root \
  /opt/telz/scripts/update-telz.sh \
  /usr/local/sbin/update-telz
sudo env TELZ_ALEMBIC_TARGET=20260818_platform_operations \
  /usr/local/sbin/update-telz /opt/telz
```

O script:

1. adquire lock exclusivo;
2. confirma worktree limpo e registra o commit anterior;
3. atualiza `main` com Git executado como `telz`;
4. instala os utilitarios operacionais root-owned;
5. cria backup validado antes de dependencias e migration;
6. valida sintaxe de scripts Bash;
7. instala dependencias Python/Node e executa `pip check`;
8. executa pytest, typecheck e Vitest;
9. gera o build de producao;
10. registra `current`, `heads` e `history` do Alembic;
11. exige exatamente um head igual a `TELZ_ALEMBIC_TARGET`;
12. aplica somente a revision explicita e confirma a convergencia do banco;
13. instala observador/timer e agendamento de backup;
14. reinicia os services e executa health check completo.

Nao ha prompt para `upgrade head` e o script nao usa essa forma. O target deve
corresponder ao head unico do commit publicado.

## 3. GitHub Actions

O push para `main` executa somente a validacao em PostgreSQL 15 descartavel,
incluindo migration, suite backend, typecheck, Vitest e build. Ele nao inicia
deploy de producao.

O deploy exige acionamento manual por `workflow_dispatch`. Nesse fluxo, o job
de producao somente inicia depois da mesma validacao e exige os secrets
`VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` e, opcionalmente, `VPS_PORT`, alem das
protecoes configuradas no environment `production`.

Na VPS, o workflow:

- confirma ownership `telz:telz` e worktree limpo;
- faz fast-forward para o SHA exato do workflow;
- instala uma copia root-owned do atualizador;
- executa o mesmo target `20260818_platform_operations`;
- confirma o commit final.

## 4. Falha e rollback

Se houver falha depois da troca de commit, o atualizador tenta restaurar o
codigo e o build do commit anterior. Ele nunca executa downgrade automatico do
banco. Se a migration ja tiver sido aplicada, a saida informa explicitamente
essa condicao.

Depois de dados reais, prefira hotfix forward-only. Restauracao de backup exige
janela aprovada e o procedimento de `docs/BACKUP_AND_RESTORE.md`; voltar somente
o codigo nao torna um schema novo antigo.

## 5. Evidencias de conclusao

Registre depois do deploy:

```bash
sudo -u telz -H git -C /opt/telz rev-parse HEAD
sudo -u telz -H bash -lc \
  'cd /opt/telz && exec .venv/bin/alembic -c backend/alembic.ini current'
sudo systemctl --no-pager --full status telz-api telz-web telz-whatsapp-gateway
sudo systemctl --no-pager --full status telz-monitoring.timer
sudo /usr/local/sbin/telz-health-check /opt/telz
```

Tambem valide HTTPS publico, login da plataforma, cada modulo operacional e
logs recentes. Neste checkout, deploy do novo target, HTTPS publico, E2E e
restore controlado ainda sao gates abertos ate existir evidencia da VPS/CI.

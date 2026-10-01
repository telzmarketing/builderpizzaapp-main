# Metodo de instalacao VPS por fases - Telz

Atualizado em: 2026-09-29

Este documento descreve os gates operacionais atuais. Ele nao e um segundo
instalador manual: os comandos avulsos antigos de criar usuario, banco, units,
Nginx, backup e migration foram removidos porque divergiam do instalador
versionado e podiam produzir uma VPS impossivel de atualizar pelo fluxo
imutavel.

## 1. Separacao obrigatoria

| Situacao | Caminho suportado |
|---|---|
| Primeira instalacao/reconstrucao | `installer/install.sh` a partir de checkout revisado |
| Retomada da primeira instalacao | `/usr/local/sbin/telz-installer-resume` com config e argumentos identicos |
| Atualizacao incremental | `workflow_dispatch` de `.github/workflows/deploy.yml` |
| Backup | `/usr/local/bin/backup-telz` root-owned |
| Restore | `/usr/local/sbin/restore-telz` em janela aprovada |
| Rollback de codigo | `/usr/local/sbin/rollback-telz` para release imutavel compativel |
| SSL posterior | `/usr/local/sbin/telz-finish-ssl` depois do HTTP aprovado |

Nao use o instalador para atualizar uma VPS existente. Nao execute
`update-telz` diretamente sem o bundle operacional, dois archives de fonte,
pacote offline de dependencias, hashes e commits promovidos pelo workflow.

## 2. Target desta entrega

Todos os componentes operacionais devem convergir para um unico target:

```text
20260930_tenant_runtime_uniqueness
```

Confirme antes de qualquer alteracao que:

- o commit publicado possui exatamente esse unico head;
- `installer/config/defaults.env`, updater e workflow usam o mesmo valor;
- o banco existente possui uma unica revision conhecida;
- existe caminho forward e compatibilidade de rollback de aplicacao.

Qualquer divergencia bloqueia instalacao/deploy. Nao use `upgrade head`, `stamp`,
downgrade ou edicao de `alembic_version` para forcar convergencia.

## 3. Fase 0 - Escopo e preflight

Defina antes de acessar a VPS:

- commit exato, dominio principal, IP e porta SSH;
- Ubuntu suportado, CPU, memoria e disco;
- usuario de servico e diretorio final;
- PostgreSQL local ou externo e conectividade;
- janela, backup, RPO/RTO e retorno;
- DNS/SSL e URL publica de health;
- gateways e integracoes que permanecerao desativados;
- criterios E2E de cliente, admin e isolamento A/B.

Gate: codigo revisado, worktree limpo, target sincronizado e nenhum segredo no
repositorio ou em logs.

## 4. Fase 1 - Configuracao segura

Crie `/root/telz-install.env` a partir dos defaults e proteja-o:

```bash
sudo chown root:root /root/telz-install.env
sudo chmod 600 /root/telz-install.env
sudo stat -c '%U:%G %a %N' /root/telz-install.env
```

Use inicialmente:

```env
ALEMBIC_TARGET=20260930_tenant_runtime_uniqueness
INSTALL_SSL=false
```

Mantenha opt-ins de tenants e funcionalidades sensiveis desativados ate os
gates especificos. O backend usa `ORDER_BOARD_ENABLED=false` por default; nao o
ative no `backend/.env` antes dos gates do painel TV. Nao publique nenhum desses
arquivos nem seu conteudo.

Gate: arquivo regular/canonico, root-owned, sem symlink e sem escrita de
grupo/outros; parametros e segredos revisados por canal seguro.

## 5. Fase 2 - Instalacao versionada

No checkout confiavel:

```bash
sudo bash installer/install.sh \
  --config /root/telz-install.env \
  --non-interactive
```

O instalador e responsavel por sistema, usuario, diretorios, firewall,
runtimes, checkout, backend, `.env`, PostgreSQL local, Alembic, frontend,
systemd, Nginx, SSL opcional, backup e health. Nao replique essas fases com
comandos manuais paralelos.

Gates durante a execucao:

- confirmar plano e migration quando solicitado;
- preservar banco, uploads, certificados, backups e `.runtime/baileys`;
- exigir um unico head igual a `20260930_tenant_runtime_uniqueness`;
- executar testes/build e validar units/Nginx;
- nao executar a aplicacao como root;
- nao iniciar duas instalacoes simultaneas.

## 6. Fase 3 - Retomada

Se a instalacao falhar depois de criar o staging privilegiado, corrija a causa
e repita config, modo e argumentos exatamente:

```bash
sudo /usr/local/sbin/telz-installer-resume \
  --config /root/telz-install.env \
  --non-interactive \
  --resume
```

O fingerprint esperado esta em
`/var/lib/telz-installer/state/config.sha256`. Nao edite esse arquivo, nao altere
segredos/opcoes e nao retome pelo `installer/install.sh` do worktree. O runner e
staging root-private sao removidos somente apos conclusao bem-sucedida.

Gate: runner `root:root 500`, staging/manifest integros e fingerprint identico.

## 7. Fase 4 - HTTP antes de SSL

Valide primeiro o runtime e HTTP:

```bash
sudo nginx -t
sudo systemctl --no-pager --full status \
  telz-api telz-web telz-whatsapp-gateway
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://SEU_DOMINIO/api/health
```

Somente depois de DNS e porta 80 aprovados:

```bash
sudo /usr/local/sbin/telz-finish-ssl \
  app.seudominio.com.br \
  admin@seudominio.com.br
```

Gate: certificado valido, redirect esperado e health HTTPS externo. Falha do
Certbot nao pode ser tratada como fase concluida.

## 8. Fase 5 - Banco, backup e restore

Depois da instalacao:

```bash
sudo -u telz -H bash -lc \
  'cd /opt/telz && .venv/bin/alembic -c backend/alembic.ini current --verbose'
sudo /usr/local/bin/backup-telz /opt/telz
sudo readlink -f /var/backups/telz/latest
```

Gate: uma unica revision `20260930_tenant_runtime_uniqueness`, backup validado e restore
ensaiado em PostgreSQL 15 fora de producao. Dump criado, `compileall`, SQL
offline e adapter/mocks nao provam restore nem migration real.

## 9. Fase 6 - Validacao funcional

Valide com dados controlados:

- login e permissoes de cliente/admin;
- loja, catalogo, carrinho, checkout e pedido;
- cozinha, expedicao, entrega e impressao aplicaveis;
- uploads e sessao/entrega real do WhatsApp;
- pagamentos/webhooks em sandbox oficial;
- isolamento entre tenants A e B;
- logs sem erro recorrente.

Para o painel TV, mantenha `ORDER_BOARD_ENABLED=false` e opt-in dos tenants
desativado ate aprovar PostgreSQL real, HTTPS/cookies, dois tenants e ativacao
controlada. Snapshot/testes locais nao equivalem a homologacao de producao.

Gate: evidencias separadas de frontend, backend, banco, integracoes e isolamento.

## 10. Fase 7 - Atualizacoes futuras

Depois da primeira instalacao, toda mudanca usa o workflow transacional. Ele
sela e verifica:

- bundle operacional allowlisted;
- fonte do commit alvo;
- fonte do commit anterior;
- dependencias offline;
- hashes SHA-256, commits e target Alembic;
- releases root-owned imutaveis.

O comando isolado abaixo e deliberadamente incompleto e nao deve ser executado:

```text
sudo /usr/local/sbin/update-telz /opt/telz
```

Siga `docs/UPDATE_TELZ_VPS.md`. Se GitHub Actions ou a promocao de artefatos
estiver indisponivel, o deploy permanece bloqueado.

## 11. Limites e gates externos

Antes de declarar producao pronta, registre evidencia de:

- VPS Ubuntu limpa e reinicio completo;
- PostgreSQL real e dados representativos;
- systemd, Nginx, UFW sem perda do SSH e health publico;
- DNS, certificado, renovacao e HTTPS cookies;
- backup, restore e rollback controlados;
- dois tenants sem vazamento;
- gateways/provedores homologados;
- retencao/off-site/monitoramento de backup;
- configuracoes customizadas de usuario, portas, slug e diretorios.

Os controles locais reduzem risco, mas nao substituem esses testes. Toda
pendencia deve aparecer no handoff; nao declare conclusao apenas porque build,
mocks ou sintaxe passaram.

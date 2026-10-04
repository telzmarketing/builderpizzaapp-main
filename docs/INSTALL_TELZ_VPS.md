# Instalacao Telz em VPS

Atualizado em: 2026-10-04

Este documento cobre somente a primeira instalacao ou uma reconstrucao
planejada em Ubuntu 22.04/24.04. Uma instalacao existente deve ser atualizada
pelo fluxo imutavel descrito em `docs/UPDATE_TELZ_VPS.md`; o instalador nao e um
substituto para update.

Status operacional: o fluxo foi validado localmente, mas instalacao limpa,
PostgreSQL real, systemd, UFW, Nginx, DNS e HTTPS ainda precisam de evidencia em
uma VPS descartavel antes do uso em producao.

## 1. Premissas

- executar como `root` ou via `sudo` em Ubuntu 22.04/24.04;
- usar um checkout confiavel e revisado do commit que sera instalado;
- usar Node.js 22 e pnpm 10.14.0;
- no Ubuntu 22.04, provisionar Python 3.12, `python3.12-venv` e headers por uma
  fonte aprovada antes da instalacao;
- apontar o DNS do dominio principal antes de solicitar SSL;
- iniciar com `INSTALL_SSL=false` quando DNS/HTTP ainda nao foram comprovados;
- preservar as flags e opt-ins de funcionalidades sensiveis desativados ate os
  respectivos gates em ambiente real.

O target Alembic desta entrega e:

```text
20261003_agente_whatsapp_tenant_foundation
```

Antes de instalar, confirme que esse valor e o unico head do commit publicado e
que `installer/config/defaults.env`, scripts operacionais e workflow usam o
mesmo target. Divergencia e um bloqueio; nao use `upgrade head` para contorna-la.

## 2. Configuracao root-private

Para instalacao nao interativa, crie `/root/telz-install.env` com base em
`installer/config/defaults.env`. O arquivo pode conter segredos e deve ser
regular, canonico, pertencente a `root`, sem symlink e sem escrita para grupo ou
outros:

```bash
sudo chown root:root /root/telz-install.env
sudo chmod 600 /root/telz-install.env
sudo stat -c '%U:%G %a %N' /root/telz-install.env
```

Defina explicitamente:

```env
ALEMBIC_TARGET=20261003_agente_whatsapp_tenant_foundation
INSTALL_SSL=false
```

Nao publique esse arquivo, `backend/.env`, tokens, senhas ou `DATABASE_URL` em
Git, tickets ou logs compartilhados.

## 3. Primeira execucao

No checkout revisado:

```bash
sudo bash installer/install.sh \
  --config /root/telz-install.env \
  --non-interactive
```

O modo interativo continua disponivel para uma instalacao assistida:

```bash
sudo bash installer/install.sh
```

O instalador prepara usuario e diretorios, firewall, runtimes, checkout,
backend, PostgreSQL local quando selecionado, Alembic, frontend, systemd,
Nginx, SSL opcional, backup e health check. Ele preserva banco, uploads,
certificados e `.runtime/baileys`; nao executa downgrade automatico.

As opcoes `RUN_ALEMBIC`, `RUN_TYPECHECK`, `RUN_TESTS` e `RUN_BUILD` controlam as
respectivas etapas, mas nao devem ser usadas como bypass de validacao. Os
defaults permanecem `true`; desabilitar migration ou build em uma instalacao
limpa normalmente impede que o health final seja aprovado.

O instalador persiste usuario, portas, workers, gateway, backup e diretorio de
monitoramento em `/etc/telz/operations.conf`, arquivo `root:root` modo `0600`.
O updater consome esse contrato por parser estrito, sem executar o arquivo como
shell. Nao o edite manualmente durante uma instalacao ou deploy.

## 4. Retomada exata

Depois que o instalador criar o runner root-private, toda retomada deve usar o
mesmo arquivo de configuracao e o mesmo modo da primeira execucao:

```bash
sudo /usr/local/sbin/telz-installer-resume \
  --config /root/telz-install.env \
  --non-interactive \
  --resume
```

Nao use `sudo bash installer/install.sh --resume` nem omita `--config` quando a
execucao original o utilizou. A retomada recalcula a configuracao efetiva e
compara com `/var/lib/telz-installer/state/config.sha256`; qualquer diferenca em
dominio, diretorio, usuario, portas, workers, segredos ou opcoes e recusada.

O runner `/usr/local/sbin/telz-installer-resume` e o staging em
`/var/lib/telz-installer/trusted-assets/` existem apenas enquanto uma instalacao
esta incompleta. Eles sao removidos depois da conclusao bem-sucedida. Se o
runner estiver ausente durante uma instalacao interrompida, nao improvise uma
retomada pelo worktree: diagnostique o staging e planeje uma reconstrucao.

Logs e estado:

```text
/var/log/telz-installer/
/var/lib/telz-installer/state/
```

## 5. HTTP primeiro e SSL posterior

Para a primeira subida, use `INSTALL_SSL=false`, confirme Nginx e HTTP e so
depois finalize o certificado:

```bash
sudo nginx -t
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://SEU_DOMINIO/api/health
sudo /usr/local/sbin/telz-finish-ssl \
  app.seudominio.com.br \
  admin@seudominio.com.br
```

Falha do Certbot nao comprova instalacao pronta. DNS, porta 80 publica,
certificado, redirect e health HTTPS devem ser validados separadamente.

## 6. Validacao final

```bash
sudo /usr/local/sbin/telz-health-check /opt/telz
sudo systemctl --no-pager --full status \
  telz-api telz-web telz-whatsapp-gateway
sudo journalctl -u telz-api -n 100 --no-pager
sudo journalctl -u telz-web -n 100 --no-pager
sudo journalctl -u telz-whatsapp-gateway -n 100 --no-pager
```

Registre separadamente:

- revision unica `20261003_agente_whatsapp_tenant_foundation` no codigo e no banco;
- health local e HTTP/HTTPS publico;
- login, loja, pedido, painel e WhatsApp;
- isolamento entre pelo menos dois tenants;
- backup criado e restore ensaiado fora de producao;
- para o painel TV, HTTPS/cookies, isolamento A/B e ativacao controlada, mantendo
  `ORDER_BOARD_ENABLED=false` e opt-in dos tenants desativado ate esses gates.

O WhatsApp Gateway ativo nao significa sessao conectada; valide o QR Code e um
envio real sem expor tokens. Adaptadores/mocks de pagamento nao equivalem a
homologacao do provedor.

## 7. Limites conhecidos

- VPS limpa, PostgreSQL real, HTTPS, restore e rollback ainda sao gates
  externos, nao comprovados por testes locais;
- configuracoes nao padrao de usuario, portas, slug ou snapshot exigem ensaio
  especifico de install, health, backup e update;
- o instalador detecta as portas efetivas do `sshd` e da conexao atual antes do
  UFW, mas mantenha uma segunda sessao aberta e confirme o acesso apos o gate;
- credenciais do PostgreSQL recebem percent-encoding na `DATABASE_URL`; valide
  a conexao real, especialmente com banco externo;
- um lock global recusa duas instancias do instalador; ainda assim, nao execute
  update, SSL ou outra manutencao paralelamente;
- `compileall`, SQL offline ou mocks nao comprovam migration em PostgreSQL nem
  prontidao de producao.

## 8. Backup manual

Depois que o helper root-owned estiver instalado:

```bash
sudo /usr/local/bin/backup-telz /opt/telz
```

Siga `docs/BACKUP_AND_RESTORE.md` para validacao e restore. Backup criado nao e
restore comprovado.

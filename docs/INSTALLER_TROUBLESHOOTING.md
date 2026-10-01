# Troubleshooting do instalador Telz

Atualizado em: 2026-09-29

Este runbook diagnostica uma primeira instalacao. Para falha de deploy
incremental, use o run do GitHub Actions e `docs/UPDATE_TELZ_VPS.md`.

## 1. Coleta sem segredos

```bash
sudo ls -lah /var/log/telz-installer/
sudo tail -n 200 /var/log/telz-installer/install-*.log
sudo find /var/lib/telz-installer/state -maxdepth 1 -type f \
  -printf '%f %U:%G %m\n'
```

Nao publique linhas com senha, token, chave, cookie, `DATABASE_URL` ou conteudo
do `.env`.

## 2. Retomada suportada

Se a execucao original usou `/root/telz-install.env` e modo nao interativo,
repita exatamente:

```bash
sudo /usr/local/sbin/telz-installer-resume \
  --config /root/telz-install.env \
  --non-interactive \
  --resume
```

Antes, confirme sem imprimir o conteudo:

```bash
sudo stat -c '%U:%G %a %N' /root/telz-install.env
sudo stat -c '%U:%G %a %N' /usr/local/sbin/telz-installer-resume
sudo sha256sum /var/lib/telz-installer/state/config.sha256
```

O config deve ser root-owned e nao gravavel por grupo/outros; o runner deve ser
`root:root 500`. O arquivo `config.sha256` e a referencia da configuracao
efetiva. Nao o edite e nao altere o config para forcar a retomada.

Nao use:

```text
sudo bash installer/install.sh --resume
```

Esse caminho carrega o worktree e nao e o runner privilegiado persistido. Se o
runner seguro estiver ausente, preserve logs/estado e diagnostique a fase que o
removeu; nao copie manualmente um script do checkout para simular retomada.

## 3. Alembic

Execute como o usuario de servico e sem revelar o ambiente:

```bash
sudo -u telz -H bash -lc \
  'cd /opt/telz && .venv/bin/alembic -c backend/alembic.ini heads --verbose'
sudo -u telz -H bash -lc \
  'cd /opt/telz && .venv/bin/alembic -c backend/alembic.ini current --verbose'
```

Deve existir exatamente um head e ele deve ser:

```text
20260930_tenant_runtime_uniqueness
```

Se defaults, script, workflow, codigo e banco divergirem, pare. Nao execute
`upgrade head`, `stamp`, downgrade ou edicao manual de `alembic_version` para
contornar o gate.

## 4. Services e health

```bash
sudo systemctl --no-pager --full status \
  telz-api telz-web telz-whatsapp-gateway
sudo journalctl -u telz-api -n 200 --no-pager
sudo journalctl -u telz-web -n 200 --no-pager
sudo journalctl -u telz-whatsapp-gateway -n 200 --no-pager
sudo /usr/local/sbin/telz-health-check /opt/telz
```

Para instalacoes com usuario ou portas nao padrao, os mesmos valores precisam
ser fornecidos aos helpers por suas variaveis `TELZ_*`; nao aceite um health que
testou as portas default como evidencia do ambiente customizado.

## 5. Nginx, HTTP e SSL

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://SEU_DOMINIO/api/health
```

Valide HTTP antes de Certbot. Se SSL falhou, corrija DNS/porta 80 e execute o
helper root-owned instalado:

```bash
sudo /usr/local/sbin/telz-finish-ssl \
  app.seudominio.com.br \
  admin@seudominio.com.br
```

Depois valide certificado, redirect e endpoint HTTPS. Um aviso do Certbot ou
uma fase marcada nao substitui essa evidencia.

## 6. WhatsApp Gateway

```bash
cd /opt/telz
sudo -u telz -H pnpm whatsapp-gateway:health
```

Service ativo nao prova sessao online. Conecte pelo QR Code e valide envio real.

## 7. Causas que exigem parar

- target Alembic diferente de `20260930_tenant_runtime_uniqueness`;
- runner/config/fingerprint com ownership ou permissao invalidos;
- worktree sujo durante update;
- Nginx invalido ou porta SSH nao preservada antes de UFW;
- tentativa de update sem os artefatos imutaveis exigidos;
- restore/rollback sem janela, backup validado ou release compativel.

Nao ative flags multi-tenant, painel TV ou gateways reais para resolver falha de
instalacao. Corrija primeiro banco, configuracao, build, Nginx ou systemd.

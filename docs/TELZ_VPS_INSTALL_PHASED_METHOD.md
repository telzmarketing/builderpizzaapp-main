# Metodo de instalacao VPS por fases - Telz SaaS multiempresa

## 1. Validacao do prompt mestre

O prompt mestre e coerente com a direcao tecnica definida para a plataforma: evoluir o sistema existente para SaaS multiempresa, preservar funcionalidades atuais, usar uma unica aplicacao, um unico PostgreSQL, schema compartilhado com `tenant_id`, dominio publico resolvendo tenant por hostname e validacao incremental por ondas.

Para o metodo de instalacao da VPS, o prompt precisa ser interpretado com os seguintes recortes:

- nao executar a transformacao completa Telz como big-bang;
- nao renomear classes, tabelas, migrations antigas ou dominios internos apenas por estetica;
- nao ativar flags multi-tenant durante a primeira instalacao;
- nao executar contract migrations antes de validar expand/backfill no PostgreSQL real;
- nao misturar cobranca SaaS da Telz com pagamento dos pedidos das lojas;
- nao substituir o `DEPLOY.md` legado enquanto a nova instalacao SaaS nao estiver validada;
- nao publicar `curl | bash` ate existir infraestrutura segura, versao assinada e URL controlada.

O ponto central do prompt para esta etapa e a secao de instalador automatico da VPS. As secoes de tenant, dominios, billing, master panel e CI/CD entram como dependencias ou validacoes futuras, nao como tarefas obrigatorias da primeira instalacao.

## 2. Objetivo do metodo

Criar uma instalacao reproduzivel para uma VPS Ubuntu que permita:

1. subir o sistema atual com seguranca;
2. validar banco, Alembic, build, Nginx, systemd e health checks em ambiente real;
3. manter todas as flags multi-tenant desligadas na primeira subida;
4. executar as validacoes pendentes das ondas multi-tenant depois da instalacao;
5. evoluir para scripts automatizados somente depois que o procedimento manual estiver provado.

## 3. Escopo desta versao

Incluido:

- metodo de instalacao por fases;
- ordem segura de execucao;
- gates antes de migrations e antes de flags;
- comandos-base para Ubuntu/VPS;
- checklist de validacao;
- rollback operacional basico;
- separacao entre instalacao, validacao multi-tenant e ativacao.

Fora do escopo desta versao:

- ativar multi-tenant em producao;
- emitir SSL dinamico para dominios de clientes;
- criar CI/CD definitivo;
- criar painel master completo;
- criar billing SaaS;
- remover constraints globais em producao;
- rodar destructive reset, drop ou downgrade automatico de banco.

## 4. Premissas tecnicas

- Sistema operacional: Ubuntu 22.04 LTS.
- Usuario operacional: `deploy`.
- Diretorio recomendado inicial: `/home/deploy/telz`.
- Servicos systemd recomendados para nova instalacao: `telz-api`, `telz-web` e `telz-whatsapp-gateway`.
- O instalador deve instalar todos os componentes existentes do sistema no momento da instalacao. No estado atual, isso inclui o WhatsApp Gateway por padrao.
- Os metodos de pagamento existentes, Mercado Pago e ASAAS, devem ser preparados na instalacao. As credenciais podem ficar vazias para configuracao posterior no painel, mas as variaveis e migrations correspondentes entram no fluxo normal.
- Backend: FastAPI via `uvicorn`, porta local `8000`.
- Web: Node servindo `dist/server/node-build.mjs`, porta local `3000`.
- Proxy: Nginx em `80/443`.
- Banco: PostgreSQL 15 ou 16.
- Frontend/build: usar `pnpm` quando possivel, pois o projeto possui `pnpm-lock.yaml` e `packageManager` definido.
- Alembic: usar `backend/alembic.ini`.

## 5. Variaveis e flags obrigatorias

Na primeira instalacao, todas as flags multi-tenant devem permanecer desligadas:

```env
MULTI_TENANT_AUTH_ENABLED=false
TENANT_DOMAINS_ENABLED=false
TENANT_DOMAINS_TRUST_PROXY_HEADERS=false
TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED=false
TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED=false
TENANT_OPERATIONS_ENFORCEMENT_ENABLED=false
TENANT_PAYMENT_WEBHOOKS_ENABLED=false
MULTI_TENANT_WAVE6_ORM_ENABLED=false
MULTI_TENANT_WAVE7_ORM_ENABLED=false
TENANT_BACKGROUND_CONTEXT_ENABLED=false
TENANT_UPLOAD_NAMESPACE_ENABLED=false
TENANT_CREDENTIALS_ENABLED=false
PLATFORM_RBAC_ENABLED=false
```

Essas flags so podem ser ligadas em fase propria, depois de:

- migrations aplicadas;
- backfill conferido;
- constraints validadas;
- dominio/tenant confiavel;
- testes A/B por tenant;
- rollback documentado.

## 6. Fase 0 - Preparacao antes da VPS

Objetivo: chegar na VPS com parametros definidos e sem improviso.

Definir:

- dominio principal da plataforma;
- IP publico da VPS;
- repositorio Git;
- branch de deploy;
- usuario SSH;
- diretorio final;
- nome dos servicos;
- nome do banco e usuario PostgreSQL;
- estrategia de backup;
- parametros do WhatsApp Gateway, que sera instalado por padrao junto com o sistema.

Checklist local antes de publicar para a VPS:

```bash
git status -sb
git diff --check
npm run typecheck
npm test
npm run build
```

Se o ambiente local for Windows e nao possuir Python, registrar que Python/Alembic serao validados na VPS.

## 7. Fase 1 - Base do servidor

Executar como `root`:

```bash
apt update
apt upgrade -y
apt install -y curl wget git unzip build-essential software-properties-common ca-certificates gnupg ufw nginx
```

Criar usuario:

```bash
adduser deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

Firewall:

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status
```

Gate da fase:

```bash
systemctl status nginx --no-pager
id deploy
```

## 8. Fase 2 - Runtime Node, Python e PostgreSQL

Node e pnpm:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs
npm install -g pnpm
node -v
pnpm -v
```

Python:

```bash
apt install -y python3 python3-venv python3-dev python3-pip
python3 --version
```

PostgreSQL:

```bash
apt install -y postgresql postgresql-contrib
systemctl enable postgresql
systemctl start postgresql
systemctl status postgresql --no-pager
```

Gate da fase:

```bash
node -v
pnpm -v
python3 --version
sudo -u postgres psql -c "select version();"
```

## 9. Fase 3 - Codigo e ambiente da aplicacao

Executar como `deploy`:

```bash
cd /home/deploy
git clone REPOSITORIO_GIT telz
cd /home/deploy/telz
git checkout main
git log --oneline -1
```

Criar venv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

Instalar dependencias Node:

```bash
pnpm install --frozen-lockfile
```

Criar `backend/.env` manualmente a partir dos parametros reais. Nao sobrescrever `.env` existente sem backup.

Campos minimos:

```env
DATABASE_URL=postgresql://telz_user:SENHA_FORTE@127.0.0.1:5432/telz
APP_NAME=Telz
APP_VERSION=1.0.0
DEBUG=false
JWT_SECRET_KEY=SENHA_FORTE_JWT
ALLOWED_ORIGINS=["https://app.seudominio.com.br"]
PUBLIC_STORE_URL=https://app.seudominio.com.br
VITE_PUBLIC_STORE_URL=https://app.seudominio.com.br
```

Adicionar tambem as flags multi-tenant desligadas listadas na fase 5 deste documento.

Gate da fase:

```bash
test -f backend/.env
source .venv/bin/activate
python -c "from backend.config import get_settings; print(get_settings().APP_NAME)"
```

## 10. Fase 4 - Banco e Alembic

Criar banco:

```bash
sudo -u postgres createuser telz_user
sudo -u postgres createdb telz -O telz_user
sudo -u postgres psql -c "ALTER USER telz_user WITH PASSWORD 'SENHA_FORTE';"
```

Validar Alembic antes de upgrade:

```bash
cd /home/deploy/telz
source .venv/bin/activate
alembic -c backend/alembic.ini heads --verbose
alembic -c backend/alembic.ini current --verbose
alembic -c backend/alembic.ini history --verbose
```

Se houver multiplas heads inesperadas, parar e corrigir antes de `upgrade`.

Executar migration:

```bash
alembic -c backend/alembic.ini upgrade head
alembic -c backend/alembic.ini current --verbose
```

Gate da fase:

```bash
sudo -u postgres psql -d telz -c "select count(*) from alembic_version;"
sudo -u postgres psql -d telz -c "select version_num from alembic_version;"
```

Observacao: em producao existente, preferir upgrade ate a revision exata da entrega quando houver uma revision alvo conhecida. Para instalacao nova e cadeia revisada, `upgrade head` e aceitavel somente depois de `heads/history` passar.

## 11. Fase 5 - Build local na VPS

Executar:

```bash
cd /home/deploy/telz
pnpm run typecheck
pnpm test
pnpm run build
```

Gate da fase:

```bash
test -d dist/spa
test -f dist/server/node-build.mjs
```

## 12. Fase 6 - Systemd

Criar `/etc/systemd/system/telz-api.service`:

```ini
[Unit]
Description=Telz - FastAPI Backend
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/telz
Environment=PATH=/home/deploy/telz/.venv/bin
EnvironmentFile=/home/deploy/telz/backend/.env
ExecStart=/home/deploy/telz/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=telz-api

[Install]
WantedBy=multi-user.target
```

Criar `/etc/systemd/system/telz-web.service`:

```ini
[Unit]
Description=Telz - Node Web
After=network.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/telz
Environment=NODE_ENV=production
Environment=PORT=3000
ExecStart=/usr/bin/node dist/server/node-build.mjs
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=telz-web

[Install]
WantedBy=multi-user.target
```

Ativar:

```bash
systemctl daemon-reload
systemctl enable telz-api telz-web
systemctl start telz-api telz-web
```

Gate da fase:

```bash
systemctl status telz-api --no-pager
systemctl status telz-web --no-pager
curl -f http://127.0.0.1:8000/health
curl -I http://127.0.0.1:3000
```

## 13. Fase 7 - Nginx e dominio principal

Configurar Nginx para encaminhar:

- `/api/` para `127.0.0.1:8000`;
- `/api/uploads/` para backend ou diretiva equivalente ja validada;
- demais rotas para `127.0.0.1:3000`;
- headers `Host`, `X-Forwarded-Host`, `X-Forwarded-Proto`, `X-Real-IP` e `X-Forwarded-For`.

Antes de confiar em `X-Forwarded-*` no backend, manter:

```env
TENANT_DOMAINS_TRUST_PROXY_HEADERS=false
TENANT_DOMAINS_TRUSTED_PROXY_IPS=
```

Gate da fase:

```bash
nginx -t
systemctl reload nginx
curl -I http://DOMINIO_PRINCIPAL
curl -f http://DOMINIO_PRINCIPAL/api/health
```

SSL do dominio principal pode ser instalado com Certbot depois que HTTP responder corretamente.

## 14. Fase 8 - Backup antes de ativacoes

Criar backup antes de qualquer validacao multi-tenant:

```bash
mkdir -p /home/deploy/backups/telz
pg_dump --format=custom --file=/home/deploy/backups/telz/telz-$(date +%Y%m%d-%H%M%S).dump "$DATABASE_URL"
tar -czf /home/deploy/backups/telz/telz-env-uploads-$(date +%Y%m%d-%H%M%S).tar.gz backend/.env uploads
```

Gate da fase:

```bash
ls -lh /home/deploy/backups/telz
```

## 15. Fase 9 - Smoke test legado com flags desligadas

Validar:

- `/health`;
- login admin;
- loja publica;
- produtos;
- carrinho;
- checkout;
- pedido;
- painel de pedidos;
- pagamentos configurados;
- uploads;
- WhatsApp Gateway instalado por padrao;
- logs sem erro recorrente.

Comandos:

```bash
journalctl -u telz-api -n 120 --no-pager
journalctl -u telz-web -n 120 --no-pager
curl -f http://127.0.0.1:8000/health
```

Gate da fase: sistema legado funcional antes de qualquer flag multi-tenant.

## 16. Fase 10 - Validacao multi-tenant em staging/VPS

Somente depois das fases anteriores:

1. conferir migrations multi-tenant aplicadas;
2. verificar registros sem `tenant_id`;
3. conferir constraints e indices;
4. criar tenants A e B;
5. testar dominio A e dominio B;
6. testar isolamento por modulo;
7. ativar flags por onda, nunca todas juntas.

Ordem recomendada de flags:

```text
MULTI_TENANT_AUTH_ENABLED
TENANT_DOMAINS_ENABLED
TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED
TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED
TENANT_OPERATIONS_ENFORCEMENT_ENABLED
TENANT_PAYMENT_WEBHOOKS_ENABLED
MULTI_TENANT_WAVE6_ORM_ENABLED
MULTI_TENANT_WAVE7_ORM_ENABLED
TENANT_UPLOAD_NAMESPACE_ENABLED
TENANT_BACKGROUND_CONTEXT_ENABLED
TENANT_CREDENTIALS_ENABLED
PLATFORM_RBAC_ENABLED
```

Cada flag exige:

- backup antes;
- restart controlado;
- smoke test;
- teste A/B;
- log review;
- plano de rollback da flag.

## 17. Fase 11 - Contract migrations

Contract so pode ocorrer depois de:

- contagens sem `tenant_id` zeradas;
- FKs validadas;
- uniques tenant-scoped validadas;
- queries por ID revisadas;
- webhooks tenantizados;
- jobs e uploads com contexto;
- rollback de aplicacao documentado.

Nao executar automaticamente:

- drop de coluna;
- drop de unique global;
- `ALTER COLUMN tenant_id SET NOT NULL`;
- downgrade de banco.

## 18. Fase 12 - Automatizacao do instalador

Somente depois do metodo manual passar pelo menos uma vez:

O instalador automatizado deve ser interativo, assistido e retomavel. A primeira forma suportada deve ser sempre a versionada no repositorio:

```bash
git clone REPOSITORIO_GIT
cd REPOSITORIO_GIT
sudo bash installer/install.sh
```

A forma remota:

```bash
curl -fsSL https://install.telz.com.br | sudo bash
```

fica apenas como alvo futuro. Ela so pode ser documentada como oficial depois de existir hospedagem controlada, HTTPS valido, versionamento do script, integridade verificavel e procedimento de rollback.

Criar estrutura recomendada:

```text
installer/
  install.sh
  lib/
    ui.sh
    validate.sh
    secrets.sh
    os.sh
    postgres.sh
    node.sh
    python.sh
    env.sh
    nginx.sh
    systemd.sh
    ssl.sh
    backup.sh
    health.sh
    alembic.sh
    state.sh
scripts/
  update-telz.sh
  health-check.sh
  backup-telz.sh
  restore-telz.sh
  telz-cli
docs/
  INSTALL_TELZ_VPS.md
```

Fluxo interativo minimo:

1. verificacao da VPS;
2. dados da plataforma;
3. repositorio Git e diretorio de instalacao;
4. banco de dados local ou externo;
5. backend;
6. frontend/build;
7. Nginx;
8. dominio e SSL;
9. servicos, backup e seguranca;
10. validacao final.

Cada fase deve:

- mostrar titulo e objetivo;
- validar respostas antes de continuar;
- permitir cancelar com seguranca;
- permitir retomada com `--resume`;
- registrar somente estado nao sensivel;
- nunca imprimir senha, token, `DATABASE_URL`, chave privada ou `.env` completo.

Estado e logs:

```text
/var/lib/telz-installer/state
/var/log/telz-installer/install-AAAA-MM-DD-HHMMSS.log
```

O estado deve registrar fase atual, fases concluidas, erro, data, versao do instalador, commit instalado e configuracoes nao sensiveis. Os logs devem mascarar pelo menos estes termos: `password`, `secret`, `token`, `api_key`, `database_url`, `private_key`.

Requisitos obrigatorios dos scripts:

- `set -Eeuo pipefail`;
- `umask 077` quando criar arquivos sensiveis;
- idempotencia;
- lock contra execucao concorrente;
- logs com mascaramento de segredos;
- parametros por flags e modo interativo;
- nenhum segredo hardcoded;
- nenhum `eval`;
- nenhuma concatenacao insegura de input em shell;
- nenhum `rm -rf` amplo;
- nenhum reset de banco;
- backup antes de migration;
- abortar em Alembic inconsistente;
- flags multi-tenant desligadas por default;
- nao rodar a aplicacao como root;
- nao salvar token Git em texto aberto;
- nao sobrescrever `.env`, Nginx, systemd, cron ou certificado sem backup e confirmacao.

Idempotencia obrigatoria:

- detectar instalacao existente;
- detectar usuario Linux existente;
- detectar diretorio existente;
- detectar banco e usuario PostgreSQL existentes;
- detectar virtualenv existente;
- detectar Nginx existente;
- detectar units systemd existentes;
- detectar certificado existente;
- detectar backup/timer existente.

Se encontrar instalacao existente, oferecer apenas acoes controladas:

```text
1. Atualizar
2. Reparar
3. Reconfigurar
4. Cancelar
```

O script de atualizacao `scripts/update-telz.sh` deve:

1. bloquear atualizacoes simultaneas;
2. registrar commit atual;
3. fazer backup;
4. buscar branch/commit/tag informado;
5. instalar dependencias;
6. executar typecheck, testes e build;
7. revisar Alembic antes de migration;
8. executar migrations;
9. reiniciar servicos;
10. executar health check;
11. voltar codigo, build, Nginx e systemd se a aplicacao falhar;
12. nunca executar downgrade automatico do banco.

CLI administrativa futura:

```bash
telz-cli status
telz-cli health
telz-cli update
telz-cli backup
telz-cli restore
telz-cli logs
telz-cli restart
telz-cli ssl setup
telz-cli ssl renew
telz-cli domain check
telz-cli config show
telz-cli migrations status
```

`telz-cli` deve ser somente wrapper seguro para scripts controlados. Nao pode aceitar execucao arbitraria de shell.

Rollback permitido automaticamente:

- codigo;
- build;
- Nginx;
- systemd.

Rollback de banco nao deve ser automatico. Se uma migration ja tiver sido aplicada e a aplicacao falhar, registrar o estado, manter backup, restaurar versao compativel quando possivel e exibir procedimento manual seguro.

Validacao final do instalador:

```bash
systemctl is-active telz-api
systemctl is-active telz-web
nginx -t
curl -f http://127.0.0.1:8000/health
curl -f https://DOMINIO_PRINCIPAL/health
```

O relatorio final deve mostrar painel, servicos, banco, diretorio, commit, SSL, backup e comandos uteis. Nunca mostrar senha.

## 19. Especificacao do instalador interativo

O prompt complementar do instalador interativo e coerente com este metodo e deve ser usado como especificacao da fase de automatizacao, com um ajuste importante: antes de criar scripts definitivos, o projeto deve ser auditado na VPS ou em ambiente descartavel para confirmar comandos reais, formato do build, Alembic, systemd, Nginx e health checks.

Comando alvo para instalacao a partir de checkout clonado:

```bash
git clone REPOSITORIO_GIT telz
cd telz
sudo bash installer/install.sh
```

Opcao futura, ainda nao liberada:

```bash
curl -fsSL https://install.telz.com.br | sudo bash
```

Essa opcao so pode ser documentada como futura ate existir hospedagem segura, versionamento, integridade verificavel e processo de publicacao controlado.

### 19.1 Fluxo interativo alvo

O instalador deve operar por fases, exibindo o que sera feito, validando entrada, permitindo cancelar e evitando continuar com informacao invalida.

Fases do instalador:

1. verificacao da VPS;
2. dados da plataforma;
3. repositorio Git;
4. banco de dados;
5. backend;
6. frontend;
7. Nginx;
8. dominio e SSL;
9. servicos, backup e seguranca;
10. validacao final.

Antes de executar alteracoes, o instalador deve exibir resumo final e exigir confirmacao explicita.

### 19.2 Perguntas e validacoes obrigatorias

VPS:

- sistema operacional;
- versao;
- arquitetura;
- memoria;
- disco;
- usuario atual;
- IP publico detectado;
- root ou sudo;
- portas disponiveis;
- conectividade externa.

Plataforma:

- nome da plataforma, default `Telz`;
- slug, default `telz`;
- dominio principal;
- e-mail administrativo;
- e-mail de SSL;
- timezone, default `America/Sao_Paulo`;
- idioma, default `pt-BR`;
- moeda, default `BRL`.

Git:

- URL do repositorio;
- branch;
- publico ou privado;
- metodo de acesso para privado, sem expor token;
- diretorio de instalacao;
- usuario de servico.

Banco:

- PostgreSQL local ou externo;
- nome do banco;
- usuario;
- senha manual ou gerada;
- porta;
- SSL mode para banco externo;
- teste de conexao antes de seguir.

Backend:

- porta da API;
- quantidade de workers;
- ambiente;
- geracao de chaves;
- `.env` protegido;
- Alembic;
- usuario master inicial, com senha oculta e nunca logada.

Frontend:

- detectar gerenciador real;
- usar `pnpm` quando aplicavel;
- executar typecheck, testes e build;
- decidir entre `telz-web` e frontend estatico conforme arquitetura real. No estado atual do projeto, o caminho comprovado e Node servindo `dist/server/node-build.mjs`.

Nginx, dominio e SSL:

- validar dominio sem protocolo, path, query ou porta;
- preservar `Host`;
- configurar headers de proxy;
- executar `nginx -t` antes de reload;
- validar DNS antes de SSL;
- se DNS nao propagou, concluir instalacao em HTTP/local e gerar comando posterior de finalizacao.

Backup e seguranca:

- configurar backup opcional;
- configurar firewall sem bloquear a porta SSH atual;
- configurar logrotate ou timer quando aplicavel;
- proteger arquivos sensiveis com permissao restritiva.

### 19.3 Estrutura modular esperada

O instalador nao deve ser um arquivo monolitico. Estrutura alvo:

```text
installer/install.sh
installer/lib/colors.sh
installer/lib/prompts.sh
installer/lib/validation.sh
installer/lib/system.sh
installer/lib/git.sh
installer/lib/database.sh
installer/lib/backend.sh
installer/lib/frontend.sh
installer/lib/nginx.sh
installer/lib/ssl.sh
installer/lib/systemd.sh
installer/lib/backup.sh
installer/lib/firewall.sh
installer/lib/summary.sh
installer/templates/telz-api.service
installer/templates/telz-web.service
installer/templates/nginx-telz.conf
installer/templates/env.production.example
installer/config/defaults.env
scripts/update-telz.sh
scripts/rollback-telz.sh
scripts/backup-telz.sh
scripts/restore-telz.sh
scripts/health-check.sh
scripts/finish-ssl.sh
docs/INSTALL_TELZ_VPS.md
docs/UPDATE_TELZ_VPS.md
docs/BACKUP_AND_RESTORE.md
docs/INSTALLER_TROUBLESHOOTING.md
```

### 19.4 Modo nao interativo

O instalador deve aceitar modo nao interativo:

```bash
sudo bash installer/install.sh --config /root/telz-install.env --non-interactive
```

Segredos devem ficar em arquivo separado com permissao `600`, nunca no log principal.

Exemplo de configuracao nao sensivel:

```env
PLATFORM_NAME=Telz
PLATFORM_SLUG=telz
PLATFORM_DOMAIN=app.telz.com.br
PLATFORM_PUBLIC_IP=000.000.000.000
ADMIN_EMAIL=admin@telz.com.br
SSL_EMAIL=admin@telz.com.br
INSTALL_DIR=/opt/telz
SERVICE_USER=telz
GIT_REPOSITORY=git@github.com:empresa/telz.git
GIT_BRANCH=main
DATABASE_MODE=local
DATABASE_NAME=telz
DATABASE_USER=telz_user
API_PORT=8000
INSTALL_NGINX=true
INSTALL_SSL=true
INSTALL_BACKUP=true
```

### 19.5 Retomada, logs e idempotencia

O instalador deve registrar estado por fase em local controlado, por exemplo:

```text
/var/lib/telz-installer/state
```

Deve permitir:

```bash
sudo bash installer/install.sh --resume
```

Logs devem ficar em:

```text
/var/log/telz-installer/install-AAAA-MM-DD-HHMMSS.log
```

Os logs devem mascarar:

- password;
- secret;
- token;
- api_key;
- database_url;
- private_key.

Reexecutar o instalador nao pode apagar banco, uploads, backups, `.env`, certificados, Nginx ou services sem confirmacao explicita. Se encontrar uma instalacao existente, deve oferecer atualizar, reparar, reconfigurar ou cancelar.

### 19.6 Atualizacao, CLI e rollback

Script alvo:

```bash
sudo install -m 0755 -o root -g root scripts/update-telz.sh /usr/local/sbin/update-telz
sudo /usr/local/sbin/update-telz /opt/telz
```

Regras:

- bloquear execucoes simultaneas;
- registrar commit atual;
- fazer backup;
- instalar dependencias;
- rodar typecheck, testes e build;
- revisar Alembic antes de migrations;
- reiniciar services;
- executar health check;
- restaurar codigo anterior se a aplicacao falhar;
- nunca fazer downgrade automatico de banco.

CLI futura:

```bash
telz-cli status
telz-cli health
telz-cli update
telz-cli backup
telz-cli restore
telz-cli logs
telz-cli restart
telz-cli ssl setup
telz-cli ssl renew
telz-cli domain check
telz-cli config show
telz-cli config edit
telz-cli migrations status
```

O `telz-cli` deve ser apenas wrapper seguro para scripts controlados e nao deve aceitar execucao arbitraria de shell.

Rollback automatico permitido apenas para:

- codigo;
- build;
- Nginx;
- systemd.

Rollback automatico de migration continua proibido sem estrategia especifica, migration reversivel e confirmacao explicita.

### 19.7 Criterios de aceite do instalador automatizado

O instalador automatizado so estara pronto quando:

1. funcionar em VPS limpa suportada;
2. perguntar dados por fase;
3. validar entradas;
4. instalar dependencias;
5. clonar Git;
6. configurar PostgreSQL local ou externo;
7. criar `.env` sem expor segredos;
8. executar Alembic com `heads/current/history` revisados;
9. executar typecheck, testes e build;
10. configurar Nginx;
11. configurar dominio principal;
12. configurar SSL quando DNS estiver pronto;
13. criar services;
14. iniciar aplicacao;
15. executar health check;
16. configurar backup;
17. permitir retomada;
18. permitir atualizacao;
19. ser idempotente;
20. nao expor segredos;
21. produzir relatorio final.

## 20. Criterios de aceite do metodo

O metodo e considerado pronto quando:

- uma VPS limpa instala dependencias;
- o repositorio clona;
- `.env` e criado sem segredo hardcoded;
- banco e criado;
- Alembic roda sem erro;
- build passa;
- `telz-api` e `telz-web` sobem;
- Nginx roteia API e frontend;
- `/health` responde local e via dominio;
- backup inicial e gerado;
- smoke test legado passa com flags desligadas;
- validacao multi-tenant fica documentada como fase posterior, nao misturada com instalacao inicial.

## 21. Resultado esperado

Este metodo permite criar primeiro uma base operacional confiavel na VPS. As validacoes pendentes das ondas multi-tenant passam a ser executadas depois, diretamente no sistema instalado, com banco real, logs reais, Nginx real, systemd real e dominios reais.

# Guia de Instalação na VPS

## Visão Geral da Arquitetura

```
Internet
    │
    ▼
 Nginx (porta 443/80)  ← SSL via Let's Encrypt
    │
    ├── /api/*  ──────► FastAPI  (Python · porta 8000)
    │                       │
    │                  PostgreSQL (porta 5432)
    │
    └── /*  ──────────► Node.js/Express (porta 3000)
                            └── serve dist/spa/ (React SPA)
```

**Requisitos do servidor:**
- Ubuntu 22.04 LTS (recomendado) ou 20.04
- Mínimo: 1 vCPU · 2 GB RAM · 20 GB SSD
- Domínio apontando para o IP da VPS (necessário para SSL)

---

## 0. Defina o Nome da Sua Loja

> **Este é o passo mais importante.** Execute este bloco inteiro no terminal da VPS antes de qualquer outro comando. As variáveis definidas aqui serão usadas em todos os passos seguintes.

```bash
# ============================================================
#  EDITE ESTAS TRÊS LINHAS conforme a sua loja e domínio
# ============================================================

# Nome da loja: apenas letras minúsculas, números e _ (sem espaços)
# Exemplos: brasell | pizzariajoia | lanchonete | pizzadoze
APP_NAME="minhaloja"

# Domínio do site (sem https://)
DOMAIN="meudominio.com.br"

# E-mail para o certificado SSL (Let's Encrypt)
ADMIN_EMAIL="seu@email.com.br"

# ============================================================
#  NÃO EDITE A PARTIR DAQUI — derivado automaticamente
# ============================================================
DB_NAME="${APP_NAME}"
DB_USER="${APP_NAME}_user"

echo "✔  APP_NAME  = $APP_NAME"
echo "✔  DOMAIN    = $DOMAIN"
echo "✔  DB_NAME   = $DB_NAME"
echo "✔  DB_USER   = $DB_USER"
```

> As variáveis `$APP_NAME`, `$DOMAIN`, `$DB_NAME` e `$DB_USER` são usadas em **todos** os comandos deste guia. Se fechar o terminal, redefina-as antes de continuar.

---

## 1. Preparação do Servidor

### 1.1 Acesso e atualização

```bash
# Acesse a VPS via SSH
ssh root@SEU_IP

# Atualize o sistema
apt update && apt upgrade -y

# Instale utilitários essenciais
apt install -y curl wget git unzip build-essential software-properties-common ufw
```

### 1.2 Crie um usuário de deploy

```bash
adduser deploy
usermod -aG sudo deploy

# Copie a chave SSH para o novo usuário
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy

# Troque para o usuário deploy
su - deploy
```

> Após trocar para o usuário `deploy`, redefina as variáveis do **Passo 0** antes de continuar.

### 1.3 Firewall

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status
```

---

## 2. Instale o Node.js 22

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

node -v   # v22.x.x
npm -v

sudo npm install -g pnpm
pnpm -v
```

---

## 3. Instale o Python 3.11

```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
python3.11 --version
```

---

## 4. Instale o PostgreSQL 16

```bash
sudo sh -c 'echo "deb https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo tee /etc/apt/trusted.gpg.d/pgdg.asc &>/dev/null

sudo apt update
sudo apt install -y postgresql-16 postgresql-contrib-16

sudo systemctl enable postgresql
sudo systemctl start postgresql
sudo systemctl status postgresql
```

---

## 5. Instale o Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

---

## 6. Clone o Projeto

```bash
cd /home/deploy

# Clone para uma pasta com o nome da sua loja
git clone https://github.com/SEU_USUARIO/SEU_REPO.git "$APP_NAME"

cd "$APP_NAME"
```

---

## 7. Configure o Banco de Dados

### Opção A — Script automático (recomendado)

```bash
# Execute a partir da raiz do projeto clonado
bash setup_database.sh --nome "$DB_NAME" --pg-usuario postgres
```

O script irá:
1. Criar o usuário `$DB_USER` no PostgreSQL
2. Criar o banco `$DB_NAME`
3. Criar todas as tabelas, índices e dados iniciais
4. Salvar a `DATABASE_URL` completa no arquivo `db_connection.txt`

```bash
# Após o script finalizar, visualize a DATABASE_URL gerada:
cat db_connection.txt
```

### Opção B — Manual (passo a passo)

```bash
# 1. Crie o usuário e banco no PostgreSQL
sudo -u postgres psql << EOF
CREATE USER "${DB_USER}" WITH PASSWORD 'TROQUE_POR_SENHA_FORTE';
CREATE DATABASE "${DB_NAME}" OWNER "${DB_USER}";
GRANT ALL PRIVILEGES ON DATABASE "${DB_NAME}" TO "${DB_USER}";
\q
EOF

# 2. Execute o script SQL informando o nome do banco
sudo -u postgres psql \
  -v DBNAME="${DB_NAME}" \
  -v DBUSER="${DB_USER}" \
  -f /home/deploy/"$APP_NAME"/setup_database.sql
```

---

## 8. Configure as Variáveis de Ambiente

### 8.1 Backend Python (FastAPI)

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Preencha o arquivo — substitua os valores marcados com `<`:

```env
# Cole aqui a DATABASE_URL do db_connection.txt (Opção A)
# ou monte manualmente com os valores da Opção B
DATABASE_URL=postgresql://<DB_USER>:<SENHA>@localhost:5432/<DB_NAME>

APP_NAME=PizzaApp API
APP_VERSION=1.0.0
DEBUG=false

# CORS — domínio real do site
ALLOWED_ORIGINS=["https://$DOMAIN","https://www.$DOMAIN"]

# JWT — gere uma chave forte:
# python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=<COLE_A_CHAVE_GERADA_AQUI>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# Gateway de pagamento
PAYMENT_GATEWAY=mock
PAYMENT_SECRET_KEY=sua_chave_secreta
PAYMENT_WEBHOOK_SECRET=sua_chave_webhook

# Fidelidade
POINTS_PER_REAL=1.0
DELIVERY_POINTS=10

# Conta admin — criada automaticamente no primeiro boot
ADMIN_EMAIL=admin@minhaloja.com.br
ADMIN_NAME=Administrador
ADMIN_PASSWORD=<SENHA_FORTE_PARA_O_PAINEL>
```

> Gere a chave JWT:
> ```bash
> python3 -c "import secrets; print(secrets.token_hex(32))"
> ```

### 8.2 Frontend Node.js

> **Atenção:** em produção o Nginx roteia `/api/*` para o FastAPI.
> O frontend deve chamar `https://$DOMAIN/api` (com o sufixo `/api`), não o domínio raiz.

```bash
cat > .env.production << EOF
VITE_API_URL=https://$DOMAIN/api
EOF
```

---

## 9. Instale as Dependências e Gere o Build

### 9.1 Frontend (Node.js)

```bash
cd /home/deploy/"$APP_NAME"

pnpm install
pnpm build
# Resultado: dist/spa/ (frontend) e dist/server/ (servidor Node)
```

### 9.2 Backend (Python)

```bash
cd /home/deploy/"$APP_NAME"

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
deactivate
```

---

## 10. Configure os Serviços Systemd

### 10.1 Serviço do backend FastAPI

```bash
sudo tee /etc/systemd/system/"${APP_NAME}"-api.service > /dev/null << EOF
[Unit]
Description=${APP_NAME} - FastAPI Backend
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/${APP_NAME}
Environment="PATH=/home/deploy/${APP_NAME}/.venv/bin"
EnvironmentFile=/home/deploy/${APP_NAME}/backend/.env
ExecStart=/home/deploy/${APP_NAME}/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${APP_NAME}-api

[Install]
WantedBy=multi-user.target
EOF
```

### 10.2 Serviço do servidor Node.js

```bash
sudo tee /etc/systemd/system/"${APP_NAME}"-web.service > /dev/null << EOF
[Unit]
Description=${APP_NAME} - Node.js Web Server
After=network.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/${APP_NAME}
Environment="NODE_ENV=production"
Environment="PORT=3000"
ExecStart=/usr/bin/node dist/server/node-build.mjs
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${APP_NAME}-web

[Install]
WantedBy=multi-user.target
EOF
```

### 10.3 Ative e inicie

```bash
sudo systemctl daemon-reload

sudo systemctl enable "${APP_NAME}"-api "${APP_NAME}"-web
sudo systemctl start  "${APP_NAME}"-api "${APP_NAME}"-web

sudo systemctl status "${APP_NAME}"-api "${APP_NAME}"-web
```

---

## 11. Configure o Nginx

```bash
sudo tee /etc/nginx/sites-available/"$APP_NAME" > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;

    # SSL (preenchido pelo Certbot)
    # ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    client_max_body_size 10M;

    # API Python (FastAPI)
    location /api/ {
        proxy_pass         http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }

    location /docs    { proxy_pass http://127.0.0.1:8000/docs;        proxy_set_header Host \$host; }
    location /redoc   { proxy_pass http://127.0.0.1:8000/redoc;       proxy_set_header Host \$host; }
    location /openapi.json { proxy_pass http://127.0.0.1:8000/openapi.json; }

    # Frontend Node.js / React SPA
    location / {
        proxy_pass         http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade           \$http_upgrade;
        proxy_set_header   Connection        "upgrade";
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        proxy_pass http://127.0.0.1:3000;
        expires    30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }
}
EOF

# Ative o site
sudo ln -s /etc/nginx/sites-available/"$APP_NAME" /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
sudo systemctl reload nginx
```

---

## 12. SSL com Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx

sudo certbot --nginx \
  -d "$DOMAIN" \
  -d "www.$DOMAIN" \
  --non-interactive \
  --agree-tos \
  --email "$ADMIN_EMAIL"

# Verifique renovação automática
sudo certbot renew --dry-run
```

---

## 13. Verificação Final

```bash
# Status de todos os serviços
sudo systemctl status "${APP_NAME}"-api "${APP_NAME}"-web nginx postgresql

# Logs em tempo real
sudo journalctl -u "${APP_NAME}"-api -f     # backend Python
sudo journalctl -u "${APP_NAME}"-web -f     # frontend Node.js

# Teste os endpoints
curl "https://$DOMAIN/api/health"
# Esperado: {"success":true,"data":{"status":"ok","version":"1.0.0"}}

curl "https://$DOMAIN/api/products"
# Esperado: {"success":true,"data":[...]}
```

**Acesse no navegador:**

| URL | Descrição |
|-----|-----------|
| `https://$DOMAIN` | Loja (app do cliente) |
| `https://$DOMAIN/painel` | Painel administrativo |
| `https://$DOMAIN/docs` | Documentação Swagger |

---

## 14. Atualizando o Site (Deploy)

```bash
cd /home/deploy/"$APP_NAME"

# 1. Baixe as alterações
git pull origin main

# 2. Reconstrua o frontend
pnpm install
pnpm build

# 3. Atualize dependências Python se necessário
source .venv/bin/activate
pip install -r backend/requirements.txt
deactivate

# 4. Reinicie os serviços
sudo systemctl restart "${APP_NAME}"-api "${APP_NAME}"-web

# 5. Confirme
sudo systemctl status "${APP_NAME}"-api "${APP_NAME}"-web
```

---

## 15. Backup do Banco de Dados

### Backup manual

```bash
# Substitua $DB_NAME pelo nome do seu banco se necessário
sudo -u postgres pg_dump "$DB_NAME" > ~/backup_"${DB_NAME}"_$(date +%Y%m%d_%H%M%S).sql
```

### Backup automático diário

```bash
mkdir -p /home/deploy/backups

# Abra o crontab
crontab -e

# Adicione (backup todo dia às 3h)
# Substitua NOME_DO_BANCO pelo valor real de $DB_NAME
0 3 * * * sudo -u postgres pg_dump NOME_DO_BANCO > /home/deploy/backups/NOME_DO_BANCO_$(date +\%Y\%m\%d).sql 2>&1
```

### Restaurar backup

```bash
sudo -u postgres psql "$DB_NAME" < ~/backup_NOME_YYYYMMDD_HHMMSS.sql
```

---

## 16. Resolução de Problemas

### Serviço não inicia

```bash
sudo journalctl -u "${APP_NAME}"-api --no-pager -n 50
sudo journalctl -u "${APP_NAME}"-web --no-pager -n 50
```

### Nginx retorna 502 Bad Gateway

```bash
# Verifique se os serviços estão de pé
curl http://127.0.0.1:8000/health   # FastAPI
curl http://127.0.0.1:3000          # Node.js

sudo systemctl restart "${APP_NAME}"-api "${APP_NAME}"-web
```

### Erro de conexão com o banco

```bash
# Teste a conexão
sudo -u postgres psql -d "$DB_NAME" -c "SELECT current_database();"

# Verifique o DATABASE_URL no .env
grep DATABASE_URL /home/deploy/"$APP_NAME"/backend/.env
```

### Permissões de arquivo

```bash
sudo chown -R deploy:deploy /home/deploy/"$APP_NAME"
```

---

## Resumo de Portas e Serviços

| Serviço | Porta | Acesso externo |
|---------|-------|----------------|
| Nginx | 80, 443 | Sim (público) |
| Node.js (frontend) | 3000 | Não (apenas via Nginx) |
| FastAPI (backend) | 8000 | Não (apenas via Nginx) |
| PostgreSQL | 5432 | Não (apenas local) |

## Credenciais padrão do admin

| Campo | Valor |
|-------|-------|
| URL do painel | `https://SEU_DOMINIO.com.br/painel` |
| E-mail | Definido no seed do banco (`backend/core/seed.py`) |
| Senha | Definida no seed do banco (`backend/core/seed.py`) |

> **Importante:** Altere o e-mail e a senha do admin diretamente em `backend/core/seed.py` **antes** de executar o setup do banco pela primeira vez. Nunca use as credenciais padrão em produção.

# Instalacao Telz em VPS

Este documento descreve o uso do instalador modular criado para Ubuntu 22.04/24.04.

Status: primeira versao executavel, ainda pendente de teste em VPS limpa.

## Premissas

- Executar em VPS Ubuntu.
- Rodar como `root` ou via `sudo`.
- Ter DNS do dominio principal apontando para a VPS se SSL for ativado.
- Manter flags multi-tenant desligadas na primeira instalacao.

## Instalacao interativa

No diretorio do projeto:

```bash
sudo bash installer/install.sh
```

O instalador pergunta dados da plataforma, Git, banco, usuario Linux, dominio e segredos.

## Instalacao nao interativa

Crie um arquivo baseado em:

```text
installer/config/defaults.env
```

Depois execute:

```bash
sudo bash installer/install.sh --config /root/telz-install.env --non-interactive
```

O arquivo de configuracao deve ter permissao restrita:

```bash
chmod 600 /root/telz-install.env
```

## Retomada

Se uma fase falhar depois de ter sido concluida, corrija o problema e execute:

```bash
sudo bash installer/install.sh --resume
```

O estado fica em:

```text
/var/lib/telz-installer/state
```

Os logs ficam em:

```text
/var/log/telz-installer/
```

## O que o instalador faz

- valida sistema operacional;
- instala pacotes base;
- cria usuario de servico;
- prepara diretorios;
- configura firewall;
- instala Node/pnpm;
- clona ou atualiza o repositorio;
- cria venv Python;
- instala dependencias backend;
- cria `backend/.env` com flags multi-tenant desligadas;
- prepara as variaveis de Mercado Pago e ASAAS no `backend/.env`;
- configura PostgreSQL local quando selecionado;
- revisa Alembic antes de `upgrade head`;
- executa typecheck, testes e build;
- cria services `telz-api` e `telz-web`;
- cria service `telz-whatsapp-gateway`;
- configura Nginx;
- tenta SSL se solicitado;
- configura backup diario opcional;
- executa health check final.

## Gates importantes

O instalador pede confirmacao antes de:

- iniciar instalacao real;
- executar `alembic upgrade head`.

Ele nao executa:

- downgrade automatico de banco;
- contract migrations separadas fora da cadeia Alembic;
- ativacao multi-tenant;
- remocao de banco/uploads/backups/certificados.

## Validacao depois da instalacao

```bash
sudo bash scripts/health-check.sh /opt/telz
sudo systemctl status telz-api --no-pager
sudo systemctl status telz-web --no-pager
sudo systemctl status telz-whatsapp-gateway --no-pager
sudo journalctl -u telz-api -n 100 --no-pager
sudo journalctl -u telz-web -n 100 --no-pager
sudo journalctl -u telz-whatsapp-gateway -n 100 --no-pager
```

O WhatsApp Gateway e instalado por padrao porque faz parte do sistema atual. O service pode ficar ativo antes de a sessao WhatsApp estar online; a conexao operacional depende da leitura do QR Code no painel.

## Pagamentos

Mercado Pago e ASAAS fazem parte do sistema atual e ficam preparados pelo instalador.

Na instalacao padrao, o `backend/.env` recebe:

```env
PAYMENT_PROVIDER=mock
PAYMENT_GATEWAY=mock
MERCADO_PAGO_ACCESS_TOKEN=
MERCADO_PAGO_PUBLIC_KEY=
MERCADO_PAGO_WEBHOOK_SECRET=
ASAAS_API_KEY=
ASAAS_WEBHOOK_TOKEN=
```

As credenciais podem ser informadas durante a instalacao, por arquivo `--config` ou depois pelo painel `/painel/pagamentos`.

Nao confundir estes gateways com billing SaaS da Telz. Mercado Pago e ASAAS aqui sao pagamentos dos pedidos das lojas.

## Backup manual

```bash
sudo bash scripts/backup-telz.sh /opt/telz
```

## SSL posterior

Se o DNS nao estava pronto durante a instalacao:

```bash
sudo bash scripts/finish-ssl.sh app.seudominio.com.br admin@seudominio.com.br
```

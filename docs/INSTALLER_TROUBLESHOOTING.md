# Troubleshooting do instalador Telz

## Logs

```bash
sudo ls -lah /var/log/telz-installer/
sudo tail -n 200 /var/log/telz-installer/install-*.log
```

## Services

```bash
sudo systemctl status telz-api --no-pager
sudo systemctl status telz-web --no-pager
sudo systemctl status telz-whatsapp-gateway --no-pager
sudo journalctl -u telz-api -n 200 --no-pager
sudo journalctl -u telz-web -n 200 --no-pager
sudo journalctl -u telz-whatsapp-gateway -n 200 --no-pager
```

## WhatsApp Gateway

```bash
cd /opt/telz
sudo -u telz pnpm whatsapp-gateway:health
```

Se o runtime estiver ativo mas a sessao nao estiver online, conecte pelo QR Code no painel antes de validar envio real.

## Nginx

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
```

## Alembic

```bash
cd /opt/telz
source .venv/bin/activate
alembic -c backend/alembic.ini heads --verbose
alembic -c backend/alembic.ini current --verbose
```

## Retomar instalacao

```bash
sudo bash installer/install.sh --resume
```

## Ponto critico

Nao ative flags multi-tenant para resolver erro de instalacao. Primeiro corrija banco, env, build, Nginx ou systemd com as flags desligadas.

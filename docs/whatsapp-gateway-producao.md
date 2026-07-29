# WhatsApp Gateway Baileys em Producao

Este documento operacionaliza o runtime Baileys como servico de producao do projeto.
Ele nao substitui o backend FastAPI nem cria outro gateway: o runtime Node fica local na VPS,
e o backend continua sendo o contrato oficial usado pelo painel e pelo agente de atendimento.

## Escopo da Fase 6

- Rodar o runtime Baileys como servico systemd.
- Manter a porta do runtime apenas local em `127.0.0.1:3020`.
- Usar token entre backend e runtime/eventos.
- Permitir health check operacional com `pnpm whatsapp-gateway:health`.
- Reiniciar e validar o runtime no deploy quando o servico existir.

## Variaveis de ambiente

Configure em `/opt/telz/backend/.env`:

```env
WHATSAPP_GATEWAY_RUNTIME_URL=http://127.0.0.1:3020
WHATSAPP_GATEWAY_RUNTIME_TOKEN=troque-por-um-token-forte
WHATSAPP_GATEWAY_RUNTIME_TIMEOUT_SECONDS=8
WHATSAPP_GATEWAY_RUNTIME_DATA_DIR=/opt/telz/.runtime/baileys
WHATSAPP_GATEWAY_BACKEND_EVENT_URL=http://127.0.0.1:8000/api/whatsapp-gateway/runtime/events
WHATSAPP_GATEWAY_EVENT_TOKEN=troque-por-outro-token-forte
```

Os dois tokens podem ser iguais em ambiente controlado, mas em producao e melhor separar.
Nao exponha `3020` no Nginx.

## Servico systemd

Crie o arquivo `/etc/systemd/system/telz-whatsapp-gateway.service`:

```bash
sudo mkdir -p /opt/telz/.runtime/baileys
sudo chown -R telz:telz /opt/telz/.runtime
```

```ini
[Unit]
Description=Telz - WhatsApp Gateway Baileys Runtime
After=network.target telz-api.service
Wants=telz-api.service

[Service]
Type=simple
User=telz
Group=telz
WorkingDirectory=/opt/telz
Environment=NODE_ENV=production
Environment=WHATSAPP_GATEWAY_RUNTIME_HOST=127.0.0.1
Environment=WHATSAPP_GATEWAY_RUNTIME_PORT=3020
Environment=WHATSAPP_GATEWAY_RUNTIME_DATA_DIR=/opt/telz/.runtime/baileys
EnvironmentFile=/opt/telz/backend/.env
ExecStart=/usr/bin/node server/whatsapp-gateway-runtime.mjs
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=telz-whatsapp-gateway

[Install]
WantedBy=multi-user.target
```

Ative o servico:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telz-whatsapp-gateway
sudo systemctl start telz-whatsapp-gateway
```

## Validacao operacional

Depois do start:

```bash
sudo systemctl status telz-whatsapp-gateway --no-pager
sudo journalctl -u telz-whatsapp-gateway -n 80 --no-pager
pnpm whatsapp-gateway:health
```

O health check passa apenas quando o runtime responde `/health` e informa estado `online`.
Se a sessao ainda nao estiver conectada no WhatsApp, o servico pode estar de pe, mas o envio
operacional ainda depende da leitura do QR Code no painel.

## Fluxo esperado em producao

1. O deploy atualiza codigo e dependencias.
2. `telz-api` reinicia.
3. `telz-web` reinicia.
4. `telz-whatsapp-gateway` reinicia se o servico estiver instalado.
5. O backend passa no `/health`.
6. O runtime passa em `pnpm whatsapp-gateway:health`.
7. O painel confirma status, QR Code ou conexao ativa.

## Troubleshooting

Se o runtime nao subir:

```bash
sudo journalctl -u telz-whatsapp-gateway -n 120 --no-pager
```

Se o backend nao conseguir chamar o runtime:

```bash
grep WHATSAPP_GATEWAY_RUNTIME_URL /opt/telz/backend/.env
curl -sf http://127.0.0.1:3020/health
```

Se os eventos do WhatsApp nao chegarem ao agente:

```bash
grep WHATSAPP_GATEWAY_BACKEND_EVENT_URL /opt/telz/backend/.env
grep WHATSAPP_GATEWAY_EVENT_TOKEN /opt/telz/backend/.env
sudo journalctl -u telz-api -n 120 --no-pager
sudo journalctl -u telz-whatsapp-gateway -n 120 --no-pager
```

## Criterio de pronto

- Runtime instalado como servico systemd.
- Porta 3020 acessivel somente localmente.
- `pnpm whatsapp-gateway:health` executado com sucesso.
- Painel mostra conexao ativa ou QR Code valido.
- Envio e recebimento passam pelo provedor `baileys` sem fila paralela.

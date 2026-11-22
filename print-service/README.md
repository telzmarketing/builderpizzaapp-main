# Gran Torino Print Service

Agente Windows para impressão local do Gran Torino. A solução é independente do ERP e conversa exclusivamente pelos endpoints do contrato de impressão.

## Build local

Requer .NET SDK 8.x e Inno Setup 6 (`ISCC.exe`) para gerar o instalador:

```powershell
./scripts/build.ps1
```

O resultado fica em `artifacts/` (`GranTorino.PrintService.exe` e `GranTorinoPrintService-Setup.exe`). Sem SDK, use o workflow `print-service-build.yml` em um runner Windows.

## Configuração

Copie `appsettings.example.json` para `appsettings.json` e configure `ErpBaseUrl`, `PairingCode` e, se necessário, `StationId`. Variáveis de ambiente usam o prefixo `PrintService__`, por exemplo `PrintService__ErpBaseUrl`.

O serviço persiste o banco SQLite em `%ProgramData%\GranTorino\PrintService\print-service.db`, logs em `%ProgramData%\GranTorino\PrintService\logs` e arquivos temporários em `%ProgramData%\GranTorino\PrintService\spool`.

## Contrato usado

- `POST /api/print-agent/v1/pair`
- `GET /api/print-agent/v1/jobs/next`
- `POST /api/print-agent/v1/jobs/{id}/status`
- `POST /api/print-agent/v1/heartbeat`

O agente também envia `Idempotency-Key` nos eventos de status. O download do agente no ERP usa os endpoints administrativos definidos no pedido, mas não é embutido no binário.

# Production Vision: componentes locais

Este pacote fornece somente componentes locais e independentes para preparar
um futuro gateway. Ele não inicia captura física, não acessa RTSP/ONVIF, não
se conecta ao banco/API e não altera o KDS ou `kds_audit`.

## Componentes

Os arquivos em `scripts/production_vision/` oferecem:

- `FakeCaptureAdapter`: payload determinístico para testes. O resultado não é
  uma imagem e não comprova câmera, rede ou gateway físico.
- `validate_camera_url`: aceita apenas HTTP/HTTPS sem credenciais e rejeita
  destinos loopback, link-local, multicast, reservados, não especificados e,
  por padrão, privados. `allow_private=True` é reservado para um gateway
  controlado dentro da LAN.
- `process_image`: usa Pillow somente se disponível; redimensiona imagens
  válidas para largura máxima de 1280, preservando proporção. O original deve
  ser mantido pelo chamador. Não há IA, detecção ou recorte inteligente.
- `AdaptiveCaptureScheduler`: gera cinco amostras intermediárias e uma foto
  final obrigatória no encerramento. A duração informa a distribuição; não há
  relógio, thread, fila ou execução automática neste pacote.

## Limites e configuração

Não há variáveis de ambiente obrigatórias. O chamador deve fornecer a URL,
identidade da sessão e armazenamento. O pacote não guarda credenciais, não
faz retry de rede e não decide associação de foto a pedido/unidade.

Exemplo local:

```python
from scripts.production_vision import AdaptiveCaptureScheduler, FakeCaptureAdapter

adapter = FakeCaptureAdapter(namespace="test-run")
frame = adapter.capture("camera-1", sequence=1)
slots = AdaptiveCaptureScheduler().plan(duration_seconds=90)
```

## Segurança

Valide URLs antes de qualquer cliente HTTP futuro e mantenha credenciais fora
do frontend e dos logs. A validação DNS deve ser repetida no momento da
conexão no gateway real para reduzir risco de DNS rebinding. Este lote não
implementa essa conexão física.

## Homologação pendente

Ainda são necessários gateway autenticado, câmera IP, fila persistente,
observabilidade, retenção, storage privado e teste em rede/ambiente físico
antes de promover captura real como pronta.

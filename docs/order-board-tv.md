# Painel TV de motoboys

## Escopo

O Painel TV e uma superficie somente leitura em `/tv/motoboys` (`/tv`
permanece como alias). Ele mostra somente pedidos de entrega que possuem uma
`Delivery` em `assigned` vinculada a um `DeliveryPerson` valido do mesmo tenant.

- **Aguardando:** pedido em `preparing`.
- **Pronto para retirada:** pedido em `ready_for_pickup`.
- **Saida:** qualquer outro status de pedido ou qualquer status de entrega
  diferente de `assigned`.

Pedidos sem motoboy, retiradas no balcao, pedidos de salao, em rota, entregues,
falhos ou cancelados nao aparecem.

O painel nao reutiliza a autenticacao do administrador nem o PWA dos motoboys.
Ele recebe uma credencial propria em cookie `HttpOnly`, vinculada a um unico
estabelecimento. O snapshot nunca inclui cliente, telefone, endereco, itens,
observacoes, pagamento ou valores.

## Ativacao segura

1. Defina `ORDER_BOARD_ENABLED=true` no backend do ambiente piloto.
2. Aplique a migration `20260927_order_board_mvp`.
3. No painel administrativo, abra **Configuracoes > Paineis TV**, informe o
   nome e a logo da empresa, habilite o recurso para o estabelecimento e salve.
4. Abra `/tv/motoboys` no dispositivo. A TV exibira um codigo temporario.
5. Informe o codigo na administracao e autorize o dispositivo.

O codigo expira em dez minutos e admite no maximo cinco tentativas. Ele nao e a
credencial do dispositivo: a TV tambem possui uma sessao temporaria secreta, e a
credencial permanente e emitida uma unica vez depois da aprovacao. O banco
armazena somente hashes SHA-256 dos segredos aleatorios.

O nome e a logo exibidos sao lidos do perfil do estabelecimento autenticado.
Cada administrador altera somente a identidade visual do proprio tenant; nao
existe nome de restaurante fixo no painel. A logo e opcional e, quando ausente
ou indisponivel, o nome da empresa continua visivel.

## Operacao e revogacao

- A TV consulta um snapshot a cada cinco segundos por padrao, com intervalo
  configuravel entre 3 e 60 segundos.
- O polling usa ETag para evitar transferir snapshots sem alteracao.
- Falhas de rede preservam o ultimo snapshot, sinalizam reconexao e tentam
  sincronizar novamente sem exigir F5.
- Respostas de revogacao (`401`) ou desativacao (`403`) limpam imediatamente os
  pedidos da tela.
- A opcao **Revogar** invalida a credencial na proxima consulta. **Excluir**
  remove definitivamente o cadastro do dispositivo.

## Provedores de entrega

O modelo atual possui uma fonte canonica apenas para motoboy proprio, por meio
de `Delivery.delivery_person_id`. O contrato do snapshot usa `provider_key`,
`provider_label` e `driver_name`, permitindo provedores futuros, mas iFood, 99
Entrega e Uber Direct nao sao inventados enquanto nao houver uma integracao
persistida e tenant-isolada no sistema.

## Validacao de producao

Antes de liberar para operacao:

- execute a migration em PostgreSQL 15 real e confirme head unico;
- valide todo o pareamento em HTTPS, inclusive os atributos do cookie;
- teste isolamento entre dois estabelecimentos;
- teste revogacao, queda e retorno de rede;
- homologue visualmente em 1920x1080 e nas demais telas usadas pela operacao;
- mantenha `ORDER_BOARD_ENABLED=false` fora dos ambientes liberados.

O modo atual usa polling e nao depende de Redis, SSE ou WebSocket.

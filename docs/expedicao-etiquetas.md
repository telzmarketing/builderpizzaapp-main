# Expedição e etiquetas

## Fluxo operacional

O KDS da cozinha usa a máquina de estados existente. Ao concluir o preparo, o pedido passa para `ready_for_pickup`, deixa a tela da cozinha e aparece na Expedição. A tela usa o polling existente, sem criar um status duplicado. Pedidos de entrega permanecem nesse status durante a atribuição do motoboy; a saída para entrega continua sendo uma transição explícita. Pedidos de retirada são concluídos pela ação própria da Expedição.

Imprimir ou reimprimir uma etiqueta não altera o status do pedido.

## Estratégia de impressão

A primeira versão é browser-first: o sistema gera HTML/CSS com `@page` e medidas em milímetros, abre uma janela previamente autorizada pelo clique do operador e chama o diálogo de impressão do sistema operacional. Isso funciona com impressoras instaladas, compartilhadas ou de rede que estejam configuradas no computador.

Os campos de IP, porta, protocolo, densidade e velocidade são metadados de preparação e calibração. O navegador não enumera filas nem envia ZPL, EPL, TSPL ou ESC/POS diretamente. Impressão silenciosa exigiria um agente local confiável, como QZ Tray/PrintNode ou uma integração equivalente, e não faz parte desta entrega.

O registro `dialog_opened` confirma somente que o diálogo foi acionado; não afirma que o equipamento imprimiu fisicamente.

## Volumes e versões

- A ordem das etiquetas segue `order_items.position` e permanece determinística.
- Por padrão, cada unidade gera um volume; pizzas com vários sabores continuam sendo uma unidade.
- Bebidas ficam excluídas por padrão.
- Regra por produto prevalece sobre regra por categoria; `0` desativa a etiqueta e valores maiores representam volumes por unidade.
- Qualquer alteração relevante do pedido ou identidade do restaurante muda o fingerprint, invalida logicamente a versão anterior e cria uma nova versão completa.
- A chave de idempotência evita duplicidade por clique repetido.

## Configuração

1. Abra **Configurações > Impressoras e etiquetas**.
2. Cadastre a impressora lógica. Para esta entrega, escolha **Navegador**; os demais modos são metadados para integração futura.
3. Crie um modelo usando um atalho (100×50, 100×60, 80×40 ou 60×40 mm) ou informe um tamanho personalizado.
4. Defina tipo, orientação, margens, DPI, escala, cópias, fonte, offset e rotação. Selecione impressoras compatíveis ou deixe sem seleção para aceitar todas.
5. Salve a impressora e o modelo padrão nas preferências.
6. Use **Testar e calibrar**, confira a prévia e selecione a fila física no diálogo do sistema.

A prévia da tela é proporcional, mas driver, navegador, escala do sistema e margens mecânicas podem alterar o resultado físico. Desative cabeçalhos e rodapés no diálogo e use escala de 100% como ponto inicial.

## Impressão e histórico

1. Conclua o pedido no KDS da cozinha.
2. Na Expedição, confira e embale os volumes.
3. Clique em **Imprimir etiqueta**, revise volumes, impressora, modelo e cópias e confirme.
4. Para reimprimir, use o mesmo botão na Expedição ou no painel de Pedidos nas etapas Pronto, A caminho ou Entregue. Informe o motivo quando a preferência exigir.
5. Consulte o histórico no próprio modal.

As rotas exigem permissão `expedicao.view` para consulta e `expedicao.edit` para configuração, impressão e mudanças operacionais. Todas as consultas e gravações são filtradas pelo tenant autenticado.

## Limites de homologação

Os testes automatizados validam geração, isolamento, idempotência, versões, contrato e HTML de impressão. Antes da produção ainda é necessário executar a migration em PostgreSQL de homologação e calibrar fisicamente cada modelo de impressora/etiqueta usado pelo estabelecimento.

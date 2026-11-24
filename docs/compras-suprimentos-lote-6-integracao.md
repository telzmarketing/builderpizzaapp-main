# Compras e Suprimentos — Lote 6: Integração

O recebimento publicado usa a `InventoryFoundationService` como autoridade única de operação e movimento, preservando a transação do recebimento. Cada linha referencia explicitamente `InventoryPurchaseItem`; a quantidade acumulada é validada por linha.

Entradas em quarentena criam lote `quarantine` e não ficam elegíveis para reserva/consumo. O CMV usa somente entradas positivas em lotes disponíveis ou sem lote, mantendo snapshots históricos existentes imutáveis. O custo da entrada permanece registrado no movimento como evidência histórica.

A reconciliação financeira mantém-se separada da postagem física e agora usa claim idempotente por tenant/documento/chave, tratando conflito concorrente pela obrigação já persistida.

Validação local: compilação Python, 10 testes contratuais, typecheck e build do cliente. Não houve aplicação online da migration nem deploy.

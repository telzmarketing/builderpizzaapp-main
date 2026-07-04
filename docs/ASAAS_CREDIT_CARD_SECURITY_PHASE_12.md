# Fase 12 - Cartao ASAAS na tela propria com seguranca

Status: executada como fase de arquitetura, seguranca e criterios de aceite.
Escopo: preparar a implementacao de cartao ASAAS sem redirecionar o cliente para a ASAAS e sem armazenar dados sensiveis de cartao no sistema.

## 1. Objetivo

Permitir que o cliente pague com cartao de credito ASAAS permanecendo no checkout da loja.

Motivacao de negocio: reduzir rejeicoes de cartao no Mercado Pago, mantendo Mercado Pago como fallback e sem criar um segundo dominio de pagamentos.

## 2. Decisao arquitetural

O cartao ASAAS sera implementado dentro do dominio existente `payments`.

Fluxo aprovado:

1. Cliente escolhe cartao no checkout da loja.
2. Cliente preenche os dados de cartao na tela da loja.
3. Frontend envia os dados sensiveis somente na requisicao de pagamento.
4. Backend encaminha os dados imediatamente para ASAAS.
5. Backend nao persiste numero, CVV, validade completa ou payload bruto.
6. ASAAS autoriza ou recusa a transacao.
7. Backend salva somente metadados nao sensiveis do pagamento.
8. Webhook ASAAS confirma o status final quando aplicavel.

## 3. Fonte oficial ASAAS usada na decisao

Documentacao oficial consultada:

- Credit Card Charges: https://docs.asaas.com/docs/payments-via-credit-card.md
- Create new payment with credit card: https://docs.asaas.com/reference/create-new-payment-with-credit-card

Pontos confirmados:

- ASAAS aceita `billingType="CREDIT_CARD"`.
- ASAAS permite processamento imediato quando `creditCard` e `creditCardHolderInfo` sao enviados na criacao da cobranca.
- `remoteIp` deve ser o IP real do comprador, nao o IP do servidor.
- HTTPS/SSL e obrigatorio quando o sistema captura dados de cartao na propria interface.
- ASAAS recomenda timeout minimo de 60 segundos para reduzir timeout e tentativa duplicada de captura.
- Se a transacao for autorizada, a API retorna sucesso; se nao for autorizada, pode retornar erro e a cobranca pode nao ser persistida.

## 4. Dados proibidos

Nunca salvar em banco, logs, analytics, storage local, storage de sessao, cookies, eventos internos ou mensagens de erro:

- numero completo do cartao;
- CVV/CCV;
- mes e ano de validade em conjunto;
- nome do titular associado ao numero em payload bruto;
- objeto `creditCard`;
- objeto `creditCardHolderInfo`;
- payload bruto da requisicao de pagamento;
- resposta bruta da ASAAS se ela contiver dados sensiveis.

## 5. Dados permitidos

Por decisao desta fase, o sistema pode persistir apenas:

- provider: `asaas`;
- id da cobranca ASAAS;
- status normalizado;
- status bruto do provider;
- valor;
- parcelas;
- bandeira do cartao quando retornada pela ASAAS;
- identificador visual da bandeira para renderizar logo;
- timestamps de criacao, confirmacao, cancelamento ou estorno.

Regra desta fase: nao salvar ultimos 4 digitos do cartao. Se houver necessidade futura, isso deve ser uma decisao explicita e documentada.

## 6. Mensagem obrigatoria ao cliente

O checkout deve informar de forma curta, perto dos campos de cartao:

> Nao armazenamos os dados do seu cartao. Eles sao usados apenas para processar esta compra com seguranca.

Essa mensagem deve aparecer antes do envio do pagamento e sem criar medo desnecessario.

## 7. Carteira Pay e preenchimento do celular

O checkout pode usar atributos HTML de autocomplete para permitir preenchimento seguro pelo navegador/celular:

- `autocomplete="cc-name"`
- `autocomplete="cc-number"`
- `autocomplete="cc-exp-month"`
- `autocomplete="cc-exp-year"`
- `autocomplete="cc-csc"`

Isso permite que o cliente use cartoes salvos no aparelho/navegador sem que a loja salve o cartao.

Fora do escopo desta fase: botao nativo Apple Pay/Google Pay. Esse recurso depende de suporte oficial ASAAS/conta/navegador e deve ser tratado como uma etapa separada se for confirmado.

## 8. Regras de backend

- Rota recebe payload validado por schema especifico de cartao ASAAS.
- Service monta payload ASAAS e chama `AsaasGateway`.
- Nenhum `print`, `logger`, excecao ou auditoria pode receber payload sensivel.
- Erros retornados ao cliente devem ser genericos e orientativos.
- Logs tecnicos devem registrar somente order id, payment id, provider, status e codigo de erro sanitizado.
- Timeout da chamada ASAAS deve ser de pelo menos 60 segundos.
- `remoteIp` deve vir do IP real do cliente considerando proxy confiavel.
- Idempotencia deve impedir dupla captura para o mesmo pedido.
- Apos resposta ou erro, dados sensiveis devem sair do estado de frontend.

## 9. Regras de frontend

- Nao usar estado global para dados de cartao.
- Nao persistir cartao em localStorage, sessionStorage, cookies ou cache.
- Nao emitir console.log de formulario ou resposta completa.
- Limpar campos sensiveis apos sucesso, erro definitivo ou troca de metodo de pagamento.
- Exibir loading claro durante a chamada ASAAS, pois o timeout recomendado e maior.
- Proteger duplo clique e reenvio manual.
- Exibir somente bandeira/logo do cartao como metadado visual.

## 10. Admin e fallback

O painel de pagamentos deve permitir:

- escolher ASAAS como provider de cartao;
- manter Mercado Pago como fallback;
- bloquear ASAAS cartao se `ASAAS_API_KEY` nao estiver configurada;
- mostrar aviso de seguranca quando ASAAS cartao estiver ativo;
- desativar ASAAS cartao rapidamente em caso de incidente.

## 11. Webhook e pos-pagamento

O webhook ASAAS ja existe no dominio `payments` e deve continuar sendo usado.

Para cartao:

- `PAYMENT_CONFIRMED` ou status equivalente confirma pagamento;
- `PAYMENT_CREDIT_CARD_CAPTURE_REFUSED` deve manter pedido sem confirmacao e exibir falha de pagamento;
- duplicidade de webhook nao pode duplicar financeiro, estoque, WhatsApp ou BI;
- conciliacao administrativa deve usar `payments.provider`, nao a configuracao atual.

## 12. Criterios de aceite da implementacao futura

A fase de implementacao so pode ser considerada pronta quando:

- checkout processar cartao ASAAS sem redirecionar para ASAAS;
- nenhum dado sensivel aparecer em banco;
- nenhum dado sensivel aparecer em log;
- cliente visualizar a mensagem de nao armazenamento;
- autocomplete de cartao estiver configurado;
- ASAAS aprovar pagamento em sandbox;
- ASAAS recusar pagamento em sandbox com mensagem amigavel;
- duplo clique nao gerar dupla cobranca;
- timeout nao gerar dupla captura;
- webhook confirmar status sem duplicar eventos internos;
- admin permitir alternar cartao entre Mercado Pago e ASAAS;
- Mercado Pago permanecer funcional como fallback.

## 13. Proximas fases

### Fase 13 - Backend ASAAS cartao

- Criar schemas sensiveis com serializacao/logging protegidos.
- Implementar criacao `CREDIT_CARD` em `AsaasGateway`.
- Implementar idempotencia para tentativa de cartao por pedido.
- Persistir somente metadados permitidos.

Status: executada em 2026-07-03.

### Fase 14 - Checkout ASAAS cartao

- Adaptar formulario para provider ASAAS.
- Adicionar autocomplete de cartao/celular.
- Exibir mensagem de nao armazenamento.
- Limpar estado sensivel apos envio.

Status: executada em 2026-07-04.

### Fase 15 - Admin, validacao e deploy

- Permitir ASAAS como provider de cartao.
- Preservar Mercado Pago Payment Brick quando Mercado Pago for o provider de cartao.
- Registrar no painel que dados de cartao nao ficam salvos no sistema.
- Validar diff, typecheck, testes e build local.
- Preparar Alembic/deploy para ambiente Python/VPS.

Status: admin e validacao local executados em 2026-07-04. Deploy real, migration em VPS e teste de webhook real seguem como etapa operacional.

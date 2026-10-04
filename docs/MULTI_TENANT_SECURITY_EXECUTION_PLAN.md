# Plano de execucao do isolamento multiempresa

## Objetivo

Permitir a operacao simultanea de varias empresas sem compartilhamento acidental
de dados, arquivos, credenciais ou processamento. A autoridade do tenant deve vir
sempre de uma fonte confiavel:

- painel: JWT selecionado e membership ativa;
- loja publica: dominio ativo resolvido no servidor;
- webhook: chave opaca vinculada a tenant e provider;
- job ou outbox: metadata persistida com `tenant_id`;
- plataforma: permissao explicita de operador da plataforma.

`tenant_id` recebido em body, query string ou header livre nunca e autoridade.

## Regra de liberacao

Um segundo tenant real nao deve ser liberado enquanto qualquer gate P0 estiver
pendente. Colunas e migrations nao provam isolamento: cada leitura, escrita,
busca por ID e relacao pai/filho precisa aplicar ownership no runtime e possuir
teste A/B.

## Sequencia de entrega

### P0.1 - inventario e contencao

- inventariar rotas, services, SQL textual, jobs, caches e arquivos;
- manter flags inseguras desligadas;
- bloquear ativacao indiscriminada no instalador;
- confirmar um unico head Alembic e preparar preflight do PostgreSQL real;
- registrar os testes A/B obrigatorios por dominio.

### P0.2 - contexto e autorizacao

- painel resolve tenant somente por JWT e membership ativa;
- loja resolve tenant somente por dominio ativo;
- IDs de outro tenant retornam 404;
- ausencia ou ambiguidade de contexto falha fechada;
- plataforma e suporte permanecem separados do RBAC operacional.

### P0.3 - nucleo comercial

- catalogo, promocoes, campanhas, cupons, tema e home;
- clientes, identidades, enderecos e LGPD;
- pedidos, itens, pagamentos e webhooks;
- testes A/B de list/get/create/update/delete e associacoes cruzadas.

### P0.4 - operacao e comunicacao

- frete, salao, loja, cozinha, expedicao e entrega;
- marketing, CRM, chatbot, e-mail, WhatsApp, BI e trafego;
- eventos e integracoes cruzadas preservam o tenant de origem.

### P0.5 - backoffice e execucao assincrona

- estoque, receitas, CMV, financeiro e fiscal;
- jobs, filas, outbox, caches e tarefas de IA exigem tenant persistido;
- uploads usam namespace e autorizacao por tenant;
- nenhum worker assume `tenant-legacy-default` em runtime.

### P0.6 - contratos e matriz A/B

- zero `tenant_id` nulo, `default`, orfao ou de tenant removido;
- zero relacao pai/filho entre tenants;
- constraints e uniques compostos validados no PostgreSQL;
- tenant A nunca lista, le, altera ou remove recurso do tenant B;
- fluxos do tenant legado permanecem funcionais apos a migracao.

### P0.7 - ativacao controlada

- backup restaurado em homologacao;
- ativacao de uma wave por vez;
- smoke, matriz A/B, logs e metricas apos cada ativacao;
- rollback documentado antes do canario;
- producao somente e declarada multiempresa segura apos evidencia real.

## Matriz minima de aceite

Para cada dominio liberado, testar com tenants A e B:

1. listagem retorna somente registros proprios;
2. ID conhecido do outro tenant retorna 404;
3. criacao ignora/rejeita tenant forjado e grava o tenant autorizado;
4. update e delete nao atravessam ownership;
5. relacoes aceitam apenas pais do mesmo tenant;
6. agregacoes, contagens e relatorios permanecem tenant-scoped;
7. job, webhook ou retry sem contexto confiavel falha sem mutacao;
8. logs e auditoria registram tenant e ator sem expor segredos.

## Estado desta execucao

- P0.1: inventario executado e head operacional atualizado para
  `20261003_agente_whatsapp_tenant_foundation`;
- P0.2: contexto confiavel e fail-closed aplicados ao nucleo comercial e as
  ferramentas do Agente WhatsApp;
- P0.3: catalogo, campanhas, promocoes, cupons, clientes, pedidos e pagamentos
  tenantizados; defaults de instalacao dessas duas waves agora sao `true`;
- P0.4: CRM/IA em massa recebeu tenant persistido; operacoes de entrega ainda
  permanecem com a flag desligada ate todas as rotas fornecerem contexto;
- P0.5: jobs gerais e uploads continuam bloqueando a liberacao completa;
- P0.6: migration remove unicidades globais comerciais, preservando por
  seguranca as de pagamentos ate os webhooks tenantizados serem ativados;
- P0.7: suite local passou com as duas waves comerciais ligadas; homologacao
  A/B em PostgreSQL real, deploy e smoke da VPS ainda sao obrigatorios.

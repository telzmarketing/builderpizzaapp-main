# HTTPS dos dominios das empresas

Data: 2026-10-14.

Status: arquitetura HTTP-01 aprovada; implementacao validada localmente. Este documento nao comprova emissao,
instalacao, renovacao ou deploy em producao.

## Objetivo e fluxo

Permitir ao administrador Master preparar HTTPS depois de cadastrar um dominio
de empresa, acompanhando verificacao, emissao e validade no cadastro existente.
Nao criar um segundo cadastro ou uma gestao paralela de dominios.

O fluxo usa a aba Dominios da empresa e a lista global de dominios:

1. Cadastrar hostname e tipo, como ocorre atualmente.
2. Exibir a prova TXT existente e as instrucoes de apontamento DNS.
3. Validar propriedade e apontamento publico no servidor.
4. Solicitar HTTPS, informando email de contato e aceite dos termos aplicaveis.
5. Acompanhar emissao e instalacao.
6. Confirmar o certificado realmente servido para o hostname.
7. Permitir publicacao do novo dominio e acompanhar renovacao.

## Regras de negocio

- A operacao e exclusiva do Master com permissao de gestao de dominios.
- O hostname vem do registro cadastrado e aparece como leitura no formulario.
  A solicitacao usa o identificador desse registro, sem aceitar um hostname livre.
- Os dados solicitados sao email de contato e aceite dos termos aplicaveis da
  autoridade certificadora. O email da plataforma pode ser sugerido.
- Nao coletar senha da VPS, credenciais DNS, chave privada ou comandos no painel.
- A prova TXT ja existente e o apontamento publico correto sao obrigatorios.
  O servidor faz as verificacoes; um booleano enviado pelo navegador nao basta.
- Considerar os registros A e AAAA publicados e o destino de CNAME quando houver.
  Um endereco publicado incorreto nao pode ser ignorado para aprovar o dominio.
- DNS verificado, certificado emitido e HTTPS servido sao evidencias diferentes.
- Novos dominios so podem ser publicados depois da verificacao DNS e TLS.
- Pedidos repetidos durante uma emissao nao iniciam operacoes concorrentes.
  Certificado existente valido pode ser reutilizado apos comprovacao de cobertura.
- Falha preserva cadastro e diagnostico, sem marcar HTTPS ativo. A nova tentativa
  deve ser controlada e ocorrer depois de corrigir a causa.
- A validade e os erros de renovacao devem ficar visiveis ao Master.
- Dominios ativos existentes exigem transicao deliberada: nao suspender todas as
  lojas automaticamente ao implantar uma exigencia nova. Exibir pendencia TLS e
  permitir sua regularizacao, conforme estrategia aprovada pelo Arquiteto.

## Estados apresentados

O estado de dominio e o estado de HTTPS devem continuar distinguiveis. As telas
devem comunicar, conforme a etapa: aguardando DNS, verificando DNS, pronto para
solicitar HTTPS, emissao em andamento, HTTPS ativo e erro recuperavel. Exibir
validade e resultado da ultima verificacao quando disponiveis.

Os nomes persistidos, as transicoes e os contratos aditivos de API ficam sujeitos
a definicao arquitetural. Nao inferir HTTPS ativo apenas de dominio ativo.

## Arquitetura HTTP-01 proposta

Esta secao registra uma proposta, nao autorizacao para executar comandos na VPS.

- Preservar a API FastAPI e os services atuais para cadastro, autorizacao,
  validacoes e acompanhamento; preservar o caminho frontend por client/lib/api.ts.
- Acrescentar operacao especifica de solicitacao de HTTPS ao dominio existente,
  sem executar Certbot ou comandos privilegiados dentro de uma requisicao web.
- Delegar a emissao ACME HTTP-01 e a configuracao TLS a um executor operacional
  restrito, com parametros validados, isolamento de privilegios e auditoria.
- Publicar desafios HTTP-01 pelo Nginx em porta 80 para os hostnames elegiveis,
  sem depender da API autenticada ou do certificado TLS que sera criado.
- Emitir para um hostname verificado por vez, instalar o certificado correspondente
  e validar a configuracao Nginx antes de recarregar o servico.
- Confirmar por conexao TLS com hostname/SNI o certificado servido, cadeia,
  validade e correspondencia do nome antes de registrar HTTPS ativo.
- Configurar renovacao automatica e recarga validada do proxy; atualizar o estado
  apresentado no painel e registrar falhas de renovacao.

HTTP-01 nao emite wildcard. Um wildcard existente pode cobrir subdominios se sua
cobertura e o certificado servido forem comprovados; emissao wildcard via DNS-01
e integracao de credenciais de provedor DNS ficam fora desta entrega.

## Dependencias operacionais

- Definir email oficial e termos da autoridade certificadora.
- Configurar os destinos DNS/IP autorizados da plataforma.
- DNS publico precisa apontar para a infraestrutura responsavel pela emissao.
- Porta 80 publica e rota de desafio precisam ser alcancaveis pelo emissor ACME.
- Nginx, emissor ACME, executor restrito, armazenamento privado de chaves,
  agendamento de renovacao e auditoria precisam estar preparados na VPS.
- Regras CAA, proxies externos e registros IPv6 devem ser avaliados quando
  interferirem na validacao. A verificacao inicial nao garante emissao futura.

## Criterios de aceite

1. Depois do cadastro, o Master ve o proximo passo DNS/HTTPS sem recadastrar o
   endereco; a lista global e o detalhe da empresa mostram o mesmo estado.
2. Sem TXT correto ou apontamento autorizado, o servidor recusa a emissao mesmo
   se a interface for alterada pelo cliente.
3. Usuario sem permissao nao solicita emissao; dominio de outra empresa ou
   hostname arbitrario nao pode ser substituido no pedido.
4. Email invalido e ausencia de aceite sao recusados conforme o contrato.
5. Durante a emissao, a interface informa andamento e pedidos duplicados nao
   geram concorrencia ou novas emissoes desnecessarias.
6. Falha apresenta diagnostico seguro e permite correcao/repeticao controlada;
   nenhuma falha pode produzir estado HTTPS ativo.
7. Certificado vencido, para outro nome ou com cadeia invalida nao aprova HTTPS.
8. Novo dominio so e ativavel apos verificacao DNS e TLS reais.
9. Renovacao atualiza validade e estado; falha fica visivel ao Master.
10. Emissao, instalacao e recarga de uma loja preservam o funcionamento das outras.

## Gates de validacao e entrega

Validacao local registrada em 2026-10-14: suite integrada com 495 testes aprovados,
8 ignorados e 3 avisos; testes de contrato frontend com 12 aprovados; typecheck e
build client/PWA aprovados. YAML dos workflows e sintaxe dos 25 scripts Bash
validados; SQL da nova revision renderizado com dialeto PostgreSQL sem conexao
ao banco. Testes locais de DNS/TLS/ACME usam dependencias controladas. Nao houve
emissao, renovacao, migration PostgreSQL real ou deploy desta funcionalidade.
Publicacao Git e CI devem ser conferidos no commit exato da entrega.

Validacao local deve cobrir autorizacao, isolamento entre empresas, validacao de
entrada, pre-requisitos DNS, transicoes, duplicacao, falhas operacionais e estados
da interface. Mocks e testes locais nao comprovam HTTPS operacional na VPS.

Antes de declarar entrega operacional, registrar evidencia em ambiente real de:

- desafio ACME acessivel e emissao em ambiente de teste do emissor;
- configuracao Nginx valida e certificado correto servido externamente;
- consulta e ativacao do dominio preservando o tenant correto;
- renovacao de teste e recarga bem-sucedidas;
- falha recuperavel sem afetar os demais dominios;
- emissao de producao e certificado publico valido para o dominio solicitado.

Commit, push, CI e deploy sao etapas distintas. Este documento nao afirma que
qualquer uma delas ocorreu nem resolve por si so o certificado atual da loja.

## Fora do escopo

Compra de dominios; alteracao automatica de DNS em provedores variados; coleta de
credenciais DNS ou senhas no painel; emissao wildcard pelo formulario da empresa;
acesso operacional da empresa a VPS; reescrita do cadastro ou resolucao de tenant.

## Preparacao operacional unica

Esta secao e um runbook de preparacao, nao evidencia de execucao. Use somente a
release imutavel publicada e aprovada no CI. A revision alvo passa a ser
`20261014_tenant_domain_ssl`. Nao ha par de rollback automatico aprovado para a
nova revision: preparar backup/restore e cutover forward-only explicito pelo
procedimento incremental, sem executar o instalador novamente.

O instalador/updater entrega o runner, o hook e as unidades root-owned, mas nao
habilita a emissao. Antes de configurar, confira DNS publico, porta 80 acessivel,
Nginx, Certbot e o backup externo de `/etc/letsencrypt`, dos vhosts de dominio e
de `/etc/telz/domain-ssl.json`. A chave privada nunca pertence ao banco ou API.

Como root, apos instalar Certbot pelo gerenciador de pacotes da VPS, configure
uma vez o runner. Substitua todos os placeholders antes de executar:

```bash
sudo /usr/local/sbin/telz-domain-ssl --configure <<'JSON'
{"public_ips":["SUBSTITUIR_PELO_IP_PUBLICO"],"service_user":"telz","install_dir":"/opt/telz","api_port":8000,"web_port":3000}
JSON
```

Inclua tambem o IPv6 autorizado se houver registros AAAA publicados. O comando
valida a estrutura e grava configuracao root-owned `0600`; nao habilita servicos
nem altera `backend/.env`. Preserve os hosts reservados da plataforma em
`TENANT_DOMAINS_PLATFORM_HOSTNAMES`. No arquivo persistente `backend/.env`,
configure os mesmos IPs publicos autorizados, separados por virgula:

```dotenv
TENANT_DOMAIN_SSL_ENABLED=true
TENANT_DOMAIN_SSL_PUBLIC_IPS=SUBSTITUIR_PELOS_IPS_PUBLICOS
```

Depois da revisao da configuracao, habilite `certbot.timer` e
`telz-domain-ssl.timer`, execute `telz-domain-ssl.service` e reinicie a API para
carregar as configuracoes. Confira heartbeat recente e disponibilidade no
painel antes de solicitar emissao. Configuracao inconsistente ou worker ausente
mantem a solicitacao indisponivel.

A emissao usa webroot HTTP-01 e preserva o challenge ao redirecionar HTTP para
HTTPS. A renovacao e feita pelo Certbot; o hook valida/recarrega Nginx sob o lock
de manutencao, e o worker reconcilia o certificado servido e as datas. Referencia:
[guia oficial do Certbot](https://eff-certbot.readthedocs.io/en/stable/using.html).

Valide `certbot renew --dry-run --run-deploy-hooks` e o acesso HTTPS externo em
janela controlada. Uma falha deve ser investigada antes de habilitar novos
dominios. Restaurar vhost nao reverte a lineage do Certbot: os certificados
anteriores permanecem em `archive`, e recuperacao de material criptografico deve
seguir o backup especifico de certificados.

# HTTPS dos dominios das empresas

Data: 2026-10-15.

Status: arquitetura HTTP-01 aprovada; implementacao validada localmente. Este documento nao comprova emissao,
instalacao, renovacao ou deploy em producao.

## Objetivo e fluxo

Permitir a propria empresa e ao administrador Master solicitar HTTPS depois de cadastrar um dominio
de empresa, acompanhando verificacao, emissao e validade no cadastro existente.
Nao criar um segundo cadastro ou uma gestao paralela de dominios.

O fluxo usa Configuracoes > Dominio e HTTPS no painel da empresa e as telas de dominios da Central Master:

1. Cadastrar hostname e tipo, como ocorre atualmente.
2. Exibir a prova TXT existente e as instrucoes de apontamento DNS.
3. Validar propriedade e apontamento publico no servidor.
4. Solicitar HTTPS, informando email de contato e aceite dos termos aplicaveis.
5. Acompanhar emissao e instalacao.
6. Confirmar o certificado realmente servido para o hostname.
7. Permitir publicacao do novo dominio e acompanhar renovacao.

## Regras de negocio

- A empresa precisa de membership PANEL ativa e permissao configuracoes.view/edit.
  O Master conserva tenants.view/manage. A API sempre limita a empresa ao seu
  tenant autenticado; suporte e contextos legados nao acessam este autoatendimento.
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
- A validade e os erros de renovacao devem ficar visiveis a empresa e ao Master.
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

1. Depois do cadastro, a empresa e o Master veem o proximo passo DNS/HTTPS sem recadastrar o
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
9. Renovacao atualiza validade e estado; falha fica visivel a empresa e ao Master.
10. Emissao, instalacao e recarga de uma loja preservam o funcionamento das outras.

## Gates de validacao e entrega

Validacao local da correcao automatica em 2026-10-15: suite integrada com 536
aprovados e 8 ignorados; testes frontend de API e telas Master com 17 aprovados;
typecheck e build client/PWA aprovados. Promocao inicial: 15 testes novos
aprovados; regressao operacional focada: 45 aprovados e 8 ignorados. DNS/TLS/ACME usam dependencias controladas.
A release anterior e47c793 ja foi atualizada na VPS pelo operador, mas nao preparava
a emissao automaticamente. Esta correcao exige sua propria publicacao e deploy.

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

## Preparacao automatica na atualizacao

O updater instala os executaveis e unidades root-owned, ativa a release imutavel,
valida a aplicacao e executa o bootstrap do emissor sob o lock de manutencao.
O bootstrap conserva IPs explicitamente aprovados existentes; caso contrario,
descobre enderecos publicos globais das interfaces locais da VPS. Valida a release,
prepara Certbot, testa Nginx, habilita os timers de emissao e renovacao e grava um
heartbeat. Somente depois publica disponibilidade para a API.

O modo padrao `TENANT_DOMAIN_SSL_MODE=auto` usa a projecao sanitizada root-owned
`/var/lib/telz/domain-ssl/runtime.json`. Nao exige editar `.env`, ativar flags ou
habilitar timers manualmente para cada empresa. A API nao executa sudo nem le
chaves privadas. `manual` preserva o fluxo legado; `disabled` bloqueia solicitacoes.

Na instalacao inicial padrao de producao (`app.telz.com.br`, HTTPS e Alembic
habilitados), o instalador promove o checkout validado pelo pipeline existente
para uma release realmente imutavel e executa a mesma preparacao. Perfis HTTP-first
ou outros hosts principais permanecem instalacoes base, com aviso explicito de
promocao pendente; nao recebem disponibilidade artificial.

Se a VPS estiver atras de NAT/balanceador e nao possuir endereco publico local,
a preparacao fica indisponivel com diagnostico. Nesse caso excepcional, a operacao
aprova os destinos em `/etc/telz/domain-ssl.json` pelo comando `--configure`
existente e repete a atualizacao/bootstrap. Nao usar IPs obtidos de DNS de um
dominio de empresa como autorizacao de destino. A configuracao operacional e
root-owned `0600` e preservada nas atualizacoes; a projecao nao contem segredos.

Depois de atualizar, a empresa cadastra o hostname no painel, publica o TXT e os
registros DNS mostrados, verifica a propriedade e solicita HTTPS com email e aceite
dos termos. O worker emite, instala o vhost, testa/recarrega Nginx e comprova o
certificado servido antes de marcar HTTPS ativo. O mesmo fluxo existe no Master.

A recarga do Nginx nao comprova que os novos workers ja servem TLS. O executor
aguarda prontidao por ate 45 segundos totais, repetindo a verificacao de todos os
IPs com cadeia e hostname validos. A lease e o DNS continuam validados antes e
depois dessa etapa; falha persistente preserva o rollback e nao ativa HTTPS.

Nao ha comando de VPS por dominio. DNS externo continua sob controle do titular.

A emissao usa webroot HTTP-01 e preserva o challenge ao redirecionar HTTP para
HTTPS. A renovacao e feita pelo Certbot; o hook valida/recarrega Nginx sob o lock
de manutencao, e o worker reconcilia o certificado servido e as datas.

Validacao operacional ainda exige emissao real, certificado correto servido e
`certbot renew --dry-run --run-deploy-hooks` em janela controlada. Testes locais
nao comprovam essas etapas. Falha de bootstrap mantem a aplicacao saudavel e
mostra indisponibilidade; nao declara o emissor pronto. Restaurar vhost nao
reverte a lineage Certbot: material criptografico segue o backup de certificados.

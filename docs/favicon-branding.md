# Favicon do gestor e das empresas

O host `app.telz.com.br` e os hosts reservados em
`TENANT_DOMAINS_PLATFORM_HOSTNAMES` usam a marca do gestor, independentemente da
empresa selecionada. O padrao do favicon e `public/icons/telz.svg`.

## Marca do gestor

Em Configuracoes da plataforma > Marca do gestor, operadores com a permissao
`platform_settings.manage` podem enviar, visualizar, remover e salvar o logo e
o favicon. O logo aparece no login e na navegacao da plataforma. Remover uma
imagem e salvar restaura o respectivo padrao Telz. Permissao somente de consulta
nao permite alterar a marca.

As imagens aceitas sao PNG, JPEG e WebP, ate 5 MB. O backend valida e converte
as imagens para PNG com nomes unicos. Os arquivos ficam em
`uploads/platform-branding`, incluidos no backup e na preservacao de uploads;
sao servidos pela rota publica dedicada `/api/platform/branding/assets/`, sem
alterar as regras de acesso aos uploads das empresas.

As duas URLs sao persistidas exclusivamente em `site_config.id =
'platform:branding'`. Os endpoints administrativos sao GET/PUT
`/api/admin/platform/settings/branding` e POST
`/api/admin/platform/settings/branding/upload`. A consulta operacional existente
de configuracoes continua somente leitura. Nao ha alteracao de schema.

## Marca das empresas

Cada empresa configura seu favicon no painel de Conteudo, em Marca e Midia.
Com a resolucao multitenant ativa, a API le e grava o conteudo na chave
`tenant:{tenant_id}:site-content` da tabela `site_config` existente. O dominio
publico determina a leitura; o token com membership valido determina a escrita.
Uma escrita com empresa diferente daquela do dominio e rejeitada.

Empresas sem favicon usam um icone neutro. O conteudo global anterior e mantido
para compatibilidade somente no modo legado e como fallback de leitura da
empresa explicitamente marcada `is_legacy`. Nenhum conteudo existente e apagado
ou copiado automaticamente para outras empresas. Nao ha alteracao de schema.

Os endpoints `/api/site-config`, `/api/site-config/favicon` e
`/api/site-config/manifest.webmanifest` preservam suas URLs. A consulta de
favicon nao utiliza o cache de imagens do service worker. O servidor web tambem
redireciona `/favicon.ico` para o resolvedor de favicon.

Para publicar, atualizar backend e frontend juntos. Para configurar empresas
por dominio, manter resolucao de dominios e autenticacao multitenant habilitadas,
dominios ativos cadastrados e o proxy encaminhando o Host original.
Depois da publicacao, verificar gestor e duas empresas em abas separadas,
incluindo login, favicon personalizado e empresa sem favicon. Build e testes
locais nao substituem essa verificacao HTTPS nem a validacao em PostgreSQL.

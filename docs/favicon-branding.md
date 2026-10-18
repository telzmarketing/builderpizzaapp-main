# Favicon do gestor e das empresas

O host `app.telz.com.br` e os hosts reservados em
`TENANT_DOMAINS_PLATFORM_HOSTNAMES` usam o icone Telz de
`public/icons/telz.svg`, independentemente da empresa selecionada.

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

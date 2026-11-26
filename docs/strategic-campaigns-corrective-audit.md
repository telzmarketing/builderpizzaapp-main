# Campanhas Estratégicas — Auditoria corretiva obrigatória

Data: 2026-11-25

## Veredito

O submódulo publicado não atende ao produto comercial solicitado. A entrega atual
é uma fundação técnica parcial: há modelos, migrations, APIs básicas, landing
pública simples, contexto de oferta no checkout, bloqueio operacional de pedidos
futuros e métricas iniciais. A interface administrativa, porém, não permite
executar o fluxo principal sem chamadas manuais de API.

O módulo não pode ser considerado concluído, nem como construtor profissional de
landing pages, nem como gerenciamento comercial completo de campanhas.

## Evidências do estado atual

- `client/pages/admin/StrategicCampaigns.tsx` concentra criação, lista, editor,
  preview, ofertas e métricas em 118 linhas e mantém o formulário de criação na
  coluna lateral.
- A mesma tela informa: `Adicione ofertas pela API de ofertas estratégicas antes
  de publicar.` Não existe cadastro administrativo de ofertas.
- `client/pages/StrategicCampaignLandingV2.tsx` possui 86 linhas e implementa uma
  landing fixa, com apenas três cores, textos, uma imagem, um vídeo e cards
  básicos.
- `backend/routes/strategic_campaigns.py` expõe CRUD parcial, criação/edição de
  ofertas, publicação e métricas, mas não expõe duplicação, remoção histórica,
  reordenação atômica, despublicação, restauração, reservas ou capacidade.
- `backend/models/strategic_campaign.py` possui somente campanha, oferta e versão.
  Não existem entidades próprias para reservas, capacidade, slots, mídias,
  auditoria ou configurações estruturadas do builder.
- `backend/services/strategic_campaign_service.py` preserva tenant, valida slug,
  estados, período, produto/kit e publicação, mas bloqueia edição após publicação
  e não oferece ciclo completo de rascunho publicado/restauração.
- `backend/services/order_service.py` valida a oferta e preserva o vínculo no
  pedido. O preço estratégico ainda precisa coincidir com o quote canônico; não
  existe um contrato completo de composição promocional configurável.
- O frontend envia oferta simples de produto diretamente ao carrinho com tamanho
  fixo `M` e sem abrir o configurador canônico. Isso é incorreto para pizzas com
  tamanho, sabores, bordas e adicionais.
- A infraestrutura existente `MediaUpload`, `ImageUpload`, `/admin/upload` e
  armazenamento tenantizado é reutilizável, mas não está integrada ao módulo.
- Os testes atuais cobrem contratos isolados. Não existe E2E administrativo com
  cinco ofertas, upload, builder, publicação, compra, pagamento e operação.

## Matriz comparativa

| Requisito | Situação atual | Evidência e correção obrigatória |
|---|---|---|
| Página geral com KPIs, pesquisa, filtros, período e ações | Implementado incorretamente | Há lista simples e formulário lateral. Substituir por página de gestão com tabela/cards responsivos, filtros e ação `Nova campanha`. |
| Cadastro de campanha por modal/página | Implementado parcialmente | Só nome e slug são realmente coletados na tela. Criar fluxo completo e redirecionar ao detalhe. |
| Página individual por campanha | Não implementado | Não há rota administrativa por ID nem layout próprio. Criar detalhe com nove abas. |
| Visão geral | Não implementado | Métricas estão comprimidas na lateral da tela única. Criar overview responsivo. |
| Configurações gerais completas | Implementado parcialmente | Backend guarda nome, slug, descrição e período; metas, categoria, objetivo e vários limites não existem na UI/modelo. |
| Ações publicar, pausar, reativar, encerrar e arquivar | Implementado parcialmente | Estado existe no backend, mas a UI só publica. Expor ações com confirmação e regras server-side. |
| Duplicação sem copiar resultados | Não implementado | Não há endpoint, service ou ação de interface. Implementar cópia transacional de configuração e ofertas. |
| Exclusão condicionada ao histórico | Não implementado | Não há contrato. Preferir arquivamento; exclusão apenas sem dependências. |
| Gerenciamento administrativo de ofertas | Implementado somente no backend | API cria/edita; UI instrui usar API. Criar aba e modal/drawer completos. |
| Seleção de produto, promoção e combo canônicos | Implementado parcialmente | Backend aceita produto ou kit; promoção e composição avançada não estão modeladas. Reutilizar catálogo, promoções e kits existentes. |
| Configuração de sabores, tamanhos, divisão, bordas, adicionais e bebidas | Não implementado | `config` genérico não constitui contrato. Criar schema validado e usar quote/configurador canônico. |
| Quantidade, disponibilidade e limite por cliente | Implementado parcialmente | Campos existem, mas não há UI nem reserva transacional que os faça seguros em concorrência. |
| Editar, duplicar, ordenar, ativar, desativar e remover oferta | Implementado parcialmente | Editar/ativar podem ser feitos por API; demais ações e histórico não existem. |
| Visual individual da oferta | Implementado parcialmente | URLs, selo, destaque e texto existem; faltam editor, cores, ícone, desktop/mobile completos e separação formal entre visual e comercial. |
| Geração automática do card | Implementado parcialmente | Cards aparecem para ofertas ativas, mas usam renderer fixo e não suportam o conjunto de configurações solicitado. |
| Editor profissional de Landing Page | Implementado incorretamente | É um formulário vertical simples. Criar workspace próprio com toolbar, painel seccionado e canvas. |
| Preview usando o renderer público | Implementado incorretamente | O preview administrativo é uma implementação diferente da página pública. Extrair renderer compartilhado. |
| Preview desktop/tablet/smartphone | Não implementado | Não há troca de viewport. Criar canvas responsivo com os três modos. |
| Estado de alterações não salvas | Não implementado | Não há dirty-state, proteção de navegação ou comparação com rascunho. |
| Upload real de mídias | Implementado somente em infraestrutura externa ao módulo | Reutilizar `MediaUpload`, `ImageUpload`, upload tenantizado, compressão e URLs internas. Adicionar drag-and-drop e progresso. |
| Logotipo e header independente | Implementado parcialmente | Há só um texto em header fixo. Implementar visibilidade, logo desktop/mobile, tamanho, alinhamento, fundo, espaçamento e fixação. |
| Hero desktop/mobile | Implementado parcialmente | Uma única URL e poucos textos. Implementar mídias separadas, enquadramento, proporção e visibilidade de textos. |
| Imagem complementar | Não implementado | Criar seção configurável antes/depois das ofertas. |
| Vídeo desktop/mobile e capas | Implementado parcialmente | Existe uma URL única com controles fixos. Implementar mídias e comportamento por dispositivo. |
| Identidade visual completa | Implementado parcialmente | Apenas fundo, texto e destaque. Criar tokens suportados de cor, tipografia, espaçamento e raio. |
| Contador regressivo real | Não implementado | Só é exibida a data final. Criar componente sincronizado com backend e bloqueio comercial server-side. |
| Ofertas ilimitadas em fluxo vertical | Implementado parcialmente | O renderer itera sem limite, mas a grade e os cards são fixos e não configuráveis. |
| Indicador flutuante de rolagem | Implementado incorretamente | Detecta a última oferta, porém o clique volta à primeira, não à próxima ainda não vista; não há opção administrativa. |
| Botão vinculado à oferta e configurador correto | Implementado incorretamente | Produto simples entra direto no carrinho com tamanho `M` e opções vazias. Deve abrir o configurador específico e validar composição no backend. |
| Preservação do carrinho | Implementado parcialmente | Usa carrinho canônico, mas não há E2E cobrindo retorno à landing e múltiplas linhas/ofertas. |
| Venda imediata e antecipada | Implementado parcialmente | Há `immediate/preorder` e agendamento no backend/checkout. Falta UI completa e E2E. |
| Venda com loja fechada | Implementado parcialmente | Regra backend existe e não altera a loja global, mas falta configuração administrativa adequada e aceite E2E. |
| Reserva sem pagamento, parcial e integral | Não implementado | Não há entidade, estados, expiração, retenção, pagamento parcial ou interface. |
| Datas, slots e capacidade operacional | Não implementado | Não existem modelos, APIs ou UI de capacidade e concorrência. |
| Pedidos futuros e KDS | Implementado parcialmente | Pedidos futuros são ocultados/bloqueados até a janela; falta job idempotente de liberação e gestão administrativa. |
| Estoque e CMV | Implementado parcialmente | Fluxo canônico é preservado na preparação, mas reservas/capacidade e efeitos antecipados não estão concluídos. |
| Financeiro completo | Implementado parcialmente | Pagamento/pedido canônicos existem; faltam tratamento explícito de recebimento antecipado, reconhecimento, parcial, reembolso e DRE da campanha. |
| CRM, clientes e notificações | Não implementado | Não há interface/serviço específico comprovado para campanha estratégica. |
| Métricas comerciais | Implementado parcialmente | Há pedidos pagos, receita e conversão. Faltam reservas, ticket, vendas antecipadas e filtros completos. |
| Métricas de marketing | Implementado parcialmente | Há sessões, visualizações, cliques, gasto e ROAS condicional. Faltam visitantes, CPA, CAC e integrações externas completas. |
| Métricas financeiras | Não implementado | CMV, custos, margem, resultado e ROI não são calculados. |
| Métricas operacionais | Não implementado | Não há pizzas vendidas, capacidade usada/disponível nem previsão consolidada. |
| URL exclusiva no domínio | Implementado parcialmente | Slug tenant-scoped e rota pública existem, mas o caminho publicado difere do `/campanha/:slug` solicitado e não há UI de copiar URL. |
| Rascunho, publicação, atualização, despublicação e rollback | Implementado parcialmente | Há snapshot e publicação; edição após publicação é bloqueada e não existem despublicação/restauração operacional. |
| UTM e rastreamento | Implementado parcialmente | Captura UTM/referrer e eventos básicos. Faltam configuração administrativa e provas de Meta Pixel, CAPI e GA. |
| Tenant e RBAC | Implementado parcialmente | Tenant está presente e há `marketing.view/edit`; faltam permissões granulares por ação sensível. |
| Idempotência e concorrência | Implementado parcialmente | Pedido canônico tem proteções, mas oferta/capacidade/reserva/publicação não possuem o conjunto exigido de locks, constraints e chaves. |
| Auditoria e histórico | Não implementado | Versões publicadas não substituem trilha administrativa de alterações e ações críticas. |
| Responsividade e acessibilidade | Implementado parcialmente | A landing é responsiva básica e respeita reduced motion; não há prova nos dispositivos/navegadores do aceite. |
| Testes unitários e integração | Implementado parcialmente | O recorte atual passa, mas não cobre a maior parte do escopo funcional. |
| E2E administrativo e comercial de 40 passos | Não implementado | O cenário bloqueia na criação/gestão de ofertas pela interface. |
| Evidências visuais obrigatórias | Não implementado | Não existem capturas do fluxo completo solicitado. |

## Componentes corretos a preservar e reutilizar

- `StrategicCampaign`, `StrategicOffer`, `StrategicCampaignVersion` e vínculos no
  pedido, com evolução aditiva.
- Tenant scope e resolução pública por domínio.
- Carrinho, quote, checkout, pedido, pagamentos e produtos canônicos.
- Kits promocionais, promoções de produto e configuradores existentes.
- `MediaUpload`, `ImageUpload`, compressão e armazenamento tenantizado.
- Captura UTM, eventos e métricas de tráfego existentes.
- Bloqueio de produção/KDS para pedidos futuros.
- Design system, tabs, modais, dashboards e padrões administrativos existentes.

## Riscos e resolução obrigatória

| Risco | Solução | Responsável | Teste/gate bloqueador | Rollback e evidência |
|---|---|---|---|---|
| Criar catálogo, preço ou checkout paralelo | Ofertas referenciam catálogo/promoções/kits e passam pelo quote canônico | Arquiteto + Backend | E2E prova configurador, quote e checkout existentes | Feature flag da oferta; pedidos preservam snapshot |
| Preço visual divergir do preço cobrado | Contrato server-side de composição e preço estratégico | Backend | Testes de manipulação de payload e mudança de preço concorrente | Desativar oferta/versão; checkout convencional permanece |
| Venda acima de estoque/capacidade | Reserva transacional com lock, constraint, expiração e idempotência | Database + Backend | Corrida pela última unidade/slot em PostgreSQL | Reconciliar reservas; não apagar pedidos pagos |
| Pedido futuro entrar cedo no KDS | Job idempotente e estado explícito de liberação | Backend + QA | Relógio controlado e E2E de liberação | Pausar job; histórico e pagamento preservados |
| Builder divergir da landing publicada | Um renderer compartilhado com snapshot publicado imutável | Frontend + Arquiteto | Snapshot visual desktop/mobile do mesmo contrato | Restaurar versão publicada anterior |
| Upload malicioso ou órfão | Upload tenantizado, MIME/size, SVG sanitizado e ownership | Backend + Segurança | Testes de MIME, tenant cruzado, tamanho e remoção | Desativar asset; fallback visual não bloqueia compra |
| Métricas falsas ou dupla contagem | Eventos idempotentes e definições documentadas | Backend + Financeiro | Reconciliação pedido/pagamento/evento | Exibir indisponível, nunca zero inventado |
| RBAC genérico expor preços/publicação/financeiro | Permissões granulares fail-closed | Backend | Matriz de papéis e tenant cruzado | Revogar permissão sem indisponibilizar leitura permitida |
| Migração destrutiva em produção | Mudanças aditivas, backfill controlado e helper oficial | Database + QA-DevOps | Upgrade em cópia PostgreSQL e rollback compatível | Backup imutável e release anterior |
| Escopo visual esconder integrações ausentes | Gates funcionais por fase e matriz atualizada | Orquestrador + QA | Nenhuma fase fecha sem fluxo integrado correspondente | Não promover feature flag |

## Plano de execução corretivo

### C0 — Contratos e baseline de aceite

- Congelar a matriz acima como baseline.
- Definir schemas de builder, composição de oferta, reserva, capacidade,
  publicação e permissões.
- Mapear explicitamente cada passo do aceite para uma tela, API, service, tabela
  e teste.
- Gate: contratos aprovados sem quebrar APIs publicadas e sem fluxo paralelo.

### C1 — Arquitetura administrativa

- Criar página geral de campanhas com KPIs, pesquisa, filtros e ações.
- Criar cadastro por modal/página.
- Criar rota individual e navegação nas nove abas.
- Gate: criar campanha e navegar por todas as áreas sem API manual.

### C2 — Ofertas comerciais completas

- Criar UI de seleção de produto, promoção e kit.
- Criar contrato validado de composição autorizada.
- Implementar criar, editar, duplicar, ordenar, ativar, desativar e arquivar.
- Gate: cadastrar cinco ofertas pela UI e validar preço pelo backend.

### C3 — Mídias e apresentação das ofertas

- Integrar upload tenantizado para desktop/mobile.
- Separar configuração comercial da visual.
- Implementar selo, cores, botão, ícone, destaque e ordem.
- Gate: cinco imagens e cinco botões persistidos e renderizados.

### C4 — Builder profissional e renderer compartilhado

- Criar toolbar, painel seccionado, dirty-state e viewports.
- Implementar identidade, header, hero, vídeo, contador, ofertas, imagem
  complementar, informações, indicador e rodapé.
- Extrair renderer compartilhado entre preview e página pública.
- Gate: preview e publicação renderizam o mesmo snapshot.

### C5 — Landing pública e conversão

- Ajustar rota pública definitiva e compatibilidade com a rota atual.
- Corrigir seta para a próxima oferta não visualizada.
- Abrir configurador canônico da oferta; preservar carrinho e contexto.
- Gate: oferta configurável até checkout sem preço controlado pelo frontend.

### C6 — Comercialização, reservas e capacidade

- Implementar modalidades imediata, antecipada e reservas sem/parcial/integral.
- Modelar slots, limites e retenções com concorrência PostgreSQL.
- Criar UI de datas, horários, bloqueios e capacidade.
- Gate: última vaga/unidade não pode ser vendida duas vezes.

### C7 — Operação integrada

- Completar pedidos programados, job de liberação, KDS, estoque, CMV,
  Financeiro, CRM, motoboy e notificações.
- Gate: pedido antecipado pago percorre o ciclo operacional no horário correto,
  sem dupla baixa ou lançamento financeiro.

### C8 — Marketing e resultados

- Implementar configuração UTM/Pixel/CAPI/GA e falha não bloqueante.
- Criar dashboards comerciais, marketing, financeiros e operacionais.
- Documentar fórmulas e fontes; valores ausentes ficam indisponíveis.
- Gate: reconciliação com pedidos/pagamentos e mídia real.

### C9 — Segurança, qualidade e aceite integral

- Granularizar RBAC, auditoria, idempotência e proteção de uploads.
- Executar unitários, integração PostgreSQL, concorrência, E2E e regressão.
- Executar os 40 passos corretivos e a duplicação Black Friday → Natal.
- Produzir todas as capturas exigidas.
- Gate: nenhum passo administrativo depende de terminal/API/SQL.

### C10 — Release controlada

- Revisar diff e migrations, gerar backup, publicar SHA imutável e validar
  serviços, HTTPS e fluxos autenticados.
- Produção somente com autorização expressa do solicitante.

## Estado dos testes no baseline

Executado em 2026-11-25:

- `pytest` focado em campanhas estratégicas: **14 passed**.
- TypeScript typecheck: **aprovado**.

Esses resultados validam apenas o código atualmente existente. Eles não são
evidência de conclusão do fluxo comercial ou do aceite corretivo.

## Critério para declarar conclusão

Somente declarar o submódulo concluído quando a matriz estiver integralmente
atendida, o cenário administrativo/comercial de 40 passos passar pela interface,
as integrações operacionais e financeiras forem reconciliadas e as evidências
visuais e automatizadas estiverem anexadas. A existência de endpoint, model ou
componente isolado não constitui aceite.

export type PageTab = {
  label: string;
  path: string;
  exact?: boolean;
};

export type PageToolbarItem = {
  label: string;
  path?: string;
};

export type PageMeta = {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  primaryAction?: {
    label: string;
    path?: string;
  };
  tabs?: PageTab[];
  toolbar?: PageToolbarItem[];
};

export const adminPageMeta: Record<string, PageMeta> = {
  "/painel/empresas": { eyebrow: "Plataforma", title: "Empresas", subtitle: "Cadastro de empresas e dominios da plataforma" },
  "/painel": { eyebrow: "Visao geral", title: "Dashboard", subtitle: "Resumo operacional da loja em tempo real" },
  "/painel/bi": { eyebrow: "Business Intelligence", title: "BI", subtitle: "Motor de analise, recomendacao e acao do negocio" },
  "/painel/bi-mobile": { eyebrow: "Business Intelligence", title: "BI Mobile", subtitle: "Resumo operacional do dia" },
  "/painel/products": { eyebrow: "Catalogo", title: "Produtos", subtitle: "Gestão do cardapio e categorias" },
  "/painel/products/landing": { eyebrow: "Catalogo", title: "Landing Promocional", subtitle: "Pagina de conversao vinculada a promocao da pizza" },
  "/painel/home-config": { eyebrow: "Catalogo", title: "Catalogo da Home", subtitle: "Organizacao da vitrine da loja" },
  "/painel/orders": { eyebrow: "Operacoes", title: "Pedidos", subtitle: "Acompanhamento e gestão dos pedidos" },
  "/painel/kds": { eyebrow: "KDS", title: "Painel Geral", subtitle: "Visão consolidada da cozinha, expedição e entregas" },
  "/painel/kds/visao-producao": { eyebrow: "KDS", title: "Registro de Produção", subtitle: "Câmeras, bancadas e sessões de produção" },
  "/painel/esfiha": { eyebrow: "KDS", title: "KDS Esfiha", subtitle: "Fila de produção e operação da estação esfiha" },
  "/painel/kds/analitico": { eyebrow: "KDS", title: "Analítico KDS", subtitle: "Indicadores históricos de todas as estações KDS" },
  "/painel/kds/sala-motoboy": { eyebrow: "KDS", title: "Painel Sala Motoboy", subtitle: "Acesso ao painel de chamadas para retirada" },
  "/painel/cozinha": { eyebrow: "KDS", title: "KDS Pizzaiolo", subtitle: "Fila touch de preparo de pizzas" },
  "/painel/expedicao": { eyebrow: "KDS", title: "KDS Expedição", subtitle: "Conferência e atribuição de motoboy" },
  "/painel/kds/auditoria": { eyebrow: "KDS", title: "KDS Auditoria", subtitle: "Conferência final e transferência ao entregador" },
  "/painel/salao": { eyebrow: "Operacoes", title: "Salao & Reservas", subtitle: "Mesas, reservas, comandas e pedidos do salao" },
  "/painel/logistica": { eyebrow: "Operacoes", title: "Logistica", subtitle: "Gerenciamento de entregas e motoboys" },
  "/painel/gestao/estoque": { eyebrow: "Gestão", title: "Estoque", subtitle: "Base de insumos, saldos e disponibilidade" },
  "/painel/gestao/estoque/insumos": { eyebrow: "Gestão / Estoque / Cadastro", title: "Cadastro de Insumos", subtitle: "Insumos, embalagens e materiais usados pelo estoque" },
  "/painel/gestao/estoque/porcionamento": { eyebrow: "Gestão / Estoque / Cadastro", title: "Cadastro de Porcionamento", subtitle: "Configuração das porções e da ficha técnica operacional" },
  "/painel/gestao/estoque/fornecedores": { eyebrow: "Gestão / Estoque / Cadastro", title: "Cadastro de Fornecedores", subtitle: "Fornecedores utilizados nas compras de estoque" },
  "/painel/gestao/estoque/base": { eyebrow: "Gestão / Estoque / Cadastro", title: "Base do Estoque", subtitle: "Unidades, categorias e locais de armazenamento" },
  "/painel/gestao/estoque/estoque-insumos": { eyebrow: "Gestão / Estoque", title: "Estoque de Insumos", subtitle: "Saldos, mínimos e locais dos insumos" },
  "/painel/gestao/estoque/estoque-porcionamento": { eyebrow: "Gestão / Estoque", title: "Estoque de Porcionamento", subtitle: "Porções disponíveis e solicitações de preparo" },
  "/painel/gestao/estoque/saldos-conversoes": { eyebrow: "Gestão / Estoque", title: "Saldos e Conversões", subtitle: "Lotes, saldos por local e conversões de unidade" },
  "/painel/gestao/estoque/preparo": { eyebrow: "Gestão / Estoque / Produção", title: "Preparo de Porcionamento", subtitle: "Ordens, fichas e apontamentos de porcionamento" },
  "/painel/gestao/estoque/reposicao": { eyebrow: "Gestão / Estoque / Operação", title: "Reposição de Estoque", subtitle: "Itens abaixo do mínimo e solicitações de compra" },
  "/painel/gestao/estoque/compras": { eyebrow: "Gestão / Estoque / Operação", title: "Compras de Estoque", subtitle: "Rascunhos, confirmação e acompanhamento de compras" },
  "/painel/gestao/estoque/entradas": { eyebrow: "Gestão / Estoque / Operação", title: "Entradas e Movimentos", subtitle: "Entradas, saídas e ajustes manuais de estoque" },
  "/painel/gestao/estoque/configuracoes": { eyebrow: "Gestão / Estoque / Operação", title: "Configurações do Estoque", subtitle: "Regras gerais de operação do módulo" },
  "/painel/gestao/cmv": { eyebrow: "Gestão", title: "CMV", subtitle: "Custo de mercadoria vendida e snapshots analiticos" },
  "/painel/gestao/financeiro": { eyebrow: "Gestão", title: "Financeiro", subtitle: "Contas, caixa, competencia e DRE" },
  "/painel/gestao/fiscal": { eyebrow: "Gestão", title: "Fiscal SEFAZ", subtitle: "Base fiscal nativa com SEFAZ direta" },
  "/painel/crm": { eyebrow: "CRM", title: "Dashboard CRM", subtitle: "Relacionamento e inteligencia de clientes" },
  "/painel/clientes": { eyebrow: "CRM", title: "Clientes", subtitle: "Base de clientes e historico" },
  "/painel/clientes/:id": { eyebrow: "CRM", title: "Detalhe do Cliente", subtitle: "Perfil, pedidos e relacionamento" },
  "/painel/crm/inteligencia": { eyebrow: "CRM", title: "Inteligencia de Clientes", subtitle: "Analises e recomendacoes de relacionamento" },
  "/painel/crm/pipeline": { eyebrow: "CRM", title: "Pipeline", subtitle: "Oportunidades e etapas comerciais" },
  "/painel/crm/grupos": { eyebrow: "CRM", title: "Grupos & Segmentacoes", subtitle: "Segmentacao da base de clientes" },
  "/painel/crm/tarefas": { eyebrow: "CRM", title: "Tarefas", subtitle: "Atividades e follow-ups" },
  "/painel/crm/agente-whatsapp": { eyebrow: "CRM", title: "Agente WhatsApp", subtitle: "Central operacional de conversas e status de pedidos" },
  "/painel/marketing": { eyebrow: "Marketing", title: "Dashboard Marketing", subtitle: "Indicadores de campanhas e canais" },
  "/painel/marketing/visitantes": { eyebrow: "Marketing", title: "Analise de Visitantes", subtitle: "Origem e comportamento no site" },
  "/painel/marketing/links": { eyebrow: "Marketing", title: "Links Rastreaveis", subtitle: "UTMs e rastreamento de campanhas" },
  "/painel/marketing/integracoes": { eyebrow: "Configuracoes", title: "Integracoes", subtitle: "Conexoes com canais externos" },
  "/painel/whatsapp-gateway": { eyebrow: "Configuracoes", title: "WhatsApp Gateway", subtitle: "Conexoes, sessoes, Baileys e saude operacional" },
  "/painel/marketing/whatsapp": { eyebrow: "Marketing", title: "Disparador WhatsApp", subtitle: "Mensagens e campanhas por WhatsApp" },
  "/painel/marketing/email": { eyebrow: "Marketing", title: "Disparador de Email", subtitle: "Campanhas e mensagens por email" },
  "/painel/marketing/automacoes": { eyebrow: "Marketing", title: "Automacao de Marketing", subtitle: "Fluxos automaticos e eventos" },
  "/painel/marketing/ads": { eyebrow: "Marketing", title: "Trafego Pago", subtitle: "Campanhas pagas, pixels e ROI" },
  "/painel/marketing/workflow": { eyebrow: "Marketing", title: "Workflow de Aprovacao", subtitle: "Aprovacao antes de disparar campanhas" },
  "/painel/marketing/cupons": { eyebrow: "Marketing", title: "Cupons de Desconto", subtitle: "Cupons e uso em campanhas" },
  "/painel/marketing/notificacoes": { eyebrow: "Marketing", title: "Notificacoes de Compradores", subtitle: "Prova social de compras na loja online" },
  "/painel/marketing/upsell": { eyebrow: "Marketing", title: "Gestão de Upsell", subtitle: "Ofertas adicionais exibidas no checkout" },
  "/painel/trafego-pago": { eyebrow: "Marketing", title: "Trafego Pago", subtitle: "Campanhas pagas, pixels e ROI" },
  "/painel/cupons": { eyebrow: "Marketing", title: "Cupons de Desconto", subtitle: "Cupons e uso em campanhas" },
  "/painel/campanhas": { eyebrow: "Marketing", title: "Banner Delivery", subtitle: "Banners promocionais da loja delivery" },
  "/painel/fidelidade": { eyebrow: "Marketing", title: "Fidelidade", subtitle: "Regras, beneficios e pontos dos clientes" },
  "/painel/popup-saida": { eyebrow: "Marketing", title: "Popup por Tempo", subtitle: "Captura e retencao por tempo de permanencia" },
  "/painel/conteudo": { eyebrow: "Configuracoes", title: "Pagina Delivery", subtitle: "Textos, marca e informacoes da loja delivery" },
  "/painel/salao/pagina": { eyebrow: "Configuracoes", title: "Pagina Salao", subtitle: "Conteudo publico do dominio moschettieri.com.br" },
  "/painel/pagamentos": { eyebrow: "Configuracoes", title: "Pagamentos", subtitle: "Meios de pagamento e credenciais" },
  "/painel/frete": { eyebrow: "Configuracoes", title: "Entregas e Fretes", subtitle: "Regras de entrega e taxas" },
  "/painel/funcionamento": { eyebrow: "Configuracoes", title: "Funcionamento da Loja Online", subtitle: "Dias, horarios, excecoes e agendamento" },
  "/painel/chatbot": { eyebrow: "Marketing", title: "Chatbot", subtitle: "Atendimento inteligente integrado ao site" },
  "/painel/aparencia": { eyebrow: "Configuracoes", title: "Aparencia", subtitle: "Tema visual e identidade da loja" },
  "/painel/usuarios": { eyebrow: "Configuracoes", title: "Usuarios do Sistema", subtitle: "Acessos administrativos" },
  "/painel/lgpd": { eyebrow: "Configuracoes", title: "LGPD & Privacidade", subtitle: "Politicas, consentimentos e privacidade" },
  "/painel/configuracoes": { eyebrow: "Configuracoes", title: "Configuracoes", subtitle: "Preferencias do sistema" },
  "/painel/comprovantes-pedidos": { eyebrow: "Configuracoes", title: "Comprovantes de pedidos", subtitle: "Notas, comandas e comprovantes de pedidos" },
  "/painel/etiquetas-expedicao": { eyebrow: "Configuracoes", title: "Etiquetas de expedição", subtitle: "Modelos de etiquetas para caixas e expedição" },
  "/painel/etiquetas-insumos": { eyebrow: "Configuracoes", title: "Etiquetas de insumos", subtitle: "Modelos de etiquetas para porcionamento, lote e validade" },
  "/painel/dominio": { eyebrow: "Configuracoes", title: "Domínio", subtitle: "Domínio, endereço e disponibilidade da loja" },
  "/painel/painel-tv-config": { eyebrow: "Configuracoes", title: "Painel de TV", subtitle: "Configurações do painel operacional de TV" },
  "/painel/som": { eyebrow: "Configuracoes", title: "Som", subtitle: "Configurações de som e alertas operacionais" },
  "/painel/identificacao-parceiros": { eyebrow: "Configuracoes", title: "Identificação de parceiros", subtitle: "Identificação exibida para parceiros e entregadores" },
};

export function getAdminPageMeta(pathname: string): PageMeta {
  if (adminPageMeta[pathname]) return adminPageMeta[pathname];
  if (pathname.startsWith("/painel/clientes/")) return adminPageMeta["/painel/clientes/:id"];
  if (pathname.startsWith("/painel/products/landing/")) return adminPageMeta["/painel/products/landing"];

  const fallback = Object.entries(adminPageMeta)
    .filter(([path]) => pathname.startsWith(`${path}/`))
    .sort(([a], [b]) => b.length - a.length)[0]?.[1];

  return fallback ?? { eyebrow: "Painel", title: "Painel Administrativo" };
}

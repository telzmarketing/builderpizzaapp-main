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
  "/painel": { eyebrow: "Visao geral", title: "Dashboard", subtitle: "Resumo operacional da loja em tempo real" },
  "/painel/bi": { eyebrow: "Business Intelligence", title: "BI", subtitle: "Motor de analise, recomendacao e acao do negocio" },
  "/painel/products": { eyebrow: "Catalogo", title: "Produtos", subtitle: "Gestao do cardapio e categorias" },
  "/painel/home-config": { eyebrow: "Catalogo", title: "Catalogo da Home", subtitle: "Organizacao da vitrine da loja" },
  "/painel/orders": { eyebrow: "Operacoes", title: "Pedidos", subtitle: "Acompanhamento e gestao dos pedidos" },
  "/painel/cozinha": { eyebrow: "Operacoes", title: "Cozinha", subtitle: "Fila de preparo e expedicao" },
  "/painel/logistica": { eyebrow: "Operacoes", title: "Logistica", subtitle: "Gerenciamento de entregas e motoboys" },
  "/painel/crm": { eyebrow: "CRM", title: "Dashboard CRM", subtitle: "Relacionamento e inteligencia de clientes" },
  "/painel/clientes": { eyebrow: "CRM", title: "Clientes", subtitle: "Base de clientes e historico" },
  "/painel/clientes/:id": { eyebrow: "CRM", title: "Detalhe do Cliente", subtitle: "Perfil, pedidos e relacionamento" },
  "/painel/crm/inteligencia": { eyebrow: "CRM", title: "Inteligencia de Clientes", subtitle: "Analises e recomendacoes de relacionamento" },
  "/painel/crm/pipeline": { eyebrow: "CRM", title: "Pipeline", subtitle: "Oportunidades e etapas comerciais" },
  "/painel/crm/grupos": { eyebrow: "CRM", title: "Grupos & Segmentacoes", subtitle: "Segmentacao da base de clientes" },
  "/painel/crm/tarefas": { eyebrow: "CRM", title: "Tarefas", subtitle: "Atividades e follow-ups" },
  "/painel/marketing": { eyebrow: "Marketing", title: "Dashboard Marketing", subtitle: "Indicadores de campanhas e canais" },
  "/painel/marketing/campanhas": { eyebrow: "Marketing", title: "Campanhas", subtitle: "Planejamento e execucao de campanhas" },
  "/painel/marketing/visitantes": { eyebrow: "Marketing", title: "Analise de Visitantes", subtitle: "Origem e comportamento no site" },
  "/painel/marketing/links": { eyebrow: "Marketing", title: "Links Rastreaveis", subtitle: "UTMs e rastreamento de campanhas" },
  "/painel/marketing/integracoes": { eyebrow: "Configuracoes", title: "Integracoes", subtitle: "Conexoes com canais externos" },
  "/painel/marketing/whatsapp": { eyebrow: "Marketing", title: "Disparador WhatsApp", subtitle: "Mensagens e campanhas por WhatsApp" },
  "/painel/marketing/email": { eyebrow: "Marketing", title: "Disparador de Email", subtitle: "Campanhas e mensagens por email" },
  "/painel/marketing/automacoes": { eyebrow: "Marketing", title: "Automacao de Marketing", subtitle: "Fluxos automaticos e eventos" },
  "/painel/marketing/ads": { eyebrow: "Marketing", title: "Ads", subtitle: "Campanhas pagas, pixels e ROI" },
  "/painel/marketing/workflow": { eyebrow: "Marketing", title: "Workflow de Aprovacao", subtitle: "Aprovacao antes de disparar campanhas" },
  "/painel/marketing/cupons": { eyebrow: "Marketing", title: "Cupons de Desconto", subtitle: "Cupons e uso em campanhas" },
  "/painel/trafego-pago": { eyebrow: "Marketing", title: "Trafego Pago", subtitle: "Campanhas pagas, pixels e ROI" },
  "/painel/campanhas": { eyebrow: "Marketing", title: "Promocoes & Banners", subtitle: "Ofertas, banners e campanhas promocionais" },
  "/painel/fidelidade": { eyebrow: "Marketing", title: "Fidelidade", subtitle: "Regras, beneficios e pontos dos clientes" },
  "/painel/popup-saida": { eyebrow: "Marketing", title: "Popup de Saida", subtitle: "Captura e retencao no site" },
  "/painel/conteudo": { eyebrow: "Configuracoes", title: "Conteudo", subtitle: "Textos, marca e informacoes da loja" },
  "/painel/pagamentos": { eyebrow: "Configuracoes", title: "Pagamentos", subtitle: "Meios de pagamento e credenciais" },
  "/painel/frete": { eyebrow: "Configuracoes", title: "Entregas e Fretes", subtitle: "Regras de entrega e taxas" },
  "/painel/funcionamento": { eyebrow: "Configuracoes", title: "Funcionamento da Loja Online", subtitle: "Dias, horarios, excecoes e agendamento" },
  "/painel/chatbot": { eyebrow: "Configuracoes", title: "Chatbot", subtitle: "Atendimento inteligente integrado ao site" },
  "/painel/aparencia": { eyebrow: "Configuracoes", title: "Aparencia", subtitle: "Tema visual e identidade da loja" },
  "/painel/usuarios": { eyebrow: "Configuracoes", title: "Usuarios do Sistema", subtitle: "Acessos administrativos" },
  "/painel/lgpd": { eyebrow: "Configuracoes", title: "LGPD & Privacidade", subtitle: "Politicas, consentimentos e privacidade" },
  "/painel/configuracoes": { eyebrow: "Configuracoes", title: "Configuracoes", subtitle: "Preferencias do sistema" },
};

export function getAdminPageMeta(pathname: string): PageMeta {
  if (adminPageMeta[pathname]) return adminPageMeta[pathname];
  if (pathname.startsWith("/painel/clientes/")) return adminPageMeta["/painel/clientes/:id"];

  const fallback = Object.entries(adminPageMeta)
    .filter(([path]) => pathname.startsWith(`${path}/`))
    .sort(([a], [b]) => b.length - a.length)[0]?.[1];

  return fallback ?? { eyebrow: "Painel", title: "Painel Administrativo" };
}

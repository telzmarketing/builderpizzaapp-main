type RouteLoader = () => Promise<unknown>;

const loadedRoutes = new Set<string>();

const routeLoaders: Array<[string, RouteLoader]> = [
  ["/painel/products/landing", () => import("@/pages/admin/PromotionalLandingEditor")],
  ["/painel/marketing/visitantes", () => import("@/pages/admin/marketing/MarketingVisitantes")],
  ["/painel/marketing/links", () => import("@/pages/admin/marketing/MarketingLinks")],
  ["/painel/marketing/integracoes", () => import("@/pages/admin/marketing/MarketingIntegracoes")],
  ["/painel/whatsapp-gateway", () => import("@/pages/admin/whatsapp/WhatsAppGateway")],
  ["/painel/marketing/whatsapp", () => import("@/pages/admin/marketing/MarketingWhatsApp")],
  ["/painel/marketing/email", () => import("@/pages/admin/marketing/MarketingEmail")],
  ["/painel/marketing/ads", () => import("@/pages/admin/PaidTraffic")],
  ["/painel/marketing/automacoes", () => import("@/pages/admin/marketing/MarketingAutomacoes")],
  ["/painel/marketing/workflow", () => import("@/pages/admin/marketing/MarketingWorkflow")],
  ["/painel/marketing/cupons", () => import("@/pages/admin/marketing/MarketingCupons")],
  ["/painel/marketing/notificacoes", () => import("@/pages/admin/marketing/MarketingStoreNotifications")],
  ["/painel/marketing/upsell", () => import("@/pages/admin/marketing/MarketingUpsell")],
  ["/painel/gestao/estoque", () => import("@/pages/admin/gestao/GestaoInventory")],
  ["/painel/gestao/cmv", () => import("@/pages/admin/gestao/GestaoCmv")],
  ["/painel/gestao/financeiro", () => import("@/pages/admin/gestao/GestaoFinance")],
  ["/painel/gestao/fiscal", () => import("@/pages/admin/gestao/GestaoFiscal")],
  ["/painel/crm/inteligencia", () => import("@/pages/admin/crm/CrmInteligencia")],
  ["/painel/crm/pipeline", () => import("@/pages/admin/crm/CrmPipeline")],
  ["/painel/crm/grupos", () => import("@/pages/admin/crm/CrmGrupos")],
  ["/painel/crm/tarefas", () => import("@/pages/admin/crm/CrmTarefas")],
  ["/painel/crm/agente-whatsapp", () => import("@/pages/admin/crm/CrmAgenteWhatsApp")],
  ["/painel/salao/pagina", () => import("@/pages/admin/salao/AdminSalaoPage")],
  ["/painel/bi-mobile", () => import("@/pages/admin/bi/BiMobile")],
  ["/painel/products", () => import("@/pages/admin/Products")],
  ["/painel/home-config", () => import("@/pages/admin/HomeConfig")],
  ["/painel/orders", () => import("@/pages/admin/Orders")],
  ["/painel/cozinha", () => import("@/pages/admin/Cozinha")],
  ["/painel/salao", () => import("@/pages/admin/salao/AdminSalao")],
  ["/painel/fidelidade", () => import("@/pages/admin/AdminFidelidade")],
  ["/painel/conteudo", () => import("@/pages/admin/Conteudo")],
  ["/painel/pagamentos", () => import("@/pages/admin/AdminPagamentos")],
  ["/painel/frete", () => import("@/pages/admin/AdminFrete")],
  ["/painel/funcionamento", () => import("@/pages/admin/StoreOperation")],
  ["/painel/campanhas", () => import("@/pages/admin/AdminCampanhas")],
  ["/painel/trafego-pago", () => import("@/pages/admin/PaidTraffic")],
  ["/painel/chatbot", () => import("@/pages/admin/AdminChatbot")],
  ["/painel/aparencia", () => import("@/pages/admin/Aparencia")],
  ["/painel/lgpd", () => import("@/pages/admin/AdminLgpd")],
  ["/painel/configuracoes", () => import("@/pages/admin/AdminConfiguracoes")],
  ["/painel/cupons", () => import("@/pages/admin/marketing/MarketingCupons")],
  ["/painel/clientes", () => import("@/pages/admin/AdminClientes")],
  ["/painel/popup-saida", () => import("@/pages/admin/AdminExitPopup")],
  ["/painel/usuarios", () => import("@/pages/admin/AdminUsuarios")],
  ["/painel/bi", () => import("@/pages/admin/bi/BiDashboard")],
  ["/painel/marketing", () => import("@/pages/admin/marketing/MarketingDashboard")],
  ["/painel/crm", () => import("@/pages/admin/crm/CrmDashboard")],
  ["/painel/logistica", () => import("@/pages/admin/logistica/AdminLogistica")],
  ["/painel", () => import("@/pages/admin/Dashboard")],
];

export function preloadAdminRoute(path: string) {
  const match = routeLoaders.find(([route]) => path === route || path.startsWith(`${route}/`));
  if (!match) return;

  const [route, loader] = match;
  if (loadedRoutes.has(route)) return;
  loadedRoutes.add(route);
  loader().catch(() => loadedRoutes.delete(route));
}

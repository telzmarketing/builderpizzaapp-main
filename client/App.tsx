import { lazy, Suspense, useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AppProvider, useApp } from "./context/AppContext";
import { themeApi, applyTheme, DEFAULT_THEME, readCachedTheme } from "./lib/themeApi";
import { captureTrackingFromUrl, trackEvent, getTrackingData } from "./lib/tracking";
import { customerEventsApi, resolveAssetUrl } from "./lib/api";

const ChatbotWidget = lazy(() => import("./components/ChatbotWidget"));

function StoreWidget() {
  const { pathname } = useLocation();
  if (pathname.startsWith("/painel")) return null;
  return (
    <Suspense fallback={null}>
      <ChatbotWidget />
    </Suspense>
  );
}

function ThemeInjector() {
  useEffect(() => {
    applyTheme(readCachedTheme() ?? DEFAULT_THEME);
    themeApi.get().then(applyTheme).catch(() => {});

    const handler = () => themeApi.get().then(applyTheme).catch(() => {});
    window.addEventListener("theme-updated", handler);
    return () => window.removeEventListener("theme-updated", handler);
  }, []);
  return null;
}


function TrackingInjector() {
  const { pathname, search } = useLocation();

  useEffect(() => {
    if (pathname.startsWith("/painel")) return;
    if (sessionStorage.getItem("_mo_site_opened")) return;
    sessionStorage.setItem("_mo_site_opened", "1");
    const td = getTrackingData();
    customerEventsApi.register({
      event_type: "site_opened",
      event_name: "Abriu o site",
      session_id: td.session_id,
      utm_source: td.utm_source,
      utm_medium: td.utm_medium,
      utm_campaign: td.utm_campaign,
      page_url: window.location.href,
      referrer_url: td.referrer,
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (pathname.startsWith("/painel")) return;
    captureTrackingFromUrl();
    trackEvent("page_view");
  }, [pathname, search]);
  return null;
}

function DocumentHead() {
  const { siteContent } = useApp();
  const { pageTitle, faviconUrl, name } = siteContent.brand;

  const resolvedFavicon = faviconUrl ? resolveAssetUrl(faviconUrl) : "";

  useEffect(() => {
    document.title = pageTitle || name || "Pizza Delivery App";
  }, [pageTitle, name]);

  useEffect(() => {
    if (!resolvedFavicon) return;

    document
      .querySelectorAll<HTMLLinkElement>("link[rel~='icon'], link[rel='apple-touch-icon']")
      .forEach((link) => link.remove());

    const separator = resolvedFavicon.includes("?") ? "&" : "?";
    const href = resolvedFavicon.startsWith("data:")
      ? resolvedFavicon
      : `${resolvedFavicon}${separator}v=${Date.now()}`;

    const icon = document.createElement("link");
    icon.rel = "icon";
    icon.type = "image/png";
    icon.href = href;
    document.head.appendChild(icon);

    const shortcut = document.createElement("link");
    shortcut.rel = "shortcut icon";
    shortcut.href = href;
    document.head.appendChild(shortcut);
  }, [resolvedFavicon]);
  return null;
}
import AdminGuard from "./components/AdminGuard";
import Index from "./pages/Index";
import Product from "./pages/Product";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";
import OrderTracking from "./pages/OrderTracking";
import AdminLogin from "./pages/admin/Login";
import AdminDashboard from "./pages/admin/Dashboard";
import AdminProducts from "./pages/admin/Products";
import AdminOrders from "./pages/admin/Orders";
import AdminCozinha from "./pages/admin/Cozinha";
import AdminFidelidade from "./pages/admin/AdminFidelidade";
import AdminConteudo from "./pages/admin/Conteudo";
import AdminPagamentos from "./pages/admin/AdminPagamentos";
import AdminFrete from "./pages/admin/AdminFrete";
import StoreOperation from "./pages/admin/StoreOperation";
import AdminCampanhas from "./pages/admin/AdminCampanhas";
import AdminPaidTraffic from "./pages/admin/PaidTraffic";
import AdminChatbot from "./pages/admin/AdminChatbot";
import AdminAparencia from "./pages/admin/Aparencia";
import AdminHomeConfig from "./pages/admin/HomeConfig";
import AdminLgpd from "./pages/admin/AdminLgpd";
import AdminConfiguracoes from "./pages/admin/AdminConfiguracoes";
import AdminCupons from "./pages/admin/AdminCupons";
import AdminClientes from "./pages/admin/AdminClientes";
import ClienteDetalhe from "./pages/admin/ClienteDetalhe";
import AdminExitPopup from "./pages/admin/AdminExitPopup";
import AdminUsuarios from "./pages/admin/AdminUsuarios";
import ExitPopup from "./components/ExitPopup";
import MarketingDashboard from "./pages/admin/marketing/MarketingDashboard";
import MarketingCampanhas from "./pages/admin/marketing/MarketingCampanhas";
import MarketingVisitantes from "./pages/admin/marketing/MarketingVisitantes";
import MarketingLinks from "./pages/admin/marketing/MarketingLinks";
import MarketingIntegracoes from "./pages/admin/marketing/MarketingIntegracoes";
import MarketingWhatsApp from "./pages/admin/marketing/MarketingWhatsApp";
import MarketingEmail from "./pages/admin/marketing/MarketingEmail";
import MarketingAutomacoes from "./pages/admin/marketing/MarketingAutomacoes";
import MarketingAdsPanel from "./pages/admin/marketing/MarketingAdsPanel";
import MarketingWorkflow from "./pages/admin/marketing/MarketingWorkflow";
import MarketingCupons from "./pages/admin/marketing/MarketingCupons";
import CrmDashboard from "./pages/admin/crm/CrmDashboard";
import CrmPipeline from "./pages/admin/crm/CrmPipeline";
import CrmGrupos from "./pages/admin/crm/CrmGrupos";
import CrmTarefas from "./pages/admin/crm/CrmTarefas";
import CrmInteligencia from "./pages/admin/crm/CrmInteligencia";
import AdminLogistica from "./pages/admin/logistica/AdminLogistica";
import Motoboy from "./pages/Motoboy";
import Campanha from "./pages/Campanha";
import Fidelidade from "./pages/Fidelidade";
import Cupons from "./pages/Cupons";
import Pedidos from "./pages/Pedidos";
import Conta from "./pages/Conta";
import Localizacao from "./pages/Localizacao";
import Cardapio from "./pages/Cardapio";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppProvider>
        <DocumentHead />
        <ThemeInjector />
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <StoreWidget />
            <TrackingInjector />
            <ExitPopup />
            <Routes>
              {/* ── Customer routes ── */}
              <Route path="/" element={<Index />} />
              <Route path="/product/:id" element={<Product />} />
              <Route path="/cart" element={<Cart />} />
              <Route path="/checkout" element={<Checkout />} />
              <Route path="/order-tracking" element={<OrderTracking />} />
              <Route path="/fidelidade" element={<Fidelidade />} />
              <Route path="/cupons" element={<Cupons />} />
              <Route path="/pedidos" element={<Pedidos />} />
              <Route path="/conta" element={<Conta />} />
              <Route path="/localizacao" element={<Localizacao />} />
              <Route path="/cardapio" element={<Cardapio />} />
              <Route path="/campanha/:slug" element={<Campanha />} />

              {/* ── Admin login (public) ── */}
              <Route path="/painel/login" element={<AdminLogin />} />
              <Route path="/motoboy" element={<Motoboy />} />

              {/* ── Admin routes (protected by JWT guard) ── */}
              <Route element={<AdminGuard />}>
                <Route path="/painel" element={<AdminDashboard />} />
                <Route path="/painel/products" element={<AdminProducts />} />
                <Route path="/painel/orders" element={<AdminOrders />} />
                <Route path="/painel/cozinha" element={<AdminCozinha />} />
                <Route path="/painel/fidelidade" element={<AdminFidelidade />} />
                <Route path="/painel/conteudo" element={<AdminConteudo />} />
                <Route path="/painel/pagamentos" element={<AdminPagamentos />} />
                <Route path="/painel/frete" element={<AdminFrete />} />
                <Route path="/painel/funcionamento" element={<StoreOperation />} />
                <Route path="/painel/campanhas" element={<AdminCampanhas />} />
                <Route path="/painel/trafego-pago" element={<AdminPaidTraffic />} />
                <Route path="/painel/chatbot"    element={<AdminChatbot />} />
                <Route path="/painel/aparencia" element={<AdminAparencia />} />
                <Route path="/painel/home-config" element={<AdminHomeConfig />} />
                <Route path="/painel/lgpd" element={<AdminLgpd />} />
                <Route path="/painel/configuracoes" element={<AdminConfiguracoes />} />
                <Route path="/painel/cupons" element={<AdminCupons />} />
                <Route path="/painel/clientes" element={<AdminClientes />} />
                <Route path="/painel/clientes/:id" element={<ClienteDetalhe />} />
                <Route path="/painel/popup-saida" element={<AdminExitPopup />} />
                <Route path="/painel/usuarios" element={<AdminUsuarios />} />
                {/* ── Marketing routes ── */}
                <Route path="/painel/marketing" element={<MarketingDashboard />} />
                <Route path="/painel/marketing/campanhas" element={<MarketingCampanhas />} />
                <Route path="/painel/marketing/visitantes" element={<MarketingVisitantes />} />
                <Route path="/painel/marketing/links" element={<MarketingLinks />} />
                <Route path="/painel/marketing/integracoes" element={<MarketingIntegracoes />} />
                <Route path="/painel/marketing/whatsapp" element={<MarketingWhatsApp />} />
                <Route path="/painel/marketing/email" element={<MarketingEmail />} />
                <Route path="/painel/marketing/automacoes" element={<MarketingAutomacoes />} />
                <Route path="/painel/marketing/ads" element={<MarketingAdsPanel />} />
                <Route path="/painel/marketing/workflow" element={<MarketingWorkflow />} />
                <Route path="/painel/marketing/cupons" element={<MarketingCupons />} />
                {/* ── CRM routes ── */}
                <Route path="/painel/crm" element={<CrmDashboard />} />
                <Route path="/painel/crm/inteligencia" element={<CrmInteligencia />} />
                <Route path="/painel/crm/pipeline" element={<CrmPipeline />} />
                <Route path="/painel/crm/grupos" element={<CrmGrupos />} />
                <Route path="/painel/crm/tarefas" element={<CrmTarefas />} />
                {/* ── Logistics routes ── */}
                <Route path="/painel/logistica" element={<AdminLogistica />} />
              </Route>

              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </AppProvider>
    </QueryClientProvider>
  );
}

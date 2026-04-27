import { lazy, Suspense, useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AppProvider, useApp } from "./context/AppContext";
import { themeApi, applyTheme, DEFAULT_THEME } from "./lib/themeApi";
import { captureTrackingFromUrl, trackEvent } from "./lib/tracking";

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
    applyTheme(DEFAULT_THEME);
    themeApi.get().then(applyTheme).catch(() => {});

    const handler = () => themeApi.get().then(applyTheme).catch(() => {});
    window.addEventListener("theme-updated", handler);
    return () => window.removeEventListener("theme-updated", handler);
  }, []);
  return null;
}

function PrimaryColorInjector() {
  const { siteContent } = useApp();
  const primaryColor = siteContent.theme?.primaryColor ?? "#f97316";
  useEffect(() => {
    const hex = primaryColor;
    const clean = hex.replace("#", "");
    const r = parseInt(clean.slice(0, 2), 16) / 255;
    const g = parseInt(clean.slice(2, 4), 16) / 255;
    const b = parseInt(clean.slice(4, 6), 16) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    const l = (max + min) / 2;
    let h = 0, s = 0;
    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
        case g: h = ((b - r) / d + 2) / 6; break;
        case b: h = ((r - g) / d + 4) / 6; break;
      }
    }
    const hsl = `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
    let el = document.getElementById("primary-color-override") as HTMLStyleElement | null;
    if (!el) {
      el = document.createElement("style");
      el.id = "primary-color-override";
      document.head.appendChild(el);
    }
    el.textContent = `
:root { --primary: ${hsl}; --accent: ${hsl}; --ring: ${hsl}; }
.bg-gold, [class*="bg-gold\\/"] { background-color: ${hex} !important; }
.text-gold, [class*="text-gold\\/"] { color: ${hex} !important; }
.border-gold, [class*="border-gold\\/"] { border-color: ${hex} !important; }
`;
  }, [primaryColor]);
  return null;
}

function TrackingInjector() {
  const { pathname, search } = useLocation();
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
  useEffect(() => {
    document.title = pageTitle || name || "Pizza Delivery App";
  }, [pageTitle, name]);
  useEffect(() => {
    if (!faviconUrl) return;
    let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']");
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      document.head.appendChild(link);
    }
    link.href = faviconUrl;
  }, [faviconUrl]);
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
import CrmDashboard from "./pages/admin/crm/CrmDashboard";
import CrmPipeline from "./pages/admin/crm/CrmPipeline";
import CrmGrupos from "./pages/admin/crm/CrmGrupos";
import CrmTarefas from "./pages/admin/crm/CrmTarefas";
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
        <PrimaryColorInjector />
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

              {/* ── Admin routes (protected by JWT guard) ── */}
              <Route element={<AdminGuard />}>
                <Route path="/painel" element={<AdminDashboard />} />
                <Route path="/painel/products" element={<AdminProducts />} />
                <Route path="/painel/orders" element={<AdminOrders />} />
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
                {/* ── CRM routes ── */}
                <Route path="/painel/crm" element={<CrmDashboard />} />
                <Route path="/painel/crm/pipeline" element={<CrmPipeline />} />
                <Route path="/painel/crm/grupos" element={<CrmGrupos />} />
                <Route path="/painel/crm/tarefas" element={<CrmTarefas />} />
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

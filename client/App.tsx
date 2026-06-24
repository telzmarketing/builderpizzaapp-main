import { Component, lazy, Suspense, useEffect, useRef, useState, type ErrorInfo, type ReactNode } from "react";
import { Toaster } from "@/components/ui/toaster";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AppProvider, useApp } from "./context/AppContext";
import { themeApi, applyTheme, DEFAULT_THEME, readCachedTheme } from "./lib/themeApi";
import { captureTrackingFromUrl, firePixelEvent, trackEvent, getTrackingData, initCampaignPixel, initStorePixels, isInternalStaffPath, requestVisitorLocation } from "./lib/tracking";
import { customerEventsApi, isAssetUrl, resolveAssetUrl } from "./lib/api";
import { getPublicExperience, isSalaoExperience } from "./lib/experience";

const ChatbotWidget = lazy(() => import("./components/ChatbotWidget"));
const StoreSocialProofNotification = lazy(() => import("./components/StoreSocialProofNotification"));
const CapacitorMotoboyEntry = lazy(() => import("./components/CapacitorMotoboyEntry"));
const StoreScreenshotProtection = lazy(() => import("./components/StoreScreenshotProtection"));

const CHUNK_RECOVERY_RELOAD_KEY = "mo_chunk_recovery_reloaded_at";
const CHUNK_RECOVERY_COOLDOWN_MS = 60_000;
const CHUNK_ERROR_PATTERNS = [
  "chunkloaderror",
  "loading chunk",
  "failed to fetch dynamically imported module",
  "dynamically imported module",
  "importing a module script failed",
  "failed to load module script",
  "expected a javascript-or-wasm module script",
  "error loading dynamically imported module",
  "load failed for module",
  "unable to preload css",
];

function getErrorMessage(reason: unknown): string {
  if (typeof reason === "string") return reason;
  if (reason instanceof Error) return reason.message;
  if (reason && typeof reason === "object" && "message" in reason) {
    return String((reason as { message?: unknown }).message || "");
  }
  return "";
}

function toSafeText(value: unknown, fallback = ""): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const text = value.map((item) => toSafeText(item)).filter(Boolean).join(", ");
    return text || fallback;
  }
  if (typeof value === "object") {
    const objectValue = value as Record<string, unknown>;
    const candidate =
      objectValue.title ?? objectValue.name ?? objectValue.label ?? objectValue.value ?? objectValue.url ?? objectValue.src;
    if (candidate !== undefined && candidate !== value) return toSafeText(candidate, fallback);
    return fallback;
  }
  return fallback;
}

function shouldRecoverFromChunkError(reason: unknown) {
  const message = getErrorMessage(reason).toLowerCase();
  return CHUNK_ERROR_PATTERNS.some((pattern) => message.includes(pattern));
}

function recoverFromChunkError() {
  const lastReload = Number(sessionStorage.getItem(CHUNK_RECOVERY_RELOAD_KEY) || 0);
  if (Date.now() - lastReload < CHUNK_RECOVERY_COOLDOWN_MS) return;

  sessionStorage.setItem(CHUNK_RECOVERY_RELOAD_KEY, String(Date.now()));
  window.location.reload();
}

function ChunkRecovery() {
  useEffect(() => {
    const clearRecoveryFlag = window.setTimeout(() => {
      sessionStorage.removeItem(CHUNK_RECOVERY_RELOAD_KEY);
    }, CHUNK_RECOVERY_COOLDOWN_MS);

    const onVitePreloadError = (event: Event) => {
      event.preventDefault();
      recoverFromChunkError();
    };

    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      if (!shouldRecoverFromChunkError(event.reason)) return;
      event.preventDefault();
      recoverFromChunkError();
    };

    const onError = (event: ErrorEvent) => {
      const target = event.target;
      const scriptSrc = target instanceof HTMLScriptElement ? target.src : "";
      if (!scriptSrc.includes("/assets/") && !shouldRecoverFromChunkError(event.message || event.error)) return;
      recoverFromChunkError();
    };

    window.addEventListener("vite:preloadError", onVitePreloadError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);
    window.addEventListener("error", onError, true);

    return () => {
      window.clearTimeout(clearRecoveryFlag);
      window.removeEventListener("vite:preloadError", onVitePreloadError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
      window.removeEventListener("error", onError, true);
    };
  }, []);

  return null;
}

function AppRouteFallback() {
  const isAdminRoute = window.location.pathname.startsWith("/painel");

  if (isAdminRoute) {
    return (
      <div className="min-h-screen bg-[#123f39] text-[#f8f1dc]">
        <div className="flex min-h-screen items-center justify-center px-6">
          <div className="rounded-lg border border-[#315a52] bg-[#173f38] px-6 py-5 text-sm font-semibold shadow-lg">
            Carregando painel...
          </div>
        </div>
      </div>
    );
  }

  return null;
}

function AppRouteErrorFallback() {
  const isAdminRoute = window.location.pathname.startsWith("/painel");

  return (
    <div className={isAdminRoute ? "min-h-screen bg-[#123f39] text-[#f8f1dc]" : "min-h-screen bg-white text-slate-900"}>
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className={isAdminRoute ? "max-w-md rounded-lg border border-[#315a52] bg-[#173f38] p-6 text-center shadow-lg" : "max-w-md rounded-lg border border-slate-200 bg-white p-6 text-center shadow-lg"}>
          <h1 className="text-lg font-black">Nao foi possivel carregar este modulo.</h1>
          <p className={isAdminRoute ? "mt-2 text-sm text-[#cbbf9f]" : "mt-2 text-sm text-slate-600"}>
            Atualize a pagina para buscar a versao mais recente do painel.
          </p>
          <button
            type="button"
            className={isAdminRoute ? "mt-5 rounded-md bg-[#c7a45d] px-4 py-2 text-sm font-black text-[#2b2118] transition hover:bg-[#d4b16b]" : "mt-5 rounded-md bg-slate-900 px-4 py-2 text-sm font-black text-white transition hover:bg-slate-700"}
            onClick={() => window.location.reload()}
          >
            Recarregar painel
          </button>
        </div>
      </div>
    </div>
  );
}

type AppErrorBoundaryState = {
  hasError: boolean;
};

class AppErrorBoundary extends Component<{ children: ReactNode }, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown, errorInfo: ErrorInfo) {
    if (shouldRecoverFromChunkError(error) || shouldRecoverFromChunkError(errorInfo.componentStack)) {
      recoverFromChunkError();
    }
  }

  render() {
    if (this.state.hasError) return <AppRouteErrorFallback />;
    return this.props.children;
  }
}

function useDeferredClientMount(delay = 1200) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let idleId: number | undefined;
    const timerId = window.setTimeout(() => {
      const requestIdle = window.requestIdleCallback;
      if (requestIdle) {
        idleId = requestIdle(() => setReady(true), { timeout: 1000 });
        return;
      }
      setReady(true);
    }, delay);

    return () => {
      window.clearTimeout(timerId);
      if (idleId !== undefined) window.cancelIdleCallback?.(idleId);
    };
  }, [delay]);

  return ready;
}

function hasNativeCapacitorBridge() {
  const bridge = (window as Window & {
    Capacitor?: { isNativePlatform?: () => boolean };
  }).Capacitor;
  try {
    return !!bridge?.isNativePlatform?.();
  } catch {
    return false;
  }
}

function MotoboyNativeEntry() {
  const { pathname } = useLocation();
  const shouldLoad = pathname.startsWith("/motoboy") || hasNativeCapacitorBridge();

  if (!shouldLoad) return null;
  return (
    <Suspense fallback={null}>
      <CapacitorMotoboyEntry />
    </Suspense>
  );
}

function RouteDataLoader() {
  const { pathname } = useLocation();
  const { loadRouteData } = useApp();
  const firstRun = useRef(true);

  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    loadRouteData(pathname).catch(() => {});
  }, [loadRouteData, pathname]);

  return null;
}

function StoreWidget() {
  const { pathname } = useLocation();
  const ready = useDeferredClientMount(2500);
  if (isSalaoExperience()) return null;

  const storeRoutes = [
    "/",
    "/product",
    "/cart",
    "/checkout",
    "/order-tracking",
    "/fidelidade",
    "/cupons",
    "/pedidos",
    "/conta",
    "/localizacao",
    "/cardapio",
    "/campanha",
    "/promocao",
  ];
  const isStoreRoute = storeRoutes.some((route) => (
    route === "/" ? pathname === "/" : pathname === route || pathname.startsWith(`${route}/`)
  ));
  if (!isStoreRoute || !ready) return null;
  return (
    <>
      <Suspense fallback={null}>
        <ChatbotWidget />
      </Suspense>
      <Suspense fallback={null}>
        <StoreSocialProofNotification />
      </Suspense>
    </>
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
    if (isInternalStaffPath(pathname)) return;
    if (sessionStorage.getItem("_mo_site_opened")) return;
    sessionStorage.setItem("_mo_site_opened", "1");
    const openingTimer = window.setTimeout(() => {
      const td = getTrackingData();
      if (isSalaoExperience()) {
        customerEventsApi.register({
          event_type: "salao_site_opened",
          event_name: "Abriu pagina do salao",
          session_id: td.session_id,
          utm_source: td.utm_source,
          utm_medium: td.utm_medium,
          utm_campaign: td.utm_campaign,
          page_url: window.location.href,
          referrer_url: td.referrer,
        }).catch(() => {});
        return;
      }

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
    }, 1800);
    const locationTimer = window.setTimeout(requestVisitorLocation, 3500);

    return () => {
      window.clearTimeout(openingTimer);
      window.clearTimeout(locationTimer);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (isInternalStaffPath(pathname)) return;
    const data = captureTrackingFromUrl();
    trackEvent("page_view");
    if (isSalaoExperience()) return;

    const pixelTimer = window.setTimeout(() => {
      const pixelTasks = [initStorePixels()];
      if (data.campaign_id) pixelTasks.push(initCampaignPixel(data.campaign_id));
      Promise.all(pixelTasks).then(() => firePixelEvent("PageView")).catch(() => {});
    }, 3000);
    return () => window.clearTimeout(pixelTimer);
  }, [pathname, search]);
  return null;
}

function DocumentHead() {
  const { siteContent } = useApp();
  const isSalao = isSalaoExperience();
  const { pageTitle, faviconUrl, name } = siteContent.brand;

  const safePageTitle = toSafeText(pageTitle);
  const safeName = toSafeText(name);
  const safeFaviconUrl = toSafeText(faviconUrl);
  const resolvedFavicon = safeFaviconUrl && isAssetUrl(safeFaviconUrl) ? resolveAssetUrl(safeFaviconUrl) : "/favicon.ico";

  useEffect(() => {
    if (isSalao) {
      document.title = "Moschettieri | Restaurante";
      return;
    }
    document.title = safePageTitle || safeName || "Pizza Delivery App";
  }, [isSalao, safePageTitle, safeName]);

  useEffect(() => {
    const favicon = resolvedFavicon || "/favicon.ico";

    document
      .querySelectorAll<HTMLLinkElement>("link[rel~='icon'], link[rel='apple-touch-icon']")
      .forEach((link) => link.remove());

    const separator = favicon.includes("?") ? "&" : "?";
    const href = favicon.startsWith("data:")
      ? favicon
      : `${favicon}${separator}v=${Date.now()}`;

    const icon = document.createElement("link");
    icon.rel = "icon";
    icon.type = favicon.endsWith(".ico") ? "image/x-icon" : "image/png";
    icon.href = href;
    document.head.appendChild(icon);

    const shortcut = document.createElement("link");
    shortcut.rel = "shortcut icon";
    shortcut.href = href;
    document.head.appendChild(shortcut);

    const apple = document.createElement("link");
    apple.rel = "apple-touch-icon";
    apple.href = "/icons/icon-192.png";
    document.head.appendChild(apple);
  }, [resolvedFavicon]);
  return null;
}
const AdminGuard = lazy(() => import("./components/AdminGuard"));
const AdminLayout = lazy(() => import("./components/layout/AdminLayout"));
const Index = lazy(() => import("./pages/Index"));
const Product = lazy(() => import("./pages/Product"));
const Cart = lazy(() => import("./pages/Cart"));
const Checkout = lazy(() => import("./pages/Checkout"));
const OrderTracking = lazy(() => import("./pages/OrderTracking"));
const AdminLogin = lazy(() => import("./pages/admin/Login"));
const AdminDashboard = lazy(() => import("./pages/admin/Dashboard"));
const AdminProducts = lazy(() => import("./pages/admin/Products"));
const AdminOrders = lazy(() => import("./pages/admin/Orders"));
const AdminCozinha = lazy(() => import("./pages/admin/Cozinha"));
const AdminFidelidade = lazy(() => import("./pages/admin/AdminFidelidade"));
const AdminConteudo = lazy(() => import("./pages/admin/Conteudo"));
const AdminPagamentos = lazy(() => import("./pages/admin/AdminPagamentos"));
const AdminFrete = lazy(() => import("./pages/admin/AdminFrete"));
const StoreOperation = lazy(() => import("./pages/admin/StoreOperation"));
const AdminCampanhas = lazy(() => import("./pages/admin/AdminCampanhas"));
const AdminPaidTraffic = lazy(() => import("./pages/admin/PaidTraffic"));
const AdminChatbot = lazy(() => import("./pages/admin/AdminChatbot"));
const AdminAparencia = lazy(() => import("./pages/admin/Aparencia"));
const AdminHomeConfig = lazy(() => import("./pages/admin/HomeConfig"));
const AdminLgpd = lazy(() => import("./pages/admin/AdminLgpd"));
const AdminConfiguracoes = lazy(() => import("./pages/admin/AdminConfiguracoes"));
const AdminClientes = lazy(() => import("./pages/admin/AdminClientes"));
const ClienteDetalhe = lazy(() => import("./pages/admin/ClienteDetalhe"));
const AdminExitPopup = lazy(() => import("./pages/admin/AdminExitPopup"));
const AdminUsuarios = lazy(() => import("./pages/admin/AdminUsuarios"));
const AdminBI = lazy(() => import("./pages/admin/bi/BiDashboard"));
const AdminBIMobile = lazy(() => import("./pages/admin/bi/BiMobile"));
const ExitPopup = lazy(() => import("./components/ExitPopup"));
const MarketingDashboard = lazy(() => import("./pages/admin/marketing/MarketingDashboard"));
const MarketingIntelligence = lazy(() => import("./pages/admin/marketing/MarketingIntelligence"));
const MarketingVisitantes = lazy(() => import("./pages/admin/marketing/MarketingVisitantes"));
const MarketingLinks = lazy(() => import("./pages/admin/marketing/MarketingLinks"));
const MarketingIntegracoes = lazy(() => import("./pages/admin/marketing/MarketingIntegracoes"));
const WhatsAppGateway = lazy(() => import("./pages/admin/whatsapp/WhatsAppGateway"));
const MarketingWhatsApp = lazy(() => import("./pages/admin/marketing/MarketingWhatsApp"));
const MarketingEmail = lazy(() => import("./pages/admin/marketing/MarketingEmail"));
const MarketingAutomacoes = lazy(() => import("./pages/admin/marketing/MarketingAutomacoes"));
const MarketingWorkflow = lazy(() => import("./pages/admin/marketing/MarketingWorkflow"));
const MarketingCupons = lazy(() => import("./pages/admin/marketing/MarketingCupons"));
const MarketingStoreNotifications = lazy(() => import("./pages/admin/marketing/MarketingStoreNotifications"));
const MarketingUpsell = lazy(() => import("./pages/admin/marketing/MarketingUpsell"));
const CrmDashboard = lazy(() => import("./pages/admin/crm/CrmDashboard"));
const CrmPipeline = lazy(() => import("./pages/admin/crm/CrmPipeline"));
const CrmGrupos = lazy(() => import("./pages/admin/crm/CrmGrupos"));
const CrmTarefas = lazy(() => import("./pages/admin/crm/CrmTarefas"));
const CrmInteligencia = lazy(() => import("./pages/admin/crm/CrmInteligencia"));
const CrmAgenteWhatsApp = lazy(() => import("./pages/admin/crm/CrmAgenteWhatsApp"));
const AdminLogistica = lazy(() => import("./pages/admin/logistica/AdminLogistica"));
const AdminSalao = lazy(() => import("./pages/admin/salao/AdminSalao"));
const AdminSalaoPage = lazy(() => import("./pages/admin/salao/AdminSalaoPage"));
const PromotionalLandingEditor = lazy(() => import("./pages/admin/PromotionalLandingEditor"));
const Motoboy = lazy(() => import("./pages/Motoboy"));
const Campanha = lazy(() => import("./pages/Campanha"));
const PromocaoLanding = lazy(() => import("./pages/PromocaoLanding"));
const Fidelidade = lazy(() => import("./pages/Fidelidade"));
const Cupons = lazy(() => import("./pages/Cupons"));
const Pedidos = lazy(() => import("./pages/Pedidos"));
const Conta = lazy(() => import("./pages/Conta"));
const Localizacao = lazy(() => import("./pages/Localizacao"));
const Cardapio = lazy(() => import("./pages/Cardapio"));
const SalaoHome = lazy(() => import("./pages/salao/SalaoHome"));
const NotFound = lazy(() => import("./pages/NotFound"));

function PublicHome() {
  return getPublicExperience() === "salao" ? <SalaoHome /> : <Index />;
}

function ExperienceRoute({ salao, delivery }: { salao: JSX.Element; delivery: JSX.Element }) {
  return getPublicExperience() === "salao" ? salao : delivery;
}

export default function App() {
  const deferredWidgetsReady = useDeferredClientMount(3200);

  return (
    <AppProvider>
      <AppErrorBoundary>
        <ChunkRecovery />
        <DocumentHead />
        <ThemeInjector />
          <Toaster />
          <BrowserRouter>
            <MotoboyNativeEntry />
            <RouteDataLoader />
            <StoreWidget />
            <TrackingInjector />
            {!isSalaoExperience() && deferredWidgetsReady && (
              <Suspense fallback={null}>
                <ExitPopup />
              </Suspense>
            )}
            <Suspense fallback={<AppRouteFallback />}>
            <Routes>
              {/* ── Customer routes ── */}
              <Route element={<StoreScreenshotProtection />}>
                <Route path="/" element={<PublicHome />} />
                <Route path="/product/:id" element={<Product />} />
                <Route path="/menu" element={<ExperienceRoute salao={<SalaoHome />} delivery={<Cardapio />} />} />
                <Route path="/cardapio" element={<ExperienceRoute salao={<SalaoHome />} delivery={<Cardapio />} />} />
                <Route path="/campanha/:slug" element={<Campanha />} />
                <Route path="/promocao/:slug" element={<PromocaoLanding />} />
              </Route>
              <Route path="/cart" element={<Cart />} />
              <Route path="/checkout" element={<Checkout />} />
              <Route path="/order-tracking" element={<OrderTracking />} />
              <Route path="/fidelidade" element={<Fidelidade />} />
              <Route path="/cupons" element={<Cupons />} />
              <Route path="/pedidos" element={<Pedidos />} />
              <Route path="/conta" element={<Conta />} />
              <Route path="/localizacao" element={<Localizacao />} />
              <Route path="/blog" element={<ExperienceRoute salao={<SalaoHome />} delivery={<NotFound />} />} />
              <Route path="/sobre" element={<ExperienceRoute salao={<SalaoHome />} delivery={<NotFound />} />} />
              <Route path="/galeria" element={<ExperienceRoute salao={<SalaoHome />} delivery={<NotFound />} />} />
              <Route path="/pessoas" element={<ExperienceRoute salao={<SalaoHome />} delivery={<NotFound />} />} />
              <Route path="/certificados" element={<ExperienceRoute salao={<SalaoHome />} delivery={<NotFound />} />} />
              <Route path="/duvidas" element={<ExperienceRoute salao={<SalaoHome />} delivery={<NotFound />} />} />
              <Route path="/reservas" element={<ExperienceRoute salao={<SalaoHome />} delivery={<NotFound />} />} />
              <Route path="/contato" element={<ExperienceRoute salao={<SalaoHome />} delivery={<NotFound />} />} />
              <Route path="/login-cadastro" element={<ExperienceRoute salao={<SalaoHome />} delivery={<NotFound />} />} />
              <Route path="/minha-conta" element={<ExperienceRoute salao={<SalaoHome />} delivery={<NotFound />} />} />

              {/* ── Admin login (public) ── */}
              <Route path="/painel/login" element={<AdminLogin />} />
              <Route path="/motoboy" element={<Motoboy />} />

              {/* ── Admin routes (protected by JWT guard) ── */}
              <Route element={<AdminGuard />}>
                <Route path="/painel/bi-mobile" element={<AdminBIMobile />} />
                <Route element={<AdminLayout />}>
                <Route path="/painel" element={<AdminDashboard />} />
                <Route path="/painel/whatsapp-gateway" element={<WhatsAppGateway />} />
                <Route path="/painel/products" element={<AdminProducts />} />
                <Route path="/painel/products/landing/:productId/:promotionId" element={<PromotionalLandingEditor />} />
                <Route path="/painel/orders" element={<AdminOrders />} />
                <Route path="/painel/cozinha" element={<AdminCozinha />} />
                <Route path="/painel/salao" element={<AdminSalao />} />
                <Route path="/painel/fidelidade" element={<AdminFidelidade />} />
                <Route path="/painel/conteudo" element={<AdminConteudo />} />
                <Route path="/painel/pagamentos" element={<AdminPagamentos />} />
                <Route path="/painel/frete" element={<AdminFrete />} />
                <Route path="/painel/funcionamento" element={<StoreOperation />} />
                <Route path="/painel/campanhas" element={<AdminCampanhas />} />
                <Route path="/painel/trafego-pago" element={<AdminPaidTraffic />} />
                <Route path="/painel/chatbot"    element={<AdminChatbot />} />
                <Route path="/painel/aparencia" element={<AdminAparencia />} />
                <Route path="/painel/salao/pagina" element={<AdminSalaoPage />} />
                <Route path="/painel/home-config" element={<AdminHomeConfig />} />
                <Route path="/painel/lgpd" element={<AdminLgpd />} />
                <Route path="/painel/configuracoes" element={<AdminConfiguracoes />} />
                <Route path="/painel/cupons" element={<MarketingCupons />} />
                <Route path="/painel/clientes" element={<AdminClientes />} />
                <Route path="/painel/clientes/:id" element={<ClienteDetalhe />} />
                <Route path="/painel/popup-saida" element={<AdminExitPopup />} />
                <Route path="/painel/usuarios" element={<AdminUsuarios />} />
                <Route path="/painel/bi" element={<AdminBI />} />
                {/* ── Marketing routes ── */}
                <Route path="/painel/marketing" element={<MarketingDashboard />} />
                <Route path="/painel/marketing-intelligence" element={<MarketingIntelligence />} />
                <Route path="/painel/marketing/visitantes" element={<MarketingVisitantes />} />
                <Route path="/painel/marketing/links" element={<MarketingLinks />} />
                <Route path="/painel/marketing/integracoes" element={<MarketingIntegracoes />} />
                <Route path="/painel/marketing/whatsapp" element={<MarketingWhatsApp />} />
                <Route path="/painel/marketing/email" element={<MarketingEmail />} />
                <Route path="/painel/marketing/automacoes" element={<MarketingAutomacoes />} />
                <Route path="/painel/marketing/ads" element={<AdminPaidTraffic />} />
                <Route path="/painel/marketing/workflow" element={<MarketingWorkflow />} />
                <Route path="/painel/marketing/cupons" element={<MarketingCupons />} />
                <Route path="/painel/marketing/notificacoes" element={<MarketingStoreNotifications />} />
                <Route path="/painel/marketing/upsell" element={<MarketingUpsell />} />
                {/* ── CRM routes ── */}
                <Route path="/painel/crm" element={<CrmDashboard />} />
                <Route path="/painel/crm/inteligencia" element={<CrmInteligencia />} />
                <Route path="/painel/crm/pipeline" element={<CrmPipeline />} />
                <Route path="/painel/crm/grupos" element={<CrmGrupos />} />
                <Route path="/painel/crm/tarefas" element={<CrmTarefas />} />
                <Route path="/painel/crm/agente-whatsapp" element={<CrmAgenteWhatsApp />} />
                {/* ── Logistics routes ── */}
                <Route path="/painel/logistica" element={<AdminLogistica />} />
                </Route>
              </Route>

              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
            </Suspense>
          </BrowserRouter>
      </AppErrorBoundary>
    </AppProvider>
  );
}

import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppProvider, useApp } from "./context/AppContext";

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
import AdminCampanhas from "./pages/admin/AdminCampanhas";
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
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
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
                <Route path="/painel/campanhas" element={<AdminCampanhas />} />
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

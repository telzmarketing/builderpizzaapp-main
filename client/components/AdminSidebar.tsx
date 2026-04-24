import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3,
  Package,
  ShoppingBag,
  ArrowLeft,
  Trophy,
  FileText,
  CreditCard,
  Truck,
  LogOut,
  Sparkles,
  MessageCircle,
  Palette,
  LayoutDashboard,
  MousePointerClick,
  User,
} from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { useApp } from "@/context/AppContext";

const navItems = [
  { to: "/painel", icon: BarChart3, label: "Dashboard" },
  { to: "/painel/products", icon: Package, label: "Produtos" },
  { to: "/painel/home-config", icon: LayoutDashboard, label: "Catálogo da Home" },
  { to: "/painel/orders", icon: ShoppingBag, label: "Pedidos" },
  { to: "/painel/trafego-pago", icon: MousePointerClick, label: "Tráfego Pago" },
  { to: "/painel/campanhas", icon: Sparkles, label: "Promoções & Campanhas" },
  { to: "/painel/fidelidade", icon: Trophy, label: "Fidelidade" },
  { to: "/painel/conteudo", icon: FileText, label: "Conteúdo" },
  { to: "/painel/pagamentos", icon: CreditCard, label: "Pagamentos" },
  { to: "/painel/frete", icon: Truck, label: "Entregas e Fretes" },
  { to: "/painel/chatbot", icon: MessageCircle, label: "Chatbot" },
  { to: "/painel/aparencia", icon: Palette, label: "Aparência" },
];

function getInitials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase() ?? "")
    .join("");
}

export default function AdminSidebar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { siteContent } = useApp();

  const adminUserRaw = localStorage.getItem("admin_user");
  const adminUser = adminUserRaw ? JSON.parse(adminUserRaw) : null;
  const adminName: string = adminUser?.name ?? "Administrador";
  const adminEmail: string = adminUser?.email ?? "";
  const initials = getInitials(adminName);

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    navigate("/painel/login");
  };

  const { brand } = siteContent;

  const isActive = (to: string) => {
    if (to === "/painel") return pathname === "/painel";
    return pathname.startsWith(to);
  };

  return (
    <div className="w-64 bg-surface-02 border-r border-surface-03 flex flex-col flex-shrink-0 h-screen">

      {/* Brand / Logo */}
      <div className="px-5 pt-5 pb-4 border-b border-surface-03 flex-shrink-0">
        <div className="flex items-center gap-3">
          {brand.logo && (brand.logo.startsWith("http") || brand.logo.startsWith("data:")) ? (
            <img src={brand.logo} alt="logo" className="w-8 h-8 object-contain rounded flex-shrink-0" />
          ) : brand.logo ? (
            <span className="text-xl flex-shrink-0">{brand.logo}</span>
          ) : null}
          <div className="min-w-0">
            <MoschettieriLogo className="text-gold text-sm leading-tight" />
            <p className="text-stone text-[10px] truncate mt-0.5">Painel administrativo</p>
          </div>
        </div>
      </div>

      {/* Admin profile card */}
      <div className="px-4 py-4 border-b border-surface-03 flex-shrink-0">
        <div className="flex items-center gap-3 bg-surface-03/50 rounded-xl px-3 py-3">
          <div className="w-9 h-9 rounded-full bg-gold/20 border border-gold/30 flex items-center justify-center flex-shrink-0">
            {initials ? (
              <span className="text-gold text-xs font-bold">{initials}</span>
            ) : (
              <User size={16} className="text-gold" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-cream text-xs font-semibold truncate">{adminName}</p>
            {adminEmail && (
              <p className="text-stone text-[10px] truncate">{adminEmail}</p>
            )}
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
        {navItems.map(({ to, icon: Icon, label }) => (
          <Link
            key={to}
            to={to}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              isActive(to)
                ? "bg-gold text-cream shadow-sm"
                : "text-stone hover:bg-surface-03 hover:text-parchment"
            }`}
          >
            <Icon size={17} className="flex-shrink-0" />
            <span className="truncate">{label}</span>
          </Link>
        ))}
      </nav>

      {/* Bottom actions */}
      <div className="px-3 py-3 border-t border-surface-03 space-y-0.5 flex-shrink-0">
        <Link
          to="/"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-stone hover:bg-surface-03 hover:text-parchment transition-colors"
        >
          <ArrowLeft size={17} className="flex-shrink-0" />
          <span>Voltar ao App</span>
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <LogOut size={17} className="flex-shrink-0" />
          <span>Sair</span>
        </button>
      </div>
    </div>
  );
}

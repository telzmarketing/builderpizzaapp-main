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
} from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { useApp } from "@/context/AppContext";

const navItems = [
  { to: "/painel", icon: BarChart3, label: "Dashboard" },
  { to: "/painel/products", icon: Package, label: "Produtos" },
  { to: "/painel/home-config", icon: LayoutDashboard, label: "Catálogo da Home" },
  { to: "/painel/orders", icon: ShoppingBag, label: "Pedidos" },
  { to: "/painel/campanhas", icon: Sparkles, label: "Promoções & Campanhas" },
  { to: "/painel/fidelidade", icon: Trophy, label: "Fidelidade" },
  { to: "/painel/conteudo", icon: FileText, label: "Conteúdo" },
  { to: "/painel/pagamentos", icon: CreditCard, label: "Pagamentos" },
  { to: "/painel/frete", icon: Truck, label: "Entregas e Fretes" },
  { to: "/painel/chatbot",    icon: MessageCircle, label: "Chatbot" },
  { to: "/painel/aparencia",  icon: Palette,       label: "Aparência" },
];

export default function AdminSidebar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { siteContent } = useApp();

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
    <div className="w-64 bg-surface-02 border-r border-surface-03 p-6 flex flex-col flex-shrink-0">
      <div className="mb-8 flex items-center gap-3">
        {brand.logo && (brand.logo.startsWith("http") || brand.logo.startsWith("data:")) ? (
          <img src={brand.logo} alt="logo" className="w-8 h-8 object-contain rounded flex-shrink-0" />
        ) : brand.logo ? (
          <span className="text-2xl flex-shrink-0">{brand.logo}</span>
        ) : null}
        <div className="min-w-0">
          <MoschettieriLogo className="text-gold text-lg" />
          <p className="text-stone text-xs truncate">{brand.tagline}</p>
        </div>
      </div>

      <nav className="space-y-2 flex-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <Link
            key={to}
            to={to}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg font-medium transition-colors ${
              isActive(to)
                ? "bg-gold text-cream"
                : "text-parchment hover:bg-surface-03"
            }`}
          >
            <Icon size={20} />
            {label}
          </Link>
        ))}
      </nav>

      <div className="space-y-1">
        <Link
          to="/"
          className="flex items-center gap-3 px-4 py-3 rounded-lg text-parchment hover:bg-surface-03 transition-colors"
        >
          <ArrowLeft size={20} />
          Voltar ao App
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <LogOut size={20} />
          Sair
        </button>
      </div>
    </div>
  );
}

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

const navSections = [
  {
    label: "Operacao",
    items: [
      { to: "/painel", icon: BarChart3, label: "Dashboard" },
      { to: "/painel/orders", icon: ShoppingBag, label: "Pedidos" },
      { to: "/painel/frete", icon: Truck, label: "Entregas e Fretes" },
      { to: "/painel/pagamentos", icon: CreditCard, label: "Pagamentos" },
    ],
  },
  {
    label: "Cardapio",
    items: [
      { to: "/painel/products", icon: Package, label: "Produtos" },
      { to: "/painel/home-config", icon: LayoutDashboard, label: "Catalogo da Home" },
      { to: "/painel/campanhas", icon: Sparkles, label: "Promocoes & Campanhas" },
      { to: "/painel/fidelidade", icon: Trophy, label: "Fidelidade" },
    ],
  },
  {
    label: "Experiencia",
    items: [
      { to: "/painel/conteudo", icon: FileText, label: "Conteudo" },
      { to: "/painel/aparencia", icon: Palette, label: "Aparencia" },
      { to: "/painel/chatbot", icon: MessageCircle, label: "Chatbot" },
    ],
  },
];

export default function AdminSidebar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { siteContent } = useApp();
  const { brand } = siteContent;

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    navigate("/painel/login");
  };

  const isActive = (to: string) => {
    if (to === "/painel") return pathname === "/painel";
    return pathname.startsWith(to);
  };

  const navClass = (active: boolean) =>
    `group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-all ${
      active
        ? "bg-gold/15 text-gold border border-gold/25 shadow-sm shadow-black/10"
        : "border border-transparent text-parchment/80 hover:bg-surface-03/80 hover:text-cream"
    }`;

  return (
    <aside className="w-[280px] bg-surface-02/95 border-r border-surface-03 flex flex-col flex-shrink-0">
      <div className="px-5 pt-5 pb-4 border-b border-surface-03/80">
        <div className="flex items-center justify-center rounded-xl bg-surface-03/45 border border-surface-03 px-4 py-4">
          <MoschettieriLogo className="text-[24px] scale-[1.08] origin-center" />
        </div>
        <p className="mt-3 text-center text-stone text-xs truncate">{brand.tagline}</p>
      </div>

      <nav className="flex-1 overflow-y-auto px-4 py-5 space-y-5">
        {navSections.map((section) => (
          <div key={section.label}>
            <p className="px-3 pb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-stone/80">
              {section.label}
            </p>
            <div className="space-y-1.5">
              {section.items.map(({ to, icon: Icon, label }) => {
                const active = isActive(to);
                return (
                  <Link key={to} to={to} className={navClass(active)}>
                    {active && <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-gold" />}
                    <span
                      className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                        active ? "bg-gold text-cream" : "bg-surface-03 text-stone group-hover:text-gold"
                      }`}
                    >
                      <Icon size={17} />
                    </span>
                    <span className="min-w-0 truncate">{label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-surface-03/80 p-4 space-y-2">
        <Link
          to="/"
          className="flex items-center gap-3 rounded-xl border border-surface-03 bg-surface-03/45 px-3 py-2.5 text-sm font-semibold text-parchment hover:text-cream hover:border-gold/30 transition-colors"
        >
          <ArrowLeft size={17} className="text-gold" />
          Voltar ao App
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <LogOut size={17} />
          Sair
        </button>
      </div>
    </aside>
  );
}

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
    `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition-all ${
      active
        ? "bg-cream text-brand-dark border border-cream shadow-sm shadow-black/10"
        : "border border-transparent text-parchment/80 hover:bg-cream/10 hover:text-cream"
    }`;

  return (
    <aside className="admin-sidebar w-[74px] lg:w-[268px] bg-brand-dark border border-surface-03/80 flex flex-col flex-shrink-0">
      <div className="px-3 lg:px-5 pt-4 lg:pt-5 pb-4 border-b border-cream/10">
        <div className="hidden lg:flex items-center justify-center rounded-lg bg-cream/5 border border-cream/10 px-4 py-4">
          <MoschettieriLogo className="text-[24px] scale-[1.08] origin-center" />
        </div>
        <div className="lg:hidden flex h-11 w-11 items-center justify-center rounded-lg bg-cream/10 border border-cream/10 mx-auto">
          <span className="font-serif text-xl font-bold text-gold leading-none">M</span>
        </div>
        <div className="hidden lg:flex mt-4 items-center gap-3 rounded-lg border border-cream/10 bg-surface-00/45 px-3 py-3">
          <div className="h-9 w-9 rounded-lg bg-gold/15 text-gold flex items-center justify-center font-bold">A</div>
          <div className="min-w-0">
            <p className="text-cream text-sm font-bold truncate">Administrativo</p>
            <p className="text-stone text-xs truncate">{brand.tagline || "Moschettieri"}</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 lg:px-4 py-4 lg:py-5 space-y-4 lg:space-y-5">
        {navSections.map((section) => (
          <div key={section.label}>
            <p className="hidden lg:block px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-stone/80">
              {section.label}
            </p>
            <div className="space-y-1.5">
              {section.items.map(({ to, icon: Icon, label }) => {
                const active = isActive(to);
                return (
                  <Link key={to} to={to} title={label} className={`${navClass(active)} justify-center lg:justify-start`}>
                    {active && <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-gold" />}
                    <span
                      className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                        active ? "bg-brand-dark text-gold" : "bg-cream/10 text-stone group-hover:text-gold"
                      }`}
                    >
                      <Icon size={17} />
                    </span>
                    <span className="hidden lg:block min-w-0 truncate">{label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-cream/10 p-2 lg:p-4 space-y-2">
        <Link
          to="/"
          title="Voltar ao App"
          className="flex items-center justify-center lg:justify-start gap-3 rounded-lg border border-cream/10 bg-cream/5 px-3 py-2.5 text-sm font-semibold text-parchment hover:text-cream hover:border-gold/30 transition-colors"
        >
          <ArrowLeft size={17} className="text-gold" />
          <span className="hidden lg:block">Voltar ao App</span>
        </Link>
        <button
          onClick={handleLogout}
          title="Sair"
          className="w-full flex items-center justify-center lg:justify-start gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <LogOut size={17} />
          <span className="hidden lg:block">Sair</span>
        </button>
      </div>
    </aside>
  );
}

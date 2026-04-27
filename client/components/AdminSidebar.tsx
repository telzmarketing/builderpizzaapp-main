import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3, Package, ShoppingBag, ArrowLeft, Trophy, FileText,
  CreditCard, Truck, LogOut, Sparkles, MessageCircle, Palette,
  LayoutDashboard, MousePointerClick, User, Users, Clock, Shield, Printer, Tag, LogIn,
  TrendingUp, Megaphone, Eye, LinkIcon, Plug, KanbanSquare, UserCheck, ClipboardList,
  Mail, Zap,
} from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { useApp } from "@/context/AppContext";

type NavItem = { to: string; icon: React.ElementType; label: string };
type NavGroup = { label: string; items: NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Visão Geral",
    items: [
      { to: "/painel", icon: BarChart3, label: "Dashboard" },
    ],
  },
  {
    label: "Catálogo",
    items: [
      { to: "/painel/products", icon: Package, label: "Produtos" },
      { to: "/painel/home-config", icon: LayoutDashboard, label: "Catálogo da Home" },
    ],
  },
  {
    label: "Operações",
    items: [
      { to: "/painel/orders", icon: ShoppingBag, label: "Pedidos" },
      { to: "/painel/clientes", icon: User, label: "Clientes" },
      { to: "/painel/trafego-pago", icon: MousePointerClick, label: "Tráfego Pago" },
    ],
  },
  {
    label: "Marketing",
    items: [
      { to: "/painel/marketing", icon: TrendingUp, label: "Dashboard Marketing" },
      { to: "/painel/marketing/campanhas", icon: Megaphone, label: "Campanhas" },
      { to: "/painel/marketing/visitantes", icon: Eye, label: "Análise de Visitantes" },
      { to: "/painel/marketing/links", icon: LinkIcon, label: "Links Rastreáveis" },
      { to: "/painel/marketing/integracoes", icon: Plug, label: "Integrações" },
      { to: "/painel/marketing/whatsapp", icon: MessageCircle, label: "WhatsApp Marketing" },
      { to: "/painel/marketing/email", icon: Mail, label: "E-mail Marketing" },
      { to: "/painel/marketing/automacoes", icon: Zap, label: "Automações" },
      { to: "/painel/marketing/ads", icon: BarChart3, label: "Painel de Anúncios" },
      { to: "/painel/campanhas", icon: Sparkles, label: "Promoções & Banners" },
      { to: "/painel/cupons", icon: Tag, label: "Cupons de Desconto" },
      { to: "/painel/fidelidade", icon: Trophy, label: "Fidelidade" },
      { to: "/painel/popup-saida", icon: LogIn, label: "Popup de Saída" },
    ],
  },
  {
    label: "CRM",
    items: [
      { to: "/painel/crm", icon: BarChart3, label: "Dashboard CRM" },
      { to: "/painel/crm/pipeline", icon: KanbanSquare, label: "Pipeline" },
      { to: "/painel/crm/grupos", icon: UserCheck, label: "Grupos & Segmentações" },
      { to: "/painel/crm/tarefas", icon: ClipboardList, label: "Tarefas" },
    ],
  },
  {
    label: "Configurações",
    items: [
      { to: "/painel/conteudo", icon: FileText, label: "Conteúdo" },
      { to: "/painel/pagamentos", icon: CreditCard, label: "Pagamentos" },
      { to: "/painel/frete", icon: Truck, label: "Entregas e Fretes" },
      { to: "/painel/funcionamento", icon: Clock, label: "Funcionamento da Loja" },
      { to: "/painel/chatbot", icon: MessageCircle, label: "Chatbot" },
      { to: "/painel/aparencia", icon: Palette, label: "Aparência" },
      { to: "/painel/usuarios", icon: Users, label: "Usuários do Sistema" },
      { to: "/painel/lgpd", icon: Shield, label: "LGPD & Privacidade" },
      { to: "/painel/configuracoes", icon: Printer, label: "Impressora & Modelos" },
    ],
  },
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

  const EXACT_ROUTES = new Set(["/painel", "/painel/marketing", "/painel/crm"]);
  const isActive = (to: string) =>
    EXACT_ROUTES.has(to) ? pathname === to : pathname.startsWith(to);

  return (
    <div className="w-full md:w-64 bg-surface-02 border-b md:border-b-0 md:border-r border-surface-03 flex flex-col flex-shrink-0 h-auto md:h-screen max-h-[52vh] md:max-h-none">

      {/* ── Brand header ─────────────────────────────────────────────── */}
      <div className="px-4 md:px-5 pt-4 md:pt-5 pb-3 md:pb-4 border-b border-surface-03 flex-shrink-0">
        <div className="flex items-center gap-3">
          {brand.logo && (brand.logo.startsWith("http") || brand.logo.startsWith("data:")) ? (
            <img
              src={brand.logo}
              alt="logo"
              className="w-8 h-8 object-contain rounded-lg flex-shrink-0 border border-surface-03"
            />
          ) : brand.logo ? (
            <span className="text-xl flex-shrink-0">{brand.logo}</span>
          ) : null}
          <div className="min-w-0">
            <MoschettieriLogo className="text-gold text-sm leading-tight" />
            <p className="text-stone text-[10px] truncate mt-0.5">Painel administrativo</p>
          </div>
        </div>
      </div>

      {/* ── Admin profile card ───────────────────────────────────────── */}
      <div className="hidden md:block px-4 py-3 border-b border-surface-03 flex-shrink-0">
        <div className="flex items-center gap-3 bg-surface-01 rounded-xl px-3 py-2.5 border border-surface-03/60">
          {/* Avatar with online dot */}
          <div className="relative flex-shrink-0">
            <div className="w-9 h-9 rounded-full bg-gold/20 border border-gold/40 flex items-center justify-center">
              {initials ? (
                <span className="text-gold text-xs font-bold">{initials}</span>
              ) : (
                <User size={16} className="text-gold" />
              )}
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-500 border-2 border-surface-02 rounded-full" />
          </div>

          {/* Info */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <p className="text-cream text-xs font-semibold truncate leading-none">{adminName}</p>
              <span className="flex-shrink-0 text-[9px] font-bold text-gold bg-gold/15 border border-gold/25 rounded px-1 py-0.5 leading-none">
                Admin
              </span>
            </div>
            {adminEmail && (
              <p className="text-stone text-[10px] truncate mt-1 leading-none">{adminEmail}</p>
            )}
          </div>
        </div>
      </div>

      {/* ── Navigation ──────────────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto py-3 px-3">
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label} className={gi > 0 ? "mt-4" : ""}>
            {/* Section label */}
            <p className="px-3 mb-1 text-[10px] font-bold uppercase tracking-[0.15em] text-stone/50 select-none">
              {group.label}
            </p>

            {/* Items */}
            <div className="space-y-0.5">
              {group.items.map(({ to, icon: Icon, label }) => {
                const active = isActive(to);
                return (
                  <Link
                    key={to}
                    to={to}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      active
                        ? "bg-gold text-cream shadow-sm shadow-gold/20"
                        : "text-stone hover:bg-surface-03 hover:text-parchment"
                    }`}
                  >
                    <Icon
                      size={16}
                      className={`flex-shrink-0 ${active ? "text-cream" : "text-stone/70"}`}
                    />
                    <span className="truncate">{label}</span>
                    {active && (
                      <span className="ml-auto w-1.5 h-1.5 rounded-full bg-cream/70 flex-shrink-0" />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* ── Bottom actions ───────────────────────────────────────────── */}
      <div className="hidden md:block px-3 py-3 border-t border-surface-03 space-y-0.5 flex-shrink-0">
        <Link
          to="/"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-stone hover:bg-surface-03 hover:text-parchment transition-colors"
        >
          <ArrowLeft size={16} className="flex-shrink-0 text-stone/70" />
          <span>Voltar ao App</span>
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-red-400/80 hover:bg-red-500/10 hover:text-red-400 transition-colors"
        >
          <LogOut size={16} className="flex-shrink-0" />
          <span>Sair</span>
        </button>
      </div>
    </div>
  );
}

import type { ElementType } from "react";
import {
  BarChart3,
  Brain,
  CheckSquare,
  ChefHat,
  Clock,
  CreditCard,
  Eye,
  FileText,
  KanbanSquare,
  LayoutDashboard,
  LogIn,
  Mail,
  MessageCircle,
  MousePointerClick,
  Package,
  Palette,
  Plug,
  Printer,
  Route,
  Shield,
  ShoppingBag,
  Sparkles,
  Tag,
  TrendingUp,
  Trophy,
  Truck,
  User,
  UserCheck,
  Users,
  ClipboardList,
  Zap,
} from "lucide-react";

export type AdminNavigationItem = {
  label: string;
  path: string;
  icon: ElementType;
  aliases?: string[];
  permissions?: string[];
  exact?: boolean;
};

export type AdminNavigationGroup = {
  label: string;
  children: AdminNavigationItem[];
  items: AdminNavigationItem[];
};

const groups: Array<{ label: string; children: AdminNavigationItem[] }> = [
  {
    label: "Visao Geral",
    children: [
      { path: "/painel", icon: BarChart3, label: "Dashboard", exact: true, permissions: ["dashboard"] },
    ],
  },
  {
    label: "BI & Relatorios",
    children: [
      { path: "/painel/bi", icon: TrendingUp, label: "Inteligencia BI", exact: true, permissions: ["relatorios"] },
    ],
  },
  {
    label: "Catalogo",
    children: [
      { path: "/painel/products", icon: Package, label: "Produtos", permissions: ["cardapio", "categorias"] },
      { path: "/painel/home-config", icon: LayoutDashboard, label: "Catalogo da Home", permissions: ["loja_online"] },
    ],
  },
  {
    label: "Operacoes",
    children: [
      { path: "/painel/orders", icon: ShoppingBag, label: "Pedidos", permissions: ["pedidos"] },
      { path: "/painel/cozinha", icon: ChefHat, label: "Cozinha", permissions: ["cozinha"] },
      { path: "/painel/logistica", icon: Route, label: "Logistica", permissions: ["entregas", "motoboys"] },
    ],
  },
  {
    label: "CRM",
    children: [
      { path: "/painel/crm", icon: BarChart3, label: "Dashboard CRM", exact: true, permissions: ["clientes"] },
      { path: "/painel/clientes", icon: User, label: "Clientes", permissions: ["clientes"] },
      { path: "/painel/crm/inteligencia", icon: Brain, label: "Inteligencia de Clientes", permissions: ["clientes"] },
      { path: "/painel/crm/pipeline", icon: KanbanSquare, label: "Pipeline", permissions: ["clientes"] },
      { path: "/painel/crm/grupos", icon: UserCheck, label: "Grupos & Segmentacoes", permissions: ["clientes"] },
      { path: "/painel/crm/tarefas", icon: ClipboardList, label: "Tarefas", permissions: ["clientes"] },
    ],
  },
  {
    label: "Marketing",
    children: [
      { path: "/painel/marketing", icon: TrendingUp, label: "Dashboard Marketing", exact: true, permissions: ["marketing"] },
      { path: "/painel/marketing/campanhas", icon: Sparkles, label: "Campanhas", permissions: ["campanhas"] },
      { path: "/painel/marketing/visitantes", icon: Eye, label: "Analise de Visitantes", permissions: ["marketing", "relatorios"] },
      { path: "/painel/marketing/links", icon: MousePointerClick, label: "Links Rastreaveis", permissions: ["marketing"] },
      { path: "/painel/marketing/whatsapp", icon: MessageCircle, label: "Disparador WhatsApp", permissions: ["whatsapp"] },
      { path: "/painel/marketing/email", icon: Mail, label: "Disparador de Email", permissions: ["marketing"] },
      { path: "/painel/trafego-pago", icon: MousePointerClick, label: "Trafego Pago", aliases: ["/painel/marketing/ads"], permissions: ["marketing", "relatorios"] },
      { path: "/painel/marketing/automacoes", icon: Zap, label: "Automacao de Marketing", permissions: ["marketing"] },
      { path: "/painel/marketing/workflow", icon: CheckSquare, label: "Workflow de Aprovacao", permissions: ["marketing"] },
      { path: "/painel/marketing/cupons", icon: Tag, label: "Cupons de Desconto", aliases: ["/painel/cupons"], permissions: ["cupons"] },
      { path: "/painel/campanhas", icon: Sparkles, label: "Promocoes & Banners", permissions: ["promocoes", "campanhas"] },
      { path: "/painel/fidelidade", icon: Trophy, label: "Fidelidade", permissions: ["clientes", "promocoes"] },
      { path: "/painel/popup-saida", icon: LogIn, label: "Popup de Saida", permissions: ["loja_online", "marketing"] },
    ],
  },
  {
    label: "Configuracoes",
    children: [
      { path: "/painel/conteudo", icon: FileText, label: "Conteudo", permissions: ["loja_online"] },
      { path: "/painel/pagamentos", icon: CreditCard, label: "Pagamentos", permissions: ["formas_pagamento"] },
      { path: "/painel/frete", icon: Truck, label: "Entregas e Fretes", permissions: ["frete"] },
      { path: "/painel/funcionamento", icon: Clock, label: "Funcionamento da Loja", permissions: ["funcionamento"] },
      { path: "/painel/chatbot", icon: MessageCircle, label: "Chatbot", permissions: ["whatsapp"] },
      { path: "/painel/aparencia", icon: Palette, label: "Aparencia", permissions: ["loja_online", "configuracoes"] },
      { path: "/painel/marketing/integracoes", icon: Plug, label: "Integracoes", permissions: ["integracoes"] },
      { path: "/painel/usuarios", icon: Users, label: "Usuarios do Sistema", permissions: ["usuarios"] },
      { path: "/painel/lgpd", icon: Shield, label: "LGPD & Privacidade", permissions: ["configuracoes"] },
      { path: "/painel/configuracoes", icon: Printer, label: "Impressora & Modelos", permissions: ["configuracoes"] },
    ],
  },
];

export const adminNavigationGroups: AdminNavigationGroup[] = groups.map((group) => ({
  ...group,
  items: group.children,
}));

export const adminNavigation = adminNavigationGroups.flatMap((group) =>
  group.children.map((item) => ({ ...item, group: group.label })),
);

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
      { path: "/painel", icon: BarChart3, label: "Dashboard", exact: true },
    ],
  },
  {
    label: "Catalogo",
    children: [
      { path: "/painel/products", icon: Package, label: "Produtos" },
      { path: "/painel/home-config", icon: LayoutDashboard, label: "Catalogo da Home" },
    ],
  },
  {
    label: "Operacoes",
    children: [
      { path: "/painel/orders", icon: ShoppingBag, label: "Pedidos" },
      { path: "/painel/cozinha", icon: ChefHat, label: "Cozinha" },
      { path: "/painel/logistica", icon: Route, label: "Logistica" },
    ],
  },
  {
    label: "CRM",
    children: [
      { path: "/painel/crm", icon: BarChart3, label: "Dashboard CRM", exact: true },
      { path: "/painel/clientes", icon: User, label: "Clientes" },
      { path: "/painel/crm/inteligencia", icon: Brain, label: "Inteligencia de Clientes" },
      { path: "/painel/crm/pipeline", icon: KanbanSquare, label: "Pipeline" },
      { path: "/painel/crm/grupos", icon: UserCheck, label: "Grupos & Segmentacoes" },
      { path: "/painel/crm/tarefas", icon: ClipboardList, label: "Tarefas" },
    ],
  },
  {
    label: "Marketing",
    children: [
      { path: "/painel/marketing", icon: TrendingUp, label: "Dashboard Marketing", exact: true },
      { path: "/painel/marketing/campanhas", icon: Sparkles, label: "Campanhas" },
      { path: "/painel/marketing/visitantes", icon: Eye, label: "Analise de Visitantes" },
      { path: "/painel/marketing/links", icon: MousePointerClick, label: "Links Rastreaveis" },
      { path: "/painel/marketing/whatsapp", icon: MessageCircle, label: "Disparador WhatsApp" },
      { path: "/painel/marketing/email", icon: Mail, label: "Disparador de Email" },
      { path: "/painel/trafego-pago", icon: MousePointerClick, label: "Trafego Pago", aliases: ["/painel/marketing/ads"] },
      { path: "/painel/marketing/automacoes", icon: Zap, label: "Automacao de Marketing" },
      { path: "/painel/marketing/workflow", icon: CheckSquare, label: "Workflow de Aprovacao" },
      { path: "/painel/marketing/cupons", icon: Tag, label: "Cupons de Desconto" },
      { path: "/painel/campanhas", icon: Sparkles, label: "Promocoes & Banners" },
      { path: "/painel/fidelidade", icon: Trophy, label: "Fidelidade" },
      { path: "/painel/popup-saida", icon: LogIn, label: "Popup de Saida" },
    ],
  },
  {
    label: "Configuracoes",
    children: [
      { path: "/painel/conteudo", icon: FileText, label: "Conteudo" },
      { path: "/painel/pagamentos", icon: CreditCard, label: "Pagamentos" },
      { path: "/painel/frete", icon: Truck, label: "Entregas e Fretes" },
      { path: "/painel/funcionamento", icon: Clock, label: "Funcionamento da Loja" },
      { path: "/painel/chatbot", icon: MessageCircle, label: "Chatbot" },
      { path: "/painel/aparencia", icon: Palette, label: "Aparencia" },
      { path: "/painel/marketing/integracoes", icon: Plug, label: "Integracoes" },
      { path: "/painel/usuarios", icon: Users, label: "Usuarios do Sistema" },
      { path: "/painel/lgpd", icon: Shield, label: "LGPD & Privacidade" },
      { path: "/painel/configuracoes", icon: Printer, label: "Impressora & Modelos" },
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

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

export type NavigationItem = {
  label: string;
  path: string;
  icon: ElementType;
  group: string;
  permissions?: string[];
  exact?: boolean;
};

export const adminNavigation: NavigationItem[] = [
  { group: "Visao Geral", path: "/painel", icon: BarChart3, label: "Dashboard", exact: true },
  { group: "Catalogo", path: "/painel/products", icon: Package, label: "Produtos" },
  { group: "Catalogo", path: "/painel/home-config", icon: LayoutDashboard, label: "Catalogo da Home" },
  { group: "Operacoes", path: "/painel/orders", icon: ShoppingBag, label: "Pedidos" },
  { group: "Operacoes", path: "/painel/cozinha", icon: ChefHat, label: "Cozinha" },
  { group: "Operacoes", path: "/painel/logistica", icon: Route, label: "Logistica" },
  { group: "CRM", path: "/painel/crm", icon: BarChart3, label: "Dashboard CRM", exact: true },
  { group: "CRM", path: "/painel/clientes", icon: User, label: "Clientes" },
  { group: "CRM", path: "/painel/crm/inteligencia", icon: Brain, label: "Inteligencia de Clientes" },
  { group: "CRM", path: "/painel/crm/pipeline", icon: KanbanSquare, label: "Pipeline" },
  { group: "CRM", path: "/painel/crm/grupos", icon: UserCheck, label: "Grupos & Segmentacoes" },
  { group: "CRM", path: "/painel/crm/tarefas", icon: ClipboardList, label: "Tarefas" },
  { group: "Marketing", path: "/painel/marketing", icon: TrendingUp, label: "Dashboard Marketing", exact: true },
  { group: "Marketing", path: "/painel/marketing/visitantes", icon: Eye, label: "Analise de Visitantes" },
  { group: "Marketing", path: "/painel/marketing/whatsapp", icon: MessageCircle, label: "Disparador WhatsApp" },
  { group: "Marketing", path: "/painel/marketing/email", icon: Mail, label: "Disparador de Email" },
  { group: "Marketing", path: "/painel/trafego-pago", icon: MousePointerClick, label: "Trafego Pago" },
  { group: "Marketing", path: "/painel/marketing/automacoes", icon: Zap, label: "Automacao de Marketing" },
  { group: "Marketing", path: "/painel/marketing/workflow", icon: CheckSquare, label: "Workflow de Aprovacao" },
  { group: "Marketing", path: "/painel/marketing/cupons", icon: Tag, label: "Cupons de Desconto" },
  { group: "Fidelizacao", path: "/painel/campanhas", icon: Sparkles, label: "Promocoes & Banners" },
  { group: "Fidelizacao", path: "/painel/fidelidade", icon: Trophy, label: "Fidelidade" },
  { group: "Fidelizacao", path: "/painel/popup-saida", icon: LogIn, label: "Popup de Saida" },
  { group: "Configuracoes", path: "/painel/conteudo", icon: FileText, label: "Conteudo" },
  { group: "Configuracoes", path: "/painel/pagamentos", icon: CreditCard, label: "Pagamentos" },
  { group: "Configuracoes", path: "/painel/frete", icon: Truck, label: "Entregas e Fretes" },
  { group: "Configuracoes", path: "/painel/funcionamento", icon: Clock, label: "Funcionamento da Loja" },
  { group: "Configuracoes", path: "/painel/chatbot", icon: MessageCircle, label: "Chatbot" },
  { group: "Configuracoes", path: "/painel/aparencia", icon: Palette, label: "Aparencia" },
  { group: "Configuracoes", path: "/painel/marketing/integracoes", icon: Plug, label: "Integracoes" },
  { group: "Configuracoes", path: "/painel/usuarios", icon: Users, label: "Usuarios do Sistema" },
  { group: "Configuracoes", path: "/painel/lgpd", icon: Shield, label: "LGPD & Privacidade" },
  { group: "Configuracoes", path: "/painel/configuracoes", icon: Printer, label: "Impressora & Modelos" },
];

export const adminNavigationGroups = Array.from(
  adminNavigation.reduce((groups, item) => {
    const entries = groups.get(item.group) ?? [];
    entries.push(item);
    groups.set(item.group, entries);
    return groups;
  }, new Map<string, NavigationItem[]>()),
).map(([label, items]) => ({ label, items }));

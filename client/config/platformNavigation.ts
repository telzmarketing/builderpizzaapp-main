import type { ElementType } from "react";
import {
  Activity,
  Archive,
  Boxes,
  Building2,
  CircleDollarSign,
  CloudCog,
  CreditCard,
  DatabaseBackup,
  FileClock,
  Gauge,
  Globe2,
  Headphones,
  Layers3,
  ListChecks,
  MessageCircle,
  ReceiptText,
  Server,
  Settings,
  ShieldAlert,
  Users,
} from "lucide-react";

export type PlatformNavigationItem = {
  label: string;
  path?: string;
  icon: ElementType;
  available: boolean;
  aliases?: string[];
};

export type PlatformNavigationGroup = {
  label: string;
  items: PlatformNavigationItem[];
};

export const platformNavigationGroups: PlatformNavigationGroup[] = [
  {
    label: "Plataforma",
    items: [
      { label: "Visao geral", path: "/painel/plataforma", icon: Gauge, available: true },
      {
        label: "Empresas",
        path: "/painel/empresas",
        aliases: ["/painel/empresas/"],
        icon: Building2,
        available: true,
      },
      { label: "Planos", path: "/painel/planos", icon: CreditCard, available: true },
      { label: "Modulos", path: "/painel/modulos", icon: Boxes, available: true },
      { label: "Cobrancas", path: "/painel/cobrancas", icon: CircleDollarSign, available: true },
      { label: "Dominios", path: "/painel/dominios", icon: Globe2, available: true },
      { label: "Usuarios da plataforma", icon: Users, available: false },
      { label: "Suporte", path: "/painel/suporte", icon: Headphones, available: true },
      { label: "Auditoria", path: "/painel/auditoria", icon: FileClock, available: true },
      { label: "Configuracoes", icon: Settings, available: false },
    ],
  },
  {
    label: "Monitoramento",
    items: [
      { label: "Saude dos servicos", icon: Activity, available: false },
      { label: "Integracoes", icon: CloudCog, available: false },
      { label: "Filas e jobs", icon: ListChecks, available: false },
      { label: "WhatsApp Gateway", icon: MessageCircle, available: false },
      { label: "Erros", icon: ShieldAlert, available: false },
      { label: "Armazenamento", icon: Archive, available: false },
      { label: "Backups", icon: DatabaseBackup, available: false },
    ],
  },
];

export function platformItemMatchesPath(item: PlatformNavigationItem, pathname: string) {
  if (!item.path) return false;
  if (pathname === item.path) return true;
  return pathname.startsWith(`${item.path}/`)
    || (item.aliases ?? []).some((alias) => pathname.startsWith(alias));
}

export const platformNavigationIcons = {
  billing: ReceiptText,
  modules: Layers3,
  services: Server,
};

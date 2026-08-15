import type { ElementType } from "react";
import type { PlatformCapability } from "@/lib/platformCapabilities";
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
  permissionKey?: PlatformCapability;
};

export type PlatformNavigationGroup = {
  label: string;
  items: PlatformNavigationItem[];
};

export const platformNavigationGroups: PlatformNavigationGroup[] = [
  {
    label: "Plataforma",
    items: [
      { label: "Visao geral", path: "/painel/plataforma", icon: Gauge, available: true, permissionKey: "tenants.view" },
      {
        label: "Empresas",
        path: "/painel/empresas",
        aliases: ["/painel/empresas/"],
        icon: Building2,
        available: true,
        permissionKey: "tenants.view",
      },
      { label: "Planos", path: "/painel/planos", icon: CreditCard, available: true, permissionKey: "tenants.view" },
      { label: "Modulos", path: "/painel/modulos", icon: Boxes, available: true, permissionKey: "tenants.view" },
      { label: "Cobrancas", path: "/painel/cobrancas", icon: CircleDollarSign, available: true, permissionKey: "tenants.view" },
      { label: "Dominios", path: "/painel/dominios", icon: Globe2, available: true, permissionKey: "tenants.view" },
      { label: "Usuarios da plataforma", path: "/painel/usuarios-plataforma", icon: Users, available: true, permissionKey: "platform_users.view" },
      { label: "Suporte", path: "/painel/suporte", icon: Headphones, available: true, permissionKey: "support.impersonate" },
      { label: "Auditoria", path: "/painel/auditoria", icon: FileClock, available: true, permissionKey: "audit.view" },
      { label: "Configuracoes", path: "/painel/configuracoes-plataforma", icon: Settings, available: true, permissionKey: "platform_settings.view" },
    ],
  },
  {
    label: "Monitoramento",
    items: [
      { label: "Saude dos servicos", path: "/painel/saude-servicos", icon: Activity, available: true, permissionKey: "monitoring.view" },
      { label: "Integracoes", path: "/painel/integracoes-plataforma", icon: CloudCog, available: true, permissionKey: "integrations.view" },
      { label: "Filas e jobs", path: "/painel/filas-jobs", icon: ListChecks, available: true, permissionKey: "jobs.view" },
      { label: "WhatsApp Gateway", path: "/painel/whatsapp-gateway-plataforma", icon: MessageCircle, available: true, permissionKey: "gateway.view" },
      { label: "Erros", path: "/painel/erros-plataforma", icon: ShieldAlert, available: true, permissionKey: "errors.view" },
      { label: "Armazenamento", path: "/painel/armazenamento-plataforma", icon: Archive, available: true, permissionKey: "storage.view" },
      { label: "Backups", path: "/painel/backups-plataforma", icon: DatabaseBackup, available: true, permissionKey: "backups.view" },
    ],
  },
];

export function platformItemMatchesPath(item: PlatformNavigationItem, pathname: string) {
  if (!item.path) return false;
  if (pathname === item.path) return true;
  return pathname.startsWith(`${item.path}/`)
    || (item.aliases ?? []).some((alias) => pathname.startsWith(alias));
}

export function platformItemAllowed(
  item: PlatformNavigationItem,
  permissions: readonly string[] | null | undefined,
): boolean {
  return !item.permissionKey || !!permissions?.includes(item.permissionKey);
}

export function firstAllowedPlatformPath(
  permissions: readonly string[] | null | undefined,
): string | undefined {
  return platformNavigationGroups
    .flatMap((group) => group.items)
    .find((item) => item.available && item.path && platformItemAllowed(item, permissions))
    ?.path;
}

export const platformNavigationIcons = {
  billing: ReceiptText,
  modules: Layers3,
  services: Server,
};

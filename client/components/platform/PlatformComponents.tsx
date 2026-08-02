import type { ReactNode } from "react";
import { AlertTriangle, Building2, CalendarClock, CheckCircle2, Clock3, ShieldAlert } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import type {
  ApiPlatformAuditLog,
  ApiPlatformDomainStatus,
  ApiPlatformLicenseStatus,
  ApiPlatformModule,
  ApiPlatformTenant,
  ApiPlatformTenantStatus,
} from "@/lib/api";

const TENANT_STATUS: Record<ApiPlatformTenantStatus, { label: string; className: string }> = {
  active: { label: "Ativa", className: "border-green-500/30 bg-green-500/10 text-green-300" },
  suspended: { label: "Suspensa", className: "border-yellow-500/30 bg-yellow-500/10 text-yellow-200" },
  disabled: { label: "Desativada", className: "border-stone/30 bg-stone/10 text-stone" },
};

const LICENSE_STATUS: Record<ApiPlatformLicenseStatus, { label: string; className: string }> = {
  trial: { label: "Teste", className: "border-blue-500/30 bg-blue-500/10 text-blue-300" },
  active: { label: "Ativa", className: "border-green-500/30 bg-green-500/10 text-green-300" },
  grace_period: { label: "Carencia", className: "border-yellow-500/30 bg-yellow-500/10 text-yellow-200" },
  expired: { label: "Vencida", className: "border-orange-500/30 bg-orange-500/10 text-orange-300" },
  suspended: { label: "Suspensa", className: "border-yellow-500/30 bg-yellow-500/10 text-yellow-200" },
  blocked: { label: "Bloqueada", className: "border-red-500/30 bg-red-500/10 text-red-300" },
  cancelled: { label: "Cancelada", className: "border-stone/30 bg-stone/10 text-stone" },
};

const DOMAIN_STATUS: Record<ApiPlatformDomainStatus, { label: string; className: string }> = {
  pending: { label: "Pendente", className: "border-yellow-500/30 bg-yellow-500/10 text-yellow-200" },
  awaiting_dns: { label: "Aguardando DNS", className: "border-yellow-500/30 bg-yellow-500/10 text-yellow-200" },
  verifying: { label: "Verificando", className: "border-blue-500/30 bg-blue-500/10 text-blue-300" },
  verified: { label: "Verificado", className: "border-blue-500/30 bg-blue-500/10 text-blue-300" },
  active: { label: "Ativo", className: "border-green-500/30 bg-green-500/10 text-green-300" },
  suspended: { label: "Suspenso", className: "border-stone/30 bg-stone/10 text-stone" },
  dns_error: { label: "Erro DNS", className: "border-red-500/30 bg-red-500/10 text-red-300" },
  ssl_error: { label: "Erro SSL", className: "border-red-500/30 bg-red-500/10 text-red-300" },
  removed: { label: "Removido", className: "border-stone/30 bg-stone/10 text-stone" },
};

function StatusPill({ label, className }: { label: string; className: string }) {
  return <Badge variant="outline" className={className}>{label}</Badge>;
}

export function StatusBadge({ status }: { status: ApiPlatformTenantStatus }) {
  const config = TENANT_STATUS[status] ?? { label: status, className: "border-stone/30 text-stone" };
  return <StatusPill {...config} />;
}

export function LicenseStatusBadge({ status }: { status: ApiPlatformLicenseStatus }) {
  const config = LICENSE_STATUS[status] ?? { label: status, className: "border-stone/30 text-stone" };
  return <StatusPill {...config} />;
}

export function DomainStatusBadge({ status }: { status: ApiPlatformDomainStatus }) {
  const config = DOMAIN_STATUS[status] ?? { label: status, className: "border-stone/30 text-stone" };
  return <StatusPill {...config} />;
}

export function CompanySummaryCard({ tenant }: { tenant: ApiPlatformTenant }) {
  return (
    <div className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gold/10 text-gold">
            <Building2 size={21} />
          </span>
          <div className="min-w-0">
            <p className="truncate font-black text-cream">{tenant.name}</p>
            <p className="truncate text-xs text-stone">{tenant.legal_name || tenant.slug}</p>
          </div>
        </div>
        <StatusBadge status={tenant.status} />
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-4 text-sm">
        <div><dt className="text-xs text-stone">Plano</dt><dd className="mt-1 font-bold text-cream">{tenant.plan?.name || "Nao definido"}</dd></div>
        <div><dt className="text-xs text-stone">Usuarios</dt><dd className="mt-1 font-bold text-cream">{tenant.user_count ?? 0}{tenant.plan?.max_users ? ` / ${tenant.plan.max_users}` : ""}</dd></div>
        <div className="col-span-2"><dt className="text-xs text-stone">Dominio principal</dt><dd className="mt-1 truncate font-bold text-cream">{tenant.primary_domain?.hostname || "Nao configurado"}</dd></div>
      </dl>
    </div>
  );
}

export function UsageProgress({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number | null;
}) {
  const percent = limit && limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-semibold text-cream">{label}</span>
        <span className="text-xs text-stone">{used} / {limit ?? "Ilimitado"}</span>
      </div>
      <Progress value={limit ? percent : 0} className="h-2 bg-surface-03 [&>div]:bg-gold" />
    </div>
  );
}

export function ModuleToggleCard({
  module,
  checked,
  disabled,
  onCheckedChange,
}: {
  module: ApiPlatformModule;
  checked: boolean;
  disabled?: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-3 rounded-xl border border-surface-03 bg-surface-01 p-4">
      <Switch checked={checked} disabled={disabled} onCheckedChange={onCheckedChange} />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-bold text-cream">{module.name}</span>
        </span>
        {module.description && <span className="mt-1 block text-xs leading-relaxed text-stone">{module.description}</span>}
      </span>
    </label>
  );
}

export function ConfirmationDialog({
  trigger,
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  destructive,
  reason,
  reasonRequired,
  confirmDisabled,
  preventCloseOnConfirm,
  onReasonChange,
  onConfirm,
  children,
}: {
  trigger?: ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  destructive?: boolean;
  reason?: string;
  reasonRequired?: boolean;
  confirmDisabled?: boolean;
  preventCloseOnConfirm?: boolean;
  onReasonChange?: (reason: string) => void;
  onConfirm: () => void;
  children?: ReactNode;
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      {trigger && <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>}
      <AlertDialogContent className="border-surface-03 bg-surface-02 text-cream">
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription className="text-stone">{description}</AlertDialogDescription>
        </AlertDialogHeader>
        {children}
        {onReasonChange && (
          <label className="space-y-2 text-sm">
            <span className="font-bold text-cream">Motivo{reasonRequired ? " *" : ""}</span>
            <textarea
              value={reason ?? ""}
              onChange={(event) => onReasonChange(event.target.value)}
              className="min-h-24 w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2 text-cream outline-none focus:border-gold"
              placeholder="Registre o motivo para a auditoria"
            />
          </label>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            disabled={confirmDisabled || reasonRequired && !reason?.trim()}
            onClick={(event) => {
              if (preventCloseOnConfirm) event.preventDefault();
              onConfirm();
            }}
            className={destructive ? "bg-red-600 text-white hover:bg-red-500" : "bg-gold text-surface-00 hover:bg-gold/90"}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export const SuspendTenantDialog = ConfirmationDialog;
export const RenewLicenseDialog = ConfirmationDialog;
export const ChangePlanDialog = ConfirmationDialog;

export function AuditLogTimeline({ items }: { items: ApiPlatformAuditLog[] }) {
  if (!items.length) {
    return <div className="rounded-xl border border-dashed border-surface-03 p-8 text-center text-sm text-stone">Nenhum evento de auditoria encontrado.</div>;
  }
  return (
    <ol className="space-y-4">
      {items.map((item) => (
        <li key={item.id} className="relative flex gap-3">
          <span className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-gold/30 bg-gold/10 text-gold">
            {item.action.includes("block") ? <ShieldAlert size={14} /> : item.action.includes("license") ? <CalendarClock size={14} /> : <CheckCircle2 size={14} />}
          </span>
          <div className="min-w-0 flex-1 rounded-xl border border-surface-03 bg-surface-01 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-bold text-cream">{item.action}</p>
                <p className="mt-1 text-xs text-stone">{item.actor_label || "Sistema"}</p>
              </div>
              <time className="flex items-center gap-1 text-xs text-stone">
                <Clock3 size={12} /> {new Date(item.created_at).toLocaleString("pt-BR")}
              </time>
            </div>
            {item.reason && <p className="mt-3 flex gap-2 rounded-lg bg-yellow-500/10 p-3 text-xs text-yellow-100"><AlertTriangle size={14} className="shrink-0" /> {item.reason}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}

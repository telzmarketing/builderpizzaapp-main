import { useState } from "react";
import { Loader2 } from "lucide-react";
import { ConfirmationDialog } from "@/components/platform/PlatformComponents";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { platformSupportApi, type ApiPlatformTenantUser } from "@/lib/api";
import { activatePlatformSupportSession } from "@/lib/platformSupportSession";

export default function PlatformSupportAccessDialog({
  open,
  onOpenChange,
  tenant,
  users = [],
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tenant: { id: string; name: string };
  users?: ApiPlatformTenantUser[];
}) {
  const { toast } = useToast();
  const [reason, setReason] = useState("");
  const [duration, setDuration] = useState(30);
  const [targetUserId, setTargetUserId] = useState("");
  const [saving, setSaving] = useState(false);

  async function start() {
    if (reason.trim().length < 3 || saving) return;
    setSaving(true);
    let createdSessionId: string | null = null;
    try {
      const created = await platformSupportApi.start({
        tenant_id: tenant.id,
        target_user_id: targetUserId || null,
        reason: reason.trim(),
        duration_minutes: duration,
      });
      createdSessionId = created.session.id;
      const scoped = await platformSupportApi.exchange(created.support_token);
      if (scoped.tenant_id !== tenant.id || scoped.support_session_id !== created.session.id) {
        throw new Error("O escopo retornado pela API diverge da sessao solicitada.");
      }
      activatePlatformSupportSession({
        session_id: scoped.support_session_id,
        tenant_id: scoped.tenant_id,
        tenant_name: tenant.name,
        expires_at: scoped.expires_at,
        access_token: scoped.access_token,
      });
      window.location.assign("/painel/gestao/financeiro");
    } catch (err) {
      if (createdSessionId) {
        await platformSupportApi.end(createdSessionId).catch(() => undefined);
      }
      toast({
        variant: "destructive",
        title: "Nao foi possivel iniciar o suporte",
        description: err instanceof Error ? err.message : "Tente novamente.",
      });
      setSaving(false);
    }
  }

  return (
    <ConfirmationDialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Acessar ${tenant.name} como suporte`}
      description="O backend emitira um JWT temporario limitado a esta empresa. Todas as acoes permanecem vinculadas ao administrador Master."
      confirmLabel={saving ? "Iniciando..." : "Iniciar sessao segura"}
      confirmDisabled={saving}
      preventCloseOnConfirm
      reason={reason}
      reasonRequired
      onReasonChange={setReason}
      onConfirm={() => void start()}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-2 text-sm">
          <span className="font-bold text-cream">Duracao</span>
          <select value={duration} onChange={(event) => setDuration(Number(event.target.value))} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream">
            <option value={15}>15 minutos</option>
            <option value={30}>30 minutos</option>
            <option value={60}>60 minutos</option>
            <option value={120}>120 minutos</option>
          </select>
        </label>
        <label className="space-y-2 text-sm">
          <span className="font-bold text-cream">Usuario de referencia (opcional)</span>
          <select value={targetUserId} onChange={(event) => setTargetUserId(event.target.value)} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream">
            <option value="">Contexto geral da empresa</option>
            {users.filter((user) => user.membership.status === "active").map((user) => (
              <option key={user.id} value={user.id}>{user.name} · {user.membership.role}</option>
            ))}
          </select>
        </label>
      </div>
      {saving && <p className="flex items-center gap-2 text-xs text-stone"><Loader2 size={13} className="animate-spin text-gold" /> Criando sessao e trocando o token...</p>}
      <Input readOnly value={tenant.id} className="border-surface-03 bg-surface-01 text-stone" aria-label="Tenant fixado no token" />
    </ConfirmationDialog>
  );
}

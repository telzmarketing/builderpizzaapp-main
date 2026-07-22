import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Ban, CheckCircle2, Clock, Loader2, MessageCircle, ShieldAlert } from "lucide-react";
import { customersApi, type ApiCustomerContactRisk, type ApiCustomerContactRiskEvent, type ApiCustomerContactRiskOverridePayload } from "@/lib/api";

const labels = { low: "Baixo", attention: "Atenção", high: "Alto", blocked: "Bloqueado" } as const;
const styles = {
  low: "bg-green-500/15 text-green-300 border-green-500/20",
  attention: "bg-yellow-500/15 text-yellow-300 border-yellow-500/20",
  high: "bg-orange-500/15 text-orange-300 border-orange-500/20",
  blocked: "bg-red-500/15 text-red-300 border-red-500/20",
} as const;

function eventLabel(value: string) {
  const known: Record<string, string> = {
    order_complaint: "Reclamação de pedido", contact_reported: "Contato denunciado",
    whatsapp_blocked: "Bloqueio no WhatsApp", campaign_delivered: "Campanha entregue",
    manual_adjustment: "Ajuste administrativo", manual_block: "Bloqueio administrativo",
    contact_unblocked: "Desbloqueio administrativo", marketing_opt_out: "Descadastro de marketing",
  };
  return known[value] ?? value.replaceAll("_", " ");
}

export default function CustomerContactRiskPanel({ customerId }: { customerId: string }) {
  const [risk, setRisk] = useState<ApiCustomerContactRisk | null>(null);
  const [events, setEvents] = useState<ApiCustomerContactRiskEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState<ApiCustomerContactRiskOverridePayload["action"]>("set_score");
  const [score, setScore] = useState(0);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [nextRisk, nextEvents] = await Promise.all([
        customersApi.getContactRisk(customerId), customersApi.getContactRiskEvents(customerId),
      ]);
      setRisk(nextRisk); setEvents(nextEvents); setScore(nextRisk.score);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar o rating de contato.");
    } finally { setLoading(false); }
  }, [customerId]);

  useEffect(() => { void load(); }, [load]);

  async function submitOverride() {
    if (!reason.trim()) { setError("Informe o motivo do ajuste administrativo."); return; }
    setSaving(true); setError(null); setSuccess(null);
    try {
      await customersApi.overrideContactRisk(customerId, {
        action, reason: reason.trim(), ...(action === "set_score" ? { score } : {}),
      });
      setReason(""); setSuccess("Rating atualizado e registrado no histórico."); await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar o ajuste.");
    } finally { setSaving(false); }
  }

  return <section className="rounded-xl border border-surface-03 bg-surface-02 p-4 space-y-4">
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2"><ShieldAlert size={17} className="text-gold" /><div>
        <h3 className="font-medium text-parchment">Rating de contato WhatsApp</h3>
        <p className="text-xs text-stone/50">Proteção contra contatos excessivos ou indesejados</p>
      </div></div>
      {risk && <span className={`w-fit rounded-full border px-2.5 py-1 text-xs font-semibold ${styles[risk.risk_level]}`}>{labels[risk.risk_level]} · {risk.score}/100</span>}
    </div>
    {loading ? <div className="flex items-center gap-2 py-6 text-sm text-stone/60"><Loader2 size={17} className="animate-spin" /> Carregando rating...</div>
    : error && !risk ? <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300"><AlertCircle size={16} /><span className="flex-1">{error}</span><button type="button" onClick={() => void load()} className="font-medium underline">Tentar novamente</button></div>
    : risk ? <>
      <div className="grid gap-3 sm:grid-cols-3">
        <Metric label="Situação">{risk.is_blocked ? <Ban size={14} /> : <CheckCircle2 size={14} />}<span className={risk.is_blocked ? "text-red-300" : "text-green-300"}>{risk.is_blocked ? "Disparos bloqueados" : "Elegível para avaliação"}</span></Metric>
        <Metric label="Campanhas em 15 dias"><MessageCircle size={14} /> {risk.campaign_deliveries_15d}</Metric>
        <Metric label="Última ocorrência"><Clock size={14} /> {risk.last_event_at ? new Date(risk.last_event_at).toLocaleString("pt-BR") : "Nenhuma"}</Metric>
      </div>
      {risk.block_reason && <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">Motivo do bloqueio: {risk.block_reason}</p>}
      <div className="grid gap-3 border-t border-surface-03 pt-4 md:grid-cols-[180px_110px_1fr_auto] md:items-end">
        <label className="space-y-1 text-xs text-stone/60">Ação<select value={action} onChange={(e) => setAction(e.target.value as typeof action)} className="w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-parchment"><option value="set_score">Ajustar score</option><option value="complaint">Registrar reclamação</option><option value="reported">Contato denunciado</option><option value="whatsapp_blocked">Bloqueou no WhatsApp</option><option value="opt_out">Pediu descadastro</option><option value="block">Bloquear manualmente</option><option value="unblock">Desbloquear</option></select></label>
        {action === "set_score" && <label className="space-y-1 text-xs text-stone/60">Score<input type="number" min={0} max={100} value={score} onChange={(e) => setScore(Math.max(0, Math.min(100, Number(e.target.value))))} className="w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-parchment" /></label>}
        <label className="space-y-1 text-xs text-stone/60">Motivo obrigatório<input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Justificativa para auditoria" className="w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-parchment" /></label>
        <button type="button" onClick={submitOverride} disabled={saving || !reason.trim()} className="rounded-lg bg-gold px-4 py-2 text-sm font-semibold text-surface-00 disabled:opacity-50">{saving ? "Salvando..." : "Registrar"}</button>
      </div>
      {error && <p className="text-sm text-red-300">{error}</p>}{success && <p className="text-sm text-green-300">{success}</p>}
      <div className="border-t border-surface-03 pt-4"><h4 className="mb-2 text-sm font-medium text-parchment">Histórico do rating</h4>
        {events.length === 0 ? <p className="text-sm text-stone/50">Nenhuma ocorrência registrada.</p> : <div className="max-h-64 space-y-2 overflow-y-auto pr-1">{events.map((event, index) => <div key={event.id ?? `${event.occurred_at}-${index}`} className="flex flex-col gap-1 rounded-lg border border-surface-03 bg-surface-01 p-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-medium text-parchment">{eventLabel(event.event_type)}</p><p className="text-xs text-stone/50">{new Date(event.occurred_at).toLocaleString("pt-BR")}{event.source_type ? ` · ${event.source_type}` : ""}</p></div><div className="sm:text-right"><p className="text-sm text-parchment">{event.score_before} → {event.score_after}</p><p className={event.points_delta > 0 ? "text-xs text-red-300" : "text-xs text-green-300"}>{event.points_delta > 0 ? "+" : ""}{event.points_delta} pontos{event.blocks_contact ? " · bloqueou contato" : ""}</p></div></div>)}</div>}
      </div>
    </> : <p className="text-sm text-stone/50">Rating ainda não disponível para este cliente.</p>}
  </section>;
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="rounded-lg border border-surface-03 bg-surface-01 p-3"><p className="text-xs text-stone/50">{label}</p><p className="mt-1 flex items-center gap-1.5 text-sm font-semibold text-parchment">{children}</p></div>;
}

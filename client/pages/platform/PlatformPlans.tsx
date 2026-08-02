import { useCallback, useEffect, useState } from "react";
import { Archive, CheckCircle2, Loader2, Pencil, Plus, RefreshCw } from "lucide-react";
import { ConfirmationDialog } from "@/components/platform/PlatformComponents";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import {
  platformModulesApi,
  platformPlansApi,
  type ApiPlatformModule,
  type ApiPlatformPlan,
} from "@/lib/api";
import { parseOptionalPlatformNumber, togglePlatformSelection } from "@/lib/platformCatalog";

type PlanDraft = {
  key: string;
  name: string;
  description: string;
  plan_type: NonNullable<ApiPlatformPlan["plan_type"]>;
  status: ApiPlatformPlan["status"];
  billing_cycle: NonNullable<ApiPlatformPlan["billing_cycle"]>;
  currency: string;
  grace_period_days: number;
  auto_renew_default: boolean;
  price: number;
  monthly_price: string;
  quarterly_price: string;
  semiannual_price: string;
  annual_price: string;
  trial_days: number;
  max_users: string;
  max_stores: string;
  max_orders: string;
  max_storage_mb: string;
  max_whatsapp_instances: string;
  support_level: string;
  display_order: number;
  module_ids: string[];
};

const EMPTY_DRAFT: PlanDraft = {
  key: "",
  name: "",
  description: "",
  plan_type: "public",
  status: "active",
  billing_cycle: "monthly",
  currency: "BRL",
  grace_period_days: 0,
  auto_renew_default: false,
  price: 0,
  monthly_price: "",
  quarterly_price: "",
  semiannual_price: "",
  annual_price: "",
  trial_days: 0,
  max_users: "",
  max_stores: "",
  max_orders: "",
  max_storage_mb: "",
  max_whatsapp_instances: "",
  support_level: "",
  display_order: 0,
  module_ids: [],
};

function fromPlan(plan: ApiPlatformPlan): PlanDraft {
  return {
    ...EMPTY_DRAFT,
    ...plan,
    description: plan.description ?? "",
    billing_cycle: plan.billing_cycle ?? "monthly",
    currency: plan.currency ?? "BRL",
    grace_period_days: plan.grace_period_days ?? 0,
    auto_renew_default: plan.auto_renew_default ?? false,
    price: Number(plan.price ?? 0),
    plan_type: plan.plan_type ?? "public",
    monthly_price: plan.monthly_price == null ? "" : String(plan.monthly_price),
    quarterly_price: plan.quarterly_price == null ? "" : String(plan.quarterly_price),
    semiannual_price: plan.semiannual_price == null ? "" : String(plan.semiannual_price),
    annual_price: plan.annual_price == null ? "" : String(plan.annual_price),
    trial_days: plan.trial_days ?? 0,
    max_users: plan.max_users == null ? "" : String(plan.max_users),
    max_stores: plan.max_stores == null ? "" : String(plan.max_stores),
    max_orders: plan.max_orders == null ? "" : String(plan.max_orders),
    max_storage_mb: plan.max_storage_mb == null ? "" : String(plan.max_storage_mb),
    max_whatsapp_instances: plan.max_whatsapp_instances == null ? "" : String(plan.max_whatsapp_instances),
    support_level: plan.support_level ?? "",
    display_order: plan.display_order ?? 0,
    module_ids: plan.module_ids ?? [],
  };
}

export default function PlatformPlans() {
  const { toast } = useToast();
  const [items, setItems] = useState<ApiPlatformPlan[]>([]);
  const [modules, setModules] = useState<ApiPlatformModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<ApiPlatformPlan | null>(null);
  const [draft, setDraft] = useState<PlanDraft>(EMPTY_DRAFT);
  const [archiving, setArchiving] = useState<ApiPlatformPlan | null>(null);
  const [archiveReason, setArchiveReason] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [plansData, modulesData] = await Promise.all([
        platformPlansApi.list(),
        platformModulesApi.list(),
      ]);
      setItems(plansData);
      setModules(modulesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar os planos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  function openCreate() {
    setEditing(null);
    setDraft({ ...EMPTY_DRAFT, module_ids: [] });
    setEditorOpen(true);
  }

  function openEdit(plan: ApiPlatformPlan) {
    setEditing(plan);
    setDraft(fromPlan(plan));
    setEditorOpen(true);
  }

  function payload() {
    return {
      key: draft.key.trim().toLowerCase(),
      name: draft.name.trim(),
      description: draft.description.trim() || null,
      plan_type: draft.plan_type,
      status: draft.status,
      billing_cycle: draft.billing_cycle,
      currency: draft.currency.trim().toUpperCase(),
      grace_period_days: draft.grace_period_days,
      auto_renew_default: draft.auto_renew_default,
      price: draft.price,
      monthly_price: parseOptionalPlatformNumber(draft.monthly_price),
      quarterly_price: parseOptionalPlatformNumber(draft.quarterly_price),
      semiannual_price: parseOptionalPlatformNumber(draft.semiannual_price),
      annual_price: parseOptionalPlatformNumber(draft.annual_price),
      trial_days: draft.trial_days,
      max_users: parseOptionalPlatformNumber(draft.max_users),
      max_stores: parseOptionalPlatformNumber(draft.max_stores),
      max_orders: parseOptionalPlatformNumber(draft.max_orders),
      max_storage_mb: parseOptionalPlatformNumber(draft.max_storage_mb),
      max_whatsapp_instances: parseOptionalPlatformNumber(draft.max_whatsapp_instances),
      support_level: draft.support_level.trim() || null,
      display_order: draft.display_order,
      module_ids: draft.module_ids,
    };
  }

  async function save() {
    if (draft.name.trim().length < 2 || draft.key.trim().length < 2 || draft.currency.trim().length !== 3) return;
    setSaving(true);
    try {
      if (editing) await platformPlansApi.update(editing.id, payload());
      else await platformPlansApi.create(payload());
      await load();
      setEditorOpen(false);
      toast({ title: editing ? "Plano atualizado" : "Plano criado" });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel salvar", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setSaving(false);
    }
  }

  async function archive() {
    if (!archiving || archiveReason.trim().length < 3) return;
    setSaving(true);
    try {
      await platformPlansApi.update(archiving.id, { status: "archived", reason: archiveReason.trim() });
      await load();
      setArchiving(null);
      setArchiveReason("");
      toast({ title: "Plano arquivado" });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel arquivar", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end"><Button onClick={openCreate} className="gap-2 bg-gold text-surface-00 hover:bg-gold/90"><Plus size={15} /> Novo plano</Button></div>
      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">{error}<Button variant="ghost" size="sm" onClick={() => void load()} className="ml-3 gap-1"><RefreshCw size={13} /> Repetir</Button></div>}
      {loading ? <div className="flex min-h-56 items-center justify-center"><Loader2 className="animate-spin text-gold" /></div> : !items.length ? (
        <div className="rounded-2xl border border-dashed border-surface-03 p-10 text-center text-stone">Nenhum plano cadastrado.</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((plan) => (
            <article key={plan.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
              <div className="flex items-start justify-between gap-3">
                <div><h2 className="font-black text-cream">{plan.name}</h2><p className="mt-1 text-xs text-stone">{plan.key}</p></div>
                <span className={plan.status === "active" ? "text-green-300" : "text-stone"}><CheckCircle2 size={18} /></span>
              </div>
              <p className="mt-4 text-sm text-stone">{plan.description || "Sem descricao."}</p>
              <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-xs text-stone">Preco</dt><dd className="font-bold text-cream">{Number(plan.price ?? 0).toLocaleString("pt-BR", { style: "currency", currency: plan.currency ?? "BRL" })}</dd></div>
                <div><dt className="text-xs text-stone">Ciclo</dt><dd className="font-bold text-cream">{plan.billing_cycle ?? "monthly"}</dd></div>
                <div><dt className="text-xs text-stone">Usuarios</dt><dd className="font-bold text-cream">{plan.max_users ?? "Ilimitado"}</dd></div>
                <div><dt className="text-xs text-stone">Tipo / teste</dt><dd className="font-bold text-cream">{plan.plan_type ?? "public"} · {plan.trial_days ?? 0}d</dd></div>
              </dl>
              <div className="mt-5 flex gap-2">
                <Button variant="outline" size="sm" onClick={() => openEdit(plan)} className="gap-2"><Pencil size={13} /> Editar</Button>
                {plan.status !== "archived" && <Button variant="destructive" size="sm" onClick={() => setArchiving(plan)} className="gap-2"><Archive size={13} /> Arquivar</Button>}
              </div>
            </article>
          ))}
        </div>
      )}

      {editorOpen && (
        <ConfirmationDialog
          open
          onOpenChange={setEditorOpen}
          title={editing ? "Editar plano" : "Criar plano"}
          description="Limites vazios permanecem ilimitados. A remocao de modulos bloqueia acesso sem apagar dados do tenant."
          confirmLabel={saving ? "Salvando..." : "Salvar plano"}
          confirmDisabled={saving || draft.name.trim().length < 2 || draft.key.trim().length < 2 || draft.currency.trim().length !== 3}
          preventCloseOnConfirm
          onConfirm={() => void save()}
        >
          <PlanForm draft={draft} modules={modules} editing={!!editing} onChange={setDraft} />
        </ConfirmationDialog>
      )}

      {archiving && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => { if (!open) setArchiving(null); }}
          title="Arquivar plano"
          description="O plano deixa de aceitar novas atribuicoes. Empresas existentes preservam o historico comercial."
          confirmLabel={saving ? "Arquivando..." : "Arquivar"}
          confirmDisabled={saving}
          preventCloseOnConfirm
          destructive
          reason={archiveReason}
          reasonRequired
          onReasonChange={setArchiveReason}
          onConfirm={() => void archive()}
        />
      )}
    </div>
  );
}

function PlanForm({ draft, modules, editing, onChange }: { draft: PlanDraft; modules: ApiPlatformModule[]; editing: boolean; onChange: (draft: PlanDraft) => void }) {
  const set = <K extends keyof PlanDraft>(key: K, value: PlanDraft[K]) => onChange({ ...draft, [key]: value });
  const numericFields: Array<[keyof Pick<PlanDraft, "max_users" | "max_stores" | "max_orders" | "max_storage_mb" | "max_whatsapp_instances">, string]> = [
    ["max_users", "Limite de usuarios"], ["max_stores", "Limite de lojas"], ["max_orders", "Limite de pedidos"],
    ["max_storage_mb", "Armazenamento MB"], ["max_whatsapp_instances", "Instancias WhatsApp"],
  ];
  return (
    <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-2">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Nome" value={draft.name} onChange={(value) => set("name", value)} />
        <Field label="Chave unica" value={draft.key} readOnly={editing} onChange={(value) => set("key", value.replace(/[^a-zA-Z0-9_-]/g, ""))} />
        <Field label="Descricao" value={draft.description} onChange={(value) => set("description", value)} />
        <Field label="Suporte incluido" value={draft.support_level} onChange={(value) => set("support_level", value)} />
        <label className="space-y-2 text-sm"><span className="font-bold text-cream">Tipo</span><select value={draft.plan_type} onChange={(event) => set("plan_type", event.target.value as PlanDraft["plan_type"])} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream"><option value="public">Publico</option><option value="custom">Personalizado</option></select></label>
        <label className="space-y-2 text-sm"><span className="font-bold text-cream">Ciclo</span><select value={draft.billing_cycle} onChange={(event) => set("billing_cycle", event.target.value as PlanDraft["billing_cycle"])} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream">{["monthly", "quarterly", "semiannual", "annual", "custom"].map((cycle) => <option key={cycle}>{cycle}</option>)}</select></label>
        <Field label="Moeda" value={draft.currency} onChange={(value) => set("currency", value.toUpperCase().slice(0, 3))} />
        <NumberField label="Preco" value={draft.price} min={0} step="0.01" onChange={(value) => set("price", value)} />
        <Field label="Preco mensal" type="number" value={draft.monthly_price} onChange={(value) => set("monthly_price", value)} />
        <Field label="Preco trimestral" type="number" value={draft.quarterly_price} onChange={(value) => set("quarterly_price", value)} />
        <Field label="Preco semestral" type="number" value={draft.semiannual_price} onChange={(value) => set("semiannual_price", value)} />
        <Field label="Preco anual" type="number" value={draft.annual_price} onChange={(value) => set("annual_price", value)} />
        <NumberField label="Periodo de teste em dias" value={draft.trial_days} min={0} onChange={(value) => set("trial_days", value)} />
        <NumberField label="Carencia em dias" value={draft.grace_period_days} min={0} onChange={(value) => set("grace_period_days", value)} />
        <NumberField label="Ordem" value={draft.display_order} min={0} onChange={(value) => set("display_order", value)} />
        {numericFields.map(([key, label]) => <Field key={key} label={label} value={draft[key]} type="number" onChange={(value) => set(key, value)} />)}
        <label className="flex items-center gap-2 text-sm text-cream sm:col-span-2"><input type="checkbox" checked={draft.auto_renew_default} onChange={(event) => set("auto_renew_default", event.target.checked)} /> Renovacao automatica por padrao</label>
      </div>
      <div><p className="mb-2 text-sm font-bold text-cream">Modulos incluidos</p><div className="grid gap-2 sm:grid-cols-2">{modules.filter((item) => item.active).map((module) => <label key={module.id} className="flex items-center gap-2 rounded-lg border border-surface-03 p-2 text-sm text-stone"><input type="checkbox" checked={draft.module_ids.includes(module.id)} onChange={(event) => set("module_ids", togglePlatformSelection(draft.module_ids, module.id, event.target.checked))} /> {module.name}</label>)}</div></div>
    </div>
  );
}

function Field({ label, value, onChange, readOnly, type = "text" }: { label: string; value: string; onChange: (value: string) => void; readOnly?: boolean; type?: string }) {
  return <label className="space-y-2 text-sm"><span className="font-bold text-cream">{label}</span><Input type={type} readOnly={readOnly} value={value} onChange={(event) => onChange(event.target.value)} className="border-surface-03 bg-surface-01 text-cream" /></label>;
}

function NumberField({ label, value, onChange, min, step }: { label: string; value: number; onChange: (value: number) => void; min?: number; step?: string }) {
  return <label className="space-y-2 text-sm"><span className="font-bold text-cream">{label}</span><Input type="number" min={min} step={step} value={value} onChange={(event) => onChange(Number(event.target.value) || 0)} className="border-surface-03 bg-surface-01 text-cream" /></label>;
}

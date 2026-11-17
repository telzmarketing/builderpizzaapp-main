import { useEffect, useMemo, useState } from "react";
import {
  Check,
  CreditCard,
  Edit3,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  X,
} from "lucide-react";
import {
  appFinanceApi,
  type ApiAppFinanceConfig,
  type AppFinanceCalculationType,
  type AppFinanceConfigInput,
  type AppFinanceRuleInput,
  type AppFinanceRuleType,
  type DeliveryAppOrigin,
} from "@/lib/api";

export const APP_OPTIONS: Array<{ key: DeliveryAppOrigin; label: string }> = [
  { key: "partner_99", label: "99 Food" },
  { key: "ifood", label: "iFood" },
  { key: "keeta", label: "Keeta" },
];

const RULE_TYPE_OPTIONS: Array<{ key: AppFinanceRuleType; label: string }> = [
  { key: "commission", label: "Comissão do aplicativo" },
  { key: "fee", label: "Taxa adicional" },
  { key: "freight", label: "Frete" },
  { key: "store_discount", label: "Desconto da pizzaria" },
  { key: "deduction", label: "Outra dedução" },
];

const CALCULATION_OPTIONS: Array<{ key: AppFinanceCalculationType; label: string }> = [
  { key: "percentage", label: "Percentual (%)" },
  { key: "fixed", label: "Valor fixo (R$)" },
];

const inputClass = "min-h-11 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 text-sm text-cream outline-none transition focus:border-gold";
const secondaryButtonClass = "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-surface-03 bg-surface-02 px-3 text-sm font-bold text-stone transition hover:border-gold/60 hover:text-cream disabled:cursor-not-allowed disabled:opacity-50";
const primaryButtonClass = "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-gold px-4 text-sm font-black text-ink transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-50";

type ConfigForm = {
  app_key: DeliveryAppOrigin;
  app_name: string;
  active: boolean;
};

type RuleForm = {
  name: string;
  rule_type: AppFinanceRuleType;
  calculation_type: AppFinanceCalculationType;
  value: string;
  sort_order: string;
  active: boolean;
};

const emptyConfigForm: ConfigForm = {
  app_key: "partner_99",
  app_name: "99 Food",
  active: true,
};

const emptyRuleForm: RuleForm = {
  name: "",
  rule_type: "commission",
  calculation_type: "percentage",
  value: "0",
  sort_order: "0",
  active: true,
};

function appLabel(key: DeliveryAppOrigin): string {
  return APP_OPTIONS.find((option) => option.key === key)?.label ?? key;
}

export function ruleTypeLabel(type: AppFinanceRuleType): string {
  return RULE_TYPE_OPTIONS.find((option) => option.key === type)?.label ?? type;
}

export function formatRuleValue(value: number | string, calculationType: AppFinanceCalculationType): string {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return String(value);
  return calculationType === "percentage"
    ? `${numericValue.toFixed(2).replace(".00", "")} %`
    : numericValue.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function ErrorMessage({ message }: { message: string }) {
  return <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{message}</div>;
}

function StatusToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={checked}
      onClick={onChange}
      className={`inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 text-xs font-bold transition ${checked ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200" : "border-surface-03 bg-surface-02 text-stone"}`}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${checked ? "bg-emerald-300" : "bg-stone/50"}`} />
      {label}: {checked ? "Ativo" : "Inativo"}
    </button>
  );
}

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-bold text-cream">{label}</span>
      {children}
      {hint && <span className="block text-[11px] leading-4 text-stone">{hint}</span>}
    </label>
  );
}

export default function OperationsAppsFinance() {
  const [configs, setConfigs] = useState<ApiAppFinanceConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [configForm, setConfigForm] = useState<ConfigForm>(emptyConfigForm);
  const [ruleConfigId, setRuleConfigId] = useState<string | null>(null);
  const [ruleForm, setRuleForm] = useState<RuleForm>(emptyRuleForm);

  const configuredKeys = useMemo(() => new Set(configs.map((config) => config.app_key)), [configs]);

  const load = async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    setError("");
    try {
      setConfigs(await appFinanceApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar as configurações dos aplicativos.");
    } finally {
      if (showSpinner) setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const resetConfig = () => {
    setEditingId(null);
    setConfigForm(emptyConfigForm);
  };

  const startCreate = () => {
    const next = APP_OPTIONS.find((option) => !configuredKeys.has(option.key));
    setEditingId(null);
    setConfigForm(next ? { ...emptyConfigForm, app_key: next.key, app_name: next.label } : emptyConfigForm);
  };

  const startEdit = (config: ApiAppFinanceConfig) => {
    setEditingId(config.id);
    setConfigForm({ app_key: config.app_key, app_name: config.app_name, active: config.active });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const submitConfig = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    const payload: AppFinanceConfigInput = configForm;
    try {
      if (editingId) {
        await appFinanceApi.update(editingId, payload);
        setNotice("Configuração do aplicativo atualizada.");
      } else {
        await appFinanceApi.create(payload);
        setNotice("Aplicativo adicionado às condições financeiras.");
      }
      resetConfig();
      await load(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar a configuração.");
    } finally {
      setSaving(false);
    }
  };

  const removeConfig = async (config: ApiAppFinanceConfig) => {
    if (!window.confirm(`Remover as condições financeiras de ${config.app_name}?`)) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await appFinanceApi.remove(config.id);
      if (editingId === config.id) resetConfig();
      setNotice("Configuração removida.");
      await load(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível remover a configuração.");
    } finally {
      setSaving(false);
    }
  };

  const submitRule = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!ruleConfigId) return;
    setSaving(true);
    setError("");
    setNotice("");
    const payload: AppFinanceRuleInput = {
      name: ruleForm.name.trim(),
      rule_type: ruleForm.rule_type,
      calculation_type: ruleForm.calculation_type,
      value: Number(ruleForm.value),
      sort_order: Number(ruleForm.sort_order),
      active: ruleForm.active,
    };
    try {
      await appFinanceApi.addRule(ruleConfigId, payload);
      setRuleForm(emptyRuleForm);
      setNotice("Regra adicionada ao aplicativo.");
      await load(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível adicionar a regra.");
    } finally {
      setSaving(false);
    }
  };

  const removeRule = async (ruleId: string) => {
    if (!window.confirm("Remover esta regra financeira?")) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await appFinanceApi.removeRule(ruleId);
      setNotice("Regra removida.");
      await load(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível remover a regra.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-01 px-4 py-6 text-cream sm:px-8">
      <div className="mx-auto max-w-7xl space-y-6 pb-10">
        <header className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-gold">Operações / Financeiro</p>
            <h1 className="mt-2 text-3xl font-black">Financeiro Apps Delivery</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-stone">Configure, por aplicativo, comissões, taxas, fretes, descontos e outras deduções usadas para calcular a receita líquida prevista dos pedidos.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={secondaryButtonClass} onClick={() => void load()} disabled={loading || saving}><RefreshCw size={15} className={loading ? "animate-spin" : ""} />Atualizar</button>
            <button type="button" className={primaryButtonClass} onClick={startCreate} disabled={saving || configuredKeys.size >= APP_OPTIONS.length}><Plus size={15} />Novo aplicativo</button>
          </div>
        </header>

        {error && <ErrorMessage message={error} />}
        {notice && <div role="status" className="flex items-center gap-2 rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200"><Check size={16} />{notice}</div>}

        <section className="rounded-2xl border border-surface-03 bg-surface-02 p-5 shadow-lg shadow-black/10">
          <div className="flex items-start gap-3">
            <div className="rounded-xl border border-gold/30 bg-gold/10 p-3 text-gold"><CreditCard size={22} /></div>
            <div><h2 className="font-bold text-cream">Cadastro por aplicativo</h2><p className="mt-1 text-xs leading-5 text-stone">Cada aplicativo possui configuração própria e isolada para a empresa atual. O valor bruto do pedido permanece preservado.</p></div>
          </div>
          <form className="mt-5 grid gap-4 lg:grid-cols-[1fr_1.4fr_auto] lg:items-end" onSubmit={(event) => void submitConfig(event)}>
            <Field label="Aplicativo">
              <select className={inputClass} value={configForm.app_key} onChange={(event) => { const key = event.target.value as DeliveryAppOrigin; setConfigForm((value) => ({ ...value, app_key: key, app_name: appLabel(key) })); }} disabled={!!editingId}>
                {APP_OPTIONS.map((option) => <option key={option.key} value={option.key} disabled={!editingId && configuredKeys.has(option.key)}>{option.label}</option>)}
              </select>
            </Field>
            <Field label="Nome exibido" hint="Você pode personalizar o nome usado no painel.">
              <input className={inputClass} required minLength={2} maxLength={120} value={configForm.app_name} onChange={(event) => setConfigForm((value) => ({ ...value, app_name: event.target.value }))} />
            </Field>
            <div className="flex flex-wrap items-center gap-2">
              <StatusToggle label="Aplicativo" checked={configForm.active} onChange={() => setConfigForm((value) => ({ ...value, active: !value.active }))} />
              <button className={primaryButtonClass} type="submit" disabled={saving}><Save size={15} />{editingId ? "Salvar" : "Cadastrar"}</button>
              {editingId && <button className={secondaryButtonClass} type="button" onClick={resetConfig} disabled={saving}><X size={15} />Cancelar</button>}
            </div>
          </form>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between gap-3"><div><h2 className="text-xl font-black">Aplicativos configurados</h2><p className="mt-1 text-sm text-stone">Adicione as regras na mesma tela e defina a ordem de aplicação.</p></div><span className="rounded-full border border-surface-03 bg-surface-02 px-3 py-1 text-xs font-bold text-stone">{configs.length} de {APP_OPTIONS.length}</span></div>
          {loading ? <div className="flex min-h-48 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02 text-sm text-stone"><Loader2 size={22} className="mr-3 animate-spin text-gold" />Carregando configurações...</div> : configs.length === 0 ? <div className="rounded-2xl border border-dashed border-surface-03 bg-surface-02 p-8 text-center text-sm text-stone">Nenhum aplicativo configurado. Cadastre o primeiro para definir suas condições financeiras.</div> : configs.map((config) => (
            <article key={config.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-5 shadow-lg shadow-black/10">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="flex items-start gap-3"><div className="rounded-xl border border-gold/30 bg-gold/10 p-3 text-gold"><CreditCard size={20} /></div><div><div className="flex flex-wrap items-center gap-2"><h3 className="text-lg font-black">{config.app_name}</h3><span className="rounded-full bg-surface-03 px-2 py-1 text-[11px] font-bold text-stone">{config.app_key}</span><span className={`rounded-full px-2 py-1 text-[11px] font-bold ${config.active ? "bg-emerald-400/10 text-emerald-200" : "bg-surface-03 text-stone"}`}>{config.active ? "Ativo" : "Inativo"}</span></div><p className="mt-1 text-xs text-stone">{config.rules.length} regra(s) cadastrada(s)</p></div></div>
                <div className="flex flex-wrap gap-2"><button type="button" className={secondaryButtonClass} onClick={() => startEdit(config)} disabled={saving}><Edit3 size={15} />Editar aplicativo</button><button type="button" className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-red-500/25 px-3 text-sm font-bold text-red-300 transition hover:bg-red-500/10 disabled:opacity-50" onClick={() => void removeConfig(config)} disabled={saving}><Trash2 size={15} />Remover</button></div>
              </div>

              <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.85fr)]">
                <div className="space-y-3"><h4 className="text-sm font-black text-cream">Regras financeiras</h4>{config.rules.length === 0 ? <p className="rounded-xl border border-dashed border-surface-03 p-4 text-xs text-stone">Nenhuma regra cadastrada. Use o formulário ao lado.</p> : config.rules.map((rule) => <div key={rule.id} className="flex flex-col gap-3 rounded-xl border border-surface-03 bg-surface-01 p-4 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex flex-wrap items-center gap-2"><p className="font-bold text-cream">{rule.name}</p><span className="rounded-full bg-gold/10 px-2 py-1 text-[11px] font-bold text-gold">{formatRuleValue(rule.value, rule.calculation_type)}</span><span className={`rounded-full px-2 py-1 text-[11px] font-bold ${rule.active ? "bg-emerald-400/10 text-emerald-200" : "bg-surface-03 text-stone"}`}>{rule.active ? "Ativa" : "Inativa"}</span></div><p className="mt-1 text-xs text-stone">{ruleTypeLabel(rule.rule_type)} · ordem {rule.sort_order}</p></div><button type="button" className="inline-flex min-h-9 items-center justify-center gap-2 self-start rounded-lg border border-red-500/25 px-3 text-xs font-bold text-red-300 hover:bg-red-500/10 sm:self-auto" onClick={() => void removeRule(rule.id)} disabled={saving}><Trash2 size={14} />Remover</button></div>)}</div>
                <form className="rounded-xl border border-gold/20 bg-gold/5 p-4" onSubmit={(event) => { setRuleConfigId(config.id); void submitRule(event); }}>
                  <h4 className="flex items-center gap-2 text-sm font-black text-cream"><Plus size={16} className="text-gold" />Adicionar regra</h4>
                  <div className="mt-4 space-y-3">
                    <Field label="Nome"><input className={inputClass} required minLength={2} maxLength={120} value={ruleConfigId === config.id ? ruleForm.name : ""} onFocus={() => setRuleConfigId(config.id)} onChange={(event) => { setRuleConfigId(config.id); setRuleForm((value) => ({ ...value, name: event.target.value })); }} placeholder="Ex.: Comissão padrão" /></Field>
                    <div className="grid gap-3 sm:grid-cols-2"><Field label="Tipo"><select className={inputClass} value={ruleConfigId === config.id ? ruleForm.rule_type : "commission"} onFocus={() => setRuleConfigId(config.id)} onChange={(event) => { setRuleConfigId(config.id); setRuleForm((value) => ({ ...value, rule_type: event.target.value as AppFinanceRuleType })); }}>{RULE_TYPE_OPTIONS.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}</select></Field><Field label="Cálculo"><select className={inputClass} value={ruleConfigId === config.id ? ruleForm.calculation_type : "percentage"} onFocus={() => setRuleConfigId(config.id)} onChange={(event) => { setRuleConfigId(config.id); setRuleForm((value) => ({ ...value, calculation_type: event.target.value as AppFinanceCalculationType })); }}>{CALCULATION_OPTIONS.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}</select></Field></div>
                    <div className="grid gap-3 sm:grid-cols-2"><Field label="Percentual / valor"><input className={inputClass} required min="0" step="0.01" type="number" value={ruleConfigId === config.id ? ruleForm.value : "0"} onFocus={() => setRuleConfigId(config.id)} onChange={(event) => { setRuleConfigId(config.id); setRuleForm((value) => ({ ...value, value: event.target.value })); }} /></Field><Field label="Ordem"><input className={inputClass} required min="0" step="1" type="number" value={ruleConfigId === config.id ? ruleForm.sort_order : "0"} onFocus={() => setRuleConfigId(config.id)} onChange={(event) => { setRuleConfigId(config.id); setRuleForm((value) => ({ ...value, sort_order: event.target.value })); }} /></Field></div>
                    <div className="flex flex-wrap items-center justify-between gap-3"><StatusToggle label="Regra" checked={ruleConfigId === config.id ? ruleForm.active : true} onChange={() => { setRuleConfigId(config.id); setRuleForm((value) => ({ ...value, active: !value.active })); }} /><button className={primaryButtonClass} type="submit" disabled={saving}><Plus size={15} />Adicionar regra</button></div>
                  </div>
                </form>
              </div>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}

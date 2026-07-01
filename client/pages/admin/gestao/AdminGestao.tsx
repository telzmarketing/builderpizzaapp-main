import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Save,
  ShieldCheck,
} from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
} from "@/components/admin/AdminPageChrome";
import { Switch } from "@/components/ui/switch";
import {
  gestaoApi,
  type GestaoModuleKey,
  type GestaoModuleSettings,
} from "@/lib/api";

const modulePlan: Record<GestaoModuleKey, string[]> = {
  inventory: [
    "Cadastros de insumos, unidades, locais e fornecedores.",
    "Ficha tecnica interna sem exposicao ao cliente final.",
    "Disponibilidade de venda somente em fase posterior.",
  ],
  cmv: [
    "Snapshots de custo apenas quando habilitado.",
    "DRE parcial enquanto nao houver CMV confiavel.",
    "Sem interferencia na cozinha, pedido ou estoque.",
  ],
  finance: [
    "Contas financeiras, categorias e centros de custo.",
    "Contas a pagar/receber e lancamentos manuais.",
    "Integracao com pagamentos apenas em fase posterior.",
  ],
  fiscal: [
    "Cadastro fiscal, series, numeracao e certificado.",
    "Preparacao para SEFAZ direta.",
    "Sem Saipos ou middleware fiscal externo.",
  ],
};

const statusLabel: Record<GestaoModuleSettings["status"], string> = {
  disabled: "Desabilitado",
  setup: "Em configuracao",
  ready: "Pronto para ativar",
  active: "Ativo",
};

const statusClass: Record<GestaoModuleSettings["status"], string> = {
  disabled: "border-surface-03 bg-surface-03/50 text-stone",
  setup: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  ready: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  active: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
};

function toDisplay(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "Sim" : "Nao";
  if (typeof value === "string" || typeof value === "number") return String(value).replace(/_/g, " ");
  return JSON.stringify(value);
}

function normalizeSettings(settings: Record<string, unknown>) {
  return Object.entries(settings).map(([key, value]) => ({
    key,
    label: key.replace(/_/g, " "),
    value,
  }));
}

export default function AdminGestao({
  moduleKey = "inventory",
  children,
  moduleTabs,
  showSettings = true,
}: {
  moduleKey?: GestaoModuleKey;
  children?: ReactNode;
  moduleTabs?: ReactNode;
  showSettings?: boolean;
}) {
  const [modules, setModules] = useState<GestaoModuleSettings[]>([]);
  const [draft, setDraft] = useState<GestaoModuleSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const activeModule = useMemo(
    () => modules.find((item) => item.module_key === moduleKey) ?? null,
    [modules, moduleKey],
  );

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError("");
    gestaoApi.settings()
      .then((data) => {
        if (!mounted) return;
        setModules(data.modules);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Nao foi possivel carregar Gestao.");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    setDraft(activeModule ? { ...activeModule, settings: { ...activeModule.settings } } : null);
    setMessage("");
  }, [activeModule]);

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const saved = await gestaoApi.updateSettings(draft.module_key, {
        enabled: draft.enabled,
        status: draft.enabled ? draft.status === "disabled" ? "setup" : draft.status : "disabled",
        settings: draft.settings,
        notes: draft.notes,
      });
      setModules((prev) => prev.map((item) => item.module_key === saved.module_key ? saved : item));
      setMessage("Configuracao salva. Nenhuma automacao operacional foi ativada nesta fase.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel salvar Gestao.");
    } finally {
      setSaving(false);
    }
  };

  const updateBooleanSetting = (key: string, value: boolean) => {
    if (!draft) return;
    setDraft({
      ...draft,
      settings: {
        ...draft.settings,
        [key]: value,
      },
    });
  };

  const settingsRows = draft ? normalizeSettings(draft.settings) : [];

  return (
    <AdminPageShell>
      <AdminPageHeader
        icon={<ShieldCheck size={20} />}
        title="Gestao"
        description="Base dos modulos ERP sem impacto operacional nos pedidos atuais"
        actions={showSettings ? (
          <button
            type="button"
            onClick={save}
            disabled={!draft || saving}
            className="inline-flex items-center gap-2 rounded-lg bg-gold px-4 py-2 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Salvar
          </button>
        ) : undefined}
      />
      {moduleTabs}
      <AdminPageContent>
        {loading && (
          <div className="flex min-h-[18rem] items-center justify-center rounded-lg border border-surface-03 bg-surface-02 text-stone">
            <Loader2 size={18} className="mr-2 animate-spin" /> Carregando Gestao...
          </div>
        )}

        {!loading && error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-5 text-red-200">
            <div className="flex items-center gap-2 font-bold">
              <AlertCircle size={18} /> Erro ao carregar
            </div>
            <p className="mt-2 text-sm">{error}</p>
          </div>
        )}

        {!loading && draft && (
          <div className="space-y-6">
            {showSettings && (
              <>
                <section className="rounded-lg border border-surface-03 bg-surface-02 p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="max-w-3xl">
                      <div className="flex flex-wrap items-center gap-3">
                        <h2 className="text-xl font-black text-cream">{draft.title}</h2>
                        <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${statusClass[draft.status]}`}>
                          {statusLabel[draft.status]}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-relaxed text-stone">{draft.description}</p>
                      <p className="mt-3 rounded-lg border border-sky-500/20 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200">
                        Fase 1 cria base, permissoes, rotas e configuracoes. Pedido, checkout, cozinha e pagamentos continuam sem alteracao.
                      </p>
                    </div>
                    <label className="flex min-w-[14rem] items-center justify-between gap-4 rounded-lg border border-surface-03 bg-surface-01 px-4 py-3">
                      <span>
                        <span className="block text-sm font-bold text-cream">Modulo habilitado</span>
                        <span className="block text-xs text-stone">Apenas configuracao interna</span>
                      </span>
                      <Switch
                        checked={draft.enabled}
                        onCheckedChange={(checked) => setDraft({
                          ...draft,
                          enabled: checked,
                          status: checked ? draft.status === "disabled" ? "setup" : draft.status : "disabled",
                        })}
                      />
                    </label>
                  </div>
                </section>

                <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
                  <div className="rounded-lg border border-surface-03 bg-surface-02 p-5">
                    <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Configuracoes base</h3>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      {settingsRows.map((item) => (
                        <div key={item.key} className="rounded-lg border border-surface-03 bg-surface-01 p-4">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="text-xs font-bold uppercase tracking-wide text-stone">{item.label}</p>
                              <p className="mt-1 text-sm font-semibold text-cream">{toDisplay(item.value)}</p>
                            </div>
                            {typeof item.value === "boolean" && (
                              <Switch
                                checked={item.value}
                                onCheckedChange={(checked) => updateBooleanSetting(item.key, checked)}
                              />
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <aside className="rounded-lg border border-surface-03 bg-surface-02 p-5">
                    <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Proxima etapa</h3>
                    <ul className="mt-4 space-y-3 text-sm text-stone">
                      {modulePlan[draft.module_key].map((item) => (
                        <li key={item} className="flex gap-2">
                          <CheckCircle2 size={15} className="mt-0.5 flex-shrink-0 text-gold" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </aside>
                </section>

                <section className="rounded-lg border border-surface-03 bg-surface-02 p-5">
                  <label className="text-sm font-black uppercase tracking-wide text-parchment" htmlFor="gestao-notes">
                    Observacoes internas
                  </label>
                  <textarea
                    id="gestao-notes"
                    value={draft.notes}
                    onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
                    className="mt-3 min-h-24 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none transition focus:border-gold"
                  />
                </section>

                {message && (
                  <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-200">
                    {message}
                  </p>
                )}
              </>
            )}

            {children}
          </div>
        )}
      </AdminPageContent>
    </AdminPageShell>
  );
}

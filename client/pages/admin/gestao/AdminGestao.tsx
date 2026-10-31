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
    "Exigência de insumos na fabricação configurada separadamente nesta tela.",
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
        setError(err instanceof Error ? err.message : "Não foi possivel carregar Gestão.");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    setDraft(activeModule ? {
      ...activeModule,
      settings: {
        ...activeModule.settings,
        ...(activeModule.module_key === "inventory" ? {
          production_stock_control_enabled: activeModule.settings.production_stock_control_enabled === true,
        } : {}),
      },
    } : null);
  }, [activeModule]);

  const save = async () => {
    if (!draft || saving) return;
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
      setMessage(saved.module_key === "inventory"
        ? `Configurações do estoque salvas. Exigência de insumos na fabricação: ${saved.settings.production_stock_control_enabled === true ? "ligada" : "desligada"}.`
        : "Configuração salva.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possivel salvar Gestão.");
    } finally {
      setSaving(false);
    }
  };

  const updateBooleanSetting = (key: string, value: boolean) => {
    if (!draft) return;
    setMessage("");
    setDraft({
      ...draft,
      settings: {
        ...draft.settings,
        [key]: value,
      },
    });
  };

  const settingsRows = draft ? normalizeSettings(draft.settings).filter(
    (item) => moduleKey !== "inventory" || item.key !== "production_stock_control_enabled",
  ) : [];
  const productionStockControlEnabled = draft?.settings.production_stock_control_enabled === true;
  const savedProductionStockControlEnabled = activeModule?.settings.production_stock_control_enabled === true;
  const productionStockControlChanged = productionStockControlEnabled !== savedProductionStockControlEnabled;

  return (
    <AdminPageShell>
      <AdminPageHeader
        icon={<ShieldCheck size={20} />}
        title="Gestão"
        description={moduleKey === "inventory" ? "Cadastros e controles de estoque e fabricação" : "Base dos modulos ERP sem impacto operacional nos pedidos atuais"}
        actions={showSettings ? (
          <button
            type="button"
            onClick={save}
            disabled={!draft || saving}
            className="inline-flex items-center gap-2 rounded-lg bg-gold px-4 py-2 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {saving ? "Salvando..." : "Salvar"}
          </button>
        ) : undefined}
      />
      {moduleTabs}
      <AdminPageContent>
        {loading && (
          <div className="flex min-h-[18rem] items-center justify-center rounded-lg border border-surface-03 bg-surface-02 text-stone">
            <Loader2 size={18} className="mr-2 animate-spin" /> Carregando Gestão...
          </div>
        )}

        {!loading && error && (
          <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-5 text-red-200">
            <div className="flex items-center gap-2 font-bold">
              <AlertCircle size={18} /> {draft ? "Não foi possível salvar" : "Erro ao carregar"}
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
                        {moduleKey === "inventory"
                          ? "O módulo de Estoque e a exigência de insumos na fabricação possuem controles separados. Configure a fabricação na seção abaixo e clique em Salvar para aplicar as alterações."
                          : "Fase 1 cria base, permissoes, rotas e configuracoes. Pedido, checkout, cozinha e pagamentos continuam sem alteracao."}
                      </p>
                    </div>
                    <label className="flex min-w-[14rem] items-center justify-between gap-4 rounded-lg border border-surface-03 bg-surface-01 px-4 py-3">
                      <span>
                        <span className="block text-sm font-bold text-cream">Modulo habilitado</span>
                        <span className="block text-xs text-stone">{moduleKey === "inventory" ? "Habilitação geral do Estoque" : "Apenas configuracao interna"}</span>
                      </span>
                      <Switch
                        aria-label="Módulo habilitado"
                        disabled={saving}
                        checked={draft.enabled}
                        onCheckedChange={(checked) => {
                          setMessage("");
                          setDraft({
                            ...draft,
                            enabled: checked,
                            status: checked ? draft.status === "disabled" ? "setup" : draft.status : "disabled",
                          });
                        }}
                      />
                    </label>
                  </div>
                </section>

                {moduleKey === "inventory" && (
                  <section aria-labelledby="production-stock-control-title" className="rounded-lg border border-gold/30 bg-surface-02 p-5">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      <div className="max-w-3xl">
                        <h3 id="production-stock-control-title" className="text-lg font-black text-cream">Exigir insumos na fabricação</h3>
                        <p id="production-stock-control-description" className="mt-2 text-sm leading-relaxed text-stone">
                          Ligado: a fabricação exige ficha técnica completa e saldo suficiente dos insumos; faltas bloqueiam o início do preparo.
                          Desligado: permite fabricar mesmo sem ficha técnica ou insumos cadastrados, sem conferência obrigatória nem baixa automática de insumos na fabricação.
                        </p>
                        <p className="mt-2 text-xs text-stone">Este controle é específico da fabricação. Ele não altera o botão geral do módulo, a disponibilidade de venda ou a configuração analítica de CMV.</p>
                        <p className="mt-3 text-sm font-semibold text-cream">Estado salvo: {savedProductionStockControlEnabled ? "Ligado" : "Desligado"}</p>
                        {productionStockControlChanged && (
                          <p role="status" className="mt-2 text-sm text-amber-300">Alteração pendente: {productionStockControlEnabled ? "ligar" : "desligar"} a exigência de insumos. Clique em Salvar para aplicar.</p>
                        )}
                      </div>
                      <label className="flex shrink-0 items-center gap-3 rounded-lg border border-surface-03 bg-surface-01 px-4 py-3" htmlFor="production-stock-control">
                        <span className="text-sm font-bold text-cream">{productionStockControlEnabled ? "Ligado" : "Desligado"}</span>
                        <Switch
                          id="production-stock-control"
                          aria-labelledby="production-stock-control-title"
                          aria-describedby="production-stock-control-description"
                          checked={productionStockControlEnabled}
                          disabled={saving}
                          onCheckedChange={(checked) => updateBooleanSetting("production_stock_control_enabled", checked)}
                        />
                      </label>
                    </div>
                  </section>
                )}

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
                                disabled={saving}
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
                    disabled={saving}
                    value={draft.notes}
                    onChange={(event) => { setMessage(""); setDraft({ ...draft, notes: event.target.value }); }}
                    className="mt-3 min-h-24 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none transition focus:border-gold"
                  />
                </section>

                {message && (
                  <p role="status" className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-200">
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

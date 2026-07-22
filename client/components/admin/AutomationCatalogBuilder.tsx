import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Eye, Loader2, RefreshCw, ShieldCheck, Zap } from "lucide-react";
import {
  marketingAutomationsApi,
  type ApiAutomationCatalog,
  type ApiAutomationCatalogDefinition,
  type ApiAutomationDefinitionPayload,
  type ApiAutomationSimulationResult,
  type ApiAutomationValidationResult,
} from "@/lib/api";

const FIELD = "w-full rounded-xl border border-surface-03 bg-surface-03 px-3 py-2 text-sm text-cream focus:border-gold focus:outline-none";

function warningText(value: string | { message: string }) {
  return typeof value === "string" ? value : value.message;
}

function normalizeCatalog(raw: ApiAutomationCatalog | ApiAutomationCatalogDefinition[]) {
  if (Array.isArray(raw)) return raw;
  const combined = [
    ...(raw.definitions ?? []),
    ...(raw.events ?? []).map(item => ({ ...item, kind: item.kind ?? "event" })),
    ...(raw.triggers ?? []).map(item => ({ ...item, kind: item.kind ?? "event" })),
    ...(raw.actions ?? []).map(item => ({ ...item, kind: item.kind ?? "action" })),
  ];
  return Array.from(new Map(combined.map(item => [item.key, item])).values());
}

function definitionKind(item: ApiAutomationCatalogDefinition) {
  return (item.kind ?? item.type ?? "").toLowerCase();
}

interface AutomationCatalogBuilderProps {
  onCreated?: () => void;
}

export default function AutomationCatalogBuilder({ onCreated }: AutomationCatalogBuilderProps) {
  const [definitions, setDefinitions] = useState<ApiAutomationCatalogDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [moduleKey, setModuleKey] = useState("");
  const [name, setName] = useState("");
  const [eventKey, setEventKey] = useState("");
  const [actionKeys, setActionKeys] = useState<string[]>([]);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [sampleEvent, setSampleEvent] = useState("{}");
  const [validation, setValidation] = useState<ApiAutomationValidationResult | null>(null);
  const [simulation, setSimulation] = useState<ApiAutomationSimulationResult | null>(null);
  const [busy, setBusy] = useState<"validate" | "simulate" | "save" | null>(null);
  const [actionError, setActionError] = useState("");
  const [success, setSuccess] = useState("");

  const loadCatalog = async () => {
    setLoading(true);
    setError("");
    try {
      const data = normalizeCatalog(await marketingAutomationsApi.catalog());
      setDefinitions(data);
      setModuleKey(current => current || data[0]?.module || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar o catálogo de automações.");
      setDefinitions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadCatalog(); }, []);

  const modules = useMemo(
    () => Array.from(new Set(definitions.map(item => item.module).filter(Boolean))).sort(),
    [definitions],
  );
  const moduleDefinitions = useMemo(() => definitions.filter(item => item.module === moduleKey), [definitions, moduleKey]);
  const events = useMemo(() => moduleDefinitions.filter(item => definitionKind(item) === "event"), [moduleDefinitions]);
  const actions = useMemo(() => definitions.filter(item => definitionKind(item) === "action"), [definitions]);

  useEffect(() => {
    setEventKey(current => events.some(item => item.key === current) ? current : events[0]?.key ?? "");
    setValidation(null);
    setSimulation(null);
  }, [moduleKey, events]);

  const itemConfig = (item: ApiAutomationCatalogDefinition) => Object.fromEntries(
    (item.required_config ?? []).map(field => [field, configValues[`${item.key}:${field}`] ?? ""]),
  );

  const buildDefinition = (): ApiAutomationDefinitionPayload => ({
    module: moduleKey,
    event_key: eventKey,
    trigger: { key: eventKey, config: itemConfig(events.find(item => item.key === eventKey) ?? { key: eventKey, label: eventKey, module: moduleKey }) },
    actions: actionKeys.map(key => ({ key, config: itemConfig(actions.find(item => item.key === key) ?? { key, label: key, module: moduleKey }) })),
    conditions: [],
  });

  const validateDefinition = async () => {
    setBusy("validate");
    setActionError("");
    setSuccess("");
    setSimulation(null);
    try {
      setValidation(await marketingAutomationsApi.validate(buildDefinition()));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Falha ao validar a automação.");
    } finally {
      setBusy(null);
    }
  };

  const simulateDefinition = async () => {
    setBusy("simulate");
    setActionError("");
    setSuccess("");
    setSimulation(null);
    try {
      const parsed = JSON.parse(sampleEvent) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("O evento de exemplo deve ser um objeto JSON.");
      const definition = buildDefinition();
      const checked = await marketingAutomationsApi.validate(definition);
      setValidation(checked);
      if (!checked.valid) return;
      setSimulation(await marketingAutomationsApi.simulate({ trigger: definition.trigger, actions: definition.actions, conditions: definition.conditions, sample_payload: parsed as Record<string, unknown> }));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Falha ao simular a automação.");
    } finally {
      setBusy(null);
    }
  };

  const saveDefinition = async () => {
    setBusy("save");
    setActionError("");
    setSuccess("");
    try {
      if (!name.trim()) throw new Error("Informe um nome para salvar a automação.");
      const definition = buildDefinition();
      const checked = await marketingAutomationsApi.validate(definition);
      setValidation(checked);
      if (!checked.valid) return;
      await marketingAutomationsApi.create({
        name: name.trim(),
        trigger: definition.trigger.key,
        trigger_config: definition.trigger.config,
        channel: "workflow",
        conditions: definition.conditions ?? [],
        actions: definition.actions,
      });
      setSuccess("Automação criada com sucesso.");
      setName("");
      setSimulation(null);
      onCreated?.();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Falha ao salvar a automação.");
    } finally {
      setBusy(null);
    }
  };

  const selectable = Boolean(moduleKey && eventKey && actionKeys.length);

  return (
    <section className="space-y-4 rounded-2xl border border-surface-03 bg-surface-02 p-4 md:p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-cream"><ShieldCheck size={18} className="text-gold" /><h2 className="font-semibold">Catálogo transversal</h2></div>
          <p className="mt-1 text-xs text-stone">Escolha somente eventos e ações publicados pelo backend. A simulação não executa efeitos externos.</p>
        </div>
        <button type="button" onClick={() => void loadCatalog()} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-03 px-3 py-2 text-xs font-semibold text-stone hover:text-cream disabled:opacity-60">
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Atualizar catálogo
        </button>
      </div>

      {loading ? <div className="flex justify-center py-8"><Loader2 className="animate-spin text-gold" /></div> : error ? (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400"><AlertCircle size={15} />{error}</div>
      ) : definitions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-03 p-8 text-center text-sm text-stone">Nenhuma capacidade de automação foi publicada para seu acesso.</div>
      ) : (
        <>
          <label className="block space-y-1 text-xs text-stone">Nome da automação
            <input className={FIELD} value={name} onChange={event => { setName(event.target.value); setSuccess(""); }} placeholder="Ex: Criar tarefa após novo pedido" />
          </label>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="space-y-1 text-xs text-stone">Módulo
              <select className={FIELD} value={moduleKey} onChange={event => setModuleKey(event.target.value)}>
                {modules.map(module => <option key={module} value={module}>{module}</option>)}
              </select>
            </label>
            <label className="space-y-1 text-xs text-stone">Evento
              <select className={FIELD} value={eventKey} onChange={event => { setEventKey(event.target.value); setValidation(null); setSimulation(null); }} disabled={!events.length}>
                {!events.length && <option value="">Nenhum evento disponível</option>}
                {events.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}
              </select>
            </label>
          </div>

          {(events.find(item => item.key === eventKey)?.required_config ?? []).map(field => (
            <label key={`${eventKey}:${field}`} className="block space-y-1 text-xs text-stone">Configuração do evento: {field}
              <input className={FIELD} value={configValues[`${eventKey}:${field}`] ?? ""} onChange={event => { setConfigValues(current => ({ ...current, [`${eventKey}:${field}`]: event.target.value })); setValidation(null); setSimulation(null); }} />
            </label>
          ))}

          <div className="space-y-2">
            <p className="text-xs text-stone">Ações permitidas</p>
            {actions.length === 0 ? <p className="rounded-xl bg-surface-03 p-3 text-xs text-stone">Nenhuma ação disponível neste módulo.</p> : (
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {actions.map(item => {
                  const checked = actionKeys.includes(item.key);
                  return <label key={item.key} className={`cursor-pointer rounded-xl border p-3 ${checked ? "border-gold/60 bg-gold/10" : "border-surface-03 bg-surface-03/40"}`}>
                    <div className="flex items-start gap-2"><input type="checkbox" checked={checked} onChange={() => { setActionKeys(current => checked ? current.filter(key => key !== item.key) : [...current, item.key]); setValidation(null); setSimulation(null); }} className="mt-1 accent-amber-500" />
                      <div className="min-w-0 flex-1"><p className="text-sm font-medium text-cream">{item.label}</p>{item.description && <p className="mt-1 text-xs text-stone">{item.description}</p>}{item.required_permission && <p className="mt-1 text-[11px] text-gold">Permissão: {item.required_permission}</p>}
                        {checked && (item.required_config ?? []).map(field => <label key={field} className="mt-2 block text-[11px] text-stone">{field}<input className={`${FIELD} mt-1`} value={configValues[`${item.key}:${field}`] ?? ""} onClick={event => event.stopPropagation()} onChange={event => { setConfigValues(current => ({ ...current, [`${item.key}:${field}`]: event.target.value })); setValidation(null); setSimulation(null); }} /></label>)}
                      </div>
                    </div>
                  </label>;
                })}
              </div>
            )}
          </div>

          <label className="block space-y-1 text-xs text-stone">Evento de exemplo (JSON)
            <textarea rows={5} className={`${FIELD} resize-y font-mono text-xs`} value={sampleEvent} onChange={event => setSampleEvent(event.target.value)} aria-describedby="sample-event-help" />
            <span id="sample-event-help" className="block text-[11px] text-stone/70">Usado apenas na simulação; nenhum envio ou alteração será realizado.</span>
          </label>

          {actionError && <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400"><AlertCircle size={15} />{actionError}</div>}
          {success && <div role="status" className="flex items-center gap-2 rounded-xl border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-400"><CheckCircle2 size={15} />{success}</div>}
          {validation && <div className={`rounded-xl border p-3 text-sm ${validation.valid ? "border-green-500/30 bg-green-500/10 text-green-400" : "border-red-500/30 bg-red-500/10 text-red-400"}`}>
            <p className="flex items-center gap-2 font-semibold">{validation.valid ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}{validation.valid ? "Definição válida" : "A definição precisa de ajustes"}</p>
            {validation.errors.map(item => <p key={`${item.path}-${item.code}`} className="mt-1 text-xs">{item.path}: {item.message}</p>)}
            {validation.warnings.map((item, index) => <p key={index} className="mt-1 text-xs text-yellow-400">Aviso: {warningText(item)}</p>)}
          </div>}

          {simulation && <div className="space-y-2 rounded-xl border border-blue-500/30 bg-blue-500/10 p-3">
            <p className="text-sm font-semibold text-cream">Resultado: {simulation.matched ? "evento corresponde" : "evento não corresponde"}</p>
            {simulation.would_execute.length === 0 ? <p className="text-xs text-stone">Nenhuma ação seria executada.</p> : simulation.would_execute.map((item, index) => (
              <div key={`${item.action_key ?? item.key}-${index}`} className="rounded-lg bg-surface-02/70 p-2 text-xs"><p className={item.allowed === false ? "text-red-400" : "text-green-400"}>{item.action_key ?? item.key}: {item.allowed === false ? "bloqueada" : "seria executada"}</p>{item.reason && <p className="mt-1 text-stone">{item.reason}</p>}{(item.preview != null || item.config != null) && <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[11px] text-parchment">{JSON.stringify(item.preview ?? item.config, null, 2)}</pre>}</div>
            ))}
            {(simulation.errors ?? []).map(item => <p key={`${item.path}-${item.code}`} className="text-xs text-red-400">{item.path}: {item.message}</p>)}
            {simulation.warnings.map((item, index) => <p key={index} className="text-xs text-yellow-400">Aviso: {warningText(item)}</p>)}
          </div>}

          <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
            <button type="button" onClick={() => void validateDefinition()} disabled={!selectable || busy !== null} className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-03 px-4 py-2 text-sm font-semibold text-stone hover:text-cream disabled:opacity-50">{busy === "validate" ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />} Validar</button>
            <button type="button" onClick={() => void simulateDefinition()} disabled={!selectable || busy !== null} className="inline-flex items-center justify-center gap-2 rounded-xl bg-gold px-4 py-2 text-sm font-semibold text-black hover:bg-gold/90 disabled:opacity-50">{busy === "simulate" ? <Loader2 size={14} className="animate-spin" /> : <Eye size={14} />} Simular sem executar</button>
            <button type="button" onClick={() => void saveDefinition()} disabled={!selectable || !name.trim() || busy !== null} className="inline-flex items-center justify-center gap-2 rounded-xl bg-green-500 px-4 py-2 text-sm font-semibold text-black hover:bg-green-400 disabled:opacity-50">{busy === "save" ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />} Salvar automação</button>
          </div>
        </>
      )}
    </section>
  );
}

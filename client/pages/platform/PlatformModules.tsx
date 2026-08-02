import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Archive,
  Boxes,
  CheckCircle2,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import { ConfirmationDialog } from "@/components/platform/PlatformComponents";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { platformModulesApi, type ApiPlatformModule } from "@/lib/api";
import {
  EMPTY_PLATFORM_MODULE_DRAFT,
  PLATFORM_MODULE_GROUPS,
  normalizePlatformCatalogKey,
  parsePlatformModuleDefaultConfig,
  parsePlatformModuleDependencies,
  platformModuleDefaultConfigPayload,
  platformModuleToDraft,
  togglePlatformSelection,
  type PlatformModuleDraft,
  type PlatformModuleGroup,
} from "@/lib/platformCatalog";

const GROUP_LABELS: Record<PlatformModuleGroup, string> = {
  operation: "Operacao",
  delivery: "Delivery",
  management: "Gestao",
  marketing: "Marketing",
  crm: "CRM",
  integrations: "Integracoes",
};

const MODULE_KEY_PATTERN = /^[a-z0-9][a-z0-9_.-]{1,99}$/;

export default function PlatformModules() {
  const { toast } = useToast();
  const [items, setItems] = useState<ApiPlatformModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<ApiPlatformModule | null>(null);
  const [draft, setDraft] = useState<PlatformModuleDraft>(EMPTY_PLATFORM_MODULE_DRAFT);
  const [editReason, setEditReason] = useState("");
  const [configError, setConfigError] = useState("");
  const [statusTarget, setStatusTarget] = useState<ApiPlatformModule | null>(null);
  const [statusReason, setStatusReason] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setItems(await platformModulesApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar os modulos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const defaultConfigProtected = draft.module_group === "integrations"
    || editing?.module_group === "integrations";
  const configIsValid = useMemo(() => {
    if (defaultConfigProtected) return true;
    try {
      parsePlatformModuleDefaultConfig(draft.default_config_text);
      return true;
    } catch {
      return false;
    }
  }, [defaultConfigProtected, draft.default_config_text]);

  const draftIsValid = MODULE_KEY_PATTERN.test(draft.key)
    && draft.name.trim().length >= 2
    && configIsValid
    && (!editing || editReason.trim().length >= 3);

  function openCreate() {
    setEditing(null);
    setDraft({ ...EMPTY_PLATFORM_MODULE_DRAFT, dependencies: [] });
    setEditReason("");
    setConfigError("");
    setEditorOpen(true);
  }

  function openEdit(module: ApiPlatformModule) {
    setEditing(module);
    setDraft(platformModuleToDraft(module));
    setEditReason("");
    setConfigError("");
    setEditorOpen(true);
  }

  async function save() {
    if (!draftIsValid || saving) return;
    let defaultConfigFields: { default_config?: Record<string, unknown> };
    try {
      defaultConfigFields = platformModuleDefaultConfigPayload(draft, editing?.module_group);
      setConfigError("");
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : "JSON invalido.");
      return;
    }

    const fields = {
      name: draft.name.trim(),
      description: draft.description.trim() || null,
      module_group: draft.module_group,
      display_order: Math.max(0, draft.display_order),
      dependencies: draft.dependencies,
      ...defaultConfigFields,
    };
    setSaving(true);
    try {
      if (editing) {
        await platformModulesApi.update(editing.id, {
          ...fields,
          reason: editReason.trim(),
        });
      } else {
        await platformModulesApi.create({
          key: draft.key,
          active: true,
          ...fields,
        });
      }
      await load();
      setEditorOpen(false);
      toast({ title: editing ? "Modulo atualizado" : "Modulo criado" });
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Nao foi possivel salvar",
        description: err instanceof Error ? err.message : "Tente novamente.",
      });
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus() {
    if (!statusTarget || statusReason.trim().length < 3 || saving) return;
    const activating = !statusTarget.active;
    setSaving(true);
    try {
      await platformModulesApi.update(statusTarget.id, {
        active: activating,
        reason: statusReason.trim(),
      });
      await load();
      setStatusTarget(null);
      setStatusReason("");
      toast({ title: activating ? "Modulo reativado" : "Modulo arquivado" });
    } catch (err) {
      toast({
        variant: "destructive",
        title: activating ? "Nao foi possivel reativar" : "Nao foi possivel arquivar",
        description: err instanceof Error ? err.message : "Tente novamente.",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button onClick={openCreate} className="gap-2 bg-gold text-surface-00 hover:bg-gold/90">
          <Plus size={15} /> Novo modulo
        </Button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
          <Button variant="ghost" size="sm" onClick={() => void load()} className="ml-3 gap-1">
            <RefreshCw size={13} /> Repetir
          </Button>
        </div>
      )}

      {loading ? (
        <div className="flex min-h-56 items-center justify-center"><Loader2 className="animate-spin text-gold" /></div>
      ) : !items.length ? (
        <div className="rounded-2xl border border-dashed border-surface-03 p-10 text-center text-stone">Nenhum modulo cadastrado.</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((module) => {
            const dependencies = parsePlatformModuleDependencies(module.dependencies_json);
            return (
              <article key={module.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gold/10 text-gold"><Boxes size={18} /></span>
                    <div className="min-w-0">
                      <h2 className="font-black text-cream">{module.name}</h2>
                      <p className="mt-1 break-all text-xs text-stone">{module.key}</p>
                    </div>
                  </div>
                  <CheckCircle2 size={18} className={module.active ? "text-green-300" : "text-stone"} />
                </div>
                <p className="mt-4 text-sm text-stone">{module.description || "Sem descricao."}</p>
                <div className="mt-4 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full border border-surface-03 px-2 py-1 text-stone">{GROUP_LABELS[module.module_group]}</span>
                  <span className="rounded-full border border-surface-03 px-2 py-1 text-stone">Ordem {module.display_order ?? 0}</span>
                  <span className={module.active ? "rounded-full border border-green-500/30 px-2 py-1 text-green-300" : "rounded-full border border-stone/30 px-2 py-1 text-stone"}>{module.active ? "Ativo" : "Arquivado"}</span>
                </div>
                <div className="mt-4 rounded-xl border border-surface-03 bg-surface-01 p-3 text-xs">
                  <p className="font-bold text-cream">Dependencias</p>
                  <p className="mt-1 break-words text-stone">{dependencies.length ? dependencies.join(", ") : "Nenhuma"}</p>
                  <p className="mt-3 font-bold text-cream">Configuracao padrao</p>
                  {module.module_group === "integrations" ? (
                    <p className="mt-1 text-stone">
                      {module.config_configured ? "Configurada e protegida pelo backend" : "Nao configurada"}
                    </p>
                  ) : (
                    <code className="mt-1 block max-h-16 overflow-hidden break-all text-stone">{module.default_config_json || "{}"}</code>
                  )}
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => openEdit(module)} className="gap-2"><Pencil size={13} /> Editar</Button>
                  <Button
                    variant={module.active ? "destructive" : "outline"}
                    size="sm"
                    onClick={() => { setStatusTarget(module); setStatusReason(""); }}
                    className="gap-2"
                  >
                    {module.active ? <Archive size={13} /> : <RotateCcw size={13} />}
                    {module.active ? "Arquivar" : "Reativar"}
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {editorOpen && (
        <ConfirmationDialog
          open
          onOpenChange={setEditorOpen}
          title={editing ? "Editar modulo" : "Criar modulo"}
          description="Dependencias usam as chaves de enforcement. A configuracao padrao precisa ser um objeto JSON valido."
          confirmLabel={saving ? "Salvando..." : "Salvar modulo"}
          confirmDisabled={saving || !draftIsValid}
          preventCloseOnConfirm
          reason={editing ? editReason : undefined}
          reasonRequired={!!editing}
          onReasonChange={editing ? setEditReason : undefined}
          onConfirm={() => void save()}
        >
          <ModuleForm
            draft={draft}
            modules={items}
            editing={editing}
            configError={configError || (!configIsValid ? "Informe um objeto JSON valido." : "")}
            onChange={(next) => { setDraft(next); setConfigError(""); }}
          />
        </ConfirmationDialog>
      )}

      {statusTarget && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => { if (!open) setStatusTarget(null); }}
          title={statusTarget.active ? "Arquivar modulo" : "Reativar modulo"}
          description={statusTarget.active
            ? "O backend impedira o arquivamento enquanto o modulo estiver atribuido a plano, empresa ou for dependencia ativa."
            : "O modulo voltara a ficar disponivel para planos e empresas."}
          confirmLabel={saving ? "Salvando..." : statusTarget.active ? "Arquivar" : "Reativar"}
          destructive={statusTarget.active}
          confirmDisabled={saving}
          preventCloseOnConfirm
          reason={statusReason}
          reasonRequired
          onReasonChange={setStatusReason}
          onConfirm={() => void changeStatus()}
        />
      )}
    </div>
  );
}

function ModuleForm({
  draft,
  modules,
  editing,
  configError,
  onChange,
}: {
  draft: PlatformModuleDraft;
  modules: ApiPlatformModule[];
  editing: ApiPlatformModule | null;
  configError: string;
  onChange: (draft: PlatformModuleDraft) => void;
}) {
  const set = <K extends keyof PlatformModuleDraft>(key: K, value: PlatformModuleDraft[K]) => {
    onChange({ ...draft, [key]: value });
  };
  const dependencyOptions = modules.filter((module) => module.active && module.id !== editing?.id);

  return (
    <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-2">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Nome" value={draft.name} onChange={(value) => set("name", value)} />
        <Field
          label="Chave unica"
          value={draft.key}
          readOnly={!!editing}
          onChange={(value) => set("key", normalizePlatformCatalogKey(value))}
        />
        <Field label="Descricao" value={draft.description} onChange={(value) => set("description", value)} />
        <label className="space-y-2 text-sm">
          <span className="font-bold text-cream">Grupo</span>
          <select disabled={editing?.module_group === "integrations"} value={draft.module_group} onChange={(event) => set("module_group", event.target.value as PlatformModuleGroup)} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream disabled:cursor-not-allowed disabled:opacity-60">
            {PLATFORM_MODULE_GROUPS.map((group) => <option key={group} value={group}>{GROUP_LABELS[group]}</option>)}
          </select>
        </label>
        <label className="space-y-2 text-sm">
          <span className="font-bold text-cream">Ordem de exibicao</span>
          <Input type="number" min={0} value={draft.display_order} onChange={(event) => set("display_order", Math.max(0, Number(event.target.value) || 0))} className="border-surface-03 bg-surface-01 text-cream" />
        </label>
      </div>

      <div>
        <p className="mb-2 text-sm font-bold text-cream">Dependencias obrigatorias</p>
        {!dependencyOptions.length ? (
          <p className="rounded-xl border border-dashed border-surface-03 p-4 text-xs text-stone">Nenhum outro modulo ativo disponivel.</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {dependencyOptions.map((module) => (
              <label key={module.id} className="flex items-start gap-2 rounded-lg border border-surface-03 p-3 text-sm text-stone">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={draft.dependencies.includes(module.key)}
                  onChange={(event) => set("dependencies", togglePlatformSelection(draft.dependencies, module.key, event.target.checked))}
                />
                <span><strong className="block text-cream">{module.name}</strong><span className="text-xs">{module.key}</span></span>
              </label>
            ))}
          </div>
        )}
      </div>

      {draft.module_group === "integrations" || editing?.module_group === "integrations" ? (
        <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 p-4 text-sm text-blue-100">
          A configuracao desta integracao e protegida. Alteracoes de metadados nao leem nem reenviam credenciais ocultas.
        </div>
      ) : (
        <label className="block space-y-2 text-sm">
          <span className="font-bold text-cream">Configuracao padrao (JSON)</span>
          <Textarea
            value={draft.default_config_text}
            onChange={(event) => set("default_config_text", event.target.value)}
            spellCheck={false}
            className="min-h-32 border-surface-03 bg-surface-01 font-mono text-xs text-cream"
          />
          {configError && <span className="block text-xs text-red-200">{configError}</span>}
        </label>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  readOnly,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
}) {
  return (
    <label className="space-y-2 text-sm">
      <span className="font-bold text-cream">{label}</span>
      <Input readOnly={readOnly} value={value} onChange={(event) => onChange(event.target.value)} className="border-surface-03 bg-surface-01 text-cream" />
    </label>
  );
}

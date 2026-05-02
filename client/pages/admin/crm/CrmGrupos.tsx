import { useEffect, useState } from "react";
import {
  FolderOpen,
  Hash,
  Layers3,
  Loader2,
  MinusCircle,
  Pencil,
  PlayCircle,
  Plus,
  PlusCircle,
  Tags,
  Trash2,
  X,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import {
  crmApi,
  type ApiCustomerSegment,
  type ApiCustomerSegmentRule,
  type ApiCustomerTag,
} from "@/lib/api";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

type Tab = "groups" | "tags" | "segments";
type GroupType = "manual" | "dynamic";

interface DynamicRule {
  field: string;
  operator: string;
  value: string;
}

interface Group {
  id: string;
  name: string;
  group_type: GroupType;
  color: string;
  icon: string;
  description?: string;
  member_count: number;
  rules?: DynamicRule[];
}

const COLORS = [
  "#f97316", "#ef4444", "#8b5cf6", "#3b82f6",
  "#10b981", "#f59e0b", "#ec4899", "#06b6d4",
];

const FIELD_OPTIONS = [
  { value: "last_order_days", label: "Dias desde ultimo pedido" },
  { value: "total_orders", label: "Total de pedidos" },
  { value: "total_spent", label: "Total gasto" },
  { value: "avg_ticket", label: "Ticket medio" },
  { value: "days_without_order", label: "Dias sem pedido" },
  { value: "city", label: "Cidade" },
  { value: "neighborhood", label: "Bairro" },
  { value: "birth_month", label: "Mes de aniversario" },
  { value: "customer_status", label: "Status do cliente" },
  { value: "coupon_used", label: "Cupom usado" },
  { value: "campaign_origin", label: "Origem de campanha" },
];

const OPERATOR_OPTIONS = [
  { value: ">", label: "maior que" },
  { value: "<", label: "menor que" },
  { value: "=", label: "igual a" },
  { value: "!=", label: "diferente de" },
  { value: ">=", label: "maior ou igual" },
  { value: "<=", label: "menor ou igual" },
  { value: "contains", label: "contem" },
];

const emptyGroupForm = (): Partial<Group> => ({
  name: "",
  group_type: "manual",
  color: "#f97316",
  icon: "G",
  description: "",
  rules: [],
});

const emptyTagForm = () => ({
  name: "",
  description: "",
  color: "#f97316",
});

const emptySegmentForm = () => ({
  name: "",
  description: "",
  rules: [] as ApiCustomerSegmentRule[],
});

function SectionTabs({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  const tabs: Array<{ key: Tab; label: string; icon: typeof FolderOpen }> = [
    { key: "groups", label: "Grupos", icon: FolderOpen },
    { key: "tags", label: "Tags", icon: Tags },
    { key: "segments", label: "Segmentos", icon: Layers3 },
  ];

  return (
    <div className="flex flex-wrap gap-2 border-b border-surface-03 pb-3">
      {tabs.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
            active === key
              ? "bg-gold text-black"
              : "bg-surface-02 border border-surface-03 text-stone hover:text-cream"
          }`}
        >
          <Icon size={15} /> {label}
        </button>
      ))}
    </div>
  );
}

function RuleEditor({
  rules,
  onChange,
}: {
  rules: DynamicRule[];
  onChange: (rules: DynamicRule[]) => void;
}) {
  const addRule = () => {
    onChange([...rules, { field: "last_order_days", operator: ">", value: "30" }]);
  };
  const updateRule = (idx: number, key: keyof DynamicRule, value: string) => {
    onChange(rules.map((rule, i) => (i === idx ? { ...rule, [key]: value } : rule)));
  };
  const removeRule = (idx: number) => {
    onChange(rules.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-xs text-stone font-medium">Regras</label>
        <button
          type="button"
          onClick={addRule}
          className="flex items-center gap-1 text-xs text-gold hover:text-gold/80 transition-colors"
        >
          <PlusCircle size={14} /> Adicionar regra
        </button>
      </div>
      {rules.length === 0 && (
        <p className="text-stone text-xs text-center py-3 border border-dashed border-surface-03 rounded-xl">
          Nenhuma regra configurada.
        </p>
      )}
      {rules.map((rule, idx) => (
        <div key={idx} className="grid grid-cols-[1fr_120px_100px_24px] gap-2 items-center">
          <select
            value={rule.field}
            onChange={(event) => updateRule(idx, "field", event.target.value)}
            className="bg-surface-03 border border-surface-03 rounded-xl px-2 py-2 text-cream text-xs focus:outline-none focus:border-gold min-w-0"
          >
            {FIELD_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <select
            value={rule.operator}
            onChange={(event) => updateRule(idx, "operator", event.target.value)}
            className="bg-surface-03 border border-surface-03 rounded-xl px-2 py-2 text-cream text-xs focus:outline-none focus:border-gold"
          >
            {OPERATOR_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <input
            value={rule.value}
            onChange={(event) => updateRule(idx, "value", event.target.value)}
            placeholder="valor"
            className="bg-surface-03 border border-surface-03 rounded-xl px-2 py-2 text-cream text-xs focus:outline-none focus:border-gold min-w-0"
          />
          <button
            type="button"
            onClick={() => removeRule(idx)}
            className="text-stone hover:text-red-400 transition-colors"
          >
            <MinusCircle size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}

export default function CrmGrupos() {
  const [activeTab, setActiveTab] = useState<Tab>("groups");

  const [groups, setGroups] = useState<Group[]>([]);
  const [groupsLoading, setGroupsLoading] = useState(true);
  const [groupsError, setGroupsError] = useState("");
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null);
  const [groupForm, setGroupForm] = useState<Partial<Group>>(emptyGroupForm());

  const [tags, setTags] = useState<ApiCustomerTag[]>([]);
  const [tagsLoading, setTagsLoading] = useState(true);
  const [tagsError, setTagsError] = useState("");
  const [showTagModal, setShowTagModal] = useState(false);
  const [editingTagId, setEditingTagId] = useState<string | null>(null);
  const [tagForm, setTagForm] = useState(emptyTagForm());

  const [segments, setSegments] = useState<ApiCustomerSegment[]>([]);
  const [segmentsLoading, setSegmentsLoading] = useState(true);
  const [segmentsError, setSegmentsError] = useState("");
  const [showSegmentModal, setShowSegmentModal] = useState(false);
  const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null);
  const [segmentForm, setSegmentForm] = useState(emptySegmentForm());
  const [previewCounts, setPreviewCounts] = useState<Record<string, number>>({});

  const [saving, setSaving] = useState(false);

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  const inputCls = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

  const fetchGroups = () => {
    setGroupsLoading(true);
    setGroupsError("");
    fetch(`${BASE}/crm/groups`, { headers })
      .then((response) => {
        if (!response.ok) throw new Error("Falha ao carregar grupos.");
        return response.json();
      })
      .then(unwrap)
      .then(setGroups)
      .catch((error) => setGroupsError(error.message))
      .finally(() => setGroupsLoading(false));
  };

  const fetchTags = () => {
    setTagsLoading(true);
    setTagsError("");
    crmApi.listTags()
      .then(setTags)
      .catch((error) => setTagsError(error.message))
      .finally(() => setTagsLoading(false));
  };

  const fetchSegments = () => {
    setSegmentsLoading(true);
    setSegmentsError("");
    crmApi.listSegments()
      .then(setSegments)
      .catch((error) => setSegmentsError(error.message))
      .finally(() => setSegmentsLoading(false));
  };

  useEffect(() => {
    fetchGroups();
    fetchTags();
    fetchSegments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openCreateGroup = () => {
    setEditingGroupId(null);
    setGroupForm(emptyGroupForm());
    setShowGroupModal(true);
  };

  const openEditGroup = (group: Group) => {
    setEditingGroupId(group.id);
    setGroupForm({ ...group, rules: group.rules ? [...group.rules] : [] });
    setShowGroupModal(true);
  };

  const saveGroup = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!groupForm.name?.trim()) {
      alert("Nome obrigatorio.");
      return;
    }
    setSaving(true);
    try {
      const response = editingGroupId
        ? await fetch(`${BASE}/crm/groups/${editingGroupId}`, {
            method: "PATCH",
            headers,
            body: JSON.stringify(groupForm),
          })
        : await fetch(`${BASE}/crm/groups`, {
            method: "POST",
            headers,
            body: JSON.stringify(groupForm),
          });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        alert(payload?.error?.message ?? "Erro ao salvar grupo.");
        return;
      }
      setShowGroupModal(false);
      fetchGroups();
    } catch {
      alert("Erro ao salvar grupo.");
    } finally {
      setSaving(false);
    }
  };

  const evaluateGroup = async (id: string) => {
    const response = await fetch(`${BASE}/crm/groups/${id}/evaluate`, { method: "POST", headers });
    const payload = await response.json().catch(() => ({}));
    alert(payload?.data?.message ?? (response.ok ? "Avaliacao concluida." : "Erro ao avaliar."));
    fetchGroups();
  };

  const deleteGroup = async (id: string) => {
    if (!confirm("Inativar grupo?")) return;
    await fetch(`${BASE}/crm/groups/${id}`, { method: "DELETE", headers });
    fetchGroups();
  };

  const openCreateTag = () => {
    setEditingTagId(null);
    setTagForm(emptyTagForm());
    setShowTagModal(true);
  };

  const openEditTag = (tag: ApiCustomerTag) => {
    setEditingTagId(tag.id);
    setTagForm({
      name: tag.name,
      description: tag.description ?? "",
      color: tag.color,
    });
    setShowTagModal(true);
  };

  const saveTag = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!tagForm.name.trim()) {
      alert("Nome obrigatorio.");
      return;
    }
    setSaving(true);
    try {
      if (editingTagId) {
        await crmApi.updateTag(editingTagId, tagForm);
      } else {
        await crmApi.createTag(tagForm);
      }
      setShowTagModal(false);
      fetchTags();
    } catch (error) {
      alert(error instanceof Error ? error.message : "Erro ao salvar tag.");
    } finally {
      setSaving(false);
    }
  };

  const inactiveTag = async (id: string) => {
    if (!confirm("Inativar tag?")) return;
    await crmApi.inactiveTag(id);
    fetchTags();
  };

  const openCreateSegment = () => {
    setEditingSegmentId(null);
    setSegmentForm(emptySegmentForm());
    setShowSegmentModal(true);
  };

  const openEditSegment = (segment: ApiCustomerSegment) => {
    setEditingSegmentId(segment.id);
    setSegmentForm({
      name: segment.name,
      description: segment.description ?? "",
      rules: segment.rules ?? [],
    });
    setShowSegmentModal(true);
  };

  const saveSegment = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!segmentForm.name.trim()) {
      alert("Nome obrigatorio.");
      return;
    }
    setSaving(true);
    try {
      if (editingSegmentId) {
        await crmApi.updateSegment(editingSegmentId, segmentForm);
      } else {
        await crmApi.createSegment(segmentForm);
      }
      setShowSegmentModal(false);
      fetchSegments();
    } catch (error) {
      alert(error instanceof Error ? error.message : "Erro ao salvar segmento.");
    } finally {
      setSaving(false);
    }
  };

  const inactiveSegment = async (id: string) => {
    if (!confirm("Inativar segmento?")) return;
    await crmApi.inactiveSegment(id);
    fetchSegments();
  };

  const previewSegment = async (id: string) => {
    try {
      const preview = await crmApi.previewSegment(id, 10);
      setPreviewCounts((prev) => ({ ...prev, [id]: preview.total }));
    } catch (error) {
      alert(error instanceof Error ? error.message : "Erro ao calcular segmento.");
    }
  };

  const renderGroups = () => {
    if (groupsLoading) return <LoadingBlock />;
    if (groupsError) return <ErrorBlock message={groupsError} />;
    if (groups.length === 0) {
      return (
        <EmptyBlock
          icon={FolderOpen}
          title="Nenhum grupo criado ainda."
          action="Criar primeiro grupo"
          onAction={openCreateGroup}
        />
      );
    }

    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {groups.map((group) => (
          <div key={group.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-black shrink-0"
                  style={{ backgroundColor: `${group.color}20`, color: group.color }}
                >
                  {group.icon || "G"}
                </span>
                <div className="min-w-0">
                  <p className="text-cream font-semibold text-sm truncate">{group.name}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    group.group_type === "dynamic"
                      ? "bg-purple-500/20 text-purple-400"
                      : "bg-surface-03 text-stone"
                  }`}>
                    {group.group_type === "dynamic" ? "Dinamico" : "Manual"}
                  </span>
                </div>
              </div>
              <CardActions
                onEdit={() => openEditGroup(group)}
                onDelete={() => deleteGroup(group.id)}
                extra={group.group_type === "dynamic" ? (
                  <button
                    onClick={() => evaluateGroup(group.id)}
                    className="p-1.5 rounded-lg hover:bg-purple-500/10 text-stone hover:text-purple-400 transition-colors"
                    title="Avaliar regras"
                  >
                    <PlayCircle size={13} />
                  </button>
                ) : null}
              />
            </div>
            {group.description && <p className="text-stone text-xs leading-relaxed">{group.description}</p>}
            <div className="flex items-center justify-between text-xs border-t border-surface-03 pt-3">
              <span className="text-stone">{group.member_count} membros</span>
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: group.color }} />
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderTags = () => {
    if (tagsLoading) return <LoadingBlock />;
    if (tagsError) return <ErrorBlock message={tagsError} />;
    if (tags.length === 0) {
      return <EmptyBlock icon={Tags} title="Nenhuma tag criada ainda." action="Criar primeira tag" onAction={openCreateTag} />;
    }

    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {tags.map((tag) => (
          <div key={tag.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                  style={{ backgroundColor: `${tag.color}20`, color: tag.color }}
                >
                  <Hash size={18} />
                </span>
                <div className="min-w-0">
                  <p className="text-cream font-semibold text-sm truncate">{tag.name}</p>
                  <p className="text-stone/60 text-xs truncate">{tag.slug}</p>
                </div>
              </div>
              <CardActions onEdit={() => openEditTag(tag)} onDelete={() => inactiveTag(tag.id)} />
            </div>
            {tag.description && <p className="text-stone text-xs leading-relaxed">{tag.description}</p>}
            <div className="flex items-center justify-between text-xs border-t border-surface-03 pt-3">
              <span className="text-stone">{tag.member_count ?? 0} clientes</span>
              <span className="text-stone/60">{tag.source}</span>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderSegments = () => {
    if (segmentsLoading) return <LoadingBlock />;
    if (segmentsError) return <ErrorBlock message={segmentsError} />;
    if (segments.length === 0) {
      return <EmptyBlock icon={Layers3} title="Nenhum segmento criado ainda." action="Criar primeiro segmento" onAction={openCreateSegment} />;
    }

    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {segments.map((segment) => (
          <div key={segment.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-4">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-cream font-semibold text-sm truncate">{segment.name}</p>
                <p className="text-stone/60 text-xs truncate">{segment.slug}</p>
              </div>
              <CardActions
                onEdit={() => openEditSegment(segment)}
                onDelete={() => inactiveSegment(segment.id)}
                extra={(
                  <button
                    onClick={() => previewSegment(segment.id)}
                    className="p-1.5 rounded-lg hover:bg-gold/10 text-stone hover:text-gold transition-colors"
                    title="Calcular segmento"
                  >
                    <PlayCircle size={13} />
                  </button>
                )}
              />
            </div>
            {segment.description && <p className="text-stone text-xs leading-relaxed">{segment.description}</p>}
            <div className="space-y-2">
              {segment.rules.length === 0 ? (
                <p className="text-stone/60 text-xs">Sem regras configuradas.</p>
              ) : (
                segment.rules.map((rule, idx) => (
                  <div key={idx} className="flex flex-wrap gap-2 text-xs">
                    <span className="px-2 py-1 rounded-lg bg-surface-03 text-stone">{rule.field}</span>
                    <span className="px-2 py-1 rounded-lg bg-surface-03 text-stone">{rule.operator}</span>
                    <span className="px-2 py-1 rounded-lg bg-surface-03 text-cream">{rule.value}</span>
                  </div>
                ))
              )}
            </div>
            <div className="flex items-center justify-between text-xs border-t border-surface-03 pt-3">
              <span className="text-stone">
                {previewCounts[segment.id] == null ? "Nao calculado" : `${previewCounts[segment.id]} clientes`}
              </span>
              <span className="text-stone/60">{segment.source}</span>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">CRM</p>
            <h1 className="text-2xl font-bold text-cream">Grupos, Tags e Segmentos</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={activeTab === "groups" ? openCreateGroup : activeTab === "tags" ? openCreateTag : openCreateSegment}
              className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
            >
              <Plus size={16} />
              {activeTab === "groups" ? "Novo grupo" : activeTab === "tags" ? "Nova tag" : "Novo segmento"}
            </button>
            <AdminTopActions />
          </div>
        </div>

        <SectionTabs active={activeTab} onChange={setActiveTab} />

        {activeTab === "groups" && renderGroups()}
        {activeTab === "tags" && renderTags()}
        {activeTab === "segments" && renderSegments()}

        {showGroupModal && (
          <FormModal
            title={editingGroupId ? "Editar grupo" : "Novo grupo"}
            onClose={() => setShowGroupModal(false)}
            onSubmit={saveGroup}
            saving={saving}
          >
            <TextField label="Nome" value={groupForm.name ?? ""} onChange={(value) => setGroupForm((prev) => ({ ...prev, name: value }))} inputCls={inputCls} />
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-stone">Tipo</label>
                <select
                  value={groupForm.group_type ?? "manual"}
                  onChange={(event) => setGroupForm((prev) => ({ ...prev, group_type: event.target.value as GroupType }))}
                  className={inputCls}
                >
                  <option value="manual">Manual</option>
                  <option value="dynamic">Dinamico</option>
                </select>
              </div>
              <TextField label="Icone" value={groupForm.icon ?? "G"} onChange={(value) => setGroupForm((prev) => ({ ...prev, icon: value }))} inputCls={inputCls} />
            </div>
            <ColorPicker value={groupForm.color ?? "#f97316"} onChange={(value) => setGroupForm((prev) => ({ ...prev, color: value }))} />
            <TextArea label="Descricao" value={groupForm.description ?? ""} onChange={(value) => setGroupForm((prev) => ({ ...prev, description: value }))} inputCls={inputCls} />
            {groupForm.group_type === "dynamic" && (
              <RuleEditor
                rules={(groupForm.rules ?? []) as DynamicRule[]}
                onChange={(rules) => setGroupForm((prev) => ({ ...prev, rules }))}
              />
            )}
          </FormModal>
        )}

        {showTagModal && (
          <FormModal
            title={editingTagId ? "Editar tag" : "Nova tag"}
            onClose={() => setShowTagModal(false)}
            onSubmit={saveTag}
            saving={saving}
          >
            <TextField label="Nome" value={tagForm.name} onChange={(value) => setTagForm((prev) => ({ ...prev, name: value }))} inputCls={inputCls} />
            <ColorPicker value={tagForm.color} onChange={(value) => setTagForm((prev) => ({ ...prev, color: value }))} />
            <TextArea label="Descricao" value={tagForm.description} onChange={(value) => setTagForm((prev) => ({ ...prev, description: value }))} inputCls={inputCls} />
          </FormModal>
        )}

        {showSegmentModal && (
          <FormModal
            title={editingSegmentId ? "Editar segmento" : "Novo segmento"}
            onClose={() => setShowSegmentModal(false)}
            onSubmit={saveSegment}
            saving={saving}
          >
            <TextField label="Nome" value={segmentForm.name} onChange={(value) => setSegmentForm((prev) => ({ ...prev, name: value }))} inputCls={inputCls} />
            <TextArea label="Descricao" value={segmentForm.description} onChange={(value) => setSegmentForm((prev) => ({ ...prev, description: value }))} inputCls={inputCls} />
            <RuleEditor
              rules={segmentForm.rules}
              onChange={(rules) => setSegmentForm((prev) => ({ ...prev, rules }))}
            />
          </FormModal>
        )}
      </main>
    </div>
  );
}

function LoadingBlock() {
  return (
    <div className="flex items-center justify-center h-48">
      <Loader2 className="animate-spin text-gold" size={28} />
    </div>
  );
}

function ErrorBlock({ message }: { message: string }) {
  return <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">{message}</div>;
}

function EmptyBlock({
  icon: Icon,
  title,
  action,
  onAction,
}: {
  icon: typeof FolderOpen;
  title: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center bg-surface-02 border border-surface-03 rounded-2xl">
      <Icon size={40} className="text-surface-03 mb-3" />
      <p className="text-stone text-sm">{title}</p>
      <button onClick={onAction} className="mt-4 text-gold text-sm hover:underline">
        {action}
      </button>
    </div>
  );
}

function CardActions({
  onEdit,
  onDelete,
  extra,
}: {
  onEdit: () => void;
  onDelete: () => void;
  extra?: React.ReactNode;
}) {
  return (
    <div className="flex gap-1 shrink-0">
      {extra}
      <button
        onClick={onEdit}
        className="p-1.5 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors"
      >
        <Pencil size={13} />
      </button>
      <button
        onClick={onDelete}
        className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors"
      >
        <Trash2 size={13} />
      </button>
    </div>
  );
}

function FormModal({
  title,
  children,
  onClose,
  onSubmit,
  saving,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  onSubmit: (event: React.FormEvent) => void;
  saving: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b border-surface-03">
          <h2 className="text-cream font-semibold">{title}</h2>
          <button onClick={onClose} className="text-stone hover:text-cream">
            <X size={18} />
          </button>
        </div>
        <form onSubmit={onSubmit} className="p-5 space-y-4">
          {children}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              Salvar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  inputCls,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  inputCls: string;
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs text-stone">{label}</label>
      <input value={value} onChange={(event) => onChange(event.target.value)} className={inputCls} />
    </div>
  );
}

function TextArea({
  label,
  value,
  onChange,
  inputCls,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  inputCls: string;
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs text-stone">{label}</label>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={2} className={`${inputCls} resize-none`} />
    </div>
  );
}

function ColorPicker({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="space-y-2">
      <label className="text-xs text-stone">Cor</label>
      <div className="flex flex-wrap gap-2">
        {COLORS.map((color) => (
          <button
            key={color}
            type="button"
            onClick={() => onChange(color)}
            className={`w-7 h-7 rounded-full transition-transform hover:scale-110 ${
              value === color ? "ring-2 ring-white ring-offset-2 ring-offset-surface-02 scale-110" : ""
            }`}
            style={{ backgroundColor: color }}
          />
        ))}
      </div>
    </div>
  );
}

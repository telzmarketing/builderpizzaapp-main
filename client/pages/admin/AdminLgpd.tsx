import { useState, useEffect } from "react";
import { Shield, Plus, Trash2, Check, Eye, Edit2, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import { lgpdApi, type ApiLgpdPolicy } from "@/lib/api";

type PolicyForm = Omit<ApiLgpdPolicy, "id" | "created_at" | "updated_at">;

const EMPTY_FORM: PolicyForm = {
  version: "",
  title: "Política de Privacidade e Proteção de Dados",
  intro_text: "",
  data_controller_text: "",
  data_collected_text: "",
  data_usage_text: "",
  data_retention_text: "",
  rights_text: "",
  contact_text: "",
  marketing_email_label: "Desejo receber promoções e novidades por e-mail",
  marketing_whatsapp_label: "Desejo receber promoções e novidades pelo WhatsApp",
  is_active: false,
};

const SECTIONS: { key: keyof PolicyForm; label: string; hint: string; rows?: number }[] = [
  { key: "intro_text", label: "Introdução", hint: "Apresentação da política e referência à LGPD (Lei 13.709/2018)", rows: 4 },
  { key: "data_controller_text", label: "Controlador dos Dados", hint: "Identificação do responsável pelo tratamento dos dados", rows: 3 },
  { key: "data_collected_text", label: "Dados Coletados", hint: "Quais dados pessoais são coletados e como", rows: 4 },
  { key: "data_usage_text", label: "Finalidade do Uso", hint: "Para que os dados são utilizados (processamento de pedidos, marketing, etc.)", rows: 4 },
  { key: "data_retention_text", label: "Retenção e Exclusão", hint: "Por quanto tempo os dados são armazenados e como solicitar exclusão", rows: 3 },
  { key: "rights_text", label: "Direitos do Titular (LGPD Art. 18)", hint: "Direito de acesso, correção, exclusão, portabilidade, revogação", rows: 4 },
  { key: "contact_text", label: "Contato / DPO", hint: "Canal de contato para exercício de direitos e dúvidas sobre privacidade", rows: 3 },
];

function TextArea({
  label, hint, value, onChange, rows = 4,
}: { label: string; hint: string; value: string; onChange: (v: string) => void; rows?: number }) {
  return (
    <div>
      <label className="block text-stone text-xs font-medium mb-1">{label}</label>
      <p className="text-stone/50 text-[10px] mb-1.5">{hint}</p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        className="w-full bg-surface-01 border border-surface-03 focus:border-gold/60 rounded-xl px-4 py-3 text-cream placeholder-stone/40 outline-none text-sm resize-y transition-colors"
        placeholder={`${label}...`}
      />
    </div>
  );
}

function PolicyPreview({ policy }: { policy: PolicyForm }) {
  const sections = SECTIONS.map((s) => ({
    label: s.label,
    text: policy[s.key] as string,
  })).filter((s) => s.text?.trim());

  return (
    <div className="bg-surface-01 rounded-2xl border border-surface-03 overflow-hidden">
      <div className="bg-surface-03/60 px-5 py-4 border-b border-surface-03 flex items-center gap-3">
        <Shield size={18} className="text-gold flex-shrink-0" />
        <div>
          <p className="text-cream font-bold text-sm">{policy.title || "Política de Privacidade"}</p>
          {policy.version && <p className="text-stone text-xs mt-0.5">Versão {policy.version}</p>}
        </div>
      </div>

      <div className="px-5 py-4 space-y-4 max-h-80 overflow-y-auto">
        {sections.map((s) => (
          <div key={s.label}>
            <p className="text-gold text-xs font-bold uppercase tracking-wide mb-1">{s.label}</p>
            <p className="text-stone text-xs leading-relaxed">{s.text}</p>
          </div>
        ))}
        {sections.length === 0 && (
          <p className="text-stone/50 text-xs">Preencha as seções para visualizar a prévia.</p>
        )}
      </div>

      <div className="px-5 py-4 border-t border-surface-03 space-y-3">
        <div className="flex items-start gap-3 opacity-70">
          <div className="w-5 h-5 rounded border-2 border-surface-03 flex-shrink-0 mt-0.5" />
          <p className="text-cream text-xs">Li e aceito a Política de Privacidade e Proteção de Dados <span className="text-red-400">*</span></p>
        </div>
        {policy.marketing_email_label && (
          <div className="flex items-start gap-3 opacity-70">
            <div className="w-5 h-5 rounded border-2 border-surface-03 flex-shrink-0 mt-0.5" />
            <p className="text-stone text-xs">{policy.marketing_email_label} <span className="text-stone/50">(opcional)</span></p>
          </div>
        )}
        {policy.marketing_whatsapp_label && (
          <div className="flex items-start gap-3 opacity-70">
            <div className="w-5 h-5 rounded border-2 border-surface-03 flex-shrink-0 mt-0.5" />
            <p className="text-stone text-xs">{policy.marketing_whatsapp_label} <span className="text-stone/50">(opcional)</span></p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdminLgpd() {
  const [policies, setPolicies] = useState<ApiLgpdPolicy[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<PolicyForm>(EMPTY_FORM);
  const [showPreview, setShowPreview] = useState(false);
  const [activatingId, setActivatingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [toast, setToast] = useState("");

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const loadPolicies = async () => {
    setLoadingList(true);
    try {
      const list = await lgpdApi.list();
      setPolicies(list);
    } catch { /* ignore */ }
    finally { setLoadingList(false); }
  };

  useEffect(() => { loadPolicies(); }, []);

  const handleEdit = (p: ApiLgpdPolicy) => {
    setEditId(p.id);
    setForm({
      version: p.version,
      title: p.title,
      intro_text: p.intro_text ?? "",
      data_controller_text: p.data_controller_text ?? "",
      data_collected_text: p.data_collected_text ?? "",
      data_usage_text: p.data_usage_text ?? "",
      data_retention_text: p.data_retention_text ?? "",
      rights_text: p.rights_text ?? "",
      contact_text: p.contact_text ?? "",
      marketing_email_label: p.marketing_email_label ?? "",
      marketing_whatsapp_label: p.marketing_whatsapp_label ?? "",
      is_active: p.is_active,
    });
    setShowForm(true);
    setShowPreview(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleNew = async () => {
    setEditId(null);
    // Seed defaults if no policies exist
    if (policies.length === 0) {
      setSaving(true);
      try {
        await lgpdApi.seedDefault();
        await loadPolicies();
        showToast("Política padrão criada com textos pré-preenchidos.");
        return;
      } catch { /* ignore */ }
      finally { setSaving(false); }
    }
    setForm({ ...EMPTY_FORM, version: `${policies.length + 1}.0` });
    setShowForm(true);
    setShowPreview(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleSave = async () => {
    if (!form.version.trim() || !form.title.trim()) {
      showToast("Versão e título são obrigatórios.");
      return;
    }
    setSaving(true);
    try {
      if (editId) {
        await lgpdApi.update(editId, form);
        showToast("Política atualizada com sucesso.");
      } else {
        await lgpdApi.create(form);
        showToast("Política criada com sucesso.");
      }
      setShowForm(false);
      setEditId(null);
      await loadPolicies();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async (id: string) => {
    setActivatingId(id);
    try {
      await lgpdApi.activate(id);
      showToast("Política ativada. Será exibida no cadastro de clientes.");
      await loadPolicies();
    } catch { showToast("Erro ao ativar."); }
    finally { setActivatingId(null); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Excluir esta política? Esta ação não pode ser desfeita.")) return;
    try {
      await lgpdApi.remove(id);
      showToast("Política excluída.");
      await loadPolicies();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Erro ao excluir.");
    }
  };

  const setField = (key: keyof PolicyForm, value: string | boolean) =>
    setForm((p) => ({ ...p, [key]: value }));

  const activePolicy = policies.find((p) => p.is_active);

  return (
    <div className="flex h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 md:px-8 py-6 space-y-6">

          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-cream text-2xl font-bold flex items-center gap-2">
                <Shield size={24} className="text-gold" />
                LGPD — Privacidade
              </h1>
              <p className="text-stone text-sm mt-1">
                Gerencie os textos da Política de Privacidade exibidos no cadastro de clientes.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleNew}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2.5 bg-gold text-cream rounded-xl font-semibold text-sm hover:bg-gold/90 transition-colors disabled:opacity-60"
              >
                <Plus size={16} />
                {policies.length === 0 ? "Criar Política Padrão" : "Nova Versão"}
              </button>
              <AdminTopActions />
            </div>
          </div>

          {/* Toast */}
          {toast && (
            <div className="bg-green-500/20 border border-green-500/40 text-green-300 text-sm px-4 py-3 rounded-xl">
              {toast}
            </div>
          )}

          {/* Status banner */}
          {activePolicy && !showForm && (
            <div className="bg-gold/10 border border-gold/30 rounded-xl px-4 py-3 flex items-center gap-3">
              <Check size={16} className="text-gold flex-shrink-0" />
              <p className="text-cream text-sm">
                Política ativa: <span className="font-bold">{activePolicy.title}</span>
                <span className="text-stone ml-2">v{activePolicy.version}</span>
              </p>
            </div>
          )}

          {!activePolicy && !showForm && policies.length === 0 && !loadingList && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl px-4 py-4 text-center">
              <Shield size={28} className="text-amber-400 mx-auto mb-2" />
              <p className="text-amber-300 font-semibold text-sm">Nenhuma política cadastrada</p>
              <p className="text-stone text-xs mt-1">
                Clique em "Criar Política Padrão" para gerar uma política com textos pré-preenchidos conforme a LGPD.
              </p>
            </div>
          )}

          {/* Form */}
          {showForm && (
            <div className="bg-surface-02 rounded-2xl border border-surface-03 overflow-hidden">
              <div className="px-5 py-4 border-b border-surface-03 flex items-center justify-between">
                <p className="text-cream font-bold">
                  {editId ? "Editar Política" : "Nova Política"}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowPreview((v) => !v)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-surface-03 text-stone text-xs hover:border-gold/40 hover:text-cream transition-colors"
                  >
                    <Eye size={13} />
                    {showPreview ? "Ocultar prévia" : "Visualizar prévia"}
                  </button>
                  <button
                    onClick={() => { setShowForm(false); setEditId(null); }}
                    className="text-stone hover:text-cream text-xs px-3 py-1.5 border border-surface-03 rounded-lg transition-colors"
                  >
                    Cancelar
                  </button>
                </div>
              </div>

              <div className="p-5 space-y-5">
                {/* Version + Title */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-stone text-xs font-medium mb-1">Versão <span className="text-red-400">*</span></label>
                    <input
                      value={form.version}
                      onChange={(e) => setField("version", e.target.value)}
                      placeholder="1.0"
                      className="w-full bg-surface-01 border border-surface-03 focus:border-gold/60 rounded-xl px-4 py-3 text-cream outline-none text-sm transition-colors"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-stone text-xs font-medium mb-1">Título <span className="text-red-400">*</span></label>
                    <input
                      value={form.title}
                      onChange={(e) => setField("title", e.target.value)}
                      placeholder="Política de Privacidade e Proteção de Dados"
                      className="w-full bg-surface-01 border border-surface-03 focus:border-gold/60 rounded-xl px-4 py-3 text-cream outline-none text-sm transition-colors"
                    />
                  </div>
                </div>

                {/* Policy sections */}
                {SECTIONS.map((s) => (
                  <TextArea
                    key={s.key}
                    label={s.label}
                    hint={s.hint}
                    rows={s.rows}
                    value={(form[s.key] as string) ?? ""}
                    onChange={(v) => setField(s.key, v)}
                  />
                ))}

                {/* Marketing consent labels */}
                <div className="space-y-3 pt-2 border-t border-surface-03">
                  <p className="text-gold text-xs font-bold uppercase tracking-wide">Textos dos consentimentos de marketing</p>
                  <div>
                    <label className="block text-stone text-xs font-medium mb-1">Texto do checkbox de e-mail</label>
                    <input
                      value={form.marketing_email_label ?? ""}
                      onChange={(e) => setField("marketing_email_label", e.target.value)}
                      placeholder="Desejo receber promoções e novidades por e-mail"
                      className="w-full bg-surface-01 border border-surface-03 focus:border-gold/60 rounded-xl px-4 py-3 text-cream outline-none text-sm transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-stone text-xs font-medium mb-1">Texto do checkbox de WhatsApp</label>
                    <input
                      value={form.marketing_whatsapp_label ?? ""}
                      onChange={(e) => setField("marketing_whatsapp_label", e.target.value)}
                      placeholder="Desejo receber promoções e novidades pelo WhatsApp"
                      className="w-full bg-surface-01 border border-surface-03 focus:border-gold/60 rounded-xl px-4 py-3 text-cream outline-none text-sm transition-colors"
                    />
                  </div>
                </div>

                {/* Activate toggle */}
                <div className="flex items-center gap-3 bg-surface-01 rounded-xl px-4 py-3 border border-surface-03">
                  <button
                    type="button"
                    onClick={() => setField("is_active", !form.is_active)}
                    className={`w-10 h-5 rounded-full transition-colors flex-shrink-0 ${form.is_active ? "bg-gold" : "bg-surface-03"}`}
                  >
                    <span className={`block w-4 h-4 rounded-full bg-white shadow transition-transform mx-0.5 ${form.is_active ? "translate-x-5" : "translate-x-0"}`} />
                  </button>
                  <div>
                    <p className="text-cream text-sm font-medium">Ativar esta versão</p>
                    <p className="text-stone text-xs">Ao ativar, esta versão será exibida no cadastro de clientes e as demais serão desativadas.</p>
                  </div>
                </div>

                {/* Preview */}
                {showPreview && (
                  <div>
                    <p className="text-gold text-xs font-bold uppercase tracking-wide mb-3">Prévia — como o cliente verá</p>
                    <PolicyPreview policy={form} />
                  </div>
                )}

                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="w-full py-3 rounded-xl bg-gold text-cream font-bold hover:bg-gold/90 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {saving ? <><Loader2 size={16} className="animate-spin" /> Salvando...</> : <><Check size={16} /> Salvar Política</>}
                </button>
              </div>
            </div>
          )}

          {/* Policies list */}
          {loadingList ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={28} className="animate-spin text-gold" />
            </div>
          ) : (
            <div className="space-y-3">
              {policies.map((p) => (
                <div key={p.id} className={`bg-surface-02 rounded-2xl border overflow-hidden transition-colors ${p.is_active ? "border-gold/40" : "border-surface-03"}`}>
                  {/* Row header */}
                  <div className="flex items-center gap-3 px-5 py-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-cream font-semibold text-sm truncate">{p.title}</p>
                        <span className="text-[10px] text-stone bg-surface-03 px-1.5 py-0.5 rounded">v{p.version}</span>
                        {p.is_active && (
                          <span className="text-[10px] font-bold text-gold bg-gold/15 border border-gold/25 px-1.5 py-0.5 rounded flex items-center gap-1">
                            <Check size={9} /> Ativa
                          </span>
                        )}
                      </div>
                      <p className="text-stone text-xs mt-0.5">
                        {new Date(p.updated_at).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" })}
                      </p>
                    </div>

                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {!p.is_active && (
                        <button
                          onClick={() => handleActivate(p.id)}
                          disabled={activatingId === p.id}
                          className="px-3 py-1.5 bg-gold/15 border border-gold/30 text-gold text-xs rounded-lg hover:bg-gold/25 transition-colors disabled:opacity-60"
                        >
                          {activatingId === p.id ? <Loader2 size={12} className="animate-spin" /> : "Ativar"}
                        </button>
                      )}
                      <button
                        onClick={() => handleEdit(p)}
                        className="p-1.5 text-stone hover:text-cream rounded-lg hover:bg-surface-03 transition-colors"
                      >
                        <Edit2 size={14} />
                      </button>
                      {!p.is_active && (
                        <button
                          onClick={() => handleDelete(p.id)}
                          className="p-1.5 text-red-400/60 hover:text-red-400 rounded-lg hover:bg-red-500/10 transition-colors"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                      <button
                        onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}
                        className="p-1.5 text-stone hover:text-cream rounded-lg hover:bg-surface-03 transition-colors"
                      >
                        {expandedId === p.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                    </div>
                  </div>

                  {/* Expanded content */}
                  {expandedId === p.id && (
                    <div className="border-t border-surface-03 px-5 py-4">
                      <PolicyPreview policy={{
                        version: p.version, title: p.title,
                        intro_text: p.intro_text ?? "", data_controller_text: p.data_controller_text ?? "",
                        data_collected_text: p.data_collected_text ?? "", data_usage_text: p.data_usage_text ?? "",
                        data_retention_text: p.data_retention_text ?? "", rights_text: p.rights_text ?? "",
                        contact_text: p.contact_text ?? "",
                        marketing_email_label: p.marketing_email_label ?? "",
                        marketing_whatsapp_label: p.marketing_whatsapp_label ?? "",
                        is_active: p.is_active,
                      }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* LGPD info box */}
          <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5">
            <p className="text-cream font-semibold text-sm mb-3 flex items-center gap-2">
              <Shield size={15} className="text-gold" />
              Requisitos legais (LGPD)
            </p>
            <ul className="space-y-2 text-stone text-xs">
              {[
                "Identifique claramente o controlador dos dados (sua empresa)",
                "Liste todos os dados pessoais coletados (nome, email, telefone, endereço)",
                "Informe a finalidade de cada dado coletado",
                "Descreva o prazo de retenção e como solicitar exclusão",
                "Inclua os direitos dos titulares conforme Art. 18 da LGPD",
                "Forneça um canal de contato para exercício de direitos",
                "Mantenha versões anteriores arquivadas para fins de auditoria",
              ].map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <Check size={11} className="text-gold mt-0.5 flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}

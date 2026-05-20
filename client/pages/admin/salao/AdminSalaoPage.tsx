import { useEffect, useState } from "react";
import { CalendarDays, Check, FileText, Image, Loader2, MapPin, Plus, Save, Trash2, Utensils } from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";
import ImageUpload from "@/components/admin/ImageUpload";
import {
  salaoPageApi,
  type ApiSalaoExperienceCard,
  type ApiSalaoMenuItem,
  type ApiSalaoPageSettings,
} from "@/lib/api";

type Tab = "hero" | "experience" | "menu" | "reservation" | "contact";

const TABS: AdminPageTab<Tab>[] = [
  { id: "hero", icon: <Image size={15} />, label: "Topo" },
  { id: "experience", icon: <FileText size={15} />, label: "Experiencia" },
  { id: "menu", icon: <Utensils size={15} />, label: "Cardapio" },
  { id: "reservation", icon: <CalendarDays size={15} />, label: "Reservas" },
  { id: "contact", icon: <MapPin size={15} />, label: "Contato & SEO" },
];

const EMPTY_CARD: ApiSalaoExperienceCard = { title: "", text: "", image: "" };
const EMPTY_MENU_ITEM: ApiSalaoMenuItem = { name: "", description: "" };

export default function AdminSalaoPage() {
  const [tab, setTab] = useState<Tab>("hero");
  const [draft, setDraft] = useState<ApiSalaoPageSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    salaoPageApi.get()
      .then(setDraft)
      .catch(() => setError("Nao foi possivel carregar a configuracao da Pagina Salao."))
      .finally(() => setLoading(false));
  }, []);

  const setField = <K extends keyof ApiSalaoPageSettings>(key: K, value: ApiSalaoPageSettings[K]) => {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const updateCard = (index: number, patch: Partial<ApiSalaoExperienceCard>) => {
    if (!draft) return;
    const next = draft.experience_cards.map((card, idx) => (idx === index ? { ...card, ...patch } : card));
    setField("experience_cards", next);
  };

  const updateMenuItem = (index: number, patch: Partial<ApiSalaoMenuItem>) => {
    if (!draft) return;
    const next = draft.menu_items.map((item, idx) => (idx === index ? { ...item, ...patch } : item));
    setField("menu_items", next);
  };

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    setError("");
    try {
      const updated = await salaoPageApi.update(draft);
      setDraft(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar Pagina Salao.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminPageShell>
      <AdminPageHeader
        eyebrow="Configuracoes"
        title="Pagina Salao"
        description="Conteudo publico do dominio moschettieri.com.br"
        icon={<FileText size={20} />}
        actions={
          <button
            type="button"
            onClick={save}
            disabled={saving || loading || !draft}
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-gold px-4 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saved ? <Check size={16} /> : saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {saved ? "Salvo" : saving ? "Salvando" : "Salvar"}
          </button>
        }
      />
      <AdminPageContent>
        <AdminPageTabs tabs={TABS} active={tab} onChange={(next) => setTab(next as Tab)} />
        {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{error}</div>}

        {loading || !draft ? (
          <div className="flex items-center justify-center gap-3 rounded-xl border border-surface-03 bg-surface-02 p-10 text-stone">
            <Loader2 className="animate-spin" size={20} />
            Carregando Pagina Salao...
          </div>
        ) : (
          <>
            {tab === "hero" && (
              <Panel title="Topo da pagina" subtitle="Hero principal da experiencia publica do salao">
                <Toggle checked={draft.enabled} onChange={(value) => setField("enabled", value)} label="Pagina ativa" />
                <Field label="Chamada superior" value={draft.hero_eyebrow} onChange={(value) => setField("hero_eyebrow", value)} />
                <Field label="Titulo principal" value={draft.hero_title} onChange={(value) => setField("hero_title", value)} />
                <Field label="Subtitulo" value={draft.hero_subtitle} onChange={(value) => setField("hero_subtitle", value)} />
                <Field label="Descricao" value={draft.hero_description} onChange={(value) => setField("hero_description", value)} multiline />
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Botao principal" value={draft.primary_cta_label} onChange={(value) => setField("primary_cta_label", value)} />
                  <Field label="Botao secundario" value={draft.secondary_cta_label} onChange={(value) => setField("secondary_cta_label", value)} />
                </div>
                <ImageUpload label="Imagem de fundo" value={draft.hero_background_image} onChange={(value) => setField("hero_background_image", value)} maxKB={3072} sizeGuide="Imagem ampla do ambiente, ate 3MB" />
                <ImageUpload label="Imagem de destaque" value={draft.hero_plate_image} onChange={(value) => setField("hero_plate_image", value)} maxKB={3072} sizeGuide="Prato/produto em PNG ou imagem recortada, ate 3MB" />
              </Panel>
            )}

            {tab === "experience" && (
              <Panel title="Experiencia" subtitle="Secao institucional com imagens do ambiente">
                <Field label="Chamada" value={draft.experience_eyebrow} onChange={(value) => setField("experience_eyebrow", value)} />
                <Field label="Titulo" value={draft.experience_title} onChange={(value) => setField("experience_title", value)} />
                <Field label="Texto" value={draft.experience_text} onChange={(value) => setField("experience_text", value)} multiline />
                <ListEditor
                  title="Cards da experiencia"
                  onAdd={() => setField("experience_cards", [...draft.experience_cards, EMPTY_CARD])}
                >
                  {draft.experience_cards.map((card, index) => (
                    <div key={index} className="rounded-xl border border-surface-03 bg-surface-01 p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-[0.18em] text-gold">Card {index + 1}</span>
                        <RemoveButton onClick={() => setField("experience_cards", draft.experience_cards.filter((_, idx) => idx !== index))} />
                      </div>
                      <div className="grid gap-4">
                        <Field label="Titulo" value={card.title} onChange={(value) => updateCard(index, { title: value })} />
                        <Field label="Texto" value={card.text} onChange={(value) => updateCard(index, { text: value })} multiline />
                        <ImageUpload label="Imagem" value={card.image} onChange={(value) => updateCard(index, { image: value })} maxKB={3072} sizeGuide="Foto do ambiente, ate 3MB" />
                      </div>
                    </div>
                  ))}
                </ListEditor>
              </Panel>
            )}

            {tab === "menu" && (
              <Panel title="Cardapio institucional" subtitle="Destaques exibidos na pagina publica, sem alterar o catalogo delivery">
                <Field label="Chamada" value={draft.menu_eyebrow} onChange={(value) => setField("menu_eyebrow", value)} />
                <Field label="Titulo" value={draft.menu_title} onChange={(value) => setField("menu_title", value)} />
                <ListEditor
                  title="Itens em destaque"
                  onAdd={() => setField("menu_items", [...draft.menu_items, EMPTY_MENU_ITEM])}
                >
                  {draft.menu_items.map((item, index) => (
                    <div key={index} className="rounded-xl border border-surface-03 bg-surface-01 p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-[0.18em] text-gold">Item {index + 1}</span>
                        <RemoveButton onClick={() => setField("menu_items", draft.menu_items.filter((_, idx) => idx !== index))} />
                      </div>
                      <div className="grid gap-4">
                        <Field label="Nome" value={item.name} onChange={(value) => updateMenuItem(index, { name: value })} />
                        <Field label="Descricao" value={item.description} onChange={(value) => updateMenuItem(index, { description: value })} multiline />
                      </div>
                    </div>
                  ))}
                </ListEditor>
              </Panel>
            )}

            {tab === "reservation" && (
              <Panel title="Reservas" subtitle="Textos e imagem do bloco de solicitacao de reserva">
                <Field label="Chamada" value={draft.reservation_eyebrow} onChange={(value) => setField("reservation_eyebrow", value)} />
                <Field label="Titulo" value={draft.reservation_title} onChange={(value) => setField("reservation_title", value)} />
                <Field label="Texto" value={draft.reservation_text} onChange={(value) => setField("reservation_text", value)} multiline />
                <ImageUpload label="Imagem de fundo" value={draft.reservation_background_image} onChange={(value) => setField("reservation_background_image", value)} maxKB={3072} sizeGuide="Imagem horizontal do salao, ate 3MB" />
              </Panel>
            )}

            {tab === "contact" && (
              <Panel title="Contato & SEO" subtitle="Dados institucionais do rodape e metadados da pagina">
                <Field label="Endereco" value={draft.address} onChange={(value) => setField("address", value)} />
                <Field label="Horario de funcionamento" value={draft.hours} onChange={(value) => setField("hours", value)} />
                <Field label="Telefone / contato" value={draft.phone} onChange={(value) => setField("phone", value)} />
                <Field label="Link WhatsApp" value={draft.whatsapp_url} onChange={(value) => setField("whatsapp_url", value)} />
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Titulo SEO" value={draft.seo_title} onChange={(value) => setField("seo_title", value)} />
                  <Field label="Descricao SEO" value={draft.seo_description} onChange={(value) => setField("seo_description", value)} multiline />
                </div>
              </Panel>
            )}
          </>
        )}
      </AdminPageContent>
    </AdminPageShell>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-5 rounded-xl border border-surface-03 bg-surface-02 p-5">
      <div>
        <h2 className="text-lg font-black text-cream">{title}</h2>
        <p className="text-sm text-stone">{subtitle}</p>
      </div>
      <div className="grid gap-4">{children}</div>
    </section>
  );
}

function Field({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  const className = "w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none focus:border-gold";
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-semibold text-stone">{label}</span>
      {multiline ? (
        <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={3} className={`${className} resize-y`} />
      ) : (
        <input value={value} onChange={(event) => onChange(event.target.value)} className={className} />
      )}
    </label>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`flex w-fit items-center gap-2 rounded-xl border px-3 py-2 text-sm font-bold ${
        checked ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-red-500/30 bg-red-500/10 text-red-300"
      }`}
    >
      {checked ? "Ativa" : "Inativa"} - {label}
    </button>
  );
}

function ListEditor({ title, onAdd, children }: { title: string; onAdd: () => void; children: React.ReactNode }) {
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-black text-cream">{title}</h3>
        <button type="button" onClick={onAdd} className="inline-flex h-9 items-center gap-2 rounded-xl border border-gold/35 px-3 text-xs font-bold text-gold hover:bg-gold/10">
          <Plus size={14} />
          Adicionar
        </button>
      </div>
      <div className="grid gap-3">{children}</div>
    </div>
  );
}

function RemoveButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex h-8 items-center gap-1 rounded-lg border border-red-500/30 px-2 text-xs font-bold text-red-300 hover:bg-red-500/10">
      <Trash2 size={13} />
      Remover
    </button>
  );
}

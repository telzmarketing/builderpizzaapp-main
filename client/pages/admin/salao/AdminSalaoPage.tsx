import { useEffect, useMemo, useState } from "react";
import { Check, Eye, FileText, Image, Loader2, RotateCcw, Save, Search, Settings } from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";
import ImageUpload from "@/components/admin/ImageUpload";
import { resolveAssetUrl, salaoPageApi, type ApiSalaoPageSettings } from "@/lib/api";
import {
  applySalaoSiteOverrides,
  extractSalaoSiteImageTargets,
  extractSalaoSiteTextTargets,
  type SalaoSiteImageTarget,
  type SalaoSiteTextTarget,
} from "@/lib/salaoSiteCms";

type Tab = "texts" | "images" | "seo" | "preview";

const SALAO_SITE_URL = "/salao-site/index.html";

const TABS: AdminPageTab<Tab>[] = [
  { id: "texts", icon: <FileText size={15} />, label: "Textos" },
  { id: "images", icon: <Image size={15} />, label: "Imagens" },
  { id: "seo", icon: <Settings size={15} />, label: "SEO & Publicacao" },
  { id: "preview", icon: <Eye size={15} />, label: "Previa" },
];

export default function AdminSalaoPage() {
  const [tab, setTab] = useState<Tab>("texts");
  const [draft, setDraft] = useState<ApiSalaoPageSettings | null>(null);
  const [siteHtml, setSiteHtml] = useState("");
  const [textTargets, setTextTargets] = useState<SalaoSiteTextTarget[]>([]);
  const [imageTargets, setImageTargets] = useState<SalaoSiteImageTarget[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      salaoPageApi.get(),
      fetch(SALAO_SITE_URL).then((response) => response.text()),
    ])
      .then(([settings, html]) => {
        setDraft(normalizeSettings(settings));
        setSiteHtml(html);
        setTextTargets(extractSalaoSiteTextTargets(html));
        setImageTargets(extractSalaoSiteImageTargets(html));
      })
      .catch(() => setError("Nao foi possivel carregar o site original da Pagina Salao."))
      .finally(() => setLoading(false));
  }, []);

  const filteredTexts = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return textTargets;
    return textTargets.filter((item) => getTextValue(draft, item).toLowerCase().includes(term));
  }, [draft, query, textTargets]);

  const filteredImages = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return imageTargets;
    return imageTargets.filter((item) => `${item.src} ${item.alt} ${draft?.site_image_overrides[item.id] ?? ""}`.toLowerCase().includes(term));
  }, [draft, imageTargets, query]);

  const previewHtml = useMemo(() => {
    if (!draft || !siteHtml) return "";
    return applySalaoSiteOverrides(siteHtml, draft.site_text_overrides, draft.site_image_overrides);
  }, [draft, siteHtml]);

  const setField = <K extends keyof ApiSalaoPageSettings>(key: K, value: ApiSalaoPageSettings[K]) => {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const updateText = (id: string, value: string) => {
    if (!draft) return;
    setField("site_text_overrides", { ...draft.site_text_overrides, [id]: value });
  };

  const restoreText = (id: string) => {
    if (!draft) return;
    const next = { ...draft.site_text_overrides };
    delete next[id];
    setField("site_text_overrides", next);
  };

  const updateImage = (id: string, value: string) => {
    if (!draft) return;
    setField("site_image_overrides", { ...draft.site_image_overrides, [id]: value });
  };

  const restoreImage = (id: string) => {
    if (!draft) return;
    const next = { ...draft.site_image_overrides };
    delete next[id];
    setField("site_image_overrides", next);
  };

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    setError("");
    try {
      const updated = await salaoPageApi.update(draft);
      setDraft(normalizeSettings(updated));
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
        description="Gerencie todos os textos e imagens do site publico moschettieri.com.br"
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
            Carregando site original...
          </div>
        ) : (
          <>
            {(tab === "texts" || tab === "images") && (
              <Toolbar
                query={query}
                onQuery={setQuery}
                total={tab === "texts" ? filteredTexts.length : filteredImages.length}
                label={tab === "texts" ? "textos encontrados" : "imagens encontradas"}
              />
            )}

            {tab === "texts" && (
              <Panel
                title="Textos do site original"
                subtitle="Cada campo abaixo corresponde a um texto encontrado no HTML do layout anexado."
              >
                <div className="grid gap-3">
                  {filteredTexts.map((item, index) => (
                    <TextRow
                      key={item.id}
                      index={index + 1}
                      target={item}
                      value={getTextValue(draft, item)}
                      changed={draft.site_text_overrides[item.id] !== undefined}
                      onChange={(value) => updateText(item.id, value)}
                      onRestore={() => restoreText(item.id)}
                    />
                  ))}
                </div>
              </Panel>
            )}

            {tab === "images" && (
              <Panel
                title="Imagens do site original"
                subtitle="Substitua imagens pontuais mantendo o restante do layout exatamente como o arquivo enviado."
              >
                <div className="grid gap-4 lg:grid-cols-2">
                  {filteredImages.map((item, index) => (
                    <ImageRow
                      key={item.id}
                      index={index + 1}
                      target={item}
                      value={draft.site_image_overrides[item.id] ?? ""}
                      onChange={(value) => updateImage(item.id, value)}
                      onRestore={() => restoreImage(item.id)}
                    />
                  ))}
                </div>
              </Panel>
            )}

            {tab === "seo" && (
              <Panel
                title="SEO & Publicacao"
                subtitle="Controle de disponibilidade e metadados do dominio principal."
              >
                <Toggle checked={draft.enabled} onChange={(value) => setField("enabled", value)} label="Pagina publica ativa" />
                <Field label="Titulo SEO" value={draft.seo_title} onChange={(value) => setField("seo_title", value)} />
                <Field label="Descricao SEO" value={draft.seo_description} onChange={(value) => setField("seo_description", value)} multiline />
              </Panel>
            )}

            {tab === "preview" && (
              <Panel
                title="Previa do site"
                subtitle="Visualizacao com os textos e imagens gerenciados aplicados sobre o layout original."
              >
                <div className="overflow-hidden rounded-xl border border-surface-03 bg-black">
                  <iframe title="Previa Pagina Salao" srcDoc={previewHtml} className="h-[720px] w-full border-0 bg-black" />
                </div>
              </Panel>
            )}
          </>
        )}
      </AdminPageContent>
    </AdminPageShell>
  );
}

function normalizeSettings(settings: ApiSalaoPageSettings): ApiSalaoPageSettings {
  return {
    ...settings,
    site_text_overrides: settings.site_text_overrides ?? {},
    site_image_overrides: settings.site_image_overrides ?? {},
  };
}

function getTextValue(settings: ApiSalaoPageSettings | null, target: SalaoSiteTextTarget) {
  return settings?.site_text_overrides[target.id] ?? target.value;
}

function siteAssetUrl(value: string) {
  if (!value) return "";
  if (/^(https?:|data:|blob:|\/)/.test(value)) return resolveAssetUrl(value);
  return `/salao-site/${value.replace(/^\.?\//, "")}`;
}

function Panel({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-5 rounded-xl border border-surface-03 bg-surface-02 p-5">
      <div>
        <h2 className="text-lg font-black text-cream">{title}</h2>
        <p className="text-sm text-stone">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

function Toolbar({ query, onQuery, total, label }: { query: string; onQuery: (value: string) => void; total: number; label: string }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-surface-03 bg-surface-02 p-3">
      <div className="text-sm font-bold text-cream">{total} {label}</div>
      <label className="relative min-w-[260px] flex-1 md:flex-none">
        <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-stone" size={15} />
        <input
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Buscar no conteudo..."
          className="h-10 w-full rounded-xl border border-surface-03 bg-surface-01 pl-9 pr-3 text-sm text-cream outline-none focus:border-gold"
        />
      </label>
    </div>
  );
}

function TextRow({
  index,
  target,
  value,
  changed,
  onChange,
  onRestore,
}: {
  index: number;
  target: SalaoSiteTextTarget;
  value: string;
  changed: boolean;
  onChange: (value: string) => void;
  onRestore: () => void;
}) {
  return (
    <div className="grid gap-3 rounded-xl border border-surface-03 bg-surface-01 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <span className="text-xs font-black uppercase tracking-[0.18em] text-gold">Texto {index}</span>
          <span className="ml-2 rounded-full bg-surface-03 px-2 py-1 text-[11px] font-bold uppercase text-stone">{target.tag}</span>
        </div>
        {changed && <RestoreButton onClick={onRestore} />}
      </div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={value.length > 120 ? 4 : 2}
        className="w-full resize-y rounded-xl border border-surface-03 bg-surface-02 px-3 py-2 text-sm text-cream outline-none focus:border-gold"
      />
    </div>
  );
}

function ImageRow({
  index,
  target,
  value,
  onChange,
  onRestore,
}: {
  index: number;
  target: SalaoSiteImageTarget;
  value: string;
  onChange: (value: string) => void;
  onRestore: () => void;
}) {
  const currentUrl = siteAssetUrl(value || target.src);
  const assetInfo = useImageAssetInfo(currentUrl);

  return (
    <div className="grid gap-4 rounded-xl border border-surface-03 bg-surface-01 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <span className="text-xs font-black uppercase tracking-[0.18em] text-gold">Imagem {index}</span>
          {value && <span className="ml-2 rounded-full bg-emerald-500/10 px-2 py-1 text-[11px] font-bold text-emerald-300">alterada</span>}
        </div>
        {value && <RestoreButton onClick={onRestore} />}
      </div>
      <div className="aspect-video overflow-hidden rounded-xl border border-surface-03 bg-black">
        {currentUrl ? <img src={currentUrl} alt={target.alt || `Imagem ${index}`} className="h-full w-full object-contain" /> : null}
      </div>
      <div className="grid gap-2 rounded-lg border border-gold/20 bg-gold/5 p-3 text-xs">
        <div className="font-black uppercase tracking-[0.16em] text-gold">Informacoes da imagem</div>
        <div className="grid gap-2 text-stone sm:grid-cols-3">
          <InfoPill label="Dimensao atual" value={assetInfo.dimensions ?? "Carregando..."} />
          <InfoPill label="Tamanho atual" value={assetInfo.fileSize ?? "Nao informado"} />
          <InfoPill label="Limite de upload" value="3 MB" />
        </div>
      </div>
      <div className="rounded-lg border border-surface-03 bg-surface-02 p-3 text-xs text-stone">
        <div className="font-bold text-cream">Arquivo original</div>
        <div className="mt-1 break-all">{target.src}</div>
      </div>
      <ImageUpload
        label="Substituir imagem"
        value={value}
        onChange={onChange}
        maxKB={3072}
        sizeGuide="Imagem da Pagina Salao, ate 3MB"
      />
    </div>
  );
}

function useImageAssetInfo(url: string) {
  const [info, setInfo] = useState<{ dimensions?: string; fileSize?: string }>({});

  useEffect(() => {
    if (!url) {
      setInfo({});
      return;
    }

    let active = true;
    const controller = new AbortController();
    setInfo({});

    const image = new window.Image();
    image.onload = () => {
      if (!active) return;
      const dimensions = image.naturalWidth && image.naturalHeight
        ? `${image.naturalWidth} x ${image.naturalHeight}px`
        : "Nao informado";
      setInfo((prev) => ({ ...prev, dimensions }));
    };
    image.onerror = () => {
      if (active) setInfo((prev) => ({ ...prev, dimensions: "Nao informado" }));
    };
    image.src = url;

    fetch(url, { method: "HEAD", signal: controller.signal })
      .then((response) => {
        const length = response.headers.get("content-length");
        if (active) setInfo((prev) => ({ ...prev, fileSize: length ? formatBytes(Number(length)) : "Nao informado" }));
      })
      .catch(() => {
        if (active) setInfo((prev) => ({ ...prev, fileSize: "Nao informado" }));
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [url]);

  return info;
}

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-surface-03 bg-surface-02 p-2">
      <div className="text-[11px] font-bold uppercase text-stone/80">{label}</div>
      <div className="mt-1 font-black text-cream">{value}</div>
    </div>
  );
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "Nao informado";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
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

function RestoreButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-8 items-center gap-2 rounded-lg border border-surface-03 px-2 text-xs font-bold text-stone hover:border-gold/40 hover:text-gold"
    >
      <RotateCcw size={13} />
      Restaurar original
    </button>
  );
}

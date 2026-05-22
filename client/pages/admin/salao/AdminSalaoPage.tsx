import { useEffect, useMemo, useState } from "react";
import { Check, Eye, FileText, Image, Layers3, Loader2, Newspaper, Plus, RotateCcw, Save, Search, Settings, Trash2 } from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";
import ImageUpload from "@/components/admin/ImageUpload";
import { resolveAssetUrl, salaoPageApi, type ApiSalaoBlogPost, type ApiSalaoPageSettings } from "@/lib/api";
import {
  applySalaoSiteOverrides,
  buildSalaoSiteBlocks,
  extractSalaoSiteImageTargets,
  extractSalaoSiteTextTargets,
  SALAO_PUBLIC_PAGES,
  type SalaoPublicPageKey,
  type SalaoRenderPageKey,
  type SalaoPublicSubPage,
  type SalaoSiteBlock,
  type SalaoSiteImageTarget,
  type SalaoSiteTextTarget,
  type SalaoTextRole,
} from "@/lib/salaoSiteCms";

type Tab = "blocks" | "blog" | "seo" | "preview";

const SALAO_SITE_URL = "/salao-site/index.html";

const TABS: AdminPageTab<Tab>[] = [
  { id: "blocks", icon: <Layers3 size={15} />, label: "Blocos" },
  { id: "blog", icon: <Newspaper size={15} />, label: "Blog" },
  { id: "seo", icon: <Settings size={15} />, label: "SEO & Publicacao" },
  { id: "preview", icon: <Eye size={15} />, label: "Previa" },
];

const TEXT_GROUP_ORDER: SalaoTextRole[] = ["title", "subtitle", "description", "button", "navigation", "label", "other"];

export default function AdminSalaoPage() {
  const [tab, setTab] = useState<Tab>("blocks");
  const [draft, setDraft] = useState<ApiSalaoPageSettings | null>(null);
  const [siteHtml, setSiteHtml] = useState("");
  const [textTargets, setTextTargets] = useState<SalaoSiteTextTarget[]>([]);
  const [imageTargets, setImageTargets] = useState<SalaoSiteImageTarget[]>([]);
  const [activeBlockId, setActiveBlockId] = useState("");
  const [activePageKey, setActivePageKey] = useState<SalaoPublicPageKey>("home");
  const [activeSubPageKey, setActiveSubPageKey] = useState("");
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

  const blocks = useMemo(() => buildSalaoSiteBlocks(textTargets, imageTargets), [imageTargets, textTargets]);
  const activePage = useMemo(
    () => SALAO_PUBLIC_PAGES.find((page) => page.key === activePageKey) ?? SALAO_PUBLIC_PAGES[0],
    [activePageKey],
  );
  const activeSubPage = useMemo(
    () => activePage.subPages?.find((subPage) => subPage.key === activeSubPageKey) ?? null,
    [activePage, activeSubPageKey],
  );
  const pageBlocks = useMemo(() => {
    const allowedBlocks = new Set(activeSubPage?.blockIds ?? activePage.blockIds);
    const scopedBlocks = blocks.filter((block) => allowedBlocks.has(block.id));
    return scopedBlocks.length ? scopedBlocks : blocks;
  }, [activePage, activeSubPage, blocks]);

  useEffect(() => {
    if (!pageBlocks.length) return;
    if (!activeBlockId || !pageBlocks.some((block) => block.id === activeBlockId)) {
      setActiveBlockId(pageBlocks[0].id);
    }
  }, [activeBlockId, pageBlocks]);

  const textById = useMemo(() => new Map(textTargets.map((item) => [item.id, item])), [textTargets]);
  const imageById = useMemo(() => new Map(imageTargets.map((item) => [item.id, item])), [imageTargets]);
  const activeBlock = useMemo(
    () => pageBlocks.find((block) => block.id === activeBlockId) ?? pageBlocks[0],
    [activeBlockId, pageBlocks],
  );

  const filteredBlockTexts = useMemo(() => {
    if (!activeBlock) return [];
    const term = query.trim().toLowerCase();
    return activeBlock.textIds
      .map((id) => textById.get(id))
      .filter((item): item is SalaoSiteTextTarget => Boolean(item))
      .filter((item) => {
        if (!term) return true;
        return `${getTextValue(draft, item)} ${item.roleLabel} ${item.context}`.toLowerCase().includes(term);
      });
  }, [activeBlock, draft, query, textById]);

  const filteredBlockImages = useMemo(() => {
    if (!activeBlock) return [];
    const term = query.trim().toLowerCase();
    return activeBlock.imageIds
      .map((id) => imageById.get(id))
      .filter((item): item is SalaoSiteImageTarget => Boolean(item))
      .filter((item) => {
        if (!term) return true;
        return `${item.src} ${item.alt} ${item.context} ${draft?.site_image_overrides[item.id] ?? ""}`.toLowerCase().includes(term);
      });
  }, [activeBlock, draft, imageById, query]);

  const previewHtml = useMemo(() => {
    if (!draft || !siteHtml) return "";
    const previewPageKey: SalaoRenderPageKey =
      activeSubPageKey && isSalaoRenderPageKey(activeSubPageKey)
        ? activeSubPageKey
        : isSalaoRenderPageKey(activePageKey)
          ? activePageKey
          : "home";
    return applySalaoSiteOverrides(
      siteHtml,
      draft.site_text_overrides,
      draft.site_image_overrides,
      draft.blog_posts,
      previewPageKey,
    );
  }, [activePageKey, activeSubPageKey, draft, siteHtml]);

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

  const updateBlogPost = (index: number, patch: Partial<ApiSalaoBlogPost>) => {
    if (!draft) return;
    const posts = [...draft.blog_posts];
    posts[index] = { ...posts[index], ...patch };
    setField("blog_posts", posts);
  };

  const addBlogPost = () => {
    if (!draft) return;
    const id = `blog-${Date.now()}`;
    setField("blog_posts", [
      ...draft.blog_posts,
      {
        id,
        title: "Novo artigo",
        excerpt: "",
        content: "",
        image: "",
        published_at: new Date().toISOString().slice(0, 10),
        author: "Moschettieri",
        category: "Restaurante",
        published: true,
      },
    ]);
  };

  const removeBlogPost = (index: number) => {
    if (!draft) return;
    setField("blog_posts", draft.blog_posts.filter((_, itemIndex) => itemIndex !== index));
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
            {tab === "blocks" && activeBlock && (
              <>
                <PublicPageSelector
                  activePageKey={activePageKey}
                  onSelect={(key) => {
                    setActivePageKey(key);
                    setActiveSubPageKey("");
                    setQuery("");
                    const page = SALAO_PUBLIC_PAGES.find((item) => item.key === key);
                    const firstBlock = blocks.find((block) => page?.blockIds.includes(block.id));
                    if (firstBlock) setActiveBlockId(firstBlock.id);
                  }}
                />
                {activePage.subPages?.length ? (
                  <PublicSubPageSelector
                    parentTitle={activePage.title}
                    subPages={activePage.subPages}
                    activeSubPageKey={activeSubPageKey}
                    onSelect={(key) => {
                      const nextKey = key === activeSubPageKey ? "" : key;
                      setActiveSubPageKey(nextKey);
                      setQuery("");
                      const subPage = activePage.subPages?.find((item) => item.key === nextKey);
                      const firstBlock = blocks.find((block) => (subPage?.blockIds ?? activePage.blockIds).includes(block.id));
                      if (firstBlock) setActiveBlockId(firstBlock.id);
                    }}
                  />
                ) : null}
                <Toolbar
                  query={query}
                  onQuery={setQuery}
                  total={filteredBlockTexts.length + filteredBlockImages.length}
                  label={`itens em ${activeSubPage?.title ?? activePage.title}`}
                />
              </>
            )}

            {tab === "blocks" && activeBlock && (
              <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
                <BlockNavigation
                  blocks={pageBlocks}
                  activeBlockId={activeBlock.id}
                  onSelect={(id) => {
                    setActiveBlockId(id);
                    setQuery("");
                  }}
                />
                <BlockEditor
                  block={activeBlock}
                  texts={filteredBlockTexts}
                  images={filteredBlockImages}
                  draft={draft}
                  onTextChange={updateText}
                  onTextRestore={restoreText}
                  onImageChange={updateImage}
                  onImageRestore={restoreImage}
                />
              </div>
            )}

            {tab === "blog" && (
              <BlogManager
                posts={draft.blog_posts}
                onAdd={addBlogPost}
                onChange={updateBlogPost}
                onRemove={removeBlogPost}
              />
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
    blog_posts: settings.blog_posts ?? [],
  };
}

function BlogManager({
  posts,
  onAdd,
  onChange,
  onRemove,
}: {
  posts: ApiSalaoBlogPost[];
  onAdd: () => void;
  onChange: (index: number, patch: Partial<ApiSalaoBlogPost>) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <Panel title="Blog List" subtitle="Crie e gerencie os artigos exibidos nos cards de blog da Pagina Salao.">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-surface-03 bg-surface-01 p-3">
        <div>
          <p className="text-sm font-black text-cream">{posts.length} artigos cadastrados</p>
          <p className="text-xs text-stone">Artigos publicados aparecem automaticamente no bloco de noticias do site.</p>
        </div>
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex h-10 items-center gap-2 rounded-xl bg-gold px-4 text-sm font-black text-black transition hover:bg-gold/90"
        >
          <Plus size={16} />
          Novo artigo
        </button>
      </div>

      {posts.length === 0 ? (
        <EmptyBlockMessage message="Nenhum artigo cadastrado ainda." />
      ) : (
        <div className="grid gap-4">
          {posts.map((post, index) => (
            <BlogPostEditor
              key={post.id || index}
              post={post}
              index={index}
              onChange={(patch) => onChange(index, patch)}
              onRemove={() => onRemove(index)}
            />
          ))}
        </div>
      )}
    </Panel>
  );
}

function BlogPostEditor({
  post,
  index,
  onChange,
  onRemove,
}: {
  post: ApiSalaoBlogPost;
  index: number;
  onChange: (patch: Partial<ApiSalaoBlogPost>) => void;
  onRemove: () => void;
}) {
  return (
    <article className="grid gap-4 rounded-xl border border-surface-03 bg-surface-01 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <span className="text-xs font-black uppercase tracking-[0.18em] text-gold">Artigo {index + 1}</span>
          <h3 className="mt-1 text-lg font-black text-cream">{post.title || "Sem titulo"}</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onChange({ published: !post.published })}
            className={`rounded-lg border px-3 py-2 text-xs font-black ${
              post.published
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                : "border-red-500/30 bg-red-500/10 text-red-300"
            }`}
          >
            {post.published ? "Publicado" : "Rascunho"}
          </button>
          <button
            type="button"
            onClick={onRemove}
            className="inline-flex h-9 items-center gap-2 rounded-lg border border-red-500/30 px-3 text-xs font-bold text-red-300 hover:bg-red-500/10"
          >
            <Trash2 size={14} />
            Excluir
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid gap-3">
          <Field label="Titulo" value={post.title} onChange={(value) => onChange({ title: value })} />
          <Field label="Resumo do card" value={post.excerpt} onChange={(value) => onChange({ excerpt: value })} multiline />
          <Field label="Conteudo do artigo" value={post.content} onChange={(value) => onChange({ content: value })} multiline />
          <div className="grid gap-3 md:grid-cols-3">
            <Field label="Data" value={post.published_at} onChange={(value) => onChange({ published_at: value })} />
            <Field label="Autor" value={post.author} onChange={(value) => onChange({ author: value })} />
            <Field label="Categoria" value={post.category} onChange={(value) => onChange({ category: value })} />
          </div>
        </div>
        <div className="grid gap-3">
          <div className="aspect-[16/10] overflow-hidden rounded-xl border border-surface-03 bg-black">
            {post.image ? (
              <img src={siteAssetUrl(post.image)} alt={post.title} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-stone">Sem imagem</div>
            )}
          </div>
          <ImageUpload
            label="Imagem do artigo"
            value={post.image}
            onChange={(value) => onChange({ image: value })}
            maxKB={3072}
            sizeGuide="Imagem do blog, ate 3MB"
          />
        </div>
      </div>
    </article>
  );
}

function PublicPageSelector({
  activePageKey,
  onSelect,
}: {
  activePageKey: SalaoPublicPageKey;
  onSelect: (key: SalaoPublicPageKey) => void;
}) {
  return (
    <section className="grid gap-3 rounded-xl border border-surface-03 bg-surface-02 p-3">
      <div>
        <h2 className="text-sm font-black uppercase tracking-[0.16em] text-gold">Paginas do site</h2>
        <p className="text-xs text-stone">Selecione uma area do menu publico para abrir os textos e imagens correspondentes.</p>
      </div>
      <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
        {SALAO_PUBLIC_PAGES.map((page) => {
          const active = page.key === activePageKey;
          return (
            <button
              key={page.key}
              type="button"
              aria-pressed={active}
              onClick={() => onSelect(page.key)}
              className={`rounded-xl border p-3 text-left transition ${
                active
                  ? "border-gold bg-gold text-black shadow-[0_0_0_3px_rgba(218,165,32,0.18)]"
                  : "border-surface-03 bg-surface-01 text-stone hover:border-gold/30 hover:text-cream"
              }`}
            >
              <span className="block text-sm font-black">{page.title}</span>
              <span className="mt-1 block line-clamp-2 text-xs">{page.description}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function PublicSubPageSelector({
  parentTitle,
  subPages,
  activeSubPageKey,
  onSelect,
}: {
  parentTitle: string;
  subPages: SalaoPublicSubPage[];
  activeSubPageKey: string;
  onSelect: (key: string) => void;
}) {
  return (
    <section className="grid gap-3 rounded-xl border border-surface-03 bg-surface-02 p-3">
      <div>
        <h2 className="text-sm font-black uppercase tracking-[0.16em] text-gold">Paginas em {parentTitle}</h2>
        <p className="text-xs text-stone">Abra uma subpagina para focar a edicao nos blocos ligados a ela.</p>
      </div>
      <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-5">
        {subPages.map((subPage) => {
          const active = subPage.key === activeSubPageKey;
          return (
            <button
              key={subPage.key}
              type="button"
              aria-pressed={active}
              onClick={() => onSelect(subPage.key)}
              className={`rounded-xl border p-3 text-left transition ${
                active
                  ? "border-gold bg-gold text-black shadow-[0_0_0_3px_rgba(218,165,32,0.18)]"
                  : "border-surface-03 bg-surface-01 text-stone hover:border-gold/30 hover:text-cream"
              }`}
            >
              <span className="block text-sm font-black">{subPage.title}</span>
              <span className="mt-1 block line-clamp-2 text-xs">{subPage.description}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function BlockNavigation({
  blocks,
  activeBlockId,
  onSelect,
}: {
  blocks: SalaoSiteBlock[];
  activeBlockId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <aside className="grid gap-3 rounded-xl border border-surface-03 bg-surface-02 p-3 xl:sticky xl:top-4 xl:self-start">
      <div className="px-2">
        <h2 className="text-sm font-black uppercase tracking-[0.16em] text-gold">Estrutura do site</h2>
        <p className="mt-1 text-xs text-stone">Blocos separados conforme o layout original importado.</p>
      </div>
      <div className="grid max-h-[680px] gap-2 overflow-y-auto pr-1">
        {blocks.map((block) => {
          const active = block.id === activeBlockId;
          const total = block.textIds.length + block.imageIds.length;
          return (
            <button
              key={block.id}
              type="button"
              onClick={() => onSelect(block.id)}
              className={`grid gap-1 rounded-xl border p-3 text-left transition ${
                active
                  ? "border-gold/60 bg-gold/10 text-cream"
                  : "border-surface-03 bg-surface-01 text-stone hover:border-gold/30 hover:text-cream"
              }`}
            >
              <span className="text-sm font-black">{block.title}</span>
              <span className="line-clamp-2 text-xs">{block.description}</span>
              <span className="mt-1 text-[11px] font-bold uppercase tracking-[0.12em] text-gold">
                {block.textIds.length} textos - {block.imageIds.length} imagens - {total} itens
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}

function BlockEditor({
  block,
  texts,
  images,
  draft,
  onTextChange,
  onTextRestore,
  onImageChange,
  onImageRestore,
}: {
  block: SalaoSiteBlock;
  texts: SalaoSiteTextTarget[];
  images: SalaoSiteImageTarget[];
  draft: ApiSalaoPageSettings;
  onTextChange: (id: string, value: string) => void;
  onTextRestore: (id: string) => void;
  onImageChange: (id: string, value: string) => void;
  onImageRestore: (id: string) => void;
}) {
  const groupedTexts = useMemo(() => {
    const map = new Map<SalaoTextRole, SalaoSiteTextTarget[]>();
    texts.forEach((item) => {
      const current = map.get(item.role) ?? [];
      current.push(item);
      map.set(item.role, current);
    });
    return TEXT_GROUP_ORDER
      .map((role) => ({ role, items: map.get(role) ?? [] }))
      .filter((group) => group.items.length > 0);
  }, [texts]);

  return (
    <Panel title={block.title} subtitle={block.description}>
      <div className="grid gap-6">
        <section className="grid gap-3">
          <SectionHeader icon={<FileText size={15} />} title="Textos organizados por funcao" count={texts.length} />
          {groupedTexts.length ? (
            <div className="grid gap-4">
              {groupedTexts.map((group) => (
                <TextGroup
                  key={group.role}
                  role={group.role}
                  items={group.items}
                  draft={draft}
                  onTextChange={onTextChange}
                  onTextRestore={onTextRestore}
                />
              ))}
            </div>
          ) : (
            <EmptyBlockMessage message="Este bloco nao possui textos editaveis." />
          )}
        </section>

        <section className="grid gap-3">
          <SectionHeader icon={<Image size={15} />} title="Imagens deste bloco" count={images.length} />
          {images.length ? (
            <div className="grid gap-4 lg:grid-cols-2">
              {images.map((item) => (
                <ImageRow
                  key={item.id}
                  index={targetNumber(item.id)}
                  target={item}
                  value={draft.site_image_overrides[item.id] ?? ""}
                  onChange={(value) => onImageChange(item.id, value)}
                  onRestore={() => onImageRestore(item.id)}
                />
              ))}
            </div>
          ) : (
            <EmptyBlockMessage message="Este bloco nao possui imagens editaveis." />
          )}
        </section>
      </div>
    </Panel>
  );
}

function TextGroup({
  role,
  items,
  draft,
  onTextChange,
  onTextRestore,
}: {
  role: SalaoTextRole;
  items: SalaoSiteTextTarget[];
  draft: ApiSalaoPageSettings;
  onTextChange: (id: string, value: string) => void;
  onTextRestore: (id: string) => void;
}) {
  const label = items[0]?.roleLabel ?? "Textos";
  const help: Record<SalaoTextRole, string> = {
    title: "Chamadas principais, nomes de secoes e titulos visiveis no layout.",
    subtitle: "Linhas curtas de apoio usadas acima ou abaixo dos titulos.",
    description: "Paragrafos e textos maiores que explicam a secao.",
    button: "Textos de botoes e chamadas de acao.",
    navigation: "Itens do menu e links de navegacao do site publico.",
    label: "Legendas, datas, aceite e informacoes curtas.",
    other: "Textos auxiliares do template que nao se encaixam nos grupos principais.",
  };

  return (
    <div className="grid gap-3 rounded-xl border border-surface-03 bg-surface-02 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-surface-03 pb-2">
        <div>
          <h3 className="text-sm font-black text-cream">{label}</h3>
          <p className="text-xs text-stone">{help[role]}</p>
        </div>
        <span className="rounded-full border border-surface-03 bg-surface-01 px-2 py-1 text-[11px] font-bold uppercase text-stone">
          {items.length} campos
        </span>
      </div>
      <div className="grid gap-3">
        {items.map((item) => (
          <TextRow
            key={item.id}
            index={targetNumber(item.id)}
            target={item}
            value={getTextValue(draft, item)}
            changed={draft.site_text_overrides[item.id] !== undefined}
            onChange={(value) => onTextChange(item.id, value)}
            onRestore={() => onTextRestore(item.id)}
          />
        ))}
      </div>
    </div>
  );
}

function SectionHeader({ icon, title, count }: { icon: React.ReactNode; title: string; count: number }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-03 pb-2">
      <div className="inline-flex items-center gap-2 text-sm font-black text-cream">
        <span className="text-gold">{icon}</span>
        {title}
      </div>
      <span className="rounded-full border border-surface-03 bg-surface-01 px-2 py-1 text-[11px] font-bold uppercase text-stone">
        {count} itens
      </span>
    </div>
  );
}

function EmptyBlockMessage({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed border-surface-03 bg-surface-01 p-4 text-sm text-stone">
      {message}
    </div>
  );
}

function getTextValue(settings: ApiSalaoPageSettings | null, target: SalaoSiteTextTarget) {
  return settings?.site_text_overrides[target.id] ?? target.value;
}

function targetNumber(id: string) {
  const [, raw] = id.split("-");
  const number = Number(raw);
  return Number.isFinite(number) ? number + 1 : 1;
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
          <span className="text-xs font-black uppercase tracking-[0.18em] text-gold">{target.roleLabel} {index}</span>
          <span className="ml-2 rounded-full bg-surface-03 px-2 py-1 text-[11px] font-bold uppercase text-stone">{target.tag}</span>
          <span className="ml-2 rounded-full bg-surface-03 px-2 py-1 text-[11px] font-bold uppercase text-stone">{target.context}</span>
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

function isSalaoRenderPageKey(value: string): value is SalaoRenderPageKey {
  return [
    "home",
    "menu",
    "blog",
    "moschettieri",
    "galeria",
    "pessoas",
    "certificados",
    "duvidas",
    "contato",
    "reservas",
    "minha-conta",
  ].includes(value);
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
        <div className="mt-2 flex flex-wrap gap-2">
          {target.width && target.height && (
            <span className="rounded-full bg-surface-03 px-2 py-1 font-bold">
              Original: {target.width} x {target.height}px
            </span>
          )}
          <span className="rounded-full bg-surface-03 px-2 py-1 font-bold">{target.context}</span>
        </div>
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

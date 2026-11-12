import TenantDomainsPanel from "@/components/admin/TenantDomainsPanel";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Bell, BellOff, Check, Monitor, Printer, Eye, Settings2, Tags, Volume2, Globe, Ruler } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import LabelSettingsPanel from "@/components/admin/LabelSettingsPanel";
import OrderBoardSettingsPanel from "@/components/admin/OrderBoardSettingsPanel";
import PartnerIdentificationPanel from "@/components/admin/PartnerIdentificationPanel";
import {
  loadPrinterSettings, savePrinterSettings,
  buildCompletoHtml, buildCozinhaHtml, buildEntregaHtml,
  SAMPLE_ORDER, DEFAULT_PRINTER_SETTINGS,
  openReceiptPreview, withReceiptBranding,
  type PrinterSettings, type PrintTemplate, type PaperWidth,
} from "@/lib/printing";
import {
  loadSoundType, saveSoundType, playOrderAlert,
  SOUND_OPTIONS, type OrderSoundType,
} from "@/lib/orderSound";
import { useApp } from "@/context/AppContext";
import { kdsLabelsApi, type KdsLabelTemplate, type KdsLabelTemplateInput } from "@/lib/api";

// ── Tabs ──────────────────────────────────────────────────────────────────────

type Tab = "comprovantes" | "etiquetas-expedicao" | "etiquetas-insumos" | "painel-tv" | "som" | "dominio-https" | "identificacao-parceiros";

export function isDomainOnlyConfigurationRoute(pathname: string): boolean {
  return pathname === "/painel/dominio";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Field({
  label, hint, children,
}: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-parchment text-sm font-medium mb-1">{label}</label>
      {children}
      {hint && <p className="text-stone text-xs mt-1">{hint}</p>}
    </div>
  );
}

const cls =
  "w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2.5 text-cream placeholder-stone focus:outline-none focus:border-gold text-sm";

// ── Template card ─────────────────────────────────────────────────────────────

function TemplateCard({
  id, title, description, selected, onSelect, html,
}: {
  id: PrintTemplate;
  title: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
  html: string;
}) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    const doc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!doc) return;
    doc.open();
    doc.write(html);
    doc.close();
  }, [html]);

  const openPreview = (print = false) => openReceiptPreview(html, print);

  return (
    <div
      className={`rounded-2xl border-2 overflow-hidden cursor-pointer transition-all ${
        selected ? "border-gold shadow-lg shadow-gold/10" : "border-surface-03 hover:border-gold/40"
      }`}
      onClick={onSelect}
    >
      {/* Header */}
      <div className={`px-4 py-3 flex items-center justify-between ${selected ? "bg-gold/15" : "bg-surface-02"}`}>
        <div>
          <div className="flex items-center gap-2">
            <Printer size={15} className={selected ? "text-gold" : "text-stone"} />
            <span className={`text-sm font-bold ${selected ? "text-gold" : "text-parchment"}`}>{title}</span>
            {selected && (
              <span className="flex items-center gap-1 text-[10px] font-bold text-gold bg-gold/15 border border-gold/30 rounded-full px-2 py-0.5">
                <Check size={9} /> Padrão
              </span>
            )}
          </div>
          <p className="text-stone text-xs mt-0.5">{description}</p>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); openPreview(); }}
          className="flex items-center gap-1.5 text-xs text-stone hover:text-parchment bg-surface-03 hover:bg-surface-03/80 px-3 py-1.5 rounded-lg transition-colors"
        >
          <Eye size={12} />
          Prévia
        </button>
        <button type="button" onClick={(event) => { event.stopPropagation(); openPreview(true); }} className="min-h-10 rounded-lg border border-surface-03 px-3 text-xs font-bold text-gold">Imprimir teste</button>
      </div>

      {/* Receipt preview */}
      <div className="bg-white overflow-hidden" style={{ height: 260 }}>
        <iframe
          ref={iframeRef}
          title={title}
          scrolling="no"
          className="w-full h-full border-none"
          style={{ transform: "scale(0.75)", transformOrigin: "top left", width: "133%", height: "133%" }}
        />
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function SuppliesLabelSettingsPanel() {
  const [template, setTemplate] = useState<KdsLabelTemplate | null>(null);
  const [name, setName] = useState("Etiqueta de insumos 20 × 40 mm");
  const [orientation, setOrientation] = useState<"portrait" | "landscape">("portrait");
  const [margin, setMargin] = useState(2);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void kdsLabelsApi.listTemplates().then((templates) => {
      const existing = templates.find((item) => item.name.toLocaleLowerCase().includes("insumo")) ?? templates.find((item) => item.width_mm === 20 && item.height_mm === 40);
      if (existing) { setTemplate(existing); setName(existing.name); setOrientation(existing.orientation); setMargin(existing.margin_top_mm); }
    }).catch((caught) => setError(caught instanceof Error ? caught.message : "Não foi possível carregar o modelo de insumos.")).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true); setFeedback(null); setError(null);
    const payload: KdsLabelTemplateInput = { name: name.trim() || "Etiqueta de insumos 20 × 40 mm", label_type: "gap", width_mm: 20, height_mm: 40, margin_top_mm: margin, margin_right_mm: margin, margin_bottom_mm: margin, margin_left_mm: margin, gap_mm: 2, safe_area_mm: 2, columns: 1, labels_per_sheet: 1, orientation, show_logo: false, show_printed_at: true, dpi: 203, scale_percent: 100, default_copies: 1, font_scale_percent: 100, offset_x_mm: 0, offset_y_mm: 0, rotation: 0, density: 8, speed: 4, printer_ids: template?.printer_ids ?? [], active: true };
    try { const savedTemplate = template ? await kdsLabelsApi.updateTemplate(template.id, payload) : await kdsLabelsApi.createTemplate(payload); setTemplate(savedTemplate); setName(savedTemplate.name); setFeedback("Modelo de insumos salvo."); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Não foi possível salvar o modelo de insumos."); }
    finally { setSaving(false); }
  };

  return <section className="space-y-6">
    <div className="rounded-2xl border border-gold/30 bg-gold/10 p-6"><div className="flex items-start gap-3"><Ruler className="mt-0.5 shrink-0 text-gold" size={20} /><div><h3 className="text-lg font-bold text-cream">Etiqueta de insumos</h3><p className="mt-1 text-sm text-parchment">Configuração exclusiva para porcionamento e classificação de estoque com validade. Este modelo não altera a etiqueta de expedição das caixas de pizza.</p><p className="mt-2 text-xs text-stone">Formato operacional fixo: 20 × 40 mm.</p></div></div></div>
    {loading && <p className="text-sm text-stone">Carregando modelo de insumos...</p>}
    {error && <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>}
    {!loading && <section className="rounded-2xl border border-surface-03 bg-surface-02 p-6"><div className="mb-5"><h3 className="text-lg font-bold text-cream">Modelo 20 × 40 mm</h3><p className="text-sm text-stone">Use este modelo para etiquetas de ingredientes, porções, lote e validade.</p></div><div className="grid gap-4 md:grid-cols-2"><Field label="Nome do modelo"><input className={cls} value={name} onChange={(event) => setName(event.target.value)} /></Field><Field label="Orientação"><select className={cls} value={orientation} onChange={(event) => setOrientation(event.target.value as "portrait" | "landscape")}><option value="portrait">Retrato</option><option value="landscape">Paisagem</option></select></Field><Field label="Largura"><input className={cls} value="20 mm" readOnly /></Field><Field label="Altura"><input className={cls} value="40 mm" readOnly /></Field><Field label="Margem interna (mm)"><input className={cls} type="number" min={0} max={20} value={margin} onChange={(event) => setMargin(Number(event.target.value))} /></Field></div><div className="mt-5 flex items-center gap-3"><button type="button" disabled={saving} onClick={() => void save()} className="rounded-xl bg-gold px-5 py-2.5 font-bold text-cream disabled:opacity-50">{saving ? "Salvando..." : "Salvar modelo de insumos"}</button>{feedback && <span className="flex items-center gap-1 text-sm text-emerald-300"><Check size={15} /> {feedback}</span>}</div></section>}
  </section>;
}

export default function AdminConfiguracoes() {
  const { pathname } = useLocation();
  const { siteContent } = useApp();
  const isDomainRoute = isDomainOnlyConfigurationRoute(pathname);
  const routeTab: Tab = pathname === "/painel/etiquetas-expedicao"
    ? "etiquetas-expedicao"
    : pathname === "/painel/etiquetas-insumos"
      ? "etiquetas-insumos"
      : pathname === "/painel/dominio"
        ? "dominio-https"
        : pathname === "/painel/painel-tv-config"
          ? "painel-tv"
          : pathname === "/painel/som"
            ? "som"
            : pathname === "/painel/identificacao-parceiros"
              ? "identificacao-parceiros"
              : "comprovantes";
  const [activeTab, setActiveTab] = useState<Tab>(routeTab);
  const [settings, setSettings] = useState<PrinterSettings>(loadPrinterSettings);
  const [saved, setSaved] = useState(false);
  const [soundType, setSoundType] = useState<OrderSoundType>(loadSoundType);
  const [soundSaved, setSoundSaved] = useState(false);

  useEffect(() => {
    setActiveTab(routeTab);
  }, [routeTab]);

  const update = (patch: Partial<PrinterSettings>) =>
    setSettings((prev) => ({ ...prev, ...patch }));

  const handleSave = () => {
    savePrinterSettings(settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleReset = () => {
    setSettings({ ...DEFAULT_PRINTER_SETTINGS });
  };

  // Build preview HTMLs with current settings + sample order
  const brandedSettings = withReceiptBranding(settings, siteContent as unknown as Record<string, unknown>);
  const htmlCompleto = buildCompletoHtml(SAMPLE_ORDER, brandedSettings);
  const htmlCozinha  = buildCozinhaHtml(SAMPLE_ORDER, brandedSettings);
  const htmlEtiqueta = buildEntregaHtml(SAMPLE_ORDER, brandedSettings);

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex flex-col md:flex-row min-h-screen md:h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          {/* Header */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 sticky top-0 z-20 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Settings2 size={22} className="text-gold" />
              <div>
                <h2 className="text-2xl font-bold text-cream">Configurações</h2>
                <p className="text-stone text-sm">Preferências do sistema</p>
              </div>
            </div>
            <AdminTopActions />
          </div>

          {/* Tabs */}
          <div className="px-4 sm:px-8 pt-4 flex flex-wrap gap-2">
            {isDomainRoute ? (
              <button type="button" onClick={() => setActiveTab("dominio-https")} className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "dominio-https" ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-parchment border border-surface-03"}`}><Globe size={14} /> Dominio e HTTPS</button>
            ) : (
              <>
            <button type="button" onClick={() => setActiveTab("dominio-https")} className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "dominio-https" ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-parchment border border-surface-03"}`}><Globe size={14} /> Dominio e HTTPS</button>
            <button
              onClick={() => setActiveTab("comprovantes")}
              className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "comprovantes" ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-parchment border border-surface-03"}`}
            >
              <Printer size={14} />
              Comprovantes de pedidos
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("etiquetas-expedicao")}
              className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "etiquetas-expedicao" ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-parchment border border-surface-03"}`}
            >
              <Tags size={14} />
              Etiquetas de expedição
            </button>
            <button type="button" onClick={() => setActiveTab("etiquetas-insumos")} className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "etiquetas-insumos" ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-parchment border border-surface-03"}`}><Tags size={14} /> Etiquetas de insumos</button>
            <button
              type="button"
              onClick={() => setActiveTab("painel-tv")}
              className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "painel-tv" ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-parchment border border-surface-03"}`}
            >
              <Monitor size={14} />
              Painéis TV
            </button>
            <button
              onClick={() => setActiveTab("som")}
              className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "som" ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-parchment border border-surface-03"}`}
            >
              <Volume2 size={14} />
              Som
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("identificacao-parceiros")}
              className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "identificacao-parceiros" ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-parchment border border-surface-03"}`}
            >
              <Tags size={14} />
              Identificação de Parceiros
            </button>
              </>
            )}
          </div>

          <div className="p-8 space-y-8 max-w-5xl">

            {activeTab === "dominio-https" && <TenantDomainsPanel />}
            {activeTab === "etiquetas-expedicao" && <><div className="rounded-2xl border border-surface-03 bg-surface-02 p-6"><h3 className="text-lg font-bold text-cream">Etiquetas de expedição</h3><p className="mt-1 text-sm text-stone">Modelos para as caixas de pizza. O formato operacional esperado é 100 × 50 mm.</p></div><LabelSettingsPanel /></>}
            {activeTab === "etiquetas-insumos" && <SuppliesLabelSettingsPanel />}
            {activeTab === "painel-tv" && <OrderBoardSettingsPanel />}
            {activeTab === "identificacao-parceiros" && <PartnerIdentificationPanel />}

            {/* ── Aba Som ───────────────────────────────────────────────── */}
            {activeTab === "som" && (
              <>
                <section className="bg-surface-02 rounded-2xl border border-surface-03 p-6">
                  <h3 className="text-cream font-bold text-lg mb-1">Alerta sonoro de novo pedido</h3>
                  <p className="text-stone text-sm mb-6">
                    Escolha o som que toca nos módulos <strong className="text-parchment">Pedidos</strong> e <strong className="text-parchment">Cozinha</strong> quando um novo pedido é recebido.
                    A preferência é salva neste navegador/dispositivo.
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {SOUND_OPTIONS.map((opt) => {
                      const isSelected = soundType === opt.id;
                      const Icon = opt.id === "silent" ? BellOff : opt.id === "bell" ? Bell : Volume2;
                      return (
                        <div
                          key={opt.id}
                          onClick={() => setSoundType(opt.id)}
                          className={`cursor-pointer rounded-2xl border-2 p-5 flex flex-col gap-3 transition-all ${
                            isSelected
                              ? "border-gold bg-gold/10 shadow-lg shadow-gold/10"
                              : "border-surface-03 hover:border-gold/40"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className={`p-2.5 rounded-xl ${isSelected ? "bg-gold/20" : "bg-surface-03"}`}>
                              <Icon size={20} className={isSelected ? "text-gold" : "text-stone"} />
                            </div>
                            {isSelected && (
                              <span className="flex items-center gap-1 text-[10px] font-bold text-gold bg-gold/15 border border-gold/30 rounded-full px-2 py-0.5">
                                <Check size={9} /> Ativo
                              </span>
                            )}
                          </div>

                          <div>
                            <p className={`font-bold text-sm ${isSelected ? "text-gold" : "text-parchment"}`}>
                              {opt.label}
                            </p>
                            <p className="text-stone text-xs mt-1 leading-snug">{opt.description}</p>
                          </div>

                          {opt.id !== "silent" && (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); playOrderAlert(opt.id); }}
                              className="mt-auto flex items-center justify-center gap-1.5 text-xs text-stone hover:text-parchment bg-surface-03 hover:bg-surface-03/70 rounded-lg px-3 py-2 transition-colors"
                            >
                              <Volume2 size={12} />
                              Ouvir prévia
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>

                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={() => {
                      saveSoundType(soundType);
                      setSoundSaved(true);
                      setTimeout(() => setSoundSaved(false), 2500);
                    }}
                    className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2.5 px-6 rounded-xl transition-colors"
                  >
                    {soundSaved ? <Check size={16} /> : <Volume2 size={16} />}
                    {soundSaved ? "Salvo!" : "Salvar preferência"}
                  </button>
                </div>

                <p className="text-stone/60 text-xs">
                  A configuração de som é salva localmente neste navegador/dispositivo. Cada terminal pode ter seu próprio som configurado.
                </p>
              </>
            )}

            {activeTab === "comprovantes" && (
              <>
                {/* ── Dados da loja ─────────────────────────────── */}
                <section className="bg-surface-02 rounded-2xl border border-surface-03 p-6">
                  <h3 className="text-cream font-bold text-lg mb-1">Dados da loja no cupom</h3>
                  <p className="text-stone text-sm mb-5">Aparecem no cabeçalho de todos os modelos de impressão.</p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Field label="Nome da loja">
                      <input
                        className={cls}
                        value={settings.storeName}
                        onChange={(e) => update({ storeName: e.target.value })}
                        placeholder="Moschettieri Pizzeria"
                      />
                    </Field>
                    <Field label="Telefone / WhatsApp">
                      <input
                        className={cls}
                        value={settings.storePhone}
                        onChange={(e) => update({ storePhone: e.target.value })}
                        placeholder="(11) 99999-9999"
                      />
                    </Field>
                    <Field label="Endereço da loja">
                      <input
                        className={cls}
                        value={settings.storeAddress}
                        onChange={(e) => update({ storeAddress: e.target.value })}
                        placeholder="Rua das Pizzas, 42 — Centro"
                      />
                    </Field>
                    <Field label="CNPJ">
                      <input
                        className={cls}
                        value={settings.storeCnpj}
                        onChange={(e) => update({ storeCnpj: e.target.value })}
                        placeholder="00.000.000/0001-00"
                      />
                    </Field>
                    <Field label="Site / URL">
                      <input
                        className={cls}
                        value={settings.storeWebsite}
                        onChange={(e) => update({ storeWebsite: e.target.value })}
                        placeholder="delivery.moschettieri.com.br"
                      />
                    </Field>
                  </div>
                </section>

                {/* ── Configuração da impressora ────────────────── */}
                <section className="bg-surface-02 rounded-2xl border border-surface-03 p-6">
                  <h3 className="text-cream font-bold text-lg mb-1">Comprovantes de pedidos</h3>
                  <p className="text-stone text-sm mb-5">Configure o papel e o comportamento de impressão.</p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Field
                      label="Largura do papel"
                      hint="58mm = impressoras de mesa pequenas. 80mm = padrão de mercado. A4 = impressora comum."
                    >
                      <div className="flex gap-2 mt-1">
                        {(["58mm", "80mm", "a4"] as PaperWidth[]).map((w) => (
                          <button
                            key={w}
                            type="button"
                            onClick={() => update({ paperWidth: w })}
                            className={`flex-1 py-2.5 rounded-lg text-sm font-bold border-2 transition-all ${
                              settings.paperWidth === w
                                ? "border-gold bg-gold/15 text-gold"
                                : "border-surface-03 text-stone hover:border-gold/40 hover:text-parchment"
                            }`}
                          >
                            {w === "a4" ? "A4" : w}
                          </button>
                        ))}
                      </div>
                    </Field>

                    <Field
                      label="Impressão automática"
                      hint="Abre a janela de impressão automaticamente ao clicar no botão de imprimir."
                    >
                      <button
                        type="button"
                        onClick={() => update({ autoPrint: !settings.autoPrint })}
                        className={`mt-1 w-full py-2.5 rounded-lg text-sm font-bold border-2 transition-all ${
                          settings.autoPrint
                            ? "border-gold bg-gold/15 text-gold"
                            : "border-surface-03 text-stone hover:border-gold/40 hover:text-parchment"
                        }`}
                      >
                        {settings.autoPrint ? "✓ Ativada" : "Desativada"}
                      </button>
                    </Field>

                    <Field
                      label="Imprimir pedido confirmado"
                      hint="Quando o painel Pedidos estiver aberto, imprime uma via da cozinha e uma via completa da recepção ao confirmar pagamento."
                    >
                      <button
                        type="button"
                        onClick={() => update({ autoPrintConfirmedOrders: !settings.autoPrintConfirmedOrders })}
                        className={`mt-1 w-full py-2.5 rounded-lg text-sm font-bold border-2 transition-all ${
                          settings.autoPrintConfirmedOrders
                            ? "border-gold bg-gold/15 text-gold"
                            : "border-surface-03 text-stone hover:border-gold/40 hover:text-parchment"
                        }`}
                      >
                        {settings.autoPrintConfirmedOrders ? "✓ Ativada" : "Desativada"}
                      </button>
                    </Field>
                  </div>
                </section>

                {/* ── Modelos de impressão ──────────────────────── */}
                <section>
                  <div className="mb-4">
                    <h3 className="text-cream font-bold text-lg">Modelos de impressão</h3>
                    <p className="text-stone text-sm mt-1">
                      Clique em um modelo para defini-lo como padrão. O botão "Prévia" mostra o resultado real com dados de exemplo.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                    <TemplateCard
                      id="completo"
                      title="Comprovante do pedido (cliente)"
                      description="Cupom com todos os dados: cliente, endereço, itens, totais e frete. Ideal para arquivo ou entrega ao motoboy."
                      selected={settings.defaultTemplate === "completo"}
                      onSelect={() => update({ defaultTemplate: "completo" })}
                      html={htmlCompleto}
                    />
                    <TemplateCard
                      id="cozinha"
                      title="Comanda do KDS Pizzaiolo"
                      description="Foco nos itens em letras grandes para facilitar a leitura na produção. Sem dados financeiros."
                      selected={settings.defaultTemplate === "cozinha"}
                      onSelect={() => update({ defaultTemplate: "cozinha" })}
                      html={htmlCozinha}
                    />
                    <TemplateCard
                      id="entrega"
                      title="Etiqueta da caixa / expedi??o"
                      description="Via focada em entrega: número do pedido, endereço completo, itens e total. Ideal para o motoboy."
                      selected={settings.defaultTemplate === "entrega"}
                      onSelect={() => update({ defaultTemplate: "entrega" })}
                      html={htmlEtiqueta}
                    />
                  </div>
                </section>

                {/* ── Ações ─────────────────────────────────────── */}
                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={handleSave}
                    className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2.5 px-6 rounded-xl transition-colors"
                  >
                    {saved ? <Check size={16} /> : <Settings2 size={16} />}
                    {saved ? "Salvo!" : "Salvar configurações"}
                  </button>
                  <button
                    onClick={handleReset}
                    className="text-stone hover:text-parchment text-sm transition-colors"
                  >
                    Restaurar padrões
                  </button>
                </div>

                {/* ── Info sobre armazenamento ──────────────────── */}
                <p className="text-stone/60 text-xs">
                  As configurações de impressora são salvas localmente neste navegador/dispositivo. Cada terminal pode ter sua própria configuração.
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

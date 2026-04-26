import { useEffect, useRef, useState } from "react";
import { Check, Printer, Eye, Settings2 } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import {
  loadPrinterSettings, savePrinterSettings,
  buildCompletoHtml, buildCozinhaHtml, buildEtiquetaHtml,
  SAMPLE_ORDER, DEFAULT_PRINTER_SETTINGS,
  type PrinterSettings, type PrintTemplate, type PaperWidth,
} from "@/lib/printing";

// ── Tabs ──────────────────────────────────────────────────────────────────────

type Tab = "impressora";

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

  const openPreview = () => {
    const w = window.open("", "_blank", "width=440,height=700,scrollbars=yes");
    if (!w) return;
    w.document.write(html);
    w.document.close();
    w.onload = () => w.focus();
  };

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

export default function AdminConfiguracoes() {
  const [activeTab] = useState<Tab>("impressora");
  const [settings, setSettings] = useState<PrinterSettings>(loadPrinterSettings);
  const [saved, setSaved] = useState(false);

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
  const htmlCompleto = buildCompletoHtml(SAMPLE_ORDER, settings);
  const htmlCozinha  = buildCozinhaHtml(SAMPLE_ORDER, settings);
  const htmlEtiqueta = buildEtiquetaHtml(SAMPLE_ORDER, settings);

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex flex-col md:flex-row min-h-screen md:h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          {/* Header */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 sticky top-0 z-20">
            <div className="flex items-center gap-3">
              <Settings2 size={22} className="text-gold" />
              <div>
                <h2 className="text-2xl font-bold text-cream">Configurações</h2>
                <p className="text-stone text-sm">Preferências do sistema</p>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="px-8 pt-4 flex gap-2">
            <button
              className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium bg-gold text-cream"
            >
              <Printer size={14} />
              Impressora
            </button>
          </div>

          <div className="p-8 space-y-8 max-w-5xl">

            {activeTab === "impressora" && (
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
                  <h3 className="text-cream font-bold text-lg mb-1">Impressora</h3>
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
                      title="Pedido Completo"
                      description="Cupom com todos os dados: cliente, endereço, itens, totais e frete. Ideal para arquivo ou entrega ao motoboy."
                      selected={settings.defaultTemplate === "completo"}
                      onSelect={() => update({ defaultTemplate: "completo" })}
                      html={htmlCompleto}
                    />
                    <TemplateCard
                      id="cozinha"
                      title="Comanda Cozinha"
                      description="Foco nos itens em letras grandes para facilitar a leitura na produção. Sem dados financeiros."
                      selected={settings.defaultTemplate === "cozinha"}
                      onSelect={() => update({ defaultTemplate: "cozinha" })}
                      html={htmlCozinha}
                    />
                    <TemplateCard
                      id="etiqueta"
                      title="Etiqueta de Entrega"
                      description="Etiqueta compacta com número do pedido em destaque, endereço completo e total. Colar na embalagem."
                      selected={settings.defaultTemplate === "etiqueta"}
                      onSelect={() => update({ defaultTemplate: "etiqueta" })}
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

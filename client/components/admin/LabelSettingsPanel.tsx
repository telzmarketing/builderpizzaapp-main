import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Loader2, Plus, Printer, RefreshCw, Ruler, Trash2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { kdsLabelsApi, type KdsLabelPrinter, type KdsLabelSettings, type KdsLabelTemplate, type KdsLabelVolumeRule } from "@/lib/api";
import { buildLabelCalibrationHtml, openLabelPrintWindow, renderHtmlAndPrint } from "@/lib/labelPrinting";

const fieldClass = "min-h-11 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 text-sm text-cream focus:border-gold focus:outline-none";
interface PrinterDraft { name: string; description: string; system_queue_hint: string; dpi: number; printer_type: string; connection_type: string; manufacturer_model: string; network_host: string; network_port: number; protocol: string; max_width_mm: number; sector: string }
interface TemplateDraft { name: string; label_type: "continuous" | "gap" | "black_mark" | "roll" | "sheet" | "seal" | "custom"; width_mm: number; height_mm: number; margin_top_mm: number; margin_right_mm: number; margin_bottom_mm: number; margin_left_mm: number; gap_mm: number; orientation: "portrait" | "landscape"; show_logo: boolean; show_printed_at: boolean; dpi: number; scale_percent: number; default_copies: number; font_scale_percent: number; safe_area_mm: number; offset_x_mm: number; offset_y_mm: number; rotation: number; density: number; speed: number; columns: number; labels_per_sheet: number; printer_ids: string[] }
interface RuleDraft { scope_type: "product" | "category"; scope_value: string; volumes_per_unit: number }
const initialPrinter: PrinterDraft = { name: "", description: "", system_queue_hint: "", dpi: 203, printer_type: "thermal", connection_type: "browser", manufacturer_model: "", network_host: "", network_port: 9100, protocol: "browser", max_width_mm: 100, sector: "dispatch" };
const initialTemplate: TemplateDraft = { name: "100 × 50 mm", label_type: "gap", width_mm: 100, height_mm: 50, margin_top_mm: 2, margin_right_mm: 2, margin_bottom_mm: 2, margin_left_mm: 2, gap_mm: 2, orientation: "portrait", show_logo: true, show_printed_at: true, dpi: 203, scale_percent: 100, default_copies: 1, font_scale_percent: 100, safe_area_mm: 2, offset_x_mm: 0, offset_y_mm: 0, rotation: 0, density: 8, speed: 4, columns: 1, labels_per_sheet: 1, printer_ids: [] };
const initialRule: RuleDraft = { scope_type: "product", scope_value: "", volumes_per_unit: 1 };

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Não foi possível carregar as configurações de etiquetas.";
}

export default function LabelSettingsPanel() {
  const { toast } = useToast();
  const [printers, setPrinters] = useState<KdsLabelPrinter[]>([]);
  const [templates, setTemplates] = useState<KdsLabelTemplate[]>([]);
  const [rules, setRules] = useState<KdsLabelVolumeRule[]>([]);
  const [settings, setSettings] = useState<KdsLabelSettings | null>(null);
  const [printerDraft, setPrinterDraft] = useState(initialPrinter);
  const [templateDraft, setTemplateDraft] = useState(initialTemplate);
  const [ruleDraft, setRuleDraft] = useState(initialRule);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextPrinters, nextTemplates, nextSettings, nextRules] = await Promise.all([
        kdsLabelsApi.listPrinters(), kdsLabelsApi.listTemplates(), kdsLabelsApi.getSettings(), kdsLabelsApi.listVolumeRules(),
      ]);
      setPrinters(nextPrinters); setTemplates(nextTemplates); setSettings(nextSettings); setRules(nextRules); setError(null);
    } catch (caught) { setError(errorText(caught)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const run = async (key: string, action: () => Promise<unknown>, success: string) => {
    if (saving) return;
    setSaving(key); setError(null);
    try { await action(); await load(); toast({ title: success }); }
    catch (caught) { setError(errorText(caught)); }
    finally { setSaving(null); }
  };

  const testPrint = async () => {
    if (!settings || saving) return;
    const target = openLabelPrintWindow();
    if (!target) { setError("Habilite pop-ups para imprimir a etiqueta de teste."); return; }
    setSaving("test"); setError(null);
    try {
      const result = await kdsLabelsApi.test({ printer_id: settings.default_printer_id, template_id: settings.default_template_id, copies: 1, idempotency_key: `label-test:${Date.now()}:${Math.random()}` });
      renderHtmlAndPrint(buildLabelCalibrationHtml(result.preview), target, () => { void kdsLabelsApi.markDialogOpened(result.job.id); });
      toast({ title: "Etiqueta de teste preparada", description: "Confirme a fila física na caixa do navegador." });
    } catch (caught) { target.close?.(); setError(errorText(caught)); }
    finally { setSaving(null); }
  };

  if (loading && !settings) return <div className="flex min-h-52 items-center justify-center gap-2 text-stone"><Loader2 className="animate-spin"/> Carregando impressoras e etiquetas...</div>;

  return <div className="space-y-6">
    {error && <div role="alert" className="flex items-start justify-between gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-200"><span className="flex gap-2"><AlertTriangle className="shrink-0"/> {error}</span><button type="button" onClick={() => void load()} className="rounded-lg border border-red-400/40 p-2" aria-label="Tentar carregar novamente"><RefreshCw size={18}/></button></div>}

    <section className="rounded-2xl border border-surface-03 bg-surface-02 p-6">
      <h3 className="text-lg font-bold text-cream">Preferências da expedição</h3><p className="mb-5 text-sm text-stone">Configuração compartilhada pelo estabelecimento. A fila física continua sendo escolhida no navegador.</p>
      {settings && <div className="grid gap-4 md:grid-cols-2">
        <label className="text-sm font-bold text-parchment">Impressora padrão<select className={fieldClass} value={settings.default_printer_id ?? ""} onChange={(e) => setSettings({ ...settings, default_printer_id: e.target.value || null })}><option value="">Sem padrão</option>{printers.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="text-sm font-bold text-parchment">Modelo padrão<select className={fieldClass} value={settings.default_template_id ?? ""} onChange={(e) => setSettings({ ...settings, default_template_id: e.target.value || null })}><option value="">Sem padrão</option>{templates.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="flex min-h-12 items-center gap-3 rounded-lg border border-surface-03 bg-surface-01 px-4 text-sm font-bold"><input type="checkbox" checked={settings.include_drinks} onChange={(e) => setSettings({ ...settings, include_drinks: e.target.checked })}/> Gerar etiquetas para bebidas</label>
        <label className="flex min-h-12 items-center gap-3 rounded-lg border border-surface-03 bg-surface-01 px-4 text-sm font-bold"><input type="checkbox" checked={settings.require_reprint_reason} onChange={(e) => setSettings({ ...settings, require_reprint_reason: e.target.checked })}/> Exigir motivo na reimpressão</label>
        <div className="flex flex-wrap gap-2 md:col-span-2"><button type="button" disabled={Boolean(saving)} onClick={() => void run("settings", () => kdsLabelsApi.updateSettings(settings), "Preferências salvas")} className="flex min-h-11 items-center gap-2 rounded-lg bg-gold px-5 font-bold text-cream disabled:opacity-50">{saving === "settings" ? <Loader2 className="animate-spin"/> : <Check/>} Salvar preferências</button><button type="button" disabled={Boolean(saving) || !settings.default_template_id} onClick={() => void testPrint()} className="flex min-h-11 items-center gap-2 rounded-lg border border-surface-03 px-5 font-bold disabled:opacity-50">{saving === "test" ? <Loader2 className="animate-spin"/> : <Printer/>} Testar e calibrar</button></div>
      </div>}
    </section>

    <section className="rounded-2xl border border-surface-03 bg-surface-02 p-6">
      <h3 className="text-lg font-bold text-cream">Impressoras lógicas</h3><p className="mb-4 text-sm text-stone">O nome da fila é uma referência para o operador; o navegador não seleciona a impressora automaticamente.</p>
      <form className="grid gap-3 md:grid-cols-4" onSubmit={(e) => { e.preventDefault(); void run("printer", () => kdsLabelsApi.createPrinter({ ...printerDraft, active: true }), "Impressora cadastrada").then(() => setPrinterDraft(initialPrinter)); }}>
        <label className="text-xs font-bold text-stone">Nome<input required className={fieldClass} value={printerDraft.name} onChange={(e) => setPrinterDraft({ ...printerDraft, name: e.target.value })}/></label>
        <label className="text-xs font-bold text-stone">Descrição<input className={fieldClass} value={printerDraft.description} onChange={(e) => setPrinterDraft({ ...printerDraft, description: e.target.value })}/></label>
        <label className="text-xs font-bold text-stone">Fila sugerida<input className={fieldClass} value={printerDraft.system_queue_hint} onChange={(e) => setPrinterDraft({ ...printerDraft, system_queue_hint: e.target.value })}/></label>
        <label className="text-xs font-bold text-stone">DPI<input required min={100} max={1200} type="number" className={fieldClass} value={printerDraft.dpi} onChange={(e) => setPrinterDraft({ ...printerDraft, dpi: Number(e.target.value) })}/></label>
        <details className="md:col-span-4 rounded-lg border border-surface-03 p-3"><summary className="cursor-pointer text-sm font-bold text-parchment">Configuração avançada</summary><div className="mt-3 grid gap-3 md:grid-cols-4">
          <label className="text-xs font-bold text-stone">Tipo<input className={fieldClass} value={printerDraft.printer_type} onChange={(e) => setPrinterDraft({ ...printerDraft, printer_type: e.target.value })}/></label>
          <label className="text-xs font-bold text-stone">Conexão<select className={fieldClass} value={printerDraft.connection_type} onChange={(e) => setPrinterDraft({ ...printerDraft, connection_type: e.target.value })}><option value="browser">Navegador</option><option value="network">Rede (metadado)</option><option value="installed">Instalada (metadado)</option><option value="shared">Compartilhada (metadado)</option><option value="local_service">Serviço local (metadado)</option></select></label>
          <label className="text-xs font-bold text-stone">Fabricante/modelo<input className={fieldClass} value={printerDraft.manufacturer_model} onChange={(e) => setPrinterDraft({ ...printerDraft, manufacturer_model: e.target.value })}/></label>
          <label className="text-xs font-bold text-stone">Setor<input className={fieldClass} value={printerDraft.sector} onChange={(e) => setPrinterDraft({ ...printerDraft, sector: e.target.value })}/></label>
          <label className="text-xs font-bold text-stone">Host de rede<input className={fieldClass} value={printerDraft.network_host} onChange={(e) => setPrinterDraft({ ...printerDraft, network_host: e.target.value })} placeholder="Somente referência"/></label>
          <label className="text-xs font-bold text-stone">Porta<input min={1} max={65535} type="number" className={fieldClass} value={printerDraft.network_port} onChange={(e) => setPrinterDraft({ ...printerDraft, network_port: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Protocolo<input className={fieldClass} value={printerDraft.protocol} onChange={(e) => setPrinterDraft({ ...printerDraft, protocol: e.target.value })}/></label>
          <label className="text-xs font-bold text-stone">Largura máx. (mm)<input min={30} max={300} type="number" className={fieldClass} value={printerDraft.max_width_mm} onChange={(e) => setPrinterDraft({ ...printerDraft, max_width_mm: Number(e.target.value) })}/></label>
        </div><p className="mt-2 text-xs text-stone">Rede e protocolo são metadados nesta fase; nenhuma conexão direta é iniciada pelo navegador.</p></details>
        <button disabled={Boolean(saving)} className="flex min-h-11 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 font-bold text-white disabled:opacity-50 md:col-span-4"><Plus/> Adicionar impressora</button>
      </form>
      <div className="mt-4 grid gap-2 md:grid-cols-2">{printers.length === 0 ? <p className="text-sm text-stone">Nenhuma impressora cadastrada.</p> : printers.map((printer) => <div key={printer.id} className="flex items-center justify-between rounded-lg border border-surface-03 bg-surface-01 p-3"><div><p className="font-bold">{printer.name}</p><p className="text-xs text-stone">{printer.dpi} DPI · {printer.system_queue_hint || "fila definida ao imprimir"}</p></div><button aria-label={`Excluir impressora ${printer.name}`} disabled={Boolean(saving)} onClick={() => void run(`printer-${printer.id}`, () => kdsLabelsApi.deletePrinter(printer.id), "Impressora removida")} className="p-2 text-red-300 disabled:opacity-50"><Trash2 size={18}/></button></div>)}</div>
    </section>

    <section className="rounded-2xl border border-surface-03 bg-surface-02 p-6">
      <h3 className="text-lg font-bold text-cream">Modelos e dimensões</h3><p className="mb-4 text-sm text-stone">Medidas reais em milímetros, margem interna e orientação usadas no CSS de impressão.</p>
      <form className="grid gap-3 md:grid-cols-3" onSubmit={(e) => { e.preventDefault(); void run("template", () => kdsLabelsApi.createTemplate({ ...templateDraft, active: true }), "Modelo cadastrado").then(() => setTemplateDraft(initialTemplate)); }}>
        <label className="text-xs font-bold text-stone md:col-span-3">Nome<input required className={fieldClass} value={templateDraft.name} onChange={(e) => setTemplateDraft({ ...templateDraft, name: e.target.value })}/></label>
        <label className="text-xs font-bold text-stone">Tipo de etiqueta<select className={fieldClass} value={templateDraft.label_type} onChange={(e) => setTemplateDraft({ ...templateDraft, label_type: e.target.value as TemplateDraft["label_type"] })}><option value="gap">Térmica com gap</option><option value="continuous">Térmica contínua</option><option value="black_mark">Marca preta</option><option value="roll">Adesiva em rolo</option><option value="sheet">Folha</option><option value="seal">Lacre</option><option value="custom">Personalizada</option></select></label>
        <label className="text-xs font-bold text-stone md:col-span-2">Atalho de tamanho<select className={fieldClass} value="" onChange={(e) => { const [width, height] = e.target.value.split("x").map(Number); if (width && height) setTemplateDraft({ ...templateDraft, width_mm: width, height_mm: height, name: `${width} × ${height} mm` }); }}><option value="">Tamanho personalizado</option><option value="100x50">100 × 50 mm</option><option value="100x60">100 × 60 mm</option><option value="80x40">80 × 40 mm</option><option value="60x40">60 × 40 mm</option></select></label>
        <label className="text-xs font-bold text-stone">Largura (mm)<input required min={30} max={300} step="0.1" type="number" className={fieldClass} value={templateDraft.width_mm} onChange={(e) => setTemplateDraft({ ...templateDraft, width_mm: Number(e.target.value) })}/></label>
        <label className="text-xs font-bold text-stone">Altura (mm)<input required min={20} max={300} step="0.1" type="number" className={fieldClass} value={templateDraft.height_mm} onChange={(e) => setTemplateDraft({ ...templateDraft, height_mm: Number(e.target.value) })}/></label>
        <label className="text-xs font-bold text-stone">Orientação<select className={fieldClass} value={templateDraft.orientation} onChange={(e) => setTemplateDraft({ ...templateDraft, orientation: e.target.value as "portrait" | "landscape" })}><option value="portrait">Retrato</option><option value="landscape">Paisagem</option></select></label>
        <label className="flex items-center gap-2 text-sm font-bold"><input type="checkbox" checked={templateDraft.show_logo} onChange={(e) => setTemplateDraft({ ...templateDraft, show_logo: e.target.checked })}/> Mostrar logo</label>
        <details className="md:col-span-3 rounded-lg border border-surface-03 p-3"><summary className="cursor-pointer text-sm font-bold text-parchment">Calibração avançada</summary><div className="mt-3 grid gap-3 md:grid-cols-4">
          {(["margin_top_mm", "margin_right_mm", "margin_bottom_mm", "margin_left_mm"] as const).map((key) => <label key={key} className="text-xs font-bold text-stone">Margem {key.replace("margin_", "").replace("_mm", "")} (mm)<input min={0} max={20} step="0.1" type="number" className={fieldClass} value={templateDraft[key]} onChange={(e) => setTemplateDraft({ ...templateDraft, [key]: Number(e.target.value) })}/></label>)}
          <label className="text-xs font-bold text-stone">Gap (mm)<input min={0} max={20} step="0.1" type="number" className={fieldClass} value={templateDraft.gap_mm} onChange={(e) => setTemplateDraft({ ...templateDraft, gap_mm: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Colunas<input min={1} max={10} type="number" className={fieldClass} value={templateDraft.columns} onChange={(e) => setTemplateDraft({ ...templateDraft, columns: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Etiquetas por folha<input min={1} max={100} type="number" className={fieldClass} value={templateDraft.labels_per_sheet} onChange={(e) => setTemplateDraft({ ...templateDraft, labels_per_sheet: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">DPI<input min={100} max={1200} type="number" className={fieldClass} value={templateDraft.dpi} onChange={(e) => setTemplateDraft({ ...templateDraft, dpi: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Escala (%)<input min={50} max={200} type="number" className={fieldClass} value={templateDraft.scale_percent} onChange={(e) => setTemplateDraft({ ...templateDraft, scale_percent: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Cópias padrão<input min={1} max={20} type="number" className={fieldClass} value={templateDraft.default_copies} onChange={(e) => setTemplateDraft({ ...templateDraft, default_copies: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Escala da fonte (%)<input min={50} max={200} type="number" className={fieldClass} value={templateDraft.font_scale_percent} onChange={(e) => setTemplateDraft({ ...templateDraft, font_scale_percent: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Área segura (mm)<input min={0} max={20} step="0.1" type="number" className={fieldClass} value={templateDraft.safe_area_mm} onChange={(e) => setTemplateDraft({ ...templateDraft, safe_area_mm: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Offset X (mm)<input min={-20} max={20} step="0.1" type="number" className={fieldClass} value={templateDraft.offset_x_mm} onChange={(e) => setTemplateDraft({ ...templateDraft, offset_x_mm: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Offset Y (mm)<input min={-20} max={20} step="0.1" type="number" className={fieldClass} value={templateDraft.offset_y_mm} onChange={(e) => setTemplateDraft({ ...templateDraft, offset_y_mm: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Rotação<select className={fieldClass} value={templateDraft.rotation} onChange={(e) => setTemplateDraft({ ...templateDraft, rotation: Number(e.target.value) })}>{[0,90,180,270].map((value) => <option key={value} value={value}>{value}°</option>)}</select></label>
          <label className="text-xs font-bold text-stone">Densidade<input min={0} max={30} type="number" className={fieldClass} value={templateDraft.density} onChange={(e) => setTemplateDraft({ ...templateDraft, density: Number(e.target.value) })}/></label>
          <label className="text-xs font-bold text-stone">Velocidade<input min={1} max={20} type="number" className={fieldClass} value={templateDraft.speed} onChange={(e) => setTemplateDraft({ ...templateDraft, speed: Number(e.target.value) })}/></label>
          <label className="flex items-center gap-2 text-sm font-bold"><input type="checkbox" checked={templateDraft.show_printed_at} onChange={(e) => setTemplateDraft({ ...templateDraft, show_printed_at: e.target.checked })}/> Mostrar data/hora</label>
        </div></details>
        <fieldset className="md:col-span-3 rounded-lg border border-surface-03 p-3"><legend className="px-2 text-sm font-bold text-parchment">Impressoras compatíveis</legend><p className="mb-2 text-xs text-stone">Sem seleção, o modelo fica disponível para todas.</p><div className="flex flex-wrap gap-3">{printers.filter((printer) => printer.active).map((printer) => <label key={printer.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={templateDraft.printer_ids.includes(printer.id)} onChange={(e) => setTemplateDraft({ ...templateDraft, printer_ids: e.target.checked ? [...templateDraft.printer_ids, printer.id] : templateDraft.printer_ids.filter((id) => id !== printer.id) })}/>{printer.name}</label>)}</div></fieldset>
        <button disabled={Boolean(saving)} className="flex min-h-11 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 font-bold text-white disabled:opacity-50"><Ruler/> Adicionar modelo</button>
      </form>
      <div className="mt-4 grid gap-2 md:grid-cols-2">{templates.length === 0 ? <p className="text-sm text-stone">Nenhum modelo cadastrado.</p> : templates.map((template) => <div key={template.id} className="flex items-center justify-between rounded-lg border border-surface-03 bg-surface-01 p-3"><div><p className="font-bold">{template.name}</p><p className="text-xs text-stone">{template.width_mm} × {template.height_mm} mm · margens {template.margin_top_mm}/{template.margin_right_mm}/{template.margin_bottom_mm}/{template.margin_left_mm} mm</p></div><button aria-label={`Excluir modelo ${template.name}`} disabled={Boolean(saving)} onClick={() => void run(`template-${template.id}`, () => kdsLabelsApi.deleteTemplate(template.id), "Modelo removido")} className="p-2 text-red-300 disabled:opacity-50"><Trash2 size={18}/></button></div>)}</div>
    </section>

    <section className="rounded-2xl border border-surface-03 bg-surface-02 p-6">
      <h3 className="text-lg font-bold text-cream">Regras de volumes</h3><p className="mb-4 text-sm text-stone">Sobrescreva a quantidade por unidade (0 a 20). Use 0 para não gerar etiqueta; produto usa UUID e categoria usa o nome exato do catálogo.</p>
      <form className="grid gap-3 md:grid-cols-4" onSubmit={(e) => { e.preventDefault(); void run("rule", () => kdsLabelsApi.createVolumeRule({ ...ruleDraft, active: true }), "Regra cadastrada").then(() => setRuleDraft(initialRule)); }}>
        <label className="text-xs font-bold text-stone">Escopo<select className={fieldClass} value={ruleDraft.scope_type} onChange={(e) => setRuleDraft({ ...ruleDraft, scope_type: e.target.value as "product" | "category" })}><option value="product">Produto</option><option value="category">Categoria</option></select></label>
        <label className="text-xs font-bold text-stone md:col-span-2">{ruleDraft.scope_type === "product" ? "UUID do produto" : "Nome exato da categoria"}<input required className={fieldClass} value={ruleDraft.scope_value} onChange={(e) => setRuleDraft({ ...ruleDraft, scope_value: e.target.value })} placeholder={ruleDraft.scope_type === "product" ? "UUID do produto" : "Ex.: Pizzas"}/></label>
        <label className="text-xs font-bold text-stone">Volumes/unidade<input required min={0} max={20} type="number" className={fieldClass} value={ruleDraft.volumes_per_unit} onChange={(e) => setRuleDraft({ ...ruleDraft, volumes_per_unit: Number(e.target.value) })}/></label>
        <button disabled={Boolean(saving)} className="flex min-h-11 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 font-bold text-white disabled:opacity-50 md:col-span-4"><Plus/> Adicionar regra</button>
      </form>
      <div className="mt-4 space-y-2">{rules.length === 0 ? <p className="text-sm text-stone">Nenhuma regra específica. Será usado um volume por unidade.</p> : rules.map((rule) => <div key={rule.id} className="flex items-center justify-between rounded-lg border border-surface-03 bg-surface-01 p-3"><div><p className="font-bold">{rule.scope_type === "product" ? "Produto" : "Categoria"} · {rule.volumes_per_unit} volume(s)</p><p className="break-all text-xs text-stone">{rule.scope_value}</p></div><button aria-label="Excluir regra de volume" disabled={Boolean(saving)} onClick={() => void run(`rule-${rule.id}`, () => kdsLabelsApi.deleteVolumeRule(rule.id), "Regra removida")} className="p-2 text-red-300 disabled:opacity-50"><Trash2 size={18}/></button></div>)}</div>
    </section>
  </div>;
}

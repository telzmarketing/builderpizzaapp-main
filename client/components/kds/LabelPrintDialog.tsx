import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, History, Loader2, Printer } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { kdsLabelsApi, type KdsLabelPreview, type KdsLabelPrinter, type KdsLabelPrintJob, type KdsLabelSettings, type KdsLabelTemplate } from "@/lib/api";
import { openLabelPrintWindow, renderAndPrintLabels } from "@/lib/labelPrinting";

interface Props {
  orderId: string | null;
  orderCode?: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "Não foi possível preparar as etiquetas.";
}

function newIdempotencyKey(orderId: string) {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  return `label:${orderId}:${suffix}`;
}

export default function LabelPrintDialog({ orderId, orderCode, open, onOpenChange }: Props) {
  const { toast } = useToast();
  const [printers, setPrinters] = useState<KdsLabelPrinter[]>([]);
  const [templates, setTemplates] = useState<KdsLabelTemplate[]>([]);
  const [settings, setSettings] = useState<KdsLabelSettings | null>(null);
  const [history, setHistory] = useState<KdsLabelPrintJob[]>([]);
  const [preview, setPreview] = useState<KdsLabelPreview | null>(null);
  const [printerId, setPrinterId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [copies, setCopies] = useState(1);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [printing, setPrinting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestSequence = useRef(0);

  const loadPreview = useCallback(async (id: string, nextPrinterId?: string, nextTemplateId?: string) => {
    const sequence = ++requestSequence.current;
    setPreviewing(true);
    try {
      const value = await kdsLabelsApi.preview(id, nextPrinterId || null, nextTemplateId || null);
      if (sequence === requestSequence.current) {
        setPreview(value);
        setError(null);
      }
    } catch (caught) {
      if (sequence === requestSequence.current) {
        setPreview(null);
        setError(message(caught));
      }
    } finally {
      if (sequence === requestSequence.current) setPreviewing(false);
    }
  }, []);

  useEffect(() => {
    if (!open || !orderId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setPreview(null);
    setReason("");
    Promise.all([kdsLabelsApi.listPrinters(), kdsLabelsApi.listTemplates(), kdsLabelsApi.getSettings(), kdsLabelsApi.history(orderId)])
      .then(([nextPrinters, nextTemplates, nextSettings, nextHistory]) => {
        if (cancelled) return;
        setPrinters(nextPrinters.filter((item) => item.active));
        setTemplates(nextTemplates.filter((item) => item.active));
        setSettings(nextSettings);
        setHistory(nextHistory);
        const nextPrinterId = nextSettings.default_printer_id ?? nextPrinters.find((item) => item.is_default)?.id ?? nextPrinters[0]?.id ?? "";
        const nextTemplateId = nextSettings.default_template_id ?? nextTemplates.find((item) => item.is_default)?.id ?? nextTemplates[0]?.id ?? "";
        setPrinterId(nextPrinterId);
        setTemplateId(nextTemplateId);
        setCopies(nextTemplates.find((item) => item.id === nextTemplateId)?.default_copies ?? 1);
        return loadPreview(orderId, nextPrinterId, nextTemplateId);
      })
      .catch((caught) => !cancelled && setError(message(caught)))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; requestSequence.current += 1; };
  }, [loadPreview, open, orderId]);

  const updateSelection = (nextPrinterId: string, nextTemplateId: string) => {
    setPrinterId(nextPrinterId);
    setTemplateId(nextTemplateId);
    setCopies(templates.find((item) => item.id === nextTemplateId)?.default_copies ?? 1);
    if (orderId) void loadPreview(orderId, nextPrinterId, nextTemplateId);
  };

  const print = async () => {
    if (!orderId || !preview || printing) return;
    const reprint = !preview.is_first_print || preview.previous_print_count > 0;
    if (reprint && settings?.require_reprint_reason && !reason.trim()) {
      setError("Informe o motivo da reimpressão.");
      return;
    }
    const target = openLabelPrintWindow();
    if (!target) {
      setError("O navegador bloqueou a janela. Habilite pop-ups para imprimir.");
      return;
    }
    setPrinting(true);
    setError(null);
    try {
      const payload = { printer_id: printerId || null, template_id: templateId || null, copies, idempotency_key: newIdempotencyKey(orderId) };
      const result = reprint
        ? await kdsLabelsApi.reprint(orderId, { ...payload, reason: reason.trim() || "Reimpressão operacional" })
        : await kdsLabelsApi.print(orderId, payload);
      const printable = result.preview;
      renderAndPrintLabels({ ...printable, volumes: Array.from({ length: copies }, () => printable.volumes).flat() }, target, () => { void kdsLabelsApi.markDialogOpened(result.job.id); });
      setPreview({ ...printable, is_first_print: false, previous_print_count: printable.previous_print_count + 1 });
      setHistory((current) => [result.job, ...current]);
      toast({ title: reprint ? "Reimpressão registrada" : "Impressão registrada", description: "A caixa de impressão foi aberta. Confirme a fila no sistema operacional." });
    } catch (caught) {
      target.close?.();
      setError(message(caught));
    } finally {
      setPrinting(false);
    }
  };

  const isReprint = Boolean(preview && (!preview.is_first_print || preview.previous_print_count > 0));

  return <Dialog open={open} onOpenChange={(next) => !printing && onOpenChange(next)}>
    <DialogContent className="border-surface-03 bg-surface-02 text-cream sm:max-w-4xl">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2"><Printer className="text-emerald-300" /> Etiquetas do pedido #{orderCode || orderId?.slice(0, 8).toUpperCase()}</DialogTitle>
        <DialogDescription className="text-stone">Revise os volumes. A impressora física será escolhida na caixa do navegador.</DialogDescription>
      </DialogHeader>

      {error && <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200"><AlertTriangle className="mt-0.5 shrink-0" size={17}/><span>{error}</span></div>}
      {loading ? <div className="flex min-h-52 items-center justify-center gap-2 text-stone"><Loader2 className="animate-spin"/> Carregando configuração...</div> : <>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="space-y-1 text-sm font-bold">Impressora lógica
            <select aria-label="Impressora lógica" value={printerId} onChange={(event) => updateSelection(event.target.value, templateId)} disabled={previewing || printing} className="min-h-11 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 text-cream">
              {printers.map((printer) => <option key={printer.id} value={printer.id}>{printer.name}</option>)}
            </select>
          </label>
          <label className="space-y-1 text-sm font-bold">Modelo
            <select aria-label="Modelo de etiqueta" value={templateId} onChange={(event) => updateSelection(printerId, event.target.value)} disabled={previewing || printing} className="min-h-11 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 text-cream">
              {templates.filter((template) => !template.printer_ids.length || !printerId || template.printer_ids.includes(printerId)).map((template) => <option key={template.id} value={template.id}>{template.name} · {template.width_mm}×{template.height_mm} mm</option>)}
            </select>
          </label>
          <label className="space-y-1 text-sm font-bold">Cópias
            <input aria-label="Número de cópias" type="number" min={1} max={10} value={copies} onChange={(event) => setCopies(Math.min(10, Math.max(1, Number(event.target.value) || 1)))} disabled={printing} className="min-h-11 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 text-cream"/>
          </label>
        </div>

        {previewing ? <div className="flex min-h-40 items-center justify-center gap-2 text-stone"><Loader2 className="animate-spin"/> Atualizando prévia...</div> : !preview ? <div className="rounded-xl border border-dashed border-surface-03 p-8 text-center text-stone">Nenhuma etiqueta disponível para este pedido.</div> : <>
          <div className="flex items-center justify-between gap-3"><p className="font-black">{preview.volume_count} volume(s)</p>{isReprint && <span className="flex items-center gap-1 rounded-full bg-amber-500/15 px-3 py-1 text-xs font-bold text-amber-200"><History size={14}/> Reimpressão · {preview.previous_print_count} anterior(es)</span>}</div>
          <div className="grid max-h-72 gap-3 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-3">
            {preview.volumes.map((volume) => <article key={volume.id ?? `${volume.order_item_id}-${volume.sequence}`} className="rounded-xl border border-surface-03 bg-white p-3 text-black" style={{ aspectRatio: `${preview.template.width_mm}/${preview.template.height_mm}` }}>
              <p className="text-xs font-bold uppercase">{preview.restaurant.name}</p><p className="text-lg font-black">Pedido #{preview.order.order_code}</p><p className="font-black">{volume.product_name}</p>
              <p className="text-xs">{[volume.selected_size, volume.selected_crust_type, volume.selected_drink_variant].filter(Boolean).join(" · ")}</p>
              {volume.notes && <p className="mt-1 border border-black p-1 text-xs font-bold">OBS: {volume.notes}</p>}
              <p className="mt-2 text-right text-xs font-black">VOLUME {volume.sequence}/{volume.total_volumes}</p>
            </article>)}
          </div>
          {isReprint && <label className="space-y-1 text-sm font-bold">Motivo da reimpressão {settings?.require_reprint_reason && <span className="text-red-300">*</span>}
            <textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={300} disabled={printing} className="min-h-20 w-full rounded-lg border border-surface-03 bg-surface-01 p-3 text-cream" placeholder="Ex.: etiqueta danificada"/>
          </label>}
          <details className="rounded-xl border border-surface-03 bg-surface-01 p-3"><summary className="cursor-pointer font-bold">Histórico de impressão ({history.length})</summary>
            {history.length === 0 ? <p className="mt-3 text-sm text-stone">Nenhuma impressão registrada.</p> : <div className="mt-3 max-h-48 space-y-2 overflow-y-auto">{history.map((job) => {
              const printer = job.printer_name ?? printers.find((item) => item.id === job.printer_id)?.name ?? "Impressora não informada";
              const template = job.template_name ?? templates.find((item) => item.id === job.template_id)?.name ?? "Modelo não informado";
              return <div key={job.id} className="rounded-lg border border-surface-03 p-3 text-xs"><div className="flex flex-wrap justify-between gap-2"><strong>{job.job_type === "reprint" ? "Reimpressão" : "Impressão"} · {job.copies} cópia(s)</strong><time>{new Date(job.created_at).toLocaleString("pt-BR")}</time></div><p className="mt-1 text-stone">{printer} · {template} · {job.actor_name || "Operador atual"}</p><p className="mt-1">Status: <strong>{job.result_status}</strong>{job.reason ? ` · Motivo: ${job.reason}` : ""}</p></div>;
            })}</div>}
          </details>
        </>}
      </>}

      <DialogFooter>
        <button type="button" onClick={() => onOpenChange(false)} disabled={printing} className="min-h-11 rounded-lg border border-surface-03 px-5 font-bold disabled:opacity-50">Cancelar</button>
        <button type="button" onClick={() => void print()} disabled={!preview || previewing || printing || printers.length === 0 || templates.length === 0} className="flex min-h-11 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-5 font-black text-white disabled:opacity-40">
          {printing ? <Loader2 className="animate-spin"/> : <Printer/>}{printing ? "Registrando..." : isReprint ? "Reimprimir etiquetas" : "Imprimir etiquetas"}
        </button>
      </DialogFooter>
    </DialogContent>
  </Dialog>;
}

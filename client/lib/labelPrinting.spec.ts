import { describe, expect, it, vi } from "vitest";
import { buildLabelPrintHtml, buildPreparationLabelPrintHtml, renderHtmlAndPrint, renderAndPrintLabels, type LabelPrintTarget } from "./labelPrinting";
import type { KdsLabelPreview } from "./api";

const preview: KdsLabelPreview = {
  order: { id: "order-12345678", order_code: "42", status: "ready_for_pickup", fulfillment_type: "delivery", customer_name: "Maria & João" },
  restaurant: { name: "Pizzaria <Centro>", logo_url: "javascript:alert(1)" },
  version: { id: "v1", number: 1, fingerprint: "abc", created_at: "2026-09-26T12:00:00Z" },
  printer: { id: "p1", name: "Browser", dpi: 203, active: true },
  template: { id: "t1", name: "100x50", label_type: "gap", width_mm: 100, height_mm: 50, margin_top_mm: 2, margin_right_mm: 2, margin_bottom_mm: 2, margin_left_mm: 2, gap_mm: 2, safe_area_mm: 1, columns: 1, labels_per_sheet: 1, orientation: "portrait", show_logo: true, show_printed_at: true, dpi: 203, scale_percent: 100, default_copies: 1, font_scale_percent: 100, offset_x_mm: 0, offset_y_mm: 0, rotation: 0, active: true, printer_ids: [] },
  volumes: [{ id: "vol1", sequence: 1, total_volumes: 1, order_item_id: "i1", unit_index: 1, volume_index: 1, product_id: "prod1", product_name: "Pizza <Grande>", quantity: 1, selected_size: "Grande", notes: "Sem 'cebola'", add_ons: ["Meia & meia"], flavors: [] }],
  volume_count: 1,
  is_first_print: true,
  previous_print_count: 0,
};

describe("labelPrinting", () => {
  it("waits for the tenant logo to load before opening print", async () => {
    vi.useFakeTimers();
    try {
      const listeners: Record<string, () => void> = {};
      const image = { complete: false, naturalWidth: 100, hidden: false, addEventListener: (event: string, callback: () => void) => { listeners[event] = callback; } };
      const target = { document: { write: vi.fn(), close: vi.fn(), images: [image] }, focus: vi.fn(), print: vi.fn() } as unknown as LabelPrintTarget;
      renderHtmlAndPrint("<html>label</html>", target);
      expect(target.print).not.toHaveBeenCalled();
      listeners.load();
      await vi.advanceTimersByTimeAsync(0);
      expect(target.print).toHaveBeenCalledOnce();
      expect(image.hidden).toBe(false);
    } finally { vi.useRealTimers(); }
  });
  it("renders preparation snapshot, safe branding and copies without inventing expiry", () => {
    const html = buildPreparationLabelPrintHtml({ execution: { execution_id: "e1", product_name: "Muçarela <porção>", quantity: "40", portion_grams: "150", lot_code: "L&1", restaurant: { name: "Cozinha", logo_url: "javascript:alert(1)" } }, printer: preview.printer!, template: preview.template }, 2);
    expect(html).toContain("Muçarela &lt;porção&gt;");
    expect(html).toContain("150 g/porção");
    expect(html).toContain("L&amp;1");
    expect(html).toContain("Validade:</b> Não informado");
    expect(html.match(/<article class="label">/g)).toHaveLength(2);
    expect(html).not.toContain("javascript:");
  });
  it("gera uma página em milímetros por volume e escapa dados do pedido", () => {
    const html = buildLabelPrintHtml(preview);
    expect(html).toContain("@page{size:100mm 50mm;margin:0}");
    expect(html).toContain("width:100mm;height:50mm;padding:2mm");
    expect(html).toContain("Pizzaria &lt;Centro&gt;");
    expect(html).toContain("Maria &amp; João");
    expect(html).not.toContain("javascript:alert");
  });

  it("inverte as medidas no modelo paisagem", () => {
    const html = buildLabelPrintHtml({ ...preview, template: { ...preview.template, orientation: "landscape" } });
    expect(html).toContain("@page{size:50mm 100mm;margin:0}");
  });

  it("escreve e dispara a impressão na janela já aberta", () => {
    vi.useFakeTimers();
    const target = { document: { write: vi.fn(), close: vi.fn() }, focus: vi.fn(), print: vi.fn() } as unknown as LabelPrintTarget;
    renderAndPrintLabels(preview, target);
    vi.runAllTimers();
    expect(target.document.write).toHaveBeenCalledOnce();
    expect(target.focus).toHaveBeenCalledOnce();
    expect(target.print).toHaveBeenCalledOnce();
    vi.useRealTimers();
  });
});

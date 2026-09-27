import type { KdsLabelPreview, KdsLabelTemplate, KdsLabelTestPreview, KdsLabelVolume } from "./api";

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeImageUrl(value?: string | null): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value, typeof window === "undefined" ? "https://localhost" : window.location.origin);
    return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : null;
  } catch {
    return null;
  }
}

function dimensions(template: KdsLabelTemplate) {
  const landscape = template.orientation === "landscape";
  return {
    width: landscape ? template.height_mm : template.width_mm,
    height: landscape ? template.width_mm : template.height_mm,
    margins: {
      top: Math.max(0, template.margin_top_mm),
      right: Math.max(0, template.margin_right_mm),
      bottom: Math.max(0, template.margin_bottom_mm),
      left: Math.max(0, template.margin_left_mm),
    },
  };
}

function volumeMarkup(preview: KdsLabelPreview, volume: KdsLabelVolume, printedAt: string) {
  const logo = preview.template.show_logo ? safeImageUrl(preview.restaurant.logo_url) : null;
  const flavorNames = (volume.flavors ?? []).map((flavor) => typeof flavor === "string" ? flavor : flavor.name);
  const details = [volume.selected_size, volume.selected_crust_type, volume.selected_drink_variant, ...flavorNames, ...(volume.add_ons ?? []).map((addOn) => `+ ${addOn}`)].filter(Boolean);
  return `<article class="label" aria-label="Volume ${volume.sequence} de ${volume.total_volumes}"><div class="label-inner">
    <section class="summary">
      <div class="caption">PEDIDO</div>
      <div class="order-number">${escapeHtml(preview.order.order_code ?? preview.order.id.slice(0, 8).toUpperCase())}</div>
      <div class="caption quantity-title">QUANTIDADE DE ITENS</div>
      <div class="quantity">${escapeHtml(volume.quantity)}</div>
      <div class="volume">${escapeHtml(volume.sequence)} DE ${escapeHtml(volume.total_volumes)}</div>
    </section>
    <section class="details">
      <header>${logo ? `<img src="${escapeHtml(logo)}" alt=""/>` : ""}<div class="store">${escapeHtml(preview.restaurant.name ?? "Expedição")}</div></header>
      <div class="product">${escapeHtml(volume.product_name)}</div>
      ${volume.product_description ? `<div class="description">${escapeHtml(volume.product_description)}</div>` : ""}
      ${details.length ? `<ul>${details.map((detail) => `<li>${escapeHtml(detail)}</li>`).join("")}</ul>` : ""}
      ${volume.notes ? `<div class="notes"><strong>OBS:</strong> ${escapeHtml(volume.notes)}</div>` : ""}
      <footer><span>${preview.order.customer_name ? escapeHtml(preview.order.customer_name) : "Cliente não informado"}</span>${preview.template.show_printed_at ? `<time>${escapeHtml(printedAt)}</time>` : ""}</footer>
    </section>
  </div></article>`;
}

export function buildLabelPrintHtml(preview: KdsLabelPreview): string {
  const { width, height, margins } = dimensions(preview.template);
  const copies = preview.volumes.length ? preview.volumes : [];
  const printedAt = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date());
  const scale = Math.max(0.5, Math.min(2, preview.template.scale_percent / 100));
  const fontScale = Math.max(0.5, Math.min(2, preview.template.font_scale_percent / 100));
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"/>
  <title>Etiquetas do pedido ${escapeHtml(preview.order.order_code ?? preview.order.id)}</title>
  <style>
    @page{size:${width}mm ${height}mm;margin:0}
    *{box-sizing:border-box}
    html,body{margin:0;padding:0;background:#fff;color:#000;font-family:Arial,sans-serif}
    .label{width:${width}mm;height:${height}mm;padding:${margins.top}mm ${margins.right}mm ${margins.bottom}mm ${margins.left}mm;overflow:hidden;page-break-after:always;break-after:page;background:#fff;color:#000}
    .label:last-child{page-break-after:auto;break-after:auto}
    .label-inner{width:100%;height:100%;display:grid;grid-template-columns:35% 65%;transform:translate(${preview.template.offset_x_mm}mm,${preview.template.offset_y_mm}mm) scale(${scale}) rotate(${preview.template.rotation}deg);transform-origin:center;font-size:${fontScale}em}
    .summary{min-width:0;padding:1mm 2mm 1mm 0;border-right:.45mm solid #000;display:flex;flex-direction:column;align-items:center;text-align:center}
    .caption{font-size:7pt;line-height:1;font-weight:900;letter-spacing:.15mm}
    .order-number{max-width:100%;font-size:30pt;line-height:.95;font-weight:900;overflow-wrap:anywhere;margin:1mm 0}
    .quantity-title{margin-top:auto;font-size:6.5pt}
    .quantity{font-size:17pt;line-height:1;font-weight:900}
    .volume{width:100%;margin-top:1mm;padding-top:1mm;border-top:.3mm solid #000;font-size:12pt;line-height:1;font-weight:900}
    .details{min-width:0;padding-left:2mm;display:flex;flex-direction:column;overflow:hidden}
    header{display:flex;align-items:center;gap:1.5mm;border-bottom:.3mm solid #000;padding-bottom:.8mm;min-height:6mm}
    header img{display:block;max-width:11mm;max-height:6mm;object-fit:contain;filter:grayscale(1) contrast(2)}
    .store{font-size:8pt;line-height:1;font-weight:900;overflow-wrap:anywhere}
    .product{font-size:11pt;line-height:1.05;font-weight:900;margin-top:1mm;overflow-wrap:anywhere;hyphens:auto}
    .description{font-size:7pt;line-height:1.05;margin-top:.6mm;overflow-wrap:anywhere}
    ul{font-size:7.5pt;line-height:1.1;margin:.8mm 0 0;padding-left:3.5mm;overflow-wrap:anywhere}
    .notes{margin-top:.8mm;border:.3mm solid #000;padding:.7mm;font-size:7.5pt;line-height:1.05;font-weight:700;overflow-wrap:anywhere}
    .details footer{display:flex;justify-content:space-between;gap:1mm;margin-top:auto;padding-top:.8mm;border-top:.3mm solid #000;font-size:6.5pt;line-height:1;font-weight:900}
    .details footer span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.details footer time{white-space:nowrap}
    @media print{html,body{width:${width}mm}.label{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  </style></head><body>${copies.map((volume) => volumeMarkup(preview, volume, printedAt)).join("")}</body></html>`;
}

export function buildLabelCalibrationHtml(preview: KdsLabelTestPreview): string {
  const width = preview.print_area.width_mm;
  const height = preview.print_area.height_mm;
  const margins = preview.print_area.margins_mm;
  const printedAt = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium" }).format(new Date(preview.content.generated_at));
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"/><title>Calibração de etiqueta</title><style>
  @page{size:${width}mm ${height}mm;margin:0}*{box-sizing:border-box}html,body{margin:0;padding:0;background:#fff;color:#000;font-family:Arial,sans-serif}
  .label{width:${width}mm;height:${height}mm;padding:${margins.top}mm ${margins.right}mm ${margins.bottom}mm ${margins.left}mm;display:grid;grid-template-columns:35% 65%;overflow:hidden}
  .number{border:.45mm solid #000;border-right:.45mm solid #000;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-weight:900}.number small{font-size:7pt}.number strong{font-size:30pt;line-height:1}.number span{font-size:9pt}
  .info{border:.45mm solid #000;border-left:0;padding:1.5mm;display:flex;flex-direction:column;overflow:hidden}.info h1{font-size:10pt;margin:0 0 1mm}.info p{font-size:7.5pt;line-height:1.15;margin:.4mm 0;overflow-wrap:anywhere}.sample{margin-top:1mm;border-top:.3mm solid #000;padding-top:1mm;font-size:8pt;font-weight:900}.info time{margin-top:auto;font-size:6.5pt;font-weight:700}
  @media print{html,body{width:${width}mm}.label{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  </style></head><body><article class="label"><section class="number"><small>TESTE</small><strong>${escapeHtml(preview.content.large_number)}</strong><span>NÚMERO GRANDE</span></section><section class="info"><h1>${escapeHtml(preview.printer.name)} · ${escapeHtml(preview.template.name)}</h1><p><b>Etiqueta:</b> ${width} × ${height} mm · ${escapeHtml(preview.template.orientation)}</p><p><b>DPI:</b> ${escapeHtml(preview.print_area.dpi)} · <b>Margens:</b> ${margins.top}/${margins.right}/${margins.bottom}/${margins.left} mm</p><p><b>Área segura:</b> ${escapeHtml(preview.print_area.safe_area_mm)} mm · <b>Offset:</b> ${escapeHtml(preview.print_area.offset_x_mm)} × ${escapeHtml(preview.print_area.offset_y_mm)} mm</p><div class="sample">${escapeHtml(preview.content.title)} — Pizza grande meia calabresa, meia mussarela + adicional</div><time>Impresso em ${escapeHtml(printedAt)}</time></section></article></body></html>`;
}

export interface LabelPrintTarget {
  document: { open?: () => void; write: (html: string) => void; close: () => void };
  focus: () => void;
  print: () => void;
  close?: () => void;
}

export function openLabelPrintWindow(): LabelPrintTarget | null {
  return window.open("", "_blank", "width=700,height=700,scrollbars=yes") as LabelPrintTarget | null;
}

export function renderAndPrintLabels(preview: KdsLabelPreview, target: LabelPrintTarget, onDialogOpened?: () => void): void {
  renderHtmlAndPrint(buildLabelPrintHtml(preview), target, onDialogOpened);
}

export function renderHtmlAndPrint(html: string, target: LabelPrintTarget, onDialogOpened?: () => void): void {
  target.document.open?.();
  target.document.write(html);
  target.document.close();
  target.focus();
  globalThis.setTimeout(() => { target.print(); onDialogOpened?.(); }, 0);
}

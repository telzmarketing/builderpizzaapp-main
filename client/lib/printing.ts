import type { ApiOrder } from "./api";

// ── Printer settings (persisted in localStorage) ──────────────────────────────

export type PaperWidth = "58mm" | "80mm" | "a4";
export type PrintTemplate = "completo" | "cozinha" | "etiqueta";

export interface PrinterSettings {
  paperWidth: PaperWidth;
  storeName: string;
  storePhone: string;
  storeAddress: string;
  storeCnpj: string;
  storeWebsite: string;
  defaultTemplate: PrintTemplate;
  autoPrint: boolean;
}

const STORAGE_KEY = "moschettieri_printer_settings";

export const DEFAULT_PRINTER_SETTINGS: PrinterSettings = {
  paperWidth: "80mm",
  storeName: "Moschettieri Pizzeria",
  storePhone: "",
  storeAddress: "",
  storeCnpj: "",
  storeWebsite: "delivery.moschettieri.com.br",
  defaultTemplate: "completo",
  autoPrint: false,
};

export function loadPrinterSettings(): PrinterSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PRINTER_SETTINGS };
    return { ...DEFAULT_PRINTER_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_PRINTER_SETTINGS };
  }
}

export function savePrinterSettings(s: PrinterSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function dt(v: string) {
  return new Date(v).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function orderNo(order: ApiOrder) {
  return order.id.slice(0, 8).toUpperCase();
}

function itemLines(order: ApiOrder) {
  return order.items.map((item) => {
    const isMulti = item.flavor_division > 1;
    const name = isMulti ? item.flavors.map((f) => f.name).join(" + ") : item.product_name;
    const details = [
      item.selected_size || null,
      item.selected_crust_type || null,
      item.selected_drink_variant || null,
    ].filter(Boolean).join(" · ");
    return { qty: item.quantity, name, details, addOns: item.add_ons ?? [], price: item.unit_price * item.quantity };
  });
}

// ── Paper width → CSS max-width ───────────────────────────────────────────────

function paperCss(width: PaperWidth) {
  if (width === "58mm") return "max-width:220px";
  if (width === "80mm") return "max-width:310px";
  return "max-width:600px";
}

// ── Base CSS ──────────────────────────────────────────────────────────────────

function baseCss() {
  return `
    body{font-family:'Courier New',Courier,monospace;font-size:12px;margin:0;padding:12px;color:#000}
    h1{font-size:14px;margin:0 0 2px;text-align:center}
    p{margin:2px 0}
    hr{border:none;border-top:1px dashed #555;margin:6px 0}
    table{width:100%;border-collapse:collapse}
    td{vertical-align:top;padding:2px 2px}
    .center{text-align:center}
    .right{text-align:right}
    .big{font-size:15px;font-weight:bold}
    .bold{font-weight:bold}
    .small{font-size:10px;color:#555}
    @media print{body{padding:0}button{display:none}}
  `;
}

// ── Template 1: Pedido Completo ───────────────────────────────────────────────

export function buildCompletoHtml(order: ApiOrder, settings: PrinterSettings): string {
  const items = itemLines(order);
  const rows = items.map((i) => `
    <tr>
      <td class="bold">${i.qty}x</td>
      <td style="width:100%">
        <span class="bold">${i.name}</span>
        ${i.details ? `<br/><span class="small">${i.details}</span>` : ""}
        ${i.addOns.map((a) => `<br/><span class="small">+ ${a}</span>`).join("")}
      </td>
      <td class="right" style="white-space:nowrap">${fmt(i.price)}</td>
    </tr>`).join("");

  const headerLines = [
    settings.storeName ? `<p class="center bold">${settings.storeName}</p>` : "",
    settings.storeWebsite ? `<p class="center small">${settings.storeWebsite}</p>` : "",
    settings.storeAddress ? `<p class="center small">${settings.storeAddress}</p>` : "",
    settings.storePhone ? `<p class="center small">${settings.storePhone}</p>` : "",
    settings.storeCnpj ? `<p class="center small">CNPJ: ${settings.storeCnpj}</p>` : "",
  ].filter(Boolean).join("");

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Pedido #${orderNo(order)}</title>
<style>${baseCss()}body{${paperCss(settings.paperWidth)}}</style>
</head><body>
${headerLines}
<hr/>
<p class="center bold">PEDIDO #${orderNo(order)}</p>
<p class="center small">${dt(order.created_at)}</p>
<hr/>
<p class="bold">${order.delivery_name}</p>
<p>${order.delivery_phone}</p>
<p>${order.delivery_street}${order.delivery_complement ? ` — ${order.delivery_complement}` : ""}</p>
<p>${order.delivery_city}</p>
<hr/>
<table>${rows}</table>
<hr/>
${order.shipping_fee > 0 ? `<p class="right">Frete: ${fmt(order.shipping_fee)}</p>` : ""}
${order.discount > 0 ? `<p class="right">Desconto: -${fmt(order.discount)}</p>` : ""}
<p class="right big">TOTAL: ${fmt(order.total)}</p>
<hr/>
<p>Entrega estimada: <span class="bold">${order.estimated_time} min</span></p>
<hr/>
<p class="center small">Obrigado pela preferência!</p>
</body></html>`;
}

// ── Template 2: Comanda Cozinha ───────────────────────────────────────────────

export function buildCozinhaHtml(order: ApiOrder, settings: PrinterSettings): string {
  const items = itemLines(order);
  const rows = items.map((i) => `
    <tr>
      <td style="font-size:15px;font-weight:bold;padding:4px 2px">${i.qty}x</td>
      <td style="width:100%;padding:4px 2px">
        <div style="font-size:14px;font-weight:bold;text-transform:uppercase">${i.name}</div>
        ${i.details ? `<div class="small">${i.details}</div>` : ""}
        ${i.addOns.map((a) => `<div class="small">+ ${a}</div>`).join("")}
      </td>
    </tr>
    <tr><td colspan="2"><hr/></td></tr>`).join("");

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Comanda #${orderNo(order)}</title>
<style>${baseCss()}body{${paperCss(settings.paperWidth)}}</style>
</head><body>
<p class="center" style="font-size:11px;font-weight:bold;letter-spacing:2px">*** COMANDA COZINHA ***</p>
<p class="center bold" style="font-size:16px">PEDIDO #${orderNo(order)}</p>
<p class="center small">${new Date(order.created_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</p>
<hr/>
<table>${rows}</table>
<p class="bold">${order.delivery_name}</p>
<p class="small">Entrega: ${order.estimated_time} min</p>
</body></html>`;
}

// ── Template 3: Etiqueta de Entrega ───────────────────────────────────────────

export function buildEtiquetaHtml(order: ApiOrder, settings: PrinterSettings): string {
  const items = itemLines(order);
  const resumo = items.slice(0, 3).map((i) => `${i.qty}x ${i.name}`).join(", ");
  const mais = items.length > 3 ? ` +${items.length - 3} itens` : "";

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Etiqueta #${orderNo(order)}</title>
<style>${baseCss()}body{${paperCss(settings.paperWidth)}}
  .box{border:2px solid #000;padding:6px;margin-bottom:4px}
  .destaque{font-size:18px;font-weight:bold;text-align:center;letter-spacing:1px}
</style>
</head><body>
<div class="box">
  <p class="small center">${settings.storeName}</p>
  <hr/>
  <p class="destaque">#${orderNo(order)}</p>
  <p class="center small">${dt(order.created_at)}</p>
</div>
<div class="box">
  <p class="bold" style="font-size:14px">${order.delivery_name}</p>
  <p>${order.delivery_phone}</p>
  <hr/>
  <p class="bold">${order.delivery_street}</p>
  ${order.delivery_complement ? `<p>${order.delivery_complement}</p>` : ""}
  <p>${order.delivery_city}</p>
</div>
<div class="box">
  <p class="small">${resumo}${mais}</p>
  <hr/>
  <p class="right bold" style="font-size:15px">TOTAL: ${fmt(order.total)}</p>
  <p class="right small">Entrega: ${order.estimated_time} min</p>
</div>
</body></html>`;
}

// ── Dispatch ──────────────────────────────────────────────────────────────────

export function printOrder(order: ApiOrder, template?: PrintTemplate): void {
  const settings = loadPrinterSettings();
  const tpl = template ?? settings.defaultTemplate;

  let html: string;
  if (tpl === "cozinha") html = buildCozinhaHtml(order, settings);
  else if (tpl === "etiqueta") html = buildEtiquetaHtml(order, settings);
  else html = buildCompletoHtml(order, settings);

  const w = window.open("", "_blank", "width=440,height=700,scrollbars=yes");
  if (!w) { alert("Habilite pop-ups para imprimir."); return; }
  w.document.write(html);
  w.document.close();
  w.onload = () => { w.focus(); if (settings.autoPrint) w.print(); };
}

// ── Sample order for preview ──────────────────────────────────────────────────

export const SAMPLE_ORDER: ApiOrder = {
  id: "abc12345-0000-0000-0000-000000000000",
  customer_id: null,
  delivery_name: "João Silva",
  delivery_phone: "(11) 99999-9999",
  delivery_street: "Rua das Flores, 123",
  delivery_city: "São Paulo/SP",
  delivery_complement: "Apto 21",
  status: "preparing",
  subtotal: 89.90,
  shipping_fee: 5.00,
  discount: 5.00,
  total: 89.90,
  estimated_time: 45,
  loyalty_points_earned: 0,
  coupon_id: null,
  items: [
    {
      id: "i1", product_id: "p1", product_name: "Pizza Pepperoni",
      quantity: 1, selected_size: "Grande", selected_size_id: null,
      flavor_division: 1, selected_crust_type: "Tradicional",
      selected_crust_type_id: null, selected_drink_variant: null,
      notes: null, flavors: [{ product_id: "p1", name: "Pepperoni", price: 79.90, icon: "🍕" }],
      add_ons: [], unit_price: 79.90, final_price: 79.90,
    },
    {
      id: "i2", product_id: "p2", product_name: "Coca-Cola",
      quantity: 2, selected_size: "600ml", selected_size_id: null,
      flavor_division: 1, selected_crust_type: null, selected_crust_type_id: null,
      selected_drink_variant: "Normal", notes: null,
      flavors: [{ product_id: "p2", name: "Coca-Cola", price: 10.00, icon: "🥤" }],
      add_ons: [], unit_price: 10.00, final_price: 10.00,
    },
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

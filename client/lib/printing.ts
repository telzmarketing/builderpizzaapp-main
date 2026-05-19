import type { ApiOrder } from "./api";

// ── Printer settings (persisted in localStorage) ──────────────────────────────

export type PaperWidth = "58mm" | "80mm" | "a4";
export type PrintTemplate = "completo" | "cozinha" | "entrega";

export interface PrinterSettings {
  paperWidth: PaperWidth;
  storeName: string;
  storePhone: string;
  storeAddress: string;
  storeCnpj: string;
  storeWebsite: string;
  defaultTemplate: PrintTemplate;
  autoPrint: boolean;
  autoPrintConfirmedOrders: boolean;
}

const STORAGE_KEY = "moschettieri_printer_settings";

export const DEFAULT_PRINTER_SETTINGS: PrinterSettings = {
  paperWidth: "80mm",
  storeName: "Moschettieri Pizzeria",
  storePhone: "",
  storeAddress: "",
  storeCnpj: "",
  storeWebsite: "delivery.moschettieri.com.br",
  defaultTemplate: "completo" as PrintTemplate,
  autoPrint: false,
  autoPrintConfirmedOrders: true,
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
  return v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function orderNum(order: ApiOrder) {
  return order.order_code ? `#${order.order_code}` : `#${order.id.slice(0, 8).toUpperCase()}`;
}

function shortDate(d: Date) {
  const day = String(d.getDate()).padStart(2, "0");
  const months = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  return `${day}/${months[d.getMonth()]}`;
}

function hhmm(d: Date) {
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function estDeliveryTime(order: ApiOrder) {
  const base = new Date(order.created_at);
  const ms = base.getTime() + order.estimated_time * 60 * 1000;
  return hhmm(new Date(ms));
}

function maskCustomerName(name?: string | null) {
  const firstName = (name || "Cliente").trim().split(/\s+/)[0] || "Cliente";
  return `${firstName} ********`;
}

// ── Paper width → CSS max-width ───────────────────────────────────────────────

function paperCss(width: PaperWidth) {
  const size = {
    "58mm": {
      page: "58mm auto",
      body: "54mm",
      padding: "1.5mm",
      font: "10px",
      small: "9.5px",
      qty: "5mm",
      price: "15mm",
    },
    "80mm": {
      page: "80mm auto",
      body: "76mm",
      padding: "2mm",
      font: "11px",
      small: "10.5px",
      qty: "6mm",
      price: "18mm",
    },
    a4: {
      page: "A4 portrait",
      body: "190mm",
      padding: "8mm",
      font: "12px",
      small: "11px",
      qty: "12mm",
      price: "24mm",
    },
  }[width];

  return `
    @page{size:${size.page};margin:0}
    html{margin:0;padding:0;width:${size.body}}
    body{
      --qty-col:${size.qty};
      --price-col:${size.price};
      --receipt-small:${size.small};
      box-sizing:border-box;
      width:${size.body};
      max-width:${size.body};
      margin:0 auto;
      padding:${size.padding};
      font-size:${size.font};
    }
    @media print{
      html,body{width:${size.body};max-width:${size.body}}
      body{margin:0;padding:${size.padding}}
    }
  `;
}

// ── Base CSS ──────────────────────────────────────────────────────────────────

function baseCss() {
  return `
    *,*::before,*::after{box-sizing:border-box}
    body{font-family:'Courier New',Courier,monospace;line-height:1.25;color:#000}
    p{margin:2px 0}
    hr{border:none;border-top:1px dashed #555;margin:6px 0}
    table{width:100%;max-width:100%;border-collapse:collapse;table-layout:fixed}
    td{vertical-align:top;padding:1px 1px;overflow-wrap:anywhere;word-break:break-word}
    .qty{width:var(--qty-col);white-space:nowrap}
    .price{width:var(--price-col);white-space:nowrap;text-align:right}
    .desc{width:auto}
    .totals td:last-child{width:var(--price-col);white-space:nowrap;text-align:right}
    .c{text-align:center}
    .r{text-align:right}
    .b{font-weight:bold}
    .s{font-size:var(--receipt-small);color:#000;font-weight:600}
    @media print{
      *{color:#000!important;text-shadow:none!important}
      body{-webkit-print-color-adjust:exact;print-color-adjust:exact}
      hr{border-top-color:#000}
      button{display:none}
    }
  `;
}

// ── Kitchen/Delivery legacy item lines ────────────────────────────────────────

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

// ── Template 1: Pedido Completo (Saipos style) ────────────────────────────────

export function buildCompletoHtml(order: ApiOrder, settings: PrinterSettings): string {
  const num = orderNum(order);
  const created = new Date(order.created_at);

  // Store header
  const headerParts = [
    settings.storeName ? `<p class="c b" style="font-size:13px">${settings.storeName}</p>` : "",
    settings.storeCnpj ? `<p class="c s">CNPJ: ${settings.storeCnpj}</p>` : "",
    settings.storeAddress ? `<p class="c s">${settings.storeAddress}</p>` : "",
    settings.storePhone ? `<p class="c s">${settings.storePhone}</p>` : "",
  ].filter(Boolean).join("");

  // Items rows (Saipos style with sub-lines)
  const itemRows = order.items.map((item) => {
    const isMulti = item.flavor_division > 1;
    const sizePart = item.selected_size ? ` (${item.selected_size})` : "";
    const flavorPart = isMulti ? ` até ${item.flavor_division} Sabores` : "";
    const mainName = `${item.product_name}${sizePart}${flavorPart}`;

    const subLines: string[] = [];
    if (item.selected_crust_type) {
      subLines.push(`-${item.quantity}x Massa ${item.selected_crust_type}`);
    }
    if (isMulti) {
      item.flavors.forEach((f) => subLines.push(`-${item.quantity}x 1/${item.flavor_division} ${f.name}`));
    } else if (item.flavors.length === 1 && item.flavors[0].name !== item.product_name) {
      subLines.push(`-${item.quantity}x ${item.flavors[0].name}`);
    }
    if (item.selected_drink_variant) {
      subLines.push(`-${item.quantity}x ${item.selected_drink_variant}`);
    }
    (item.add_ons ?? []).forEach((a) => subLines.push(`+ ${a}`));

    const subHtml = subLines.map((l) => `<br/><span class="s">${l}</span>`).join("");

    return `<tr>
      <td class="qty" style="padding-top:2px">${item.quantity}</td>
      <td class="desc"><span class="b">${mainName}</span>${subHtml}</td>
      <td class="price" style="padding-top:2px">${fmt(item.unit_price * item.quantity)}</td>
    </tr>`;
  }).join("");

  const totalQty = order.items.reduce((s, i) => s + i.quantity, 0);

  // Financial rows
  const finRows = [
    `<tr><td>Total itens(=)</td><td class="r">${fmt(order.subtotal)}</td></tr>`,
    order.shipping_fee > 0 ? `<tr><td>Taxa de entrega(+)</td><td class="r">${fmt(order.shipping_fee)}</td></tr>` : "",
    order.discount > 0 ? `<tr><td>Desconto(-)</td><td class="r">-${fmt(order.discount)}</td></tr>` : "",
    `<tr><td class="b" style="font-size:13px;padding-top:4px">TOTAL(=)</td><td class="b r" style="font-size:13px;padding-top:4px">${fmt(order.total)}</td></tr>`,
  ].filter(Boolean).join("");

  // Delivery person
  const motoboy = order.delivery?.delivery_person_name;
  const deliveryLine = motoboy
    ? `<p class="s">Entrega: ${motoboy}</p>`
    : `<p class="s">Entrega pela loja</p>`;

  // Address
  const addrLine = `${order.delivery_street}${order.delivery_complement ? `, ${order.delivery_complement}` : ""}`;
  const refLine = order.delivery_complement ? `<p class="s">Ref: ${order.delivery_complement}</p>` : "";

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Pedido ${num}</title>
<style>${baseCss()}${paperCss(settings.paperWidth)}</style>
</head><body>

${headerParts}
${headerParts ? "<hr/>" : ""}

<table><tr>
  <td class="b" style="font-size:15px;letter-spacing:2px">ENTREGA</td>
  <td class="r s">${shortDate(created)} — ${hhmm(created)}</td>
</tr></table>

<hr/>
<p><span class="s">Pedido: </span><span class="b" style="font-size:14px">${num}</span></p>
<p class="b">${order.delivery_name}</p>
<p class="s">Telefone: ${order.delivery_phone} | ID: ${order.id.slice(0, 8).toUpperCase()}</p>

<hr/>
<p>${addrLine}</p>
<p>${order.delivery_city}</p>
${refLine}

<hr/>
<p class="s">Entrega para as <span class="b">${estDeliveryTime(order)}</span></p>
${deliveryLine}

<hr/>
<table>
  <tr>
    <td class="b s qty">Qt.</td>
    <td class="b s">Descrição</td>
    <td class="b s price">Valor</td>
  </tr>
</table>
<hr/>
<table>${itemRows}</table>
<hr/>

<table>
  <tr>
    <td class="s">Quantidade de itens:</td>
    <td class="s r">${totalQty}</td>
  </tr>
</table>
<hr/>

<table class="totals">${finRows}</table>
<hr/>

<p class="c s">Obrigado pela preferência!</p>
${settings.storeWebsite ? `<p class="c s">${settings.storeWebsite}</p>` : ""}

</body></html>`;
}

// ── Template 2: Comanda Cozinha ───────────────────────────────────────────────

export function buildCozinhaHtml(order: ApiOrder, settings: PrinterSettings): string {
  const num = orderNum(order);
  const items = itemLines(order);
  const rows = items.map((i) => `
    <tr>
      <td class="qty" style="font-size:15px;font-weight:bold;padding:4px 2px">${i.qty}x</td>
      <td class="desc" style="padding:4px 2px">
        <div style="font-size:14px;font-weight:bold;text-transform:uppercase">${i.name}</div>
        ${i.details ? `<div class="s">${i.details}</div>` : ""}
        ${i.addOns.map((a) => `<div class="s">+ ${a}</div>`).join("")}
      </td>
    </tr>
    <tr><td colspan="2"><hr/></td></tr>`).join("");

  const created = new Date(order.created_at);

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Comanda ${num}</title>
<style>${baseCss()}${paperCss(settings.paperWidth)}</style>
</head><body>
<p class="c" style="font-size:11px;font-weight:bold;letter-spacing:2px">*** COMANDA COZINHA ***</p>
<p class="c b" style="font-size:16px">PEDIDO ${num}</p>
<p class="c s">${hhmm(created)}</p>
<hr/>
<table>${rows}</table>
<p class="b">${order.delivery_name}</p>
<p class="s">Entrega: ${order.estimated_time} min</p>
</body></html>`;
}

// ── Template 3: Via Entrega ────────────────────────────────────────────────────

export function buildEntregaHtml(order: ApiOrder, settings: PrinterSettings): string {
  const num = orderNum(order);
  const items = itemLines(order);
  const rows = items.map((i) => `
    <tr>
      <td class="b qty">${i.qty}x</td>
      <td class="desc">
        <span class="b">${i.name}</span>
        ${i.details ? `<br/><span class="s">${i.details}</span>` : ""}
        ${i.addOns.map((a) => `<br/><span class="s">+ ${a}</span>`).join("")}
      </td>
      <td class="price">${fmt(i.price)}</td>
    </tr>`).join("");

  const created = new Date(order.created_at);
  const addrLine = `${order.delivery_street}${order.delivery_complement ? `, ${order.delivery_complement}` : ""}`;

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Entrega ${num}</title>
<style>${baseCss()}${paperCss(settings.paperWidth)}</style>
</head><body>
<p class="c" style="font-size:11px;font-weight:bold;letter-spacing:2px">*** VIA ENTREGA ***</p>
<p class="c b" style="font-size:16px">PEDIDO ${num}</p>
<p class="c s">${shortDate(created)} — ${hhmm(created)}</p>
<hr/>
<p class="b" style="font-size:13px">ENDEREÇO DE ENTREGA</p>
<p class="b">${maskCustomerName(order.delivery_name)}</p>
<p>${addrLine}</p>
<p>${order.delivery_city}</p>
<hr/>
<p class="b s">ITENS DO PEDIDO</p>
<table>${rows}</table>
<hr/>
${order.shipping_fee > 0 ? `<p class="r">Taxa de entrega: ${fmt(order.shipping_fee)}</p>` : ""}
${order.discount > 0 ? `<p class="r">Desconto: -${fmt(order.discount)}</p>` : ""}
<p class="r b" style="font-size:13px">TOTAL: R$ ${fmt(order.total)}</p>
</body></html>`;
}

// ── Dispatch ──────────────────────────────────────────────────────────────────

export function buildPrintHtml(order: ApiOrder, template: PrintTemplate, settings: PrinterSettings): string {
  let html: string;
  const tpl = template;
  if (tpl === "cozinha") html = buildCozinhaHtml(order, settings);
  else if (tpl === "entrega") html = buildEntregaHtml(order, settings);
  else html = buildCompletoHtml(order, settings);
  return html;
}

function openPrintWindow(html: string, shouldPrint: boolean, printDelayMs = 0): boolean {
  const w = window.open("", "_blank", "width=440,height=700,scrollbars=yes");
  if (!w) return false;
  w.document.write(html);
  w.document.close();
  w.onload = () => {
    w.focus();
    if (shouldPrint) window.setTimeout(() => w.print(), printDelayMs);
  };
  return true;
}

export function printOrder(order: ApiOrder, template?: PrintTemplate): void {
  const settings = loadPrinterSettings();
  const tpl = template ?? settings.defaultTemplate;
  const opened = openPrintWindow(buildPrintHtml(order, tpl, settings), settings.autoPrint);
  if (!opened) alert("Habilite pop-ups para imprimir.");
}

export function printConfirmedOrder(order: ApiOrder): boolean {
  const settings = loadPrinterSettings();
  if (!settings.autoPrintConfirmedOrders) return true;

  const templates: PrintTemplate[] = ["cozinha", "completo"];
  const results = templates.map((tpl, index) => {
    const html = buildPrintHtml(order, tpl, settings);
    return openPrintWindow(html, true, index * 600);
  });

  return results.every(Boolean);
}

// ── Sample order for preview ──────────────────────────────────────────────────

export const SAMPLE_ORDER: ApiOrder = {
  id: "abc12345-0000-0000-0000-000000000000",
  order_code: "4",
  customer_id: null,
  delivery_name: "Nicholas",
  delivery_phone: "(11) 98765-4321",
  delivery_street: "R. Vicente Ferreira Leite, 133",
  delivery_city: "São Paulo — Vila Siqueira (Zona Norte)",
  delivery_complement: "ap 9",
  status: "preparing",
  subtotal: 87.40,
  shipping_fee: 11.99,
  discount: 9.90,
  total: 89.49,
  estimated_time: 48,
  loyalty_points_earned: 0,
  coupon_id: null,
  paid_at: null,
  preparation_started_at: null,
  out_for_delivery_at: null,
  delivered_at: null,
  target_delivery_minutes: 48,
  total_time_minutes: null,
  preparation_time_minutes: null,
  delivery_time_minutes: null,
  items: [
    {
      id: "i1", product_id: "p1", product_name: "Pizza Grande Salgada",
      quantity: 1, selected_size: "Grande (8 Pedaços)", selected_size_id: null,
      flavor_division: 2, selected_crust_type: "Massa Tradicional",
      selected_crust_type_id: null, selected_drink_variant: null,
      notes: null,
      flavors: [
        { product_id: "p1", name: "Bacon", price: 43.70, icon: "🍕" },
        { product_id: "p2", name: "Castelões", price: 43.70, icon: "🍕" },
      ],
      add_ons: [], unit_price: 87.40, final_price: 87.40,
    },
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

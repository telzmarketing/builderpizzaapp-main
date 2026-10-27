import { orderDisplayCode } from "@/lib/orderIdentity";
import { operationalPaymentHtml } from "./operationalPayment";
import { siteConfigApi, type ApiOrder } from "./api";
import { isOperationalDrink, operationalDrinks } from "./operationalDrinks";
import { storeBranding } from "./storeBranding";
import { readPlatformSupportSession } from "./platformSupportSession";

// ── Printer settings (persisted in localStorage) ──────────────────────────────

export type PaperWidth = "58mm" | "80mm" | "a4";
export type PrintTemplate = "completo" | "cozinha" | "entrega";

export interface PrinterSettings {
  storeLogoUrl?: string;
  paperWidth: PaperWidth;
  storeName: string;
  storePhone: string;
  storeAddress: string;
  storeCnpj: string;
  storeWebsite: string;
  logoUrl?: string;
  defaultTemplate: PrintTemplate;
  autoPrint: boolean;
  autoPrintConfirmedOrders: boolean;
}

const STORAGE_KEY = "moschettieri_printer_settings";
const scopedStorageKey = () => {
  const tenant = readPlatformSupportSession()?.tenant_id;
  return `${STORAGE_KEY}:${window.location.hostname}${tenant ? `:${tenant}` : ""}`;
};

export const DEFAULT_PRINTER_SETTINGS: PrinterSettings = {
  paperWidth: "80mm",
  storeName: "Sua Loja",
  storePhone: "",
  storeAddress: "",
  storeCnpj: "",
  storeWebsite: "",
  logoUrl: "/api/site-config/favicon?size=192",
  defaultTemplate: "completo" as PrintTemplate,
  autoPrint: false,
  autoPrintConfirmedOrders: true,
};

export function loadPrinterSettings(): PrinterSettings {
  try {
    const raw = localStorage.getItem(scopedStorageKey());
    if (!raw) {
      // Migrate device behavior, never another establishment's identity.
      const old = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (!old) return { ...DEFAULT_PRINTER_SETTINGS };
      return { ...DEFAULT_PRINTER_SETTINGS, paperWidth: old.paperWidth ?? DEFAULT_PRINTER_SETTINGS.paperWidth, defaultTemplate: old.defaultTemplate ?? DEFAULT_PRINTER_SETTINGS.defaultTemplate, autoPrint: old.autoPrint ?? false, autoPrintConfirmedOrders: old.autoPrintConfirmedOrders ?? true };
    }
    return { ...DEFAULT_PRINTER_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_PRINTER_SETTINGS };
  }
}

export function savePrinterSettings(s: PrinterSettings): void {
  localStorage.setItem(scopedStorageKey(), JSON.stringify(s));
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number) {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function escapeText(value: unknown) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!);
}

export function withReceiptBranding(settings: PrinterSettings, content: Record<string, unknown>): PrinterSettings {
  const brand = (content.brand || {}) as Record<string, unknown>;
  const identity = storeBranding(content);
  return { ...settings, storeName: typeof brand.name === "string" && brand.name.trim() ? identity.name : settings.storeName, storeLogoUrl: identity.logo || undefined };
}

function storeHeader(settings: PrinterSettings) {
  const logo = settings.storeLogoUrl || "";
  const safeLogo = /^(https?:\/\/|\/(?!\/)|data:image\/(?:png|jpeg|gif|webp|svg\+xml)[;,])/i.test(logo);
  return `${safeLogo ? `<img class="receipt-logo" src="${escapeText(logo)}" alt="${escapeText(settings.storeName)}"/>` : ""}<p class="c b" style="font-size:13px">${escapeText(settings.storeName)}</p>`;
}

function drinksBlock(order: ApiOrder) {
  const drinks = operationalDrinks(order);
  if (!drinks.length) return "";
  return `<section class="drinks"><p class="b">ATENÇÃO — BEBIDAS</p>${drinks.map((drink) => `<p class="b">${drink.quantity} × ${escapeText(drink.name)}</p>${drink.notes ? `<p class="s">Obs.: ${escapeText(drink.notes)}</p>` : ""}`).join("")}</section>`;
}

function operationalHeader(order: ApiOrder) {
  const origins: Record<string, string> = { counter: "Balcão", delivery: "Loja virtual", pickup: "Retirada", dine_in: "Salão", ifood: "iFood", "99food": "99Food", keeta: "Keeta" };
  const mode = order.fulfillment_type === "pickup" ? "Retirada" : order.fulfillment_type === "dine_in" ? "Consumo no local" : "Entrega";
  return `<p class="s">Origem: ${escapeText(origins[order.sales_channel || ""] || order.sales_channel || "Não informada")}</p><p class="s">Modalidade: ${mode}</p>`;
}

function dispatchChecklist(order: ApiOrder) {
  return `<section class="dispatch-check"><p class="b">CONFERÊNCIA DA EXPEDIÇÃO</p><p>[ ] Produtos conferidos</p>${operationalDrinks(order).length ? "<p>[ ] Bebidas conferidas</p>" : ""}<p>[ ] Embalagens e lacres conferidos</p></section>`;
}

function orderNum(order: ApiOrder) {
  return `#${orderDisplayCode(order)}`;
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
    .receipt-logo{display:block;max-width:75%;max-height:24mm;width:auto;height:auto;object-fit:contain;margin:0 auto 3mm;filter:grayscale(1) contrast(1.6)}
    .drinks{background:#eee;border:2px solid #000;padding:2mm;margin:3mm 0;break-inside:avoid}
    .dispatch-check{border-top:1px dashed #000;margin-top:3mm;padding-top:2mm;break-inside:avoid}
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
  return order.items.filter((item) => !isOperationalDrink(item)).map((item) => {
    const isMulti = item.flavor_division > 1;
    const name = isMulti ? item.flavors.map((f) => f.name).join(" + ") : item.product_name;
    const details = [
      item.selected_size || null,
      item.selected_crust_type || null,
      item.selected_drink_variant || null,
    ].filter(Boolean).join(" · ");
    return { qty: item.quantity, name: escapeText(name), details: escapeText(details), notes: escapeText(item.notes), addOns: (item.add_ons ?? []).map(escapeText), price: item.unit_price * item.quantity };
  });
}

// ── Template 1: Pedido Completo ───────────────────────────────────────────────

export function buildCompletoHtml(order: ApiOrder, settings: PrinterSettings): string {
  const num = escapeText(orderNum(order));
  const created = new Date(order.created_at);

  // Store header
  const headerParts = [
    storeHeader(settings),
    settings.storeCnpj ? `<p class="c s">CNPJ: ${escapeText(settings.storeCnpj)}</p>` : "",
    settings.storeAddress ? `<p class="c s">${escapeText(settings.storeAddress)}</p>` : "",
    settings.storePhone ? `<p class="c s">${escapeText(settings.storePhone)}</p>` : "",
  ].filter(Boolean).join("");

  // Items rows with sub-lines
  const itemRows = order.items.filter((item) => !isOperationalDrink(item)).map((item) => {
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

    if (item.notes) subLines.push(`Obs.: ${item.notes}`);
    const subHtml = subLines.map((l) => `<br/><span class="s">${escapeText(l)}</span>`).join("");

    return `<tr>
      <td class="qty" style="padding-top:2px">${item.quantity}</td>
      <td class="desc"><span class="b">${escapeText(mainName)}</span>${subHtml}</td>
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
  const deliveryLine = order.fulfillment_type === "pickup" ? `<p class="s">Retirada no balcão</p>` : order.fulfillment_type === "dine_in" ? `<p class="s">Consumo no local</p>` : motoboy
    ? `<p class="s">Entrega: ${escapeText(motoboy)}</p>`
    : `<p class="s">Entrega pela loja</p>`;

  // Address
  const addrLine = escapeText(`${order.delivery_street}${order.delivery_complement ? `, ${order.delivery_complement}` : ""}`);
  const refLine = order.delivery_complement ? `<p class="s">Ref: ${escapeText(order.delivery_complement)}</p>` : "";

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Pedido ${num}</title>
<style>${baseCss()}${paperCss(settings.paperWidth)}</style>
</head><body>

${headerParts}
${headerParts ? "<hr/>" : ""}

<table><tr>
  <td class="b" style="font-size:15px;letter-spacing:2px">PEDIDO</td>
  <td class="r s">${shortDate(created)} — ${hhmm(created)}</td>
</tr></table>

<hr/>
<p><span class="s">Pedido: </span><span class="b" style="font-size:14px">${num}</span></p>
${operationalHeader(order)}
<p class="b">${escapeText(order.delivery_name)}</p>
<p class="s">Telefone: ${escapeText(order.delivery_phone)} | ID: ${escapeText(order.id.slice(0, 8).toUpperCase())}</p>

<hr/>
<p>${addrLine}</p>
<p>${escapeText(order.delivery_city)}</p>
${refLine}

<hr/>
<p class="s">Previsão: <span class="b">${estDeliveryTime(order)}</span></p>
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
${drinksBlock(order)}
<hr/>

<table>
  <tr>
    <td class="s">Quantidade de itens:</td>
    <td class="s r">${totalQty}</td>
  </tr>
</table>
<hr/>

<table class="totals">${finRows}</table>
${operationalPaymentHtml(order)}
${dispatchChecklist(order)}
<hr/>

<p class="c s">Obrigado pela preferência!</p>
${settings.storeWebsite ? `<p class="c s">${escapeText(settings.storeWebsite)}</p>` : ""}

</body></html>`;
}

// ── Template 2: Comanda Cozinha ───────────────────────────────────────────────

export function buildCozinhaHtml(order: ApiOrder, settings: PrinterSettings): string {
  const num = escapeText(orderNum(order));
  const items = itemLines(order);
  const rows = items.map((i) => `
    <tr>
      <td class="qty" style="font-size:15px;font-weight:bold;padding:4px 2px">${i.qty}x</td>
      <td class="desc" style="padding:4px 2px">
        <div style="font-size:14px;font-weight:bold;text-transform:uppercase">${i.name}</div>
        ${i.details ? `<div class="s">${i.details}</div>` : ""}
        ${i.addOns.map((a) => `<div class="s">+ ${a}</div>`).join("")}
        ${i.notes ? `<div class="s b">Obs.: ${i.notes}</div>` : ""}
      </td>
    </tr>
    <tr><td colspan="2"><hr/></td></tr>`).join("");

  const created = new Date(order.created_at);

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Comanda ${num}</title>
<style>${baseCss()}${paperCss(settings.paperWidth)}</style>
</head><body>
${storeHeader(settings)}
<p class="c" style="font-size:11px;font-weight:bold;letter-spacing:2px">*** COMANDA COZINHA ***</p>
<p class="c b" style="font-size:16px">PEDIDO ${num}</p>
<p class="c s">${hhmm(created)}</p>
${operationalHeader(order)}
<hr/>
<table>${rows}</table>
${drinksBlock(order)}
<p class="b">${escapeText(order.delivery_name)}</p>
<p class="s">Entrega: ${order.estimated_time} min</p>
${operationalPaymentHtml(order)}
</body></html>`;
}

// ── Template 3: Via Entrega ────────────────────────────────────────────────────

export function buildEntregaHtml(order: ApiOrder, settings: PrinterSettings): string {
  const num = escapeText(orderNum(order));
  const items = itemLines(order);
  const rows = items.map((i) => `
    <tr>
      <td class="b qty">${i.qty}x</td>
      <td class="desc">
        <span class="b">${i.name}</span>
        ${i.details ? `<br/><span class="s">${i.details}</span>` : ""}
        ${i.addOns.map((a) => `<br/><span class="s">+ ${a}</span>`).join("")}
        ${i.notes ? `<br/><span class="s b">Obs.: ${i.notes}</span>` : ""}
      </td>
      <td class="price">${fmt(i.price)}</td>
    </tr>`).join("");

  const created = new Date(order.created_at);
  const addrLine = escapeText(`${order.delivery_street}${order.delivery_complement ? `, ${order.delivery_complement}` : ""}`);

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Entrega ${num}</title>
<style>${baseCss()}${paperCss(settings.paperWidth)}</style>
</head><body>
${storeHeader(settings)}
<p class="c" style="font-size:11px;font-weight:bold;letter-spacing:2px">*** VIA ENTREGA ***</p>
<p class="c b" style="font-size:16px">PEDIDO ${num}</p>
<p class="c s">${shortDate(created)} — ${hhmm(created)}</p>
${operationalHeader(order)}
<hr/>
<p class="b" style="font-size:13px">${order.fulfillment_type === "pickup" ? "RETIRADA NO BALCÃO" : order.fulfillment_type === "dine_in" ? "CONSUMO NO LOCAL" : "ENDEREÇO DE ENTREGA"}</p>
<p class="b">${escapeText(maskCustomerName(order.delivery_name))}</p>
<p>${addrLine}</p>
<p>${escapeText(order.delivery_city)}</p>
<hr/>
<p class="b s">ITENS DO PEDIDO</p>
<table>${rows}</table>
${drinksBlock(order)}
<hr/>
${order.shipping_fee > 0 ? `<p class="r">Taxa de entrega: ${fmt(order.shipping_fee)}</p>` : ""}
${order.discount > 0 ? `<p class="r">Desconto: -${fmt(order.discount)}</p>` : ""}
<p class="r b" style="font-size:13px">TOTAL: R$ ${fmt(order.total)}</p>
${operationalPaymentHtml(order)}
${dispatchChecklist(order)}
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

function writeReceiptWindow(w: Window, html: string, shouldPrint: boolean, printDelayMs = 0) {
  w.document.open();
  w.document.write(html);
  w.document.close();
  const images = Array.from(w.document.images);
  const ready = Promise.all(images.map((image) => image.complete ? Promise.resolve() : new Promise<void>((resolve) => { image.onload = () => resolve(); image.onerror = () => resolve(); })));
  void Promise.race([ready, new Promise<void>((resolve) => window.setTimeout(resolve, 4000))]).then(() => {
    // A missing/blocked logo leaves the textual company name legible.
    images.filter((image) => !image.complete || image.naturalWidth === 0).forEach((image) => { image.hidden = true; });
    w.focus();
    if (shouldPrint) window.setTimeout(() => w.print(), printDelayMs);
  });
}

export function openReceiptPreview(html: string, shouldPrint = false): boolean {
  const w = window.open("", "_blank", "width=440,height=700,scrollbars=yes");
  if (!w) return false;
  writeReceiptWindow(w, html, shouldPrint);
  return true;
}

async function currentReceiptSettings(settings: PrinterSettings) {
  try {
    return await Promise.race([
      siteConfigApi.getAdmin().then((content) => withReceiptBranding(settings, content)),
      new Promise<PrinterSettings>((resolve) => window.setTimeout(() => resolve(settings), 2500)),
    ]);
  }
  catch { return settings; }
}

export function printOrder(order: ApiOrder, template?: PrintTemplate): boolean {
  const settings = loadPrinterSettings();
  const tpl = template ?? settings.defaultTemplate;
  const target = window.open("", "_blank", "width=440,height=700,scrollbars=yes");
  if (!target) { alert("Habilite pop-ups para imprimir."); return false; }
  void currentReceiptSettings(settings).then((branded) => writeReceiptWindow(target, buildPrintHtml(order, tpl, branded), settings.autoPrint));
  return true;
}

export function printConfirmedOrder(order: ApiOrder): boolean {
  const settings = loadPrinterSettings();
  if (!settings.autoPrintConfirmedOrders) return true;

  const templates: PrintTemplate[] = ["cozinha", "completo"];
  const targets = templates.map(() => window.open("", "_blank", "width=440,height=700,scrollbars=yes"));
  void currentReceiptSettings(settings).then((branded) => targets.forEach((target, index) => {
    if (target) writeReceiptWindow(target, buildPrintHtml(order, templates[index], branded), true, index * 600);
  }));
  return targets.every(Boolean);
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
  subtotal: 97.40,
  shipping_fee: 11.99,
  discount: 9.90,
  total: 99.49,
  sales_channel: "counter",
  fulfillment_type: "delivery",
  payment_method: "cash",
  payment_status: "pending",
  pay_on_delivery: true,
  delivery_payment_method: "cash",
  cash_needs_change: true,
  cash_change_for: 100,
  cash_change_amount: 0.51,
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
    {
      id: "sample-drink", product_id: "sample-drink", product_name: "Refrigerante 2 L", product_type: "drink", is_drink: true,
      quantity: 1, selected_size: "2 L", flavor_division: 1, flavors: [], add_ons: [], unit_price: 10, final_price: 10,
      selected_crust_type: null, selected_drink_variant: null, notes: null,
    },
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

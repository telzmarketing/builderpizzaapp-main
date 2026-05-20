export interface SalaoSiteTextTarget {
  id: string;
  tag: string;
  value: string;
  blockId: string;
  blockTitle: string;
  context: string;
}

export interface SalaoSiteImageTarget {
  id: string;
  src: string;
  alt: string;
  blockId: string;
  blockTitle: string;
  context: string;
  width: string;
  height: string;
}

export interface SalaoSiteBlock {
  id: string;
  title: string;
  description: string;
  textIds: string[];
  imageIds: string[];
}

export type SalaoPublicPageKey = "home" | "menu" | "blog" | "pages" | "contact";

export interface SalaoPublicPage {
  key: SalaoPublicPageKey;
  title: string;
  description: string;
  paths: string[];
}

const SKIP_TEXT_PARENTS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "SVG", "META", "LINK", "TITLE", "HEAD"]);

export const SALAO_PUBLIC_PAGES: SalaoPublicPage[] = [
  {
    key: "home",
    title: "Home 1",
    description: "Pagina inicial principal definida para o dominio moschettieri.com.br.",
    paths: ["/", ""],
  },
  {
    key: "menu",
    title: "Menu 2",
    description: "Pagina de cardapio institucional definida como Menu 2.",
    paths: ["/cardapio", "/menu", "/menu-ii"],
  },
  {
    key: "blog",
    title: "Blog List",
    description: "Listagem de conteudos do restaurante.",
    paths: ["/blog", "/blog-list"],
  },
  {
    key: "pages",
    title: "Pages",
    description: "Paginas institucionais, galeria, chefs, premios e perguntas frequentes.",
    paths: ["/sobre", "/galeria", "/chefs", "/premios", "/faq"],
  },
  {
    key: "contact",
    title: "Contato",
    description: "Contato, reservas e canais de atendimento do salao.",
    paths: ["/contato", "/reservas", "/contact-us", "/reservation"],
  },
];

const SECTION_ORDER = [
  "781f60e",
  "8b3e972",
  "622ae3c",
  "9b4b28c",
  "8246d51",
  "7082ce9",
  "4d7a5a0",
  "e677573",
  "0d41703",
  "7a5b8b1",
  "e7af066",
  "54d2708",
  "d594721",
  "e83d900",
  "964391c",
  "f97eb41",
  "5618613",
  "1c1b66b",
  "2952b59",
  "049259e",
  "header",
  "footer",
  "uncategorized",
];

const SECTION_META: Record<string, { title: string; description: string }> = {
  "781f60e": {
    title: "Topo - faixa de contato",
    description: "Endereco, telefone, e-mail e informacoes rapidas acima do menu.",
  },
  "8b3e972": {
    title: "Topo - logo e navegacao",
    description: "Logo principal, menus, links e chamada de reserva do cabecalho.",
  },
  "622ae3c": {
    title: "Hero - slide 1",
    description: "Primeiro destaque visual da abertura, com chamada, texto, botao e imagens.",
  },
  "9b4b28c": {
    title: "Hero - slide 2",
    description: "Segundo destaque visual do carrossel inicial.",
  },
  "8246d51": {
    title: "Hero - slide 3",
    description: "Terceiro destaque visual do carrossel inicial.",
  },
  "7082ce9": {
    title: "Newsletter e reserva rapida",
    description: "Bloco com convite de assinatura, redes sociais e chamada para reserva.",
  },
  "4d7a5a0": {
    title: "Apresentacao do restaurante",
    description: "Descricao institucional, imagem principal e chamadas para menu, reservas e eventos.",
  },
  "e677573": {
    title: "Diferenciais e pratos",
    description: "Beneficios, destaques de experiencia e chamada para pratos especiais.",
  },
  "0d41703": {
    title: "Ocasioes e celebracoes",
    description: "Lista de momentos e motivos para visitar o salao.",
  },
  "7a5b8b1": {
    title: "Cardapio - categorias",
    description: "Titulo do cardapio institucional e abas de categorias.",
  },
  "e7af066": {
    title: "Cardapio - Indian",
    description: "Itens e imagens da primeira categoria do cardapio.",
  },
  "54d2708": {
    title: "Cardapio - Italian",
    description: "Itens e imagens da segunda categoria do cardapio.",
  },
  "d594721": {
    title: "Cardapio - French",
    description: "Itens e imagens da terceira categoria do cardapio.",
  },
  "e83d900": {
    title: "Cardapio - Chinese",
    description: "Itens, imagens e chamada para ver o cardapio completo.",
  },
  "964391c": {
    title: "Especiais e precos",
    description: "Lista de pratos especiais, descricoes, categorias e valores.",
  },
  "f97eb41": {
    title: "Equipe culinaria",
    description: "Chefs, cargos, imagens e apresentacao da equipe.",
  },
  "5618613": {
    title: "Galeria do ambiente",
    description: "Imagens e nomes dos ambientes do restaurante.",
  },
  "1c1b66b": {
    title: "Noticias e conteudos",
    description: "Cards de blog, datas, textos de apoio e imagens.",
  },
  "2952b59": {
    title: "Formulario de reservas",
    description: "Textos, horarios, campos e mensagens do bloco de reserva.",
  },
  "049259e": {
    title: "Rodape",
    description: "Logo, contatos, links, newsletter, lojas de app e pagamentos.",
  },
  header: {
    title: "Cabecalho",
    description: "Itens gerais do cabecalho que nao pertencem a um bloco especifico.",
  },
  footer: {
    title: "Rodape",
    description: "Itens gerais do rodape que nao pertencem a um bloco especifico.",
  },
  uncategorized: {
    title: "Outros conteudos",
    description: "Textos e imagens encontrados fora dos blocos principais do layout.",
  },
};

const EXCLUDED_MENU_ITEM_CLASSES = new Set([
  "menu-item-113",
  "menu-item-117",
  "menu-item-116",
  "menu-item-977",
  "menu-item-980",
  "menu-item-981",
  "menu-item-978",
  "menu-item-979",
  "menu-item-281",
  "menu-item-271",
  "menu-item-246",
  "menu-item-97",
  "menu-item-95",
  "menu-item-96",
  "menu-item-94",
  "menu-item-457",
  "menu-item-47",
  "menu-item-48",
]);

const MENU_LABELS: Record<string, string> = {
  "menu-item-46": "Home 1",
  "menu-item-247": "Menu 2",
  "menu-item-74": "Blog List",
};

const MENU_HREFS: Record<string, string> = {
  "menu-item-112": "/",
  "menu-item-46": "/",
  "menu-item-248": "/cardapio",
  "menu-item-247": "/cardapio",
  "menu-item-75": "/blog",
  "menu-item-74": "/blog",
  "menu-item-893": "/sobre",
  "menu-item-55": "/galeria",
  "menu-item-196": "/chefs",
  "menu-item-327": "/premios",
  "menu-item-328": "/faq",
  "menu-item-229": "/contato",
  "menu-item-230": "/contato",
  "menu-item-56": "/reservas",
};

function parseHtml(html: string): Document {
  return new DOMParser().parseFromString(html, "text/html");
}

function shouldUseTextNode(node: Node): node is Text {
  const parent = node.parentElement;
  if (!parent || SKIP_TEXT_PARENTS.has(parent.tagName)) return false;
  const text = node.nodeValue?.replace(/\s+/g, " ").trim() ?? "";
  if (text.length < 2) return false;
  if (/^[{}[\]();,.\-_:|/\\]+$/.test(text)) return false;
  return true;
}

function walkTextNodes(doc: Document): Text[] {
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => shouldUseTextNode(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT,
  });
  const nodes: Text[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  return nodes;
}

export function extractSalaoSiteTextTargets(html: string): SalaoSiteTextTarget[] {
  const doc = parseHtml(html);
  return walkTextNodes(doc)
    .map((node, index) => ({
      id: `text-${index}`,
      tag: node.parentElement?.tagName.toLowerCase() ?? "text",
      value: node.nodeValue?.replace(/\s+/g, " ").trim() ?? "",
      ...getElementMeta(node.parentElement),
      hiddenByNavigationPreset: isExcludedSalaoNavigationElement(node.parentElement),
    }))
    .filter((target) => !target.hiddenByNavigationPreset)
    .map(({ hiddenByNavigationPreset: _hiddenByNavigationPreset, ...target }) => target);
}

export function extractSalaoSiteImageTargets(html: string): SalaoSiteImageTarget[] {
  const doc = parseHtml(html);
  return Array.from(doc.querySelectorAll<HTMLImageElement>("img[src]"))
    .map((image, index) => ({
      id: `image-${index}`,
      src: image.getAttribute("src") ?? "",
      alt: image.getAttribute("alt") ?? "",
      width: image.getAttribute("width") ?? "",
      height: image.getAttribute("height") ?? "",
      ...getElementMeta(image),
      hiddenByNavigationPreset: isExcludedSalaoNavigationElement(image),
    }))
    .filter((target) => !target.hiddenByNavigationPreset)
    .map(({ hiddenByNavigationPreset: _hiddenByNavigationPreset, ...target }) => target);
}

export function buildSalaoSiteBlocks(
  textTargets: SalaoSiteTextTarget[],
  imageTargets: SalaoSiteImageTarget[],
): SalaoSiteBlock[] {
  const blocks = new Map<string, SalaoSiteBlock>();

  const ensureBlock = (id: string) => {
    const meta = SECTION_META[id] ?? SECTION_META.uncategorized;
    if (!blocks.has(id)) {
      blocks.set(id, {
        id,
        title: meta.title,
        description: meta.description,
        textIds: [],
        imageIds: [],
      });
    }
    return blocks.get(id)!;
  };

  textTargets.forEach((target) => ensureBlock(target.blockId).textIds.push(target.id));
  imageTargets.forEach((target) => ensureBlock(target.blockId).imageIds.push(target.id));

  return Array.from(blocks.values()).sort((a, b) => getBlockOrder(a.id) - getBlockOrder(b.id));
}

export function getSalaoPublicPageKey(pathname = "/"): SalaoPublicPageKey {
  const path = normalizePath(pathname);
  return SALAO_PUBLIC_PAGES.find((page) => page.paths.some((candidate) => normalizePath(candidate) === path))?.key ?? "home";
}

export function getSalaoPageScopedKey(pageKey: SalaoPublicPageKey, targetId: string) {
  return pageKey === "home" ? targetId : `${pageKey}:${targetId}`;
}

export function getSalaoOverrideValue(overrides: Record<string, string>, pageKey: SalaoPublicPageKey, targetId: string) {
  const scopedKey = getSalaoPageScopedKey(pageKey, targetId);
  return overrides[scopedKey] ?? overrides[targetId];
}

export function getSalaoPageOverrides(overrides: Record<string, string> = {}, pageKey: SalaoPublicPageKey) {
  const pageOverrides: Record<string, string> = {};

  Object.entries(overrides).forEach(([key, value]) => {
    if (!key.includes(":")) pageOverrides[key] = value;
  });

  if (pageKey !== "home") {
    const prefix = `${pageKey}:`;
    Object.entries(overrides).forEach(([key, value]) => {
      if (key.startsWith(prefix)) pageOverrides[key.slice(prefix.length)] = value;
    });
  }

  return pageOverrides;
}

export function setSalaoPageOverride(
  overrides: Record<string, string>,
  pageKey: SalaoPublicPageKey,
  targetId: string,
  value: string,
) {
  return { ...overrides, [getSalaoPageScopedKey(pageKey, targetId)]: value };
}

export function removeSalaoPageOverride(
  overrides: Record<string, string>,
  pageKey: SalaoPublicPageKey,
  targetId: string,
) {
  const next = { ...overrides };
  delete next[getSalaoPageScopedKey(pageKey, targetId)];
  if (pageKey === "home") delete next[targetId];
  return next;
}

function ensureBase(doc: Document) {
  if (doc.head.querySelector("base")) return;
  const base = doc.createElement("base");
  base.href = "/salao-site/";
  doc.head.prepend(base);
}

function getElementMeta(element: Element | null) {
  const blockId = getBlockId(element);
  const meta = SECTION_META[blockId] ?? SECTION_META.uncategorized;
  return {
    blockId,
    blockTitle: meta.title,
    context: getElementContext(element),
  };
}

function getBlockId(element: Element | null) {
  if (!element) return "uncategorized";

  const knownSection = getElementorAncestors(element).find((ancestor) => {
    const id = ancestor.getAttribute("data-id") ?? "";
    return Boolean(SECTION_META[id]);
  });
  if (knownSection) return knownSection.getAttribute("data-id") ?? "uncategorized";

  if (element.closest("#header")) return "header";
  if (element.closest("#footer")) return "footer";
  return "uncategorized";
}

function getElementorAncestors(element: Element) {
  const ancestors: Element[] = [];
  let current: Element | null = element;

  while (current) {
    if (current.matches(".elementor-element[data-id]")) ancestors.push(current);
    current = current.parentElement;
  }

  return ancestors;
}

function getElementContext(element: Element | null) {
  if (!element) return "conteudo";
  const widget = element.closest("[data-widget_type]");
  const widgetType = widget?.getAttribute("data-widget_type");
  if (widgetType) return widgetType.replace(".default", "");
  return element.tagName.toLowerCase();
}

function getBlockOrder(id: string) {
  const index = SECTION_ORDER.indexOf(id);
  return index >= 0 ? index : SECTION_ORDER.length;
}

export function applySalaoSiteOverrides(
  html: string,
  textOverrides: Record<string, string> = {},
  imageOverrides: Record<string, string> = {},
): string {
  const doc = parseHtml(html);
  ensureBase(doc);

  walkTextNodes(doc).forEach((node, index) => {
    const value = textOverrides[`text-${index}`];
    if (value !== undefined && value.trim()) node.nodeValue = value;
  });

  Array.from(doc.querySelectorAll<HTMLImageElement>("img[src]")).forEach((image, index) => {
    const value = imageOverrides[`image-${index}`];
    if (!value?.trim()) return;
    image.setAttribute("src", value);
    image.removeAttribute("srcset");
    image.removeAttribute("data-src");
    image.removeAttribute("data-large_image");
    image.removeAttribute("data-lazy-src");
    image.removeAttribute("sizes");
  });

  applySalaoNavigationPreset(doc);

  return `<!doctype html>\n${doc.documentElement.outerHTML}`;
}

function normalizePath(pathname: string) {
  const path = pathname.split("?")[0].split("#")[0].replace(/\/+$/, "");
  return path || "/";
}

function applySalaoNavigationPreset(doc: Document) {
  doc.querySelectorAll("li").forEach((item) => {
    if (getMenuItemClasses(item).some((className) => EXCLUDED_MENU_ITEM_CLASSES.has(className))) {
      item.remove();
    }
  });

  doc.querySelectorAll("li").forEach((item) => {
    const className = getMenuItemClasses(item).find((name) => MENU_LABELS[name] || MENU_HREFS[name]);
    if (!className) return;

    const label = MENU_LABELS[className];
    if (label) {
      const span = item.querySelector(":scope > a span");
      if (span) span.textContent = label;
    }

    const href = MENU_HREFS[className];
    const link = item.querySelector<HTMLAnchorElement>(":scope > a");
    if (href && link) {
      link.setAttribute("href", href);
      link.setAttribute("target", "_top");
    }
  });
}

function isExcludedSalaoNavigationElement(element: Element | null) {
  if (!element) return false;
  const item = element.closest("li");
  return Boolean(item && getMenuItemClasses(item).some((className) => EXCLUDED_MENU_ITEM_CLASSES.has(className)));
}

function getMenuItemClasses(element: Element) {
  return Array.from(element.classList).filter((className) => className.startsWith("menu-item-"));
}

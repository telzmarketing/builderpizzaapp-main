export type SalaoTextRole = "title" | "subtitle" | "description" | "button" | "navigation" | "label" | "other";

export interface SalaoSiteTextTarget {
  id: string;
  tag: string;
  value: string;
  blockId: string;
  blockTitle: string;
  context: string;
  role: SalaoTextRole;
  roleLabel: string;
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

export type SalaoPublicPageKey = "home" | "menu" | "blog" | "moschettieri" | "contact" | "popup";
export type SalaoRenderPageKey =
  | "home"
  | "menu"
  | "blog"
  | "moschettieri"
  | "galeria"
  | "pessoas"
  | "certificados"
  | "duvidas"
  | "contato"
  | "reservas"
  | "minha-conta";

export interface SalaoPublicSubPage {
  key: string;
  title: string;
  description: string;
  blockIds: string[];
}

export interface SalaoPublicPage {
  key: SalaoPublicPageKey;
  title: string;
  description: string;
  blockIds: string[];
  subPages?: SalaoPublicSubPage[];
}

export interface SalaoSiteBlogPost {
  id: string;
  title: string;
  excerpt: string;
  content?: string;
  image: string;
  published_at: string;
  author?: string;
  category?: string;
  published: boolean;
}

const SKIP_TEXT_PARENTS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "SVG", "META", "LINK", "TITLE", "HEAD"]);

const SALAO_COMMON_BLOCK_IDS = ["781f60e", "8b3e972", "049259e"];

const SALAO_DEFAULT_TEXT_REPLACEMENTS: Record<string, string> = {};

const SALAO_DEFAULT_IMAGE_REPLACEMENTS: Record<string, string> = {
};

const SALAO_PAGE_BLOCK_IDS: Record<SalaoRenderPageKey, string[]> = {
  home: [
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
  ],
  menu: ["7a5b8b1", "e7af066", "54d2708", "d594721", "e83d900", "964391c"],
  blog: ["1c1b66b"],
  moschettieri: ["4d7a5a0", "e677573", "0d41703"],
  galeria: ["5618613"],
  pessoas: ["f97eb41"],
  certificados: ["0d41703", "f97eb41"],
  duvidas: ["049259e"],
  contato: ["2952b59", "049259e"],
  reservas: ["2952b59", "7082ce9"],
  "minha-conta": ["049259e"],
};

export const SALAO_PUBLIC_PAGES: SalaoPublicPage[] = [
  {
    key: "home",
    title: "Home",
    description: "Home I definida como pagina inicial publica.",
    blockIds: [
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
      "footer",
    ],
  },
  {
    key: "menu",
    title: "Menu",
    description: "Menu 2 definido como cardapio institucional.",
    blockIds: ["7a5b8b1", "e7af066", "54d2708", "d594721", "e83d900", "964391c"],
  },
  {
    key: "blog",
    title: "Blog",
    description: "Blog List com artigos e noticias do restaurante.",
    blockIds: ["1c1b66b"],
  },
  {
    key: "moschettieri",
    title: "Moschettieri",
    description: "Paginas institucionais do restaurante.",
    blockIds: ["4d7a5a0", "e677573", "0d41703", "5618613"],
    subPages: [
      {
        key: "moschettieri",
        title: "Moschettieri",
        description: "Apresentacao institucional, historia e experiencia do restaurante.",
        blockIds: ["4d7a5a0", "e677573", "0d41703"],
      },
      {
        key: "galeria",
        title: "Galeria",
        description: "Imagens do ambiente e apresentacao visual do salao.",
        blockIds: ["5618613"],
      },
      {
        key: "duvidas",
        title: "Perguntas e Dúvidas",
        description: "Conteudos de apoio, perguntas frequentes e informacoes institucionais.",
        blockIds: ["049259e", "footer"],
      },
    ],
  },
  {
    key: "contact",
    title: "Contato e Reservas",
    description: "Contatos, reservas, login e cadastro.",
    blockIds: ["2952b59", "049259e", "footer"],
    subPages: [
      {
        key: "contatos",
        title: "Contatos",
        description: "Endereco, telefone, e-mail e canais de atendimento.",
        blockIds: ["781f60e", "049259e", "footer"],
      },
      {
        key: "reservas",
        title: "Reservas",
        description: "Formulario e chamadas para reserva de mesa.",
        blockIds: ["2952b59", "7082ce9"],
      },
      {
        key: "minha-conta",
        title: "Login e Cadastro",
        description: "Link de acesso e cadastro do cliente.",
        blockIds: ["049259e", "footer"],
      },
    ],
  },
  {
    key: "popup",
    title: "Popup",
    description: "Popup de entrada, captura de e-mail e chamada exibida sobre o site.",
    blockIds: ["popup"],
  },
];

const REMOVED_MENU_ITEM_CLASSES = new Set([
  "menu-item-46",
  "menu-item-113",
  "menu-item-116",
  "menu-item-117",
  "menu-item-977",
  "menu-item-980",
  "menu-item-981",
  "menu-item-978",
  "menu-item-979",
  "menu-item-281",
  "menu-item-245",
  "menu-item-280",
  "menu-item-271",
  "menu-item-246",
  "menu-item-247",
  "menu-item-97",
  "menu-item-74",
  "menu-item-95",
  "menu-item-96",
  "menu-item-94",
  "menu-item-196",
  "menu-item-327",
  "menu-item-457",
  "menu-item-233",
  "menu-item-47",
  "menu-item-48",
]);

const DIRECT_MENU_ITEM_CLASSES = new Set(["menu-item-112", "menu-item-248", "menu-item-75", "menu-item-232"]);

const MENU_ITEM_LABELS: Record<string, string> = {
  "menu-item-112": "Home",
  "menu-item-113": "Home",
  "menu-item-248": "Menu",
  "menu-item-247": "Menu",
  "menu-item-75": "Blog",
  "menu-item-74": "Blog",
  "menu-item-195": "Moschettieri",
  "menu-item-893": "Moschettieri",
  "menu-item-55": "Galeria",
  "menu-item-196": "Pessoas",
  "menu-item-327": "Certificados & History",
  "menu-item-328": "Perguntas e Dúvidas",
  "menu-item-229": "Contato e Reservas",
  "menu-item-230": "Contatos",
  "menu-item-56": "Reservas",
  "menu-item-232": "Login e Cadastro",
  "menu-item-49": "Login e Cadastro",
};

const MENU_ITEM_HREFS: Record<string, string> = {
  "menu-item-112": "/",
  "menu-item-113": "/",
  "menu-item-248": "/menu",
  "menu-item-247": "/menu",
  "menu-item-75": "/blog",
  "menu-item-74": "/blog",
  "menu-item-195": "/sobre",
  "menu-item-893": "/sobre",
  "menu-item-55": "/galeria",
  "menu-item-196": "/pessoas",
  "menu-item-327": "/certificados",
  "menu-item-328": "/duvidas",
  "menu-item-229": "/contato",
  "menu-item-230": "/contato",
  "menu-item-56": "/reservas",
  "menu-item-232": "/login-cadastro",
  "menu-item-49": "/login-cadastro",
};

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
  "popup",
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
  popup: {
    title: "Popup de entrada",
    description: "Titulo, texto descritivo, aceite e chamada do popup exibido na abertura do site.",
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
  return walkTextNodes(doc).map((node, index) => {
    const value = node.nodeValue?.replace(/\s+/g, " ").trim() ?? "";
    return {
      id: `text-${index}`,
      tag: node.parentElement?.tagName.toLowerCase() ?? "text",
      value,
      ...getElementMeta(node.parentElement),
      ...getTextRole(node.parentElement, value),
    };
  });
}

export function extractSalaoSiteImageTargets(html: string): SalaoSiteImageTarget[] {
  const doc = parseHtml(html);
  return Array.from(doc.querySelectorAll<HTMLImageElement>("img[src]")).map((image, index) => ({
    id: `image-${index}`,
    src: image.getAttribute("src") ?? "",
    alt: image.getAttribute("alt") ?? "",
    width: image.getAttribute("width") ?? "",
    height: image.getAttribute("height") ?? "",
    ...getElementMeta(image),
  }));
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

function ensureBase(doc: Document) {
  if (doc.head.querySelector("base")) return;
  const base = doc.createElement("base");
  base.href = "/salao-site/";
  doc.head.prepend(base);
}

function normalizeSalaoAssetUrls(doc: Document) {
  doc.querySelectorAll<HTMLElement>("[style]").forEach((element) => {
    const style = element.getAttribute("style");
    if (style) element.setAttribute("style", normalizeSalaoAssetReference(style));
  });

  doc.querySelectorAll<HTMLStyleElement>("style").forEach((style) => {
    style.textContent = normalizeSalaoAssetReference(style.textContent ?? "");
  });
}

function normalizeSalaoAssetReference(value: string) {
  return value.replace(/url\((['"]?)(?!data:|https?:|\/|#)(?:\.\/)?images\//gi, "url($1/salao-site/images/");
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

  if (element.closest(".wdt-popup-box-content-holder, .wdt-popup-box-window")) return "popup";

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

function getTextRole(element: Element | null, value: string): { role: SalaoTextRole; roleLabel: string } {
  if (!element) return roleInfo("other");

  if (element.closest("nav, .menu, .main-navigation, .menu-item")) return roleInfo("navigation");
  if (element.closest("button, .wdt-button, .entry-button")) return roleInfo("button");
  if (
    element.closest(".wdt-heading-title, .entry-title, .wdt-content-title") ||
    /^(H1|H2|H3)$/i.test(element.tagName)
  ) {
    return roleInfo("title");
  }
  if (
    element.closest(".wdt-heading-subtitle, .wdt-content-subtitle") ||
    /^(H4|H5|H6)$/i.test(element.tagName)
  ) {
    return roleInfo("subtitle");
  }
  if (
    element.closest(".wdt-heading-content-wrapper, .elementor-widget-text-editor, .entry-body") ||
    element.tagName === "P" ||
    value.length > 90
  ) {
    return roleInfo("description");
  }
  if (element.closest("label, .wdt-terms-condition-lbl, .entry-date, .elementor-icon-list-text")) {
    return roleInfo("label");
  }
  return roleInfo("other");
}

function roleInfo(role: SalaoTextRole) {
  const labels: Record<SalaoTextRole, string> = {
    title: "Titulo",
    subtitle: "Subtitulo",
    description: "Texto descritivo",
    button: "Botao / CTA",
    navigation: "Menu / navegacao",
    label: "Legenda / informacao",
    other: "Texto auxiliar",
  };
  return { role, roleLabel: labels[role] };
}

function getBlockOrder(id: string) {
  const index = SECTION_ORDER.indexOf(id);
  return index >= 0 ? index : SECTION_ORDER.length;
}

export function applySalaoSiteOverrides(
  html: string,
  textOverrides: Record<string, string> = {},
  imageOverrides: Record<string, string> = {},
  blogPosts: SalaoSiteBlogPost[] = [],
  pageKey: SalaoRenderPageKey = "home",
): string {
  const doc = parseHtml(html);
  ensureBase(doc);
  normalizeSalaoAssetUrls(doc);

  walkTextNodes(doc).forEach((node, index) => {
    const value = textOverrides[`text-${index}`];
    if (value !== undefined && value.trim()) {
      node.nodeValue = value;
      return;
    }

    const current = node.nodeValue?.replace(/\s+/g, " ").trim() ?? "";
    const defaultValue = SALAO_DEFAULT_TEXT_REPLACEMENTS[current];
    if (defaultValue) node.nodeValue = defaultValue;
  });

  Array.from(doc.querySelectorAll<HTMLImageElement>("img[src]")).forEach((image, index) => {
    const value = imageOverrides[`image-${index}`];
    const src = image.getAttribute("src") ?? "";
    const defaultValue = SALAO_DEFAULT_IMAGE_REPLACEMENTS[src];
    const nextValue = value?.trim() || defaultValue;
    if (!nextValue) return;
    image.setAttribute("src", nextValue);
    image.removeAttribute("srcset");
    image.removeAttribute("data-src");
    image.removeAttribute("data-large_image");
    image.removeAttribute("data-lazy-src");
    image.removeAttribute("sizes");
  });

  applySalaoMenuButtonPreset(doc);
  applySalaoNavigationPreset(doc);
  applySalaoPagePreset(doc, pageKey);
  applySalaoHomeMenuAnchor(doc);
  applySalaoAnimationFallbacks(doc);
  applySalaoBlogPosts(doc, blogPosts);

  return `<!doctype html>\n${doc.documentElement.outerHTML}`;
}

function applySalaoAnimationFallbacks(doc: Document) {
  if (doc.getElementById("moschettieri-salao-animation-fallbacks")) return;

  const style = doc.createElement("style");
  style.id = "moschettieri-salao-animation-fallbacks";
  style.textContent = `
    @keyframes moschettieri-salao-plate-rotate {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    .elementor-element[data-id="91de15a"] img {
      animation: moschettieri-salao-plate-rotate 30s linear infinite;
      transform-origin: center center;
      will-change: transform;
    }
    @media (prefers-reduced-motion: reduce) {
      .elementor-element[data-id="91de15a"] img {
        animation: none;
      }
    }
    .wdt-custom-h1-slider-carousel .wdt-carousel-pagination-wrapper.wdt-swiper-custom-pagination {
      display: block;
      opacity: 1;
      visibility: visible;
      position: absolute;
      right: clamp(16px, 1.5vw, 24px);
      bottom: clamp(14px, 1.5vw, 20px);
      left: auto;
      width: min(450px, calc(100% - 40px));
      max-width: min(450px, calc(100% - 40px));
      margin: 0;
      padding: 21px 76px;
      z-index: 5;
    }
    .wdt-custom-h1-slider-carousel .wdt-carousel-pagination-wrapper.wdt-swiper-custom-pagination .swiper-pagination-progressbar {
      height: 3px;
    }
    .wdt-custom-h1-slider-carousel .wdt-carousel-pagination-wrapper.wdt-swiper-custom-pagination .wdt-carousel-arrow-pagination > div.wdt-arrow-pagination-prev {
      left: 20px;
    }
    .wdt-custom-h1-slider-carousel .wdt-carousel-pagination-wrapper.wdt-swiper-custom-pagination .wdt-carousel-arrow-pagination > div.wdt-arrow-pagination-next {
      right: 20px;
    }
    @media (max-width: 1024px) {
      .wdt-custom-h1-slider-carousel .wdt-carousel-pagination-wrapper.wdt-swiper-custom-pagination {
        position: relative;
        right: auto;
        bottom: auto;
        width: 100%;
        max-width: 600px;
        margin: 24px auto 0;
      }
    }
    .elementor-31 .elementor-element.elementor-element-74874fe .wdt-content-item,
    .elementor-31 .elementor-element.elementor-element-74874fe .wdt-content-item .wdt-content-title h5,
    .elementor-31 .elementor-element.elementor-element-74874fe .wdt-content-item .wdt-content-title h5 > a,
    .elementor-31 .elementor-element.elementor-element-438b53c .wdt-content-item,
    .elementor-31 .elementor-element.elementor-element-438b53c .wdt-content-item .wdt-content-title h5,
    .elementor-31 .elementor-element.elementor-element-438b53c .wdt-content-item .wdt-content-title h5 > a {
      transition: var(--wdt-Ad-Transition);
      -webkit-transition: var(--wdt-Ad-Transition);
    }
    .elementor-31 .elementor-element.elementor-element-74874fe .wdt-content-item:hover,
    .elementor-31 .elementor-element.elementor-element-74874fe .wdt-content-item:hover .wdt-content-title h5,
    .elementor-31 .elementor-element.elementor-element-74874fe .wdt-content-item:hover .wdt-content-title h5 > a,
    .elementor-31 .elementor-element.elementor-element-74874fe .wdt-content-item:hover span,
    .elementor-31 .elementor-element.elementor-element-438b53c .wdt-content-item:hover,
    .elementor-31 .elementor-element.elementor-element-438b53c .wdt-content-item:hover .wdt-content-title h5,
    .elementor-31 .elementor-element.elementor-element-438b53c .wdt-content-item:hover .wdt-content-title h5 > a,
    .elementor-31 .elementor-element.elementor-element-438b53c .wdt-content-item:hover span {
      color: var(--e-global-color-66c7778);
    }
    .wdt-tabs-container.moschettieri-tabs-fallback-ready .wdt-tabs-content:not(.moschettieri-tab-active) {
      display: none;
    }
    .wdt-tabs-container.moschettieri-tabs-fallback-ready .wdt-tabs-list li.moschettieri-tab-active {
      color: var(--wdtPrimaryColor);
    }
    .wdt-google-map.moschettieri-map-fallback {
      min-height: 400px;
      overflow: hidden;
    }
    .wdt-google-map.moschettieri-map-fallback iframe {
      display: block;
      width: 100%;
      min-height: 400px;
      border: 0;
      filter: grayscale(1) invert(0.88) contrast(0.9);
    }
  `;
  doc.head.appendChild(style);

  const script = doc.createElement("script");
  script.id = "moschettieri-salao-runtime-fallbacks";
  script.textContent = `
    (function () {
      function ready(callback) {
        if (document.readyState === "loading") {
          document.addEventListener("DOMContentLoaded", callback, { once: true });
        } else {
          callback();
        }
        window.addEventListener("load", callback, { once: true });
      }

      function installHomeCarouselFallback() {
        document.querySelectorAll(".wdt-custom-h1-slider-carousel .wdt-carousel-holder").forEach(function (holder) {
          var swiper = holder.querySelector(".swiper");
          var wrapper = holder.querySelector(".swiper-wrapper");
          var slides = Array.prototype.slice.call(holder.querySelectorAll(".swiper-slide"));
          if (!swiper || !wrapper || slides.length < 2 || swiper.swiper || holder.classList.contains("moschettieri-fallback-carousel")) return;

          var pagination = holder.querySelector(".wdt-carousel-pagination-wrapper.wdt-swiper-custom-pagination");
          var progressFill = pagination && pagination.querySelector(".swiper-pagination-progressbar-fill");
          var fraction = pagination && pagination.querySelector("[class*='swiper-pagination-fraction-']");
          var prev = pagination && pagination.querySelector(".wdt-arrow-pagination-prev");
          var next = pagination && pagination.querySelector(".wdt-arrow-pagination-next");
          var current = Math.max(0, slides.findIndex(function (slide) {
            return slide.classList.contains("swiper-slide-active");
          }));

          holder.classList.add("moschettieri-fallback-carousel");
          swiper.style.overflow = "hidden";
          wrapper.style.position = "relative";
          wrapper.style.display = "block";

          function update(nextIndex) {
            current = (nextIndex + slides.length) % slides.length;
            slides.forEach(function (slide, index) {
              slide.classList.toggle("swiper-slide-active", index === current);
              slide.classList.toggle("swiper-slide-visible", index === current);
              slide.classList.toggle("swiper-slide-prev", index === ((current - 1 + slides.length) % slides.length));
              slide.classList.toggle("swiper-slide-next", index === ((current + 1) % slides.length));
              slide.setAttribute("aria-hidden", index === current ? "false" : "true");
              slide.style.position = index === current ? "relative" : "absolute";
              slide.style.inset = "0";
              slide.style.width = "100%";
              slide.style.opacity = index === current ? "1" : "0";
              slide.style.visibility = index === current ? "visible" : "hidden";
              slide.style.pointerEvents = index === current ? "auto" : "none";
              slide.style.transition = "opacity 600ms ease";
            });

            if (pagination) {
              pagination.style.display = "block";
              pagination.style.opacity = "1";
              pagination.style.visibility = "visible";
            }
            if (progressFill) progressFill.style.width = (((current + 1) / slides.length) * 100) + "%";
            if (fraction) fraction.textContent = (current + 1) + " / " + slides.length;
          }

          if (prev) {
            prev.addEventListener("click", function (event) {
              event.preventDefault();
              update(current - 1);
            });
          }
          if (next) {
            next.addEventListener("click", function (event) {
              event.preventDefault();
              update(current + 1);
            });
          }

          update(current);
        });
      }

      function installMenuHoverFallback() {
        document.querySelectorAll(".wdt-image-box-holder.wdt-image-active-class").forEach(function (holder) {
          if (holder.classList.contains("moschettieri-menu-hover-ready")) return;
          holder.classList.add("moschettieri-menu-hover-ready");

          var isCarousel = holder.classList.contains("wdt-carousel-holder");
          var items = Array.prototype.slice.call(holder.querySelectorAll(isCarousel
            ? ".wdt-image-box-container .wdt-image-box-wrapper .swiper-slide"
            : ".wdt-column-wrapper .wdt-column"
          ));
          if (!items.length) return;

          function activate(item) {
            items.forEach(function (entry) {
              entry.classList.toggle("wdt-active", entry === item);
            });
          }

          if (!items.some(function (item) { return item.classList.contains("wdt-active"); })) {
            activate(items[0]);
          }

          items.forEach(function (item) {
            item.addEventListener("mouseover", function () { activate(item); });
            item.addEventListener("focusin", function () { activate(item); });
          });
        });
      }

      function installFlexBannerFallback() {
        document.querySelectorAll(".wdt-flex-banner-options").forEach(function (banner) {
          if (banner.classList.contains("moschettieri-flex-banner-ready")) return;
          banner.classList.add("moschettieri-flex-banner-ready");

          var items = Array.prototype.slice.call(banner.querySelectorAll(".wdt-flex-banner-option"));
          if (!items.length) return;

          function activate(item) {
            items.forEach(function (entry) {
              entry.classList.toggle("active", entry === item);
            });
          }

          if (!items.some(function (item) { return item.classList.contains("active"); })) {
            activate(items[0]);
          }

          var settings = {};
          try {
            settings = JSON.parse((banner.getAttribute("data-settings") || "{}").replace(/\\n=\"\"/g, ""));
          } catch (error) {}

          items.forEach(function (item) {
            if (settings.option === "yes") {
              item.addEventListener("mouseenter", function () { activate(item); });
              item.addEventListener("mouseover", function () { activate(item); });
            } else {
              item.addEventListener("click", function () { activate(item); });
            }
            item.addEventListener("focusin", function () { activate(item); });
          });
        });
      }

      function installTabsFallback() {
        document.querySelectorAll(".wdt-tabs-container").forEach(function (container) {
          if (container.classList.contains("ui-tabs") || container.classList.contains("moschettieri-tabs-fallback-ready")) return;

          var tabs = Array.prototype.slice.call(container.querySelectorAll(".wdt-tabs-list a[href^='#']"));
          var contents = Array.prototype.slice.call(container.querySelectorAll(".wdt-tabs-content"));
          if (!tabs.length || !contents.length) return;

          container.classList.add("moschettieri-tabs-fallback-ready");

          function activate(hash) {
            var target = container.querySelector(hash);
            if (!target) target = contents[0];

            contents.forEach(function (content) {
              var active = content === target;
              content.classList.toggle("moschettieri-tab-active", active);
              content.style.display = active ? "block" : "none";
            });

            tabs.forEach(function (link) {
              var active = link.getAttribute("href") === "#" + target.id;
              var item = link.closest("li");
              if (item) {
                item.classList.toggle("moschettieri-tab-active", active);
                item.classList.toggle("ui-state-active", active);
              }
              link.setAttribute("aria-selected", active ? "true" : "false");
            });
          }

          tabs.forEach(function (link) {
            link.addEventListener("click", function (event) {
              event.preventDefault();
              activate(link.getAttribute("href") || "");
            });
          });

          activate(tabs[0].getAttribute("href") || "");
        });
      }

      function installMapFallback() {
        document.querySelectorAll(".wdt-google-map").forEach(function (map) {
          if (map.classList.contains("moschettieri-map-checked")) return;
          map.classList.add("moschettieri-map-checked");

          window.setTimeout(function () {
            if (map.querySelector(".gm-style, iframe")) return;

            var options = {};
            try {
              options = JSON.parse((map.getAttribute("data-options") || "{}").replace(/\\n=\"\"/g, ""));
            } catch (error) {}

            var center = options.center || { lat: 34.052235, lng: -118.243683 };
            var lat = Number(center.lat) || 34.052235;
            var lng = Number(center.lng) || -118.243683;
            var zoom = Number(options.zoom) || 15;
            var iframe = document.createElement("iframe");
            iframe.loading = "lazy";
            iframe.referrerPolicy = "no-referrer-when-downgrade";
            iframe.src = "https://www.google.com/maps?q=" + encodeURIComponent(lat + "," + lng) + "&z=" + zoom + "&output=embed";
            iframe.title = "Mapa";
            map.classList.add("moschettieri-map-fallback");
            map.innerHTML = "";
            map.appendChild(iframe);
          }, 1800);
        });
      }

      ready(function () {
        window.setTimeout(function () {
          installHomeCarouselFallback();
          installMenuHoverFallback();
          installFlexBannerFallback();
          installTabsFallback();
          installMapFallback();
        }, 900);
      });
    })();
  `;
  doc.body.appendChild(script);
}

function applySalaoPagePreset(doc: Document, pageKey: SalaoRenderPageKey) {
  if (pageKey !== "home") {
    const allowedBlockIds = new Set([
      ...SALAO_COMMON_BLOCK_IDS,
      ...(SALAO_PAGE_BLOCK_IDS[pageKey] ?? SALAO_PAGE_BLOCK_IDS.home),
    ]);

    Object.keys(SECTION_META).forEach((blockId) => {
      if (blockId === "header" || blockId === "footer" || blockId === "uncategorized") return;
      if (allowedBlockIds.has(blockId)) return;

      doc.querySelectorAll<HTMLElement>(`.elementor-element[data-id="${blockId}"]`).forEach((element) => {
        const slide = element.closest<HTMLElement>(".swiper-slide");
        if (slide && slide.closest(".wdt-custom-h1-slider-carousel")) {
          slide.remove();
          return;
        }
        element.remove();
      });
    });
  }

  if (pageKey !== "home") {
    doc.querySelector<HTMLElement>(".wdt-custom-h1-slider-carousel")?.remove();
  }

  doc.body.classList.add(`salao-page-${pageKey}`);
}

function applySalaoNavigationPreset(doc: Document) {
  doc.querySelectorAll("li").forEach((item) => {
    const classes = getMenuItemClasses(item);
    if (classes.some((className) => REMOVED_MENU_ITEM_CLASSES.has(className))) {
      item.remove();
      return;
    }

    const className = classes.find((name) => MENU_ITEM_LABELS[name] || MENU_ITEM_HREFS[name]);
    if (!className) return;

    const link = getDirectMenuLink(item);
    if (!link) return;

    const label = MENU_ITEM_LABELS[className];
    if (label) setMenuLinkLabel(link, label);

    const href = MENU_ITEM_HREFS[className];
    if (href) {
      link.setAttribute("href", href);
      if (href.startsWith("#")) {
        link.removeAttribute("target");
      } else {
        link.setAttribute("target", "_top");
      }
    }

    if (classes.some((name) => DIRECT_MENU_ITEM_CLASSES.has(name))) {
      removeDirectSubMenus(item);
      item.classList.remove("menu-item-has-children");
    }
  });
}

function applySalaoMenuButtonPreset(doc: Document) {
  doc.querySelectorAll("li.menu-item-248").forEach((item) => {
    const link = getDirectMenuLink(item);
    if (!link) return;

    setMenuLinkLabel(link, "Menu");
    link.setAttribute("href", "/menu");
    link.setAttribute("target", "_top");
    removeDirectSubMenus(item);
    item.classList.remove("menu-item-has-children");
  });
}

function applySalaoHomeMenuAnchor(doc: Document) {
  const menuSection = doc.querySelector<HTMLElement>('.elementor-element[data-id="7a5b8b1"]');
  if (!menuSection) return;

  menuSection.id = "salao-menu";
  menuSection.style.scrollMarginTop = "120px";
}

function getMenuItemClasses(element: Element) {
  return Array.from(element.classList).filter((className) => className.startsWith("menu-item-"));
}

function getDirectMenuLink(item: Element) {
  return Array.from(item.children).find((child): child is HTMLAnchorElement => child.tagName === "A") ?? null;
}

function setMenuLinkLabel(link: HTMLAnchorElement, label: string) {
  const span = link.querySelector("span");
  if (span) {
    span.textContent = label;
    return;
  }

  const textNode = Array.from(link.childNodes).find((node) => node.nodeType === Node.TEXT_NODE);
  if (textNode) {
    textNode.nodeValue = label;
    return;
  }

  link.textContent = label;
}

function removeDirectSubMenus(item: Element) {
  Array.from(item.children).forEach((child) => {
    if (child.tagName === "UL") child.remove();
  });
}

function applySalaoBlogPosts(doc: Document, blogPosts: SalaoSiteBlogPost[]) {
  const publishedPosts = blogPosts.filter((post) => post.published !== false && post.title.trim());
  if (!publishedPosts.length) return;

  const holder = doc.querySelector(".tpl-blog-holder");
  const entries = Array.from(doc.querySelectorAll<HTMLElement>(".wdt-post-entry"))
    .filter((entry) => entry.querySelector("article"));
  const template = entries[0];
  if (!holder || !template) return;

  entries.forEach((entry, index) => {
    if (index >= publishedPosts.length) entry.remove();
  });

  publishedPosts.forEach((post, index) => {
    const entry = entries[index] ?? template.cloneNode(true) as HTMLElement;
    if (!entries[index]) holder.appendChild(entry);
    hydrateBlogEntry(entry, post, index);
  });
}

function hydrateBlogEntry(entry: HTMLElement, post: SalaoSiteBlogPost, index: number) {
  const slug = slugify(post.title || post.id || `artigo-${index + 1}`);
  const href = `/blog#${slug}`;
  const date = formatBlogDate(post.published_at);

  const article = entry.querySelector("article");
  if (article) article.id = post.id || `salao-blog-${index + 1}`;

  entry.querySelectorAll<HTMLAnchorElement>("a").forEach((link) => {
    link.href = href;
    link.target = "_top";
    link.title = post.title;
  });

  const image = entry.querySelector<HTMLImageElement>(".entry-thumb img");
  if (image && post.image) {
    image.src = post.image;
    image.alt = post.title;
    image.removeAttribute("srcset");
    image.removeAttribute("sizes");
    image.removeAttribute("data-src");
    image.removeAttribute("data-lazy-src");
  }

  const dateNode = entry.querySelector(".entry-date");
  if (dateNode) dateNode.textContent = date;

  const titleNode = entry.querySelector(".entry-title a");
  if (titleNode) titleNode.textContent = post.title;

  const bodyNode = entry.querySelector(".entry-body p");
  if (bodyNode) bodyNode.textContent = post.excerpt || post.content || "";

  const button = entry.querySelector(".entry-button a");
  if (button?.firstChild) button.firstChild.textContent = "Leia mais";
}

function formatBlogDate(value: string) {
  if (!value) return "";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}

function slugify(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "artigo";
}

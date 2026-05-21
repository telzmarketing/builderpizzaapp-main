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

export type SalaoPublicPageKey = "home" | "menu" | "blog" | "moschettieri" | "contact";

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

export const SALAO_PUBLIC_PAGES: SalaoPublicPage[] = [
  {
    key: "home",
    title: "Home",
    description: "Home 2 definida como pagina inicial publica.",
    blockIds: ["781f60e", "8b3e972", "9b4b28c", "7082ce9", "4d7a5a0", "e677573", "0d41703"],
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
    title: "A Moschettieri",
    description: "Paginas institucionais do restaurante.",
    blockIds: ["4d7a5a0", "e677573", "0d41703", "f97eb41", "5618613"],
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
        key: "pessoas",
        title: "Pessoas",
        description: "Equipe, pessoas e apresentacao dos profissionais.",
        blockIds: ["f97eb41"],
      },
      {
        key: "certificados",
        title: "Certificados & History",
        description: "Premios, certificados e historico institucional.",
        blockIds: ["0d41703", "f97eb41"],
      },
      {
        key: "duvidas",
        title: "Dúvidas e Perguntas",
        description: "Conteudos de apoio, perguntas frequentes e informacoes institucionais.",
        blockIds: ["049259e", "footer"],
      },
    ],
  },
  {
    key: "contact",
    title: "Contato",
    description: "Contatos, reservas e Minha Conta.",
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
        title: "Minha Conta",
        description: "Link de acesso a conta do cliente e rodape relacionado.",
        blockIds: ["049259e", "footer"],
      },
    ],
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
  "menu-item-457",
  "menu-item-232",
  "menu-item-233",
  "menu-item-47",
  "menu-item-48",
]);

const DIRECT_MENU_ITEM_CLASSES = new Set(["menu-item-112", "menu-item-248", "menu-item-75"]);

const MENU_ITEM_LABELS: Record<string, string> = {
  "menu-item-112": "Home",
  "menu-item-113": "Home",
  "menu-item-248": "Menu",
  "menu-item-247": "Menu",
  "menu-item-75": "Blog",
  "menu-item-74": "Blog",
  "menu-item-195": "A Moschettieri",
  "menu-item-893": "Moschettieri",
  "menu-item-55": "Galeria",
  "menu-item-196": "Pessoas",
  "menu-item-327": "Certificados & History",
  "menu-item-328": "Dúvidas e Perguntas",
  "menu-item-229": "Contato",
  "menu-item-230": "Contatos",
  "menu-item-56": "Reservas",
  "menu-item-49": "Minha Conta",
};

const MENU_ITEM_HREFS: Record<string, string> = {
  "menu-item-112": "/",
  "menu-item-113": "/",
  "menu-item-248": "/cardapio",
  "menu-item-247": "/cardapio",
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
  "menu-item-49": "/minha-conta",
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
  return walkTextNodes(doc).map((node, index) => ({
    id: `text-${index}`,
    tag: node.parentElement?.tagName.toLowerCase() ?? "text",
    value: node.nodeValue?.replace(/\s+/g, " ").trim() ?? "",
    ...getElementMeta(node.parentElement),
  }));
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
  blogPosts: SalaoSiteBlogPost[] = [],
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
  applySalaoHomePreset(doc);
  applySalaoBlogPosts(doc, blogPosts);

  return `<!doctype html>\n${doc.documentElement.outerHTML}`;
}

function applySalaoHomePreset(doc: Document) {
  const homeCarousel = doc.querySelector<HTMLElement>(".wdt-custom-h1-slider-carousel");
  const wrapper = homeCarousel?.querySelector<HTMLElement>(".wdt-advanced-carousel-wrapper");
  if (!homeCarousel || !wrapper) return;

  const home2Slide = Array.from(wrapper.querySelectorAll<HTMLElement>(".swiper-slide"))
    .find((slide) => slide.querySelector('[data-id="9b4b28c"], .elementor-496'));
  if (!home2Slide) return;

  wrapper.replaceChildren(home2Slide);
  home2Slide.classList.add("swiper-slide-active");
  home2Slide.classList.remove("swiper-slide-next", "swiper-slide-prev", "swiper-slide-duplicate");
  home2Slide.removeAttribute("style");
  home2Slide.setAttribute("aria-label", "Home 2");

  const carouselContainer = homeCarousel.querySelector<HTMLElement>(".wdt-advanced-carousel-container");
  carouselContainer?.classList.remove("swiper-initialized", "swiper-horizontal", "swiper-backface-hidden");
  carouselContainer?.removeAttribute("style");
  wrapper.removeAttribute("style");

  homeCarousel.querySelectorAll<HTMLElement>(
    ".wdt-carousel-pagination-wrapper, .wdt-carousel-arrow-pagination, .swiper-pagination, [class*='arrow-pagination']",
  ).forEach((element) => element.remove());

  const style = doc.createElement("style");
  style.id = "moschettieri-home-2-static";
  style.textContent = `
    .wdt-custom-h1-slider-carousel .wdt-advanced-carousel-wrapper {
      transform: none !important;
      display: block !important;
    }
    .wdt-custom-h1-slider-carousel .swiper-slide {
      width: 100% !important;
      opacity: 1 !important;
      visibility: visible !important;
      transform: none !important;
      position: relative !important;
      pointer-events: auto !important;
    }
  `;
  doc.head.appendChild(style);
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
      link.setAttribute("target", "_top");
    }

    if (classes.some((name) => DIRECT_MENU_ITEM_CLASSES.has(name))) {
      removeDirectSubMenus(item);
      item.classList.remove("menu-item-has-children");
    }
  });
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

export interface SalaoSiteTextTarget {
  id: string;
  tag: string;
  value: string;
}

export interface SalaoSiteImageTarget {
  id: string;
  src: string;
  alt: string;
}

const SKIP_TEXT_PARENTS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "SVG", "META", "LINK", "TITLE", "HEAD"]);

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
  }));
}

export function extractSalaoSiteImageTargets(html: string): SalaoSiteImageTarget[] {
  const doc = parseHtml(html);
  return Array.from(doc.querySelectorAll<HTMLImageElement>("img[src]")).map((image, index) => ({
    id: `image-${index}`,
    src: image.getAttribute("src") ?? "",
    alt: image.getAttribute("alt") ?? "",
  }));
}

function ensureBase(doc: Document) {
  if (doc.head.querySelector("base")) return;
  const base = doc.createElement("base");
  base.href = "/salao-site/";
  doc.head.prepend(base);
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

  return `<!doctype html>\n${doc.documentElement.outerHTML}`;
}

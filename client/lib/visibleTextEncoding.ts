const PAIR_MAP: Record<string, number> = {};
const LATIN = [0xe0, 0xe1, 0xe2, 0xe3, 0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9, 0xea, 0xeb, 0xec, 0xed, 0xee, 0xef, 0xf0, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8, 0xf9, 0xfa, 0xfb, 0xfc, 0xfd, 0xfe, 0xff];
LATIN.forEach((code, index) => { PAIR_MAP[`195:${0xa0 + index}`] = code; });
for (const [code, value] of [[0xa0, 0x20], [0xb0, 0xb0], [0xb1, 0xb1], [0xb5, 0xb5], [0xb7, 0xb7]]) PAIR_MAP[`194:${code}`] = value;

function repairPass(value: string): string {
  let result = "";
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    const next = value.charCodeAt(index + 1);
    const decoded = PAIR_MAP[`${code}:${next}`];
    if (decoded !== undefined) {
      result += String.fromCharCode(decoded);
      index += 1;
    } else {
      result += value[index];
    }
  }
  return result;
}

export function repairVisibleText(value: string): string {
  if (!/[\u00c2\u00c3]/.test(value) || /[\u00f0\ufffd]/.test(value)) return value;
  let result = value;
  for (let pass = 0; pass < 3; pass += 1) {
    const next = repairPass(result);
    if (next === result) break;
    result = next;
  }
  return result.replaceAll("\u00e2\u2014\u201d", "\u2014").replaceAll("\u00e2\u20ac\u201c", "\u2013");
}

const SKIPPED_TAGS = new Set(["INPUT", "TEXTAREA", "SCRIPT", "STYLE", "PRE", "CODE"]);

function repairTree(root: Node): void {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  let current: Node | null;
  while ((current = walker.nextNode())) nodes.push(current as Text);
  nodes.forEach((node) => {
    const parent = node.parentElement;
    if (!parent || SKIPPED_TAGS.has(parent.tagName) || parent.closest("[data-preserve-encoding]")) return;
    const repaired = repairVisibleText(node.nodeValue ?? "");
    if (repaired !== node.nodeValue) node.nodeValue = repaired;
  });
}

export function installVisibleTextEncodingRepair(): () => void {
  if (typeof document === "undefined") return () => undefined;
  repairTree(document.body);
  const observer = new MutationObserver((records) => {
    records.forEach((record) => {
      record.addedNodes.forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE) {
          const text = node.nodeValue ?? "";
          const repaired = repairVisibleText(text);
          if (repaired !== text) node.nodeValue = repaired;
        } else if (node.nodeType === Node.ELEMENT_NODE) {
          repairTree(node);
        }
      });
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });
  return () => observer.disconnect();
}

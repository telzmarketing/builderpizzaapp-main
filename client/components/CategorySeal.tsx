import type { ApiProduct } from "@/lib/api";

type CategorySealProps = {
  product?: Pick<ApiProduct, "category" | "subcategory"> | null;
  className?: string;
  compact?: boolean;
};

const SEAL_STYLES = [
  "bg-red-600 text-white shadow-red-950/50",
  "bg-amber-400 text-black shadow-amber-950/40",
  "bg-emerald-500 text-black shadow-emerald-950/45",
  "bg-sky-500 text-black shadow-sky-950/45",
  "bg-fuchsia-600 text-white shadow-fuchsia-950/50",
  "bg-violet-600 text-white shadow-violet-950/50",
  "bg-orange-500 text-black shadow-orange-950/45",
  "bg-lime-400 text-black shadow-lime-950/40",
  "bg-cyan-400 text-black shadow-cyan-950/40",
  "bg-rose-600 text-white shadow-rose-950/50",
];

const SEAL_STYLES_BY_KEY: Record<string, string> = {
  especiais: "bg-red-600 text-white shadow-red-950/50",
  especial: "bg-red-600 text-white shadow-red-950/50",
  promocoes: "bg-orange-500 text-black shadow-orange-950/45",
  promocao: "bg-orange-500 text-black shadow-orange-950/45",
  promo: "bg-orange-500 text-black shadow-orange-950/45",
  novidades: "bg-sky-500 text-black shadow-sky-950/45",
  novidade: "bg-sky-500 text-black shadow-sky-950/45",
  tradicionais: "bg-emerald-500 text-black shadow-emerald-950/45",
  tradicional: "bg-emerald-500 text-black shadow-emerald-950/45",
  doces: "bg-fuchsia-600 text-white shadow-fuchsia-950/50",
  doce: "bg-fuchsia-600 text-white shadow-fuchsia-950/50",
  bebidas: "bg-cyan-400 text-black shadow-cyan-950/40",
  bebida: "bg-cyan-400 text-black shadow-cyan-950/40",
};

function sealLabel(product?: Pick<ApiProduct, "category" | "subcategory"> | null) {
  return (product?.subcategory || product?.category || "").trim();
}

function normalizeLabel(label: string) {
  return label
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function styleFor(label: string) {
  const key = normalizeLabel(label);
  const knownStyle = SEAL_STYLES_BY_KEY[key];
  if (knownStyle) return knownStyle;

  const index = Array.from(label).reduce((sum, char) => sum + char.charCodeAt(0), 0) % SEAL_STYLES.length;
  return SEAL_STYLES[index];
}

export default function CategorySeal({ product, className = "", compact = false }: CategorySealProps) {
  const label = sealLabel(product);
  if (!label) return null;

  return (
    <span
      className={`pointer-events-none absolute left-2 top-2 z-10 max-w-[78%] truncate rounded-full border border-white/80 shadow-lg ring-1 ring-black/20 ${
        compact ? "px-1.5 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]"
      } font-bold uppercase leading-none ${styleFor(label)} ${className}`}
      title={label}
    >
      {label}
    </span>
  );
}

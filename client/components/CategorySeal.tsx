import type { ApiProduct } from "@/lib/api";

type CategorySealProps = {
  product?: Pick<ApiProduct, "category" | "subcategory"> | null;
  className?: string;
  compact?: boolean;
};

const SEAL_STYLES = [
  "border-gold/70 bg-gold/95 text-black",
  "border-emerald-300/60 bg-emerald-400/95 text-surface-00",
  "border-sky-300/60 bg-sky-400/95 text-surface-00",
  "border-rose-300/60 bg-rose-400/95 text-surface-00",
  "border-violet-300/60 bg-violet-400/95 text-surface-00",
  "border-orange-300/60 bg-orange-400/95 text-surface-00",
];

function sealLabel(product?: Pick<ApiProduct, "category" | "subcategory"> | null) {
  return (product?.subcategory || product?.category || "").trim();
}

function styleFor(label: string) {
  const index = Array.from(label).reduce((sum, char) => sum + char.charCodeAt(0), 0) % SEAL_STYLES.length;
  return SEAL_STYLES[index];
}

export default function CategorySeal({ product, className = "", compact = false }: CategorySealProps) {
  const label = sealLabel(product);
  if (!label) return null;

  return (
    <span
      className={`pointer-events-none absolute left-2 top-2 z-10 max-w-[78%] truncate rounded-full border shadow-lg shadow-black/25 backdrop-blur-sm ${
        compact ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-1 text-[10px]"
      } font-bold uppercase leading-none ${styleFor(label)} ${className}`}
      title={label}
    >
      {label}
    </span>
  );
}

import { cn } from "@/lib/utils";

export default function MoschettieriLogo({ className = "h-10" }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex flex-col items-center justify-center text-center uppercase leading-none text-cream select-none",
        "font-serif tracking-normal",
        className
      )}
      style={{ fontFamily: "'Cormorant Garamond', Georgia, serif" }}
      aria-label="Del Basito by Moschettieri Pizzeria"
    >
      <span className="mb-[-0.12em] text-[0.38em] font-bold leading-[0.85] tracking-[0.03em]">Del Basito By</span>
      <span className="text-[1em] font-bold leading-[0.82] tracking-[0.03em]">Moschettieri</span>
      <span className="mt-[-0.06em] flex w-full items-center gap-[0.35em] text-[0.34em] font-bold leading-none tracking-[0.42em]">
        <span className="h-px flex-1 bg-current" />
        <span>Pizzeria</span>
        <span className="h-px flex-1 bg-current" />
      </span>
    </span>
  );
}

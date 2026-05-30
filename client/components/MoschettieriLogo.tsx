import { cn } from "@/lib/utils";

export default function MoschettieriLogo({ className = "h-10" }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex flex-col items-center justify-center gap-[0.055em] text-center uppercase leading-none text-cream select-none",
        "font-serif tracking-normal",
        className
      )}
      style={{ fontFamily: "'Cormorant Garamond', Georgia, serif" }}
      aria-label="Del Basito by Moschettieri Pizzeria"
    >
      <span className="whitespace-nowrap text-[0.483em] font-bold leading-[0.9] tracking-[0.03em]">Del Basito By</span>
      <span className="whitespace-nowrap text-[1em] font-bold leading-[0.88] tracking-[0.03em]">Moschettieri</span>
      <span className="mt-[0.12em] flex w-full items-center gap-[0.35em] text-[0.391em] font-bold leading-[1] tracking-[0.42em]">
        <span className="h-px flex-1 bg-current" />
        <span className="whitespace-nowrap">Pizzeria</span>
        <span className="h-px flex-1 bg-current" />
      </span>
    </span>
  );
}

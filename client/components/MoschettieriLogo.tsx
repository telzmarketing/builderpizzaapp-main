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
      <span className="text-[0.38em] font-bold tracking-[0.12em]">Del Basito By</span>
      <span className="text-[1em] font-bold tracking-[0.03em]">Moschettieri</span>
      <span className="flex w-full items-center gap-[0.35em] text-[0.34em] font-bold tracking-[0.42em]">
        <span className="h-px flex-1 bg-current" />
        <span>Pizzeria</span>
        <span className="h-px flex-1 bg-current" />
      </span>
    </span>
  );
}

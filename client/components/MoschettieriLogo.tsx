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
      aria-label="Marca da loja"
    >
      <span className="whitespace-nowrap text-[1em] font-bold leading-[0.88] tracking-[0.03em]">Sua Loja</span>
      <span className="mt-[0.12em] flex w-full items-center gap-[0.35em] text-[0.391em] font-bold leading-[1] tracking-[0.42em]">
        <span className="h-px flex-1 bg-current" />
        <span className="whitespace-nowrap">Delivery</span>
        <span className="h-px flex-1 bg-current" />
      </span>
    </span>
  );
}

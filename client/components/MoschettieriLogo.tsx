import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import { storeBranding } from "@/lib/storeBranding";

export default function MoschettieriLogo({ className = "h-10" }: { className?: string }) {
  const { siteContent } = useApp();
  const brand = storeBranding(siteContent);
  const [failed, setFailed] = useState(false);
  useEffect(() => { setFailed(false); }, [brand.logo]);
  if (brand.logo && !failed) return <span className={cn("inline-flex items-center justify-center", className)}><img src={brand.logo} alt={brand.name} className="h-auto max-h-12 w-auto max-w-[180px] object-contain" onError={() => setFailed(true)} /></span>;
  return (
    <span
      className={cn(
        "inline-flex flex-col items-center justify-center gap-[0.055em] text-center uppercase leading-none text-cream select-none",
        "font-serif tracking-normal",
        className
      )}
      style={{ fontFamily: "'Cormorant Garamond', Georgia, serif" }}
      aria-label={brand.name}
    >
      <span className="text-[1em] font-bold leading-[0.88] tracking-[0.03em]">{brand.name}</span>
      <span className="mt-[0.12em] flex w-full items-center gap-[0.35em] text-[0.391em] font-bold leading-[1] tracking-[0.42em]">
        <span className="h-px flex-1 bg-current" />
        <span className="whitespace-nowrap">{brand.tagline || "Delivery"}</span>
        <span className="h-px flex-1 bg-current" />
      </span>
    </span>
  );
}

import { useState, type ReactNode } from "react";
import { useApp } from "@/context/AppContext";
import { storeBranding } from "@/lib/storeBranding";

/** Uses the same tenant branding already loaded for the storefront and admin. */
export default function KdsBrandLogo({ fallback, className = "h-14 w-20 shrink-0 object-contain sm:w-24" }: { fallback: ReactNode; className?: string }) {
  const { siteContent } = useApp();
  const brand = storeBranding(siteContent);
  const [failedLogo, setFailedLogo] = useState<string | null>(null);

  if (!brand.logo || failedLogo === brand.logo) return <>{fallback}</>;

  return <img src={brand.logo} alt={`Logo de ${brand.name}`} className={className} onError={() => setFailedLogo(brand.logo)} />;
}

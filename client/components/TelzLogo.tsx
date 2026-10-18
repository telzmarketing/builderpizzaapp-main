import { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import { usePlatformSurface } from "@/context/PlatformSurfaceContext";
import { resolveAssetUrl } from "@/lib/api";

export default function TelzLogo({ className = "" }: { className?: string }) {
  const { siteContent } = useApp();
  const platformSurface = usePlatformSurface();
  const logo = platformSurface ? siteContent.brand.logo : "";
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [logo]);
  return (
    <span className={`inline-flex items-center font-black tracking-tight ${className}`} aria-label="Telz">
      {logo && !failed
        ? <img src={resolveAssetUrl(logo)} alt="Telz" className="h-[1.5em] max-w-[10em] object-contain" onError={() => setFailed(true)} />
        : "Telz"}
    </span>
  );
}

import { X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { getPwaApp } from "@/lib/motoboyPwa";
import PwaInstallButton from "./PwaInstallButton";

/** Installation is offered on the app's own page, inside its manifest/SW scope. */
export default function PwaInstallIntent() {
  const location = useLocation();
  const navigate = useNavigate();
  const params = new URLSearchParams(location.search);
  const app = getPwaApp(location.pathname);
  if (params.get("instalar") !== "1" || !app) return null;

  const close = () => {
    params.delete("instalar");
    void navigate({ pathname: location.pathname, search: params.toString() ? `?${params}` : "", hash: location.hash }, { replace: true });
  };

  return (
    <aside data-pwa-install-intent={app.key} className="fixed bottom-4 left-4 right-4 z-[100] mx-auto max-w-sm rounded-2xl border border-gold/40 bg-surface-01 p-4 text-cream shadow-2xl shadow-black/50" role="dialog" aria-label={`Instalar ${app.label}`}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-black">Instalar {app.label}</h2>
          <p className="mt-1 text-xs text-stone">A instalação será feita neste dispositivo. Toque em Instalar; se o navegador não abrir a instalação, siga as instruções exibidas.</p>
        </div>
        <button type="button" onClick={close} className="rounded-lg p-1 text-stone hover:text-cream" aria-label="Fechar instalação"><X size={18} /></button>
      </div>
      <PwaInstallButton only={[app.key]} inline installIntent />
    </aside>
  );
}

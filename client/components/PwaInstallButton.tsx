import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { getPwaApp, getPwaEntryApp, type PwaAppKey } from "@/lib/motoboyPwa";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform?: string }>;
};

function isStandaloneMode() {
  const navigatorWithStandalone = navigator as Navigator & { standalone?: boolean };
  return window.matchMedia("(display-mode: standalone)").matches || navigatorWithStandalone.standalone === true;
}

export default function PwaInstallButton({ only, pathname = typeof window === "undefined" ? "" : window.location.pathname }: { only?: readonly PwaAppKey[]; pathname?: string } = {}) {
  const app = getPwaApp(pathname);
  const entryApp = getPwaEntryApp(pathname);
  const legacyInstallable = app?.key === "motoboy" || app?.key === "bi-mobile";
  const allowed = !!app && (entryApp?.key === app.key || legacyInstallable) && (!only || only.includes(app.key));
  const [prompt, setPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);

  useEffect(() => {
    setInstalled(allowed && isStandaloneMode());
    setShowInstructions(false);
    if (!allowed) { setPrompt(null); return; }
    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      if (!isStandaloneMode()) setPrompt(event as BeforeInstallPromptEvent);
    };
    const onInstalled = () => { setInstalled(true); setPrompt(null); };
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, [allowed, pathname]);

  if (!allowed || installed || !app) return null;
  return (
    <div className="pwa-install-anchor" data-pwa-app={app.key}>
      <button type="button" onClick={() => {
        const current = prompt;
        if (!current) { setShowInstructions((value) => !value); return; }
        setPrompt(null);
        void current.prompt().then(() => current.userChoice).catch(() => setPrompt(current));
      }} className="pwa-install-button" aria-expanded={showInstructions} aria-label={`Instalar ${app.label}`} title={`Instalar ${app.label}`}>
        <Download size={15} aria-hidden="true" /> <span>Instalar</span>
      </button>
      {showInstructions && !prompt && (
        <p className="pwa-install-hint" role="status">
          No iPhone/iPad: use Compartilhar e escolha &quot;Adicionar a Tela de Inicio&quot;.
        </p>
      )}
      {false && showInstructions && !prompt && (
        <p className="pwa-install-hint" role="status">
          No iPhone/iPad: use Compartilhar e escolha “Adicionar à Tela de Início”.
        </p>
      )}
    </div>
  );
}

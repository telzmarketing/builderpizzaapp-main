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

  useEffect(() => {
    setInstalled(allowed && isStandaloneMode());
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

  if (!allowed || installed || !prompt || !app) return null;
  return (
    <button type="button" onClick={() => {
      const current = prompt;
      setPrompt(null);
      void current.prompt().then(() => current.userChoice).catch(() => setPrompt(current));
    }} className="fixed bottom-4 left-1/2 z-50 flex min-h-12 -translate-x-1/2 items-center justify-center gap-2 rounded-xl border border-gold/30 bg-surface-01 px-4 py-3 text-sm font-black text-gold shadow-xl shadow-black/40 transition-colors hover:bg-surface-02" aria-label={`Instalar ${app.label}`}>
      <Download size={16} /> Instalar {app.label}
    </button>
  );
}

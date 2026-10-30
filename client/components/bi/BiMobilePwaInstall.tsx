import { Download, CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

/** Progressive enhancement: uses the browser's existing PWA install flow. */
export default function BiMobilePwaInstall() {
  const [prompt, setPrompt] = useState<InstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      setPrompt(event as InstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setPrompt(null);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (installed) {
    return <span className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 text-[11px] font-bold text-emerald-200"><CheckCircle2 size={14} /> Instalado</span>;
  }
  if (!prompt) return null;

  return (
    <button
      type="button"
      className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg border border-gold/40 bg-gold/10 px-2.5 text-[11px] font-bold text-gold transition hover:bg-gold/20"
      onClick={() => {
        const current = prompt;
        setPrompt(null);
        void current.prompt().then(() => current.userChoice).catch(() => setPrompt(current));
      }}
    >
      <Download size={14} /> Instalar BI
    </button>
  );
}

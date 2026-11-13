import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { getPwaApp, getPwaEntryApp, type PwaAppKey } from "@/lib/motoboyPwa";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform?: string }>;
};

export type PwaInstallPlatform = "android" | "ios" | "desktop";

export function detectPwaInstallPlatform(navigatorValue: Pick<Navigator, "userAgent" | "platform" | "maxTouchPoints"> = typeof navigator === "undefined" ? { userAgent: "", platform: "", maxTouchPoints: 0 } : navigator): PwaInstallPlatform {
  const userAgent = navigatorValue.userAgent || "";
  const platform = navigatorValue.platform || "";
  const isAndroid = /Android/i.test(userAgent);
  const isIosDevice = /iPhone|iPod|iPad/i.test(userAgent)
    || (/Macintosh/i.test(userAgent) && /MacIntel/i.test(platform) && navigatorValue.maxTouchPoints > 1);
  if (isAndroid) return "android";
  if (isIosDevice) return "ios";
  return "desktop";
}

export const PWA_INSTALL_DELAY_MS = 60_000;

function installedStorageKey(appKey: PwaAppKey) {
  return `telz:pwa-installed:${appKey}`;
}

export function hasRecordedPwaInstallation(appKey: PwaAppKey, storage: Storage = localStorage) {
  try {
    return storage.getItem(installedStorageKey(appKey)) === "1";
  } catch {
    return false;
  }
}

function recordPwaInstallation(appKey: PwaAppKey, storage: Storage = localStorage) {
  try { storage.setItem(installedStorageKey(appKey), "1"); } catch { /* storage can be unavailable */ }
}

function isStandaloneMode(mediaQuery?: MediaQueryList) {
  const navigatorWithStandalone = navigator as Navigator & { standalone?: boolean };
  return (mediaQuery ?? window.matchMedia("(display-mode: standalone)")).matches || navigatorWithStandalone.standalone === true;
}

export function canShowPwaInstallButton(pathname: string, only?: readonly PwaAppKey[]) {
  const app = getPwaApp(pathname);
  const entryApp = getPwaEntryApp(pathname);
  const legacyInstallable = app?.key === "motoboy" || app?.key === "bi-mobile";
  const canonicalInstallable = !!app?.canonicalPaths.includes(pathname);
  return !!app && (entryApp?.key === app.key || canonicalInstallable || legacyInstallable) && (!only || only.includes(app.key));
}

export default function PwaInstallButton({ only, pathname, hideOnKds = false, inline = false, mobileOnly = false, delayMs = 0, variant = "compact" }: { only?: readonly PwaAppKey[]; pathname?: string; hideOnKds?: boolean; inline?: boolean; mobileOnly?: boolean; delayMs?: number; variant?: "compact" | "banner" } = {}) {
  const location = useLocation();
  const currentPathname = pathname ?? location.pathname;
  const app = getPwaApp(currentPathname);
  const allowed = canShowPwaInstallButton(currentPathname, only);
  const isKds = app?.key.startsWith("kds-") === true;
  const [prompt, setPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);
  const [delayElapsed, setDelayElapsed] = useState(delayMs === 0);
  const [platform, setPlatform] = useState<PwaInstallPlatform>(() => detectPwaInstallPlatform());

  useEffect(() => {
    const standaloneMedia = window.matchMedia("(display-mode: standalone)");
    setPlatform(detectPwaInstallPlatform());
    const refreshInstalledState = () => setInstalled(allowed && (isStandaloneMode(standaloneMedia) || (app ? hasRecordedPwaInstallation(app.key) : false)));
    refreshInstalledState();
    setDelayElapsed(delayMs === 0);
    setShowInstructions(false);
    if (!allowed) { setPrompt(null); return; }
    const timer = delayMs > 0 ? window.setTimeout(() => setDelayElapsed(true), delayMs) : undefined;
    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      if (!isStandaloneMode()) setPrompt(event as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      if (app) recordPwaInstallation(app.key);
      setInstalled(true);
      setPrompt(null);
    };
    const onDisplayModeChange = () => {
      if (standaloneMedia.matches) {
        setInstalled(true);
        setPrompt(null);
      } else {
        refreshInstalledState();
      }
    };
    standaloneMedia.addEventListener?.("change", onDisplayModeChange);
    standaloneMedia.addListener?.(onDisplayModeChange);
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      standaloneMedia.removeEventListener?.("change", onDisplayModeChange);
      standaloneMedia.removeListener?.(onDisplayModeChange);
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [allowed, app, currentPathname, delayMs]);

  const canOfferInstall = !!prompt || platform === "android" || platform === "ios";
  if (!allowed || installed || !delayElapsed || !app || (hideOnKds && isKds) || !canOfferInstall) return null;
  const instruction = platform === "ios"
    ? "No iPhone/iPad: use Compartilhar e escolha \"Adicionar à Tela de Início\"."
    : platform === "android"
      ? "No Android: use o menu do navegador e escolha \"Instalar app\" ou \"Adicionar à tela inicial\"."
      : "No computador: use o ícone de instalação na barra de endereço do navegador.";
  return (
    <div
      className={`pwa-install-anchor${inline ? " pwa-install-anchor-inline" : ""}${mobileOnly ? " pwa-install-anchor-mobile-only" : ""}${variant === "banner" ? " pwa-install-anchor-banner" : ""}`}
      data-pwa-app={app.key}
      style={{
        position: "static",
        width: "100%",
        maxWidth: "100%",
        alignItems: inline ? "stretch" : "flex-start",
        margin: "0 0 1rem",
        padding: "0",
        pointerEvents: "auto",
      }}
    >
      {variant === "banner" && <div className="pwa-install-message" role="status">Instale a loja no seu celular para acessar mais rápido.</div>}
      <button type="button" onClick={() => {
        const current = prompt;
        if (!current) { setShowInstructions((value) => !value); return; }
        setPrompt(null);
        void current.prompt().then(() => current.userChoice).then((choice) => {
          if (choice.outcome === "accepted" && app) {
            recordPwaInstallation(app.key);
            setInstalled(true);
          }
        }).catch(() => setPrompt(current));
      }} className="pwa-install-button" aria-expanded={showInstructions} aria-label={`Instalar ${app.label}`} title={`Instalar ${app.label}`}>
        <Download size={15} aria-hidden="true" /> <span>Instalar</span>
      </button>
      {showInstructions && !prompt && (
        <p className="pwa-install-hint" role="status">
          {instruction}
        </p>
      )}
    </div>
  );
}

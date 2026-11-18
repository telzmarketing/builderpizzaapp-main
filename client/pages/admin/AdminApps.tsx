import { useState } from "react";
import { BarChart3, Bike, Check, Copy, Download, Monitor, Store } from "lucide-react";
import { PWA_APPS, manifestUrl, type PwaAppDefinition } from "@/lib/motoboyPwa";

const iconByKey = {
  storefront: Store,
  motoboy: Bike,
  "bi-mobile": BarChart3,
} as const;

function AppIcon({ app }: { app: PwaAppDefinition }) {
  const Icon = iconByKey[app.key as keyof typeof iconByKey] ?? Monitor;
  return <Icon size={22} aria-hidden="true" />;
}

export default function AdminApps() {
  const [copied, setCopied] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const installUrl = (app: PwaAppDefinition) => {
    const url = new URL(app.aliasScope ?? app.entryPath, window.location.origin);
    url.searchParams.set("instalar", "1");
    return `${url.pathname}${url.search}`;
  };
  const appUrl = (app: PwaAppDefinition) => `${window.location.origin}${installUrl(app)}`;

  const copy = async (app: PwaAppDefinition) => {
    const url = appUrl(app);
    try {
      await navigator.clipboard.writeText(url);
      setCopied(app.key);
      setCopyError(null);
      window.setTimeout(() => setCopied((value) => value === app.key ? null : value), 2200);
    } catch {
      setCopied(null);
      setCopyError(app.key);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-01 px-4 py-6 text-cream sm:px-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <header>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-gold">Configuracoes / Apps</p>
          <h1 className="mt-2 text-3xl font-black">Aplicativos</h1>
          <p className="mt-2 max-w-2xl text-sm text-stone">Abra este painel no dispositivo em que deseja instalar. Toque em Instalar para acessar a pagina do aplicativo e siga a solicitacao de instalacao do navegador.</p>
        </header>

        <section className="grid gap-4 md:grid-cols-2">
          {PWA_APPS.map((app) => {
            const url = appUrl(app);
            return (
              <article key={app.key} className="rounded-2xl border border-surface-03 bg-surface-02 p-5 shadow-lg shadow-black/10">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-xl border border-gold/30 bg-gold/10 p-3 text-gold"><AppIcon app={app} /></div>
                    <div>
                      <h2 className="font-bold text-cream">{app.label}</h2>
                      <p className="text-xs text-stone">Escopo: {app.scope}</p>
                    </div>
                  </div>
                </div>
                <a href={installUrl(app)} className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-gold px-4 py-3 text-sm font-bold text-cream hover:bg-gold/90" aria-label={`Instalar ${app.label}`}>
                  <Download size={17} aria-hidden="true" />
                  Instalar
                </a>
                <p className="mt-2 text-xs text-stone">A instalacao sera oferecida na pagina do aplicativo, conforme o navegador deste dispositivo.</p>
                <div className="mt-4 flex gap-2">
                  <input readOnly value={url} className="min-w-0 flex-1 rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-xs text-parchment" aria-label={`Link de instalacao do ${app.label}`} />
                  <button type="button" onClick={() => void copy(app)} className="flex shrink-0 items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-xs font-bold text-parchment hover:bg-surface-03" aria-label={`Copiar link de instalacao do ${app.label}`}>
                    {copied === app.key ? <Check size={15} /> : <Copy size={15} />}
                    {copied === app.key ? "Copiado" : "Copiar"}
                  </button>
                </div>
                {copyError === app.key && <p role="alert" className="mt-2 text-xs text-red-400">Nao foi possivel copiar o link neste navegador.</p>}
                <p className="mt-2 text-[11px] text-stone">Manifesto: {manifestUrl(app.key)}</p>
              </article>
            );
          })}
        </section>
      </div>
    </main>
  );
}

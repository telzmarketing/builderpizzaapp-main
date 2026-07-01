import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { salaoPageApi } from "@/lib/api";
import { applySalaoSiteOverrides, type SalaoRenderPageKey } from "@/lib/salaoSiteCms";

const SALAO_SITE_URL = "/salao-site/index.html";

function resolveSalaoPageKey(pathname: string): SalaoRenderPageKey {
  if (pathname.startsWith("/menu") || pathname.startsWith("/cardapio")) return "menu";
  if (pathname.startsWith("/blog")) return "blog";
  if (pathname.startsWith("/galeria")) return "galeria";
  if (pathname.startsWith("/pessoas")) return "pessoas";
  if (pathname.startsWith("/certificados")) return "certificados";
  if (pathname.startsWith("/duvidas")) return "duvidas";
  if (pathname.startsWith("/reservas")) return "reservas";
  if (pathname.startsWith("/contato")) return "contato";
  if (pathname.startsWith("/login-cadastro")) return "minha-conta";
  if (pathname.startsWith("/minha-conta")) return "minha-conta";
  if (pathname.startsWith("/sobre")) return "moschettieri";
  return "home";
}

export default function SalaoHome() {
  const { pathname } = useLocation();
  const pageKey = resolveSalaoPageKey(pathname);
  const [srcDoc, setSrcDoc] = useState("");
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    document.title = "Moschettieri";
    document.documentElement.style.background = "#0b0b0b";
    document.body.style.margin = "0";
    document.body.style.background = "#0b0b0b";

    let active = true;
    setSrcDoc("");
    setUnavailable(false);

    Promise.all([
      fetch(SALAO_SITE_URL).then((response) => response.text()),
      salaoPageApi.get().catch(() => null),
    ])
      .then(([html, settings]) => {
        if (!active) return;
        if (settings && !settings.enabled) {
          setUnavailable(true);
          return;
        }
        document.title = settings?.seo_title || "Moschettieri";
        const metaDescription = document.querySelector<HTMLMetaElement>('meta[name="description"]');
        if (metaDescription) {
          metaDescription.content = settings?.seo_description || "";
        }
        setSrcDoc(applySalaoSiteOverrides(
          html,
          settings?.site_text_overrides,
          settings?.site_image_overrides,
          settings?.blog_posts,
          pageKey,
        ));
      })
      .catch(() => {
        if (active) {
          setSrcDoc("");
        }
      });

    return () => {
      active = false;
    };
  }, [pageKey]);

  if (unavailable) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-black px-6 text-center text-white">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-amber-300">Moschettieri</p>
          <h1 className="mt-3 text-3xl font-black">Pagina temporariamente indisponivel</h1>
        </div>
      </main>
    );
  }

  return (
    <iframe
      title="Moschettieri Salao"
      src={srcDoc ? undefined : SALAO_SITE_URL}
      srcDoc={srcDoc || undefined}
      className="block h-screen min-h-screen w-full border-0 bg-black"
      loading="eager"
    />
  );
}

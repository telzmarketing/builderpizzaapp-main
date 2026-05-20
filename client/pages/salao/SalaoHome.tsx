import { useEffect, useState } from "react";
import { salaoPageApi } from "@/lib/api";
import { applySalaoSiteOverrides } from "@/lib/salaoSiteCms";

const SALAO_SITE_URL = "/salao-site/index.html";

export default function SalaoHome() {
  const [srcDoc, setSrcDoc] = useState("");
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    document.title = "Moschettieri";
    document.documentElement.style.background = "#0b0b0b";
    document.body.style.margin = "0";
    document.body.style.background = "#0b0b0b";

    let active = true;

    Promise.all([
      fetch(SALAO_SITE_URL).then((response) => response.text()),
      salaoPageApi.get(),
    ])
      .then(([html, settings]) => {
        if (!active) return;
        if (!settings.enabled) {
          setUnavailable(true);
          return;
        }
        document.title = settings.seo_title || "Moschettieri";
        const metaDescription = document.querySelector<HTMLMetaElement>('meta[name="description"]');
        if (metaDescription) {
          metaDescription.content = settings.seo_description || "";
        }
        setSrcDoc(applySalaoSiteOverrides(
          html,
          settings.site_text_overrides,
          settings.site_image_overrides,
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
  }, []);

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

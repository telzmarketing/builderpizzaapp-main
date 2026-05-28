import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Copy, ExternalLink, Loader2, Pencil, RefreshCw, Send, XCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  promotionLandingsApi,
  type ApiPromotionLandingPage,
} from "@/lib/api";

type PromotionLandingsTabProps = {
  title?: string;
  actionLabel?: string;
  onCreateCampaign?: (landing: ApiPromotionLandingPage) => void;
};

function publicLandingUrl(path: string) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${window.location.origin}${path.startsWith("/") ? path : `/${path}`}`;
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString("pt-BR") : "-";
}

export default function PromotionLandingsTab({
  title = "Promoções Loja Delivery",
  actionLabel = "Criar campanha",
  onCreateCampaign,
}: PromotionLandingsTabProps) {
  const navigate = useNavigate();
  const [landings, setLandings] = useState<ApiPromotionLandingPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const sortedLandings = useMemo(
    () =>
      [...landings].sort((a, b) => {
        const activeDiff = Number(b.promotion_active_now) - Number(a.promotion_active_now);
        if (activeDiff !== 0) return activeDiff;
        return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
      }),
    [landings],
  );

  const loadLandings = () => {
    setLoading(true);
    setError("");
    promotionLandingsApi
      .list()
      .then(setLandings)
      .catch((err: unknown) => {
        setLandings([]);
        setError(err instanceof Error ? err.message : "Erro ao carregar promoções.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadLandings();
  }, []);

  const copyUrl = async (landing: ApiPromotionLandingPage) => {
    const url = publicLandingUrl(landing.public_url);
    await navigator.clipboard.writeText(url);
    setCopiedId(landing.id);
    window.setTimeout(() => setCopiedId(null), 1500);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-cream">{title}</h2>
          <p className="text-sm text-stone">Promoções criadas nas landings dos produtos.</p>
        </div>
        <button
          type="button"
          onClick={loadLandings}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-03 bg-surface-02 px-3 py-2 text-sm font-semibold text-parchment hover:text-cream"
        >
          <RefreshCw size={15} />
          Atualizar
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex h-52 items-center justify-center rounded-xl border border-surface-03 bg-surface-02">
          <Loader2 className="animate-spin text-gold" size={28} />
        </div>
      ) : sortedLandings.length === 0 ? (
        <div className="rounded-xl border border-surface-03 bg-surface-02 px-4 py-10 text-center">
          <p className="text-cream font-semibold">Nenhuma promoção de landing criada.</p>
          <p className="mt-1 text-sm text-stone">Crie uma promoção no produto e publique a landing promocional.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {sortedLandings.map((landing) => {
            const url = publicLandingUrl(landing.public_url);
            return (
              <div key={landing.id} className="rounded-xl border border-surface-03 bg-surface-02 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-base font-bold text-cream">{landing.title}</h3>
                    <p className="mt-1 text-xs text-stone">
                      {[landing.product_name, landing.promotion_name].filter(Boolean).join(" • ") || "Produto promocional"}
                    </p>
                  </div>
                  <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-[11px] font-bold ${
                    landing.promotion_active_now
                      ? "bg-green-500/15 text-green-300"
                      : "bg-surface-03 text-stone"
                  }`}>
                    {landing.promotion_active_now ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                    {landing.promotion_active_now ? "Ativa agora" : "Fora do horario"}
                  </span>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-lg bg-surface-03/70 px-3 py-2">
                    <p className="text-stone">Status</p>
                    <p className="mt-0.5 font-semibold text-parchment">
                      {landing.status === "published" && landing.is_active ? "Publicada" : "Rascunho"}
                    </p>
                  </div>
                  <div className="rounded-lg bg-surface-03/70 px-3 py-2">
                    <p className="text-stone">Atualizada</p>
                    <p className="mt-0.5 font-semibold text-parchment">{formatDate(landing.updated_at)}</p>
                  </div>
                </div>

                <div className="mt-3 rounded-lg border border-surface-03 bg-surface-01 px-3 py-2">
                  <p className="truncate text-xs text-stone">{url}</p>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => onCreateCampaign?.(landing)}
                    className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-gold px-3 py-2 text-sm font-bold text-cream hover:bg-gold/90"
                  >
                    <Send size={15} />
                    {actionLabel}
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(`/painel/products/landing/${landing.product_id}/${landing.promotion_id}`)}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment hover:text-cream"
                  >
                    <Pencil size={15} />
                    Editar
                  </button>
                  <button
                    type="button"
                    onClick={() => copyUrl(landing)}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment hover:text-cream"
                  >
                    <Copy size={15} />
                    {copiedId === landing.id ? "Copiado" : "Copiar"}
                  </button>
                  <a
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment hover:text-cream"
                  >
                    <ExternalLink size={15} />
                    Abrir
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

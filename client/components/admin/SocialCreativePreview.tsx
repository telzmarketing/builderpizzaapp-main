import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Heart, ImageOff, MessageCircle, Send, Share2, Volume2 } from "lucide-react";
import { resolveAssetUrl, type CampaignCreative } from "@/lib/api";

export type SocialPlacement = "generic" | "facebook_feed" | "instagram_feed" | "instagram_story" | "instagram_reels" | "tiktok";

type Props = {
  creative: CampaignCreative;
  campaignName?: string;
  campaignPlatform?: string;
};

type Placement = {
  id: SocialPlacement;
  label: string;
  network: string;
  ratio: number;
  ratioLabel: string;
  vertical: boolean;
};

const placements: Placement[] = [
  { id: "generic", label: "Preview genérico", network: "Anúncio", ratio: 16 / 9, ratioLabel: "16:9", vertical: false },
  { id: "facebook_feed", label: "Facebook Feed", network: "Facebook", ratio: 1.91, ratioLabel: "1,91:1", vertical: false },
  { id: "instagram_feed", label: "Instagram Feed", network: "Instagram", ratio: 1, ratioLabel: "1:1", vertical: false },
  { id: "instagram_story", label: "Instagram Stories", network: "Instagram", ratio: 9 / 16, ratioLabel: "9:16", vertical: true },
  { id: "instagram_reels", label: "Instagram Reels", network: "Instagram", ratio: 9 / 16, ratioLabel: "9:16", vertical: true },
  { id: "tiktok", label: "TikTok", network: "TikTok", ratio: 9 / 16, ratioLabel: "9:16", vertical: true },
];

function defaultPlacement(platform?: string): SocialPlacement {
  const normalized = (platform || "").toLowerCase();
  if (normalized === "tiktok") return "tiktok";
  if (normalized === "facebook") return "facebook_feed";
  if (normalized === "meta" || normalized === "instagram") return "instagram_feed";
  return "generic";
}

export default function SocialCreativePreview({ creative, campaignName, campaignPlatform }: Props) {
  const [placementId, setPlacementId] = useState<SocialPlacement>(() => defaultPlacement(campaignPlatform));
  const [mediaSize, setMediaSize] = useState<{ width: number; height: number } | null>(null);
  const [mediaError, setMediaError] = useState(false);
  const placement = placements.find((item) => item.id === placementId) ?? placements[0];
  const mediaUrl = creative.media_url ? resolveAssetUrl(creative.media_url) : "";

  useEffect(() => {
    setMediaError(false);
    setMediaSize(null);
  }, [creative.id, placementId]);

  useEffect(() => {
    setPlacementId(defaultPlacement(campaignPlatform));
  }, [creative.id, campaignPlatform]);

  const ratioWarning = useMemo(() => {
    if (!mediaSize) return null;
    const actual = mediaSize.width / mediaSize.height;
    const tolerance = placement.vertical ? 0.08 : 0.22;
    return Math.abs(actual - placement.ratio) > tolerance
      ? `A mídia é ${mediaSize.width}×${mediaSize.height}. Para ${placement.label}, prefira ${placement.ratioLabel}; o preview aplica recorte.`
      : null;
  }, [mediaSize, placement]);

  const media = !mediaUrl || mediaError ? (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-surface-03 px-6 text-center text-stone">
      <ImageOff size={32} />
      <p className="text-sm font-bold">Mídia indisponível</p>
      <p className="text-xs">O arquivo não foi encontrado ou não pôde ser carregado.</p>
    </div>
  ) : creative.creative_type === "video" ? (
    <video
      key={`${creative.id}-${placement.id}`}
      src={mediaUrl}
      controls
      muted
      playsInline
      onLoadedMetadata={(event) => setMediaSize({ width: event.currentTarget.videoWidth, height: event.currentTarget.videoHeight })}
      onError={() => setMediaError(true)}
      className={`absolute inset-0 h-full w-full ${placement.id === "generic" ? "object-contain" : "object-cover"}`}
    />
  ) : (
    <img
      key={`${creative.id}-${placement.id}`}
      src={mediaUrl}
      alt={creative.name ?? "Criativo da campanha"}
      onLoad={(event) => setMediaSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })}
      onError={() => setMediaError(true)}
      className={`absolute inset-0 h-full w-full ${placement.id === "generic" ? "object-contain" : "object-cover"}`}
    />
  );

  return (
    <div className="flex min-h-0 w-full flex-col gap-4 md:flex-row">
      <aside className="w-full shrink-0 md:w-56">
        <p className="mb-2 text-xs font-black uppercase tracking-wider text-stone">Visualizar como</p>
        <div className="flex gap-2 overflow-x-auto pb-2 md:flex-col md:overflow-visible">
          {placements.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setPlacementId(item.id)}
              aria-pressed={placementId === item.id}
              className={`whitespace-nowrap rounded-xl border px-3 py-2 text-left text-xs font-bold transition-colors ${
                placementId === item.id
                  ? "border-gold bg-gold/15 text-gold"
                  : "border-surface-03 bg-surface-02 text-parchment hover:border-stone"
              }`}
            >
              {item.label}
              <span className="mt-0.5 block text-[10px] font-medium text-stone">Formato {item.ratioLabel}</span>
            </button>
          ))}
        </div>
        {ratioWarning && (
          <div className="mt-3 flex gap-2 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-xs leading-relaxed text-amber-200" role="status">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>{ratioWarning}</span>
          </div>
        )}
      </aside>

      <div className="min-w-0 flex-1 overflow-y-auto">
        <div className={`mx-auto overflow-hidden bg-black shadow-2xl ${placement.vertical ? "max-w-[340px] rounded-[28px]" : "max-w-[560px] rounded-xl"}`}>
          {placement.id === "generic" ? (
            <GenericPreview creativeName={creative.name} campaignName={campaignName}>{media}</GenericPreview>
          ) : placement.vertical ? (
            <VerticalPreview placement={placement}>{media}</VerticalPreview>
          ) : (
            <FeedPreview placement={placement} campaignName={campaignName} creativeName={creative.name}>{media}</FeedPreview>
          )}
        </div>
        <p className="mx-auto mt-3 max-w-xl text-center text-[11px] leading-relaxed text-stone">
          Simulação visual. Recortes, fontes e controles podem variar no aplicativo da rede social.
        </p>
      </div>
    </div>
  );
}

function GenericPreview({ creativeName, campaignName, children }: { creativeName: string | null; campaignName?: string; children: React.ReactNode }) {
  return <div className="bg-surface-02 text-parchment">
    <div className="border-b border-surface-03 px-4 py-3"><p className="text-xs font-black uppercase tracking-wider text-stone">Preview genérico de anúncio</p><p className="mt-1 text-sm font-bold">{creativeName || campaignName || "Criativo da campanha"}</p></div>
    <div className="relative aspect-video w-full bg-black">{children}</div>
    <p className="px-4 py-3 text-xs text-stone">A plataforma desta campanha não possui uma moldura social aplicável. A mídia original foi preservada.</p>
  </div>;
}

function FeedPreview({ placement, campaignName, creativeName, children }: { placement: Placement; campaignName?: string; creativeName: string | null; children: React.ReactNode }) {
  return (
    <div className="bg-white text-neutral-900">
      <div className="flex items-center gap-3 p-3">
        <div className={`grid h-9 w-9 place-items-center rounded-full text-sm font-black text-white ${placement.network === "Facebook" ? "bg-blue-600" : "bg-gradient-to-tr from-yellow-400 via-pink-500 to-purple-600"}`}>M</div>
        <div className="min-w-0 flex-1"><p className="truncate text-sm font-bold">Sua Loja</p><p className="text-[11px] text-neutral-500">Patrocinado · Público</p></div>
        <span className="text-lg text-neutral-500">•••</span>
      </div>
      <p className="px-3 pb-3 text-sm">{creativeName || campaignName || "Conheça nossas novidades e faça seu pedido."}</p>
      <div className={`relative w-full bg-neutral-900 ${placement.id === "facebook_feed" ? "aspect-[1.91/1]" : "aspect-square"}`}>{children}</div>
      <div className="flex items-center justify-between border-b px-3 py-2 text-xs text-neutral-500"><span>👍 ❤️ 128</span><span>12 comentários</span></div>
      <div className="flex justify-around px-2 py-2 text-xs font-semibold text-neutral-600">
        <span className="flex items-center gap-1"><Heart size={16} /> Curtir</span><span className="flex items-center gap-1"><MessageCircle size={16} /> Comentar</span><span className="flex items-center gap-1"><Share2 size={16} /> Compartilhar</span>
      </div>
    </div>
  );
}

function VerticalPreview({ placement, children }: { placement: Placement; children: React.ReactNode }) {
  const isStory = placement.id === "instagram_story";
  return (
    <div className="relative aspect-[9/16] w-full overflow-hidden bg-neutral-900 text-white">
      {children}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[14%] border-b border-dashed border-white/50 bg-gradient-to-b from-black/70 to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[20%] border-t border-dashed border-white/50 bg-gradient-to-t from-black/80 to-transparent" />
      <div className="pointer-events-none absolute left-3 right-3 top-5 flex items-center gap-2">
        <div className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-tr from-yellow-400 via-pink-500 to-purple-600 text-xs font-black">M</div>
        <span className="text-xs font-bold drop-shadow">sua_loja</span><span className="text-[10px]">Patrocinado</span>
      </div>
      {!isStory && (
        <div className="pointer-events-none absolute bottom-[17%] right-3 flex flex-col items-center gap-4 drop-shadow">
          <Heart size={25} fill="white" /><MessageCircle size={25} fill="white" /><Send size={24} /><Volume2 size={23} />
        </div>
      )}
      <div className="pointer-events-none absolute bottom-5 left-4 right-14 text-xs drop-shadow">
        <p className="font-bold">@sua_loja</p><p className="mt-1 line-clamp-2">Descubra nossas novidades e faça seu pedido.</p>
        {isStory && <div className="mt-3 rounded-full border border-white/70 bg-black/20 py-2 text-center font-bold">Saiba mais</div>}
      </div>
      <span className="pointer-events-none absolute right-2 top-[15%] rounded bg-black/45 px-1.5 py-0.5 text-[9px]">Área segura</span>
    </div>
  );
}

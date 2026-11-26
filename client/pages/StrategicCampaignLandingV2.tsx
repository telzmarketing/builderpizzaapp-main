import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import StrategicCampaignRenderer from "@/components/strategic-campaigns/StrategicCampaignRenderer";
import { strategicCampaignsApi, type ApiStrategicCampaign, type ApiStrategicOffer } from "@/lib/api";
import { captureTrackingFromUrl, trackEvent } from "@/lib/tracking";

export default function StrategicCampaignLandingV2() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<ApiStrategicCampaign | null>(null);
  const [error, setError] = useState("");
  const trackedViewRef = useRef<string | null>(null);

  useEffect(() => { captureTrackingFromUrl(); }, []);

  useEffect(() => {
    if (!slug) return;
    setError("");
    strategicCampaignsApi.publicBySlug(slug).then((data) => {
      setCampaign(data);
      if (trackedViewRef.current !== data.id) {
        trackedViewRef.current = data.id;
        trackEvent("strategic_campaign_view", undefined, { campaign_id: data.id, campaign_slug: data.slug });
      }
    }).catch(() => setError("Campanha não encontrada ou encerrada."));
  }, [slug]);

  const selectOffer = (offer: ApiStrategicOffer) => {
    if (!campaign) return;
    trackEvent("strategic_campaign_offer_click", undefined, { campaign_id: campaign.id, campaign_slug: campaign.slug, offer_id: offer.id });
    const context = new URLSearchParams({ strategic_offer_id: offer.id, strategic_campaign_id: campaign.id, strategic_campaign_slug: campaign.slug });
    if (offer.product_id) navigate(`/product/${encodeURIComponent(offer.product_id)}?${context.toString()}`);
    else if (offer.kit_id) navigate(`/combo/${encodeURIComponent(offer.kit_id)}?${context.toString()}`);
  };

  if (error) return <div className="flex min-h-screen items-center justify-center bg-surface-00 p-6 text-center text-cream"><div><p className="text-xl font-bold">{error}</p><button onClick={() => navigate("/")} className="mt-4 rounded-lg bg-gold px-4 py-2 text-surface-00">Voltar</button></div></div>;
  if (!campaign) return <div className="flex min-h-screen items-center justify-center bg-surface-00 text-gold" role="status">Carregando campanha...</div>;

  return <main className="min-h-screen"><StrategicCampaignRenderer campaign={campaign} mode="public" onOfferSelect={selectOffer} /></main>;
}

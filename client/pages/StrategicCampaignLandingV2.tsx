import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import StrategicCampaignRenderer from "@/components/strategic-campaigns/StrategicCampaignRenderer";
import StrategicOfferConfigurator from "@/components/strategic-campaigns/StrategicOfferConfigurator";
import {
  strategicCampaignsApi,
  type ApiStrategicCampaign,
  type ApiStrategicOffer,
} from "@/lib/api";
import { useApp, type StrategicCartMeta } from "@/context/AppContext";
import {
  normalizeStrategicOfferConfiguration,
  type StrategicOfferConfiguration,
} from "@/lib/strategicOfferSelection";
import { captureTrackingFromUrl, trackEvent } from "@/lib/tracking";

type PublicStrategicCampaignApi = typeof strategicCampaignsApi & {
  publicOfferConfiguration: (
    offerId: string,
    campaignVersion?: number,
  ) => ReturnType<typeof strategicCampaignsApi.getOfferConfiguration>;
};

export default function StrategicCampaignLandingV2() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { addToCart, multiFlavorsConfig } = useApp();
  const [campaign, setCampaign] = useState<ApiStrategicCampaign | null>(null);
  const [error, setError] = useState("");
  const [configuration, setConfiguration] =
    useState<StrategicOfferConfiguration | null>(null);
  const trackedViewRef = useRef<string | null>(null);

  useEffect(() => {
    captureTrackingFromUrl();
  }, []);

  useEffect(() => {
    if (!slug) return;
    setError("");
    strategicCampaignsApi
      .publicBySlug(slug)
      .then((data) => {
        setCampaign(data);
        if (trackedViewRef.current !== data.id) {
          trackedViewRef.current = data.id;
          trackEvent("strategic_campaign_view", undefined, {
            campaign_id: data.id,
            campaign_slug: data.slug,
          });
        }
      })
      .catch(() => setError("Campanha não encontrada ou encerrada."));
  }, [slug]);

  const selectOffer = async (offer: ApiStrategicOffer) => {
    if (!campaign) return;
    trackEvent("strategic_campaign_offer_click", undefined, {
      campaign_id: campaign.id,
      campaign_slug: campaign.slug,
      offer_id: offer.id,
    });
    const context = new URLSearchParams({
      strategic_offer_id: offer.id,
      strategic_campaign_id: campaign.id,
      strategic_campaign_slug: campaign.slug,
      strategic_campaign_version: String(campaign.published_version ?? 1),
      strategic_composition_revision: String(offer.composition_revision),
      strategic_reference_type: offer.reference_type,
    });
    if (
      offer.reference_type === "subcategory" ||
      offer.reference_type === "mixed_subcategories"
    ) {
      try {
        const raw = await (
          strategicCampaignsApi as PublicStrategicCampaignApi
        ).publicOfferConfiguration(
          offer.id,
          campaign.published_version ?? undefined,
        );
        setConfiguration({
          ...normalizeStrategicOfferConfiguration(raw),
          title: offer.title,
        });
      } catch {
        setError("Não foi possível abrir esta oferta.");
      }
    } else if (offer.product_id)
      navigate(
        `/product/${encodeURIComponent(offer.product_id)}?${context.toString()}`,
      );
    else if (offer.kit_id)
      navigate(
        `/combo/${encodeURIComponent(offer.kit_id)}?${context.toString()}`,
      );
  };

  if (error)
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-00 p-6 text-center text-cream">
        <div>
          <p className="text-xl font-bold">{error}</p>
          <button
            onClick={() => navigate("/")}
            className="mt-4 rounded-lg bg-gold px-4 py-2 text-surface-00"
          >
            Voltar
          </button>
        </div>
      </div>
    );
  if (!campaign)
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-surface-00 text-gold"
        role="status"
      >
        Carregando campanha...
      </div>
    );

  if (configuration)
    return (
      <main className="min-h-screen bg-surface-00">
        <StrategicOfferConfigurator
          configuration={configuration}
          flavorConfig={multiFlavorsConfig}
          onCancel={() => setConfiguration(null)}
          onComplete={({ configured, instanceId }) => {
            configured.forEach(({ args, step }) => {
              const forwarded = [...args] as unknown[];
              const strategic: StrategicCartMeta = {
                campaignId: configuration.campaign_id,
                offerId: configuration.offer_id,
                campaignSlug: campaign.slug,
                group: {
                  instanceId,
                  name: configuration.title,
                  campaignVersion: configuration.campaign_version,
                  compositionRevision: configuration.composition_revision,
                  referenceType: configuration.reference_type,
                  stepKey: step.key,
                  sourceSubcategoryId: step.subcategory_id,
                  quantity: 1,
                },
              };
              forwarded[15] = strategic;
              (addToCart as (...values: unknown[]) => void)(...forwarded);
            });
            navigate("/cart");
          }}
        />
      </main>
    );

  return (
    <main className="min-h-screen">
      <StrategicCampaignRenderer
        campaign={campaign}
        mode="public"
        onOfferSelect={selectOffer}
      />
    </main>
  );
}

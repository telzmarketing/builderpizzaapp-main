import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import StrategicCampaignRenderer from "@/components/strategic-campaigns/StrategicCampaignRenderer";
import StrategicOfferConfigurator from "@/components/strategic-campaigns/StrategicOfferConfigurator";
import {
  strategicCampaignsApi,
  type ApiStrategicCampaign,
  type ApiStrategicOffer,
  type ApiStrategicCampaignAvailability,
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

const localDateTimeValue = (value: string) => {
  const date = new Date(value);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

export default function StrategicCampaignLandingV2() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { addToCart, multiFlavorsConfig } = useApp();
  const [campaign, setCampaign] = useState<ApiStrategicCampaign | null>(null);
  const [error, setError] = useState("");
  const [configuration, setConfiguration] =
    useState<StrategicOfferConfiguration | null>(null);
  const [pendingOffer, setPendingOffer] = useState<ApiStrategicOffer | null>(null);
  const [availability, setAvailability] = useState<ApiStrategicCampaignAvailability | null>(null);
  const [selectedScheduledFor, setSelectedScheduledFor] = useState("");
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
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

  const openOffer = async (offer: ApiStrategicOffer, scheduledFor = "") => {
    if (!campaign) return;
    setPendingOffer(null);
    setAvailability(null);
    if (scheduledFor) sessionStorage.setItem("telz:strategic-scheduled-for", scheduledFor);
    else sessionStorage.removeItem("telz:strategic-scheduled-for");
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

  const selectOffer = async (offer: ApiStrategicOffer) => {
    if (!campaign) return;
    const mode = campaign.commercial_config.sales_mode;
    setAvailabilityLoading(true);
    setSelectedScheduledFor("");
    try {
      const currentAvailability = await strategicCampaignsApi.publicAvailability(campaign.id, offer.id);
      const hasAvailableSlot = currentAvailability.dates.some((day) =>
        day.slots.some((slot) => slot.available),
      );
      if (hasAvailableSlot || mode === "hybrid" || mode === "preorder") {
        setAvailability(currentAvailability);
        setPendingOffer(offer);
      } else {
        await openOffer(offer);
      }
    } catch {
      setAvailability(null);
      if (mode === "preorder" || mode === "hybrid") {
        setError("Não foi possível carregar os horários disponíveis.");
      } else {
        await openOffer(offer);
      }
    } finally {
      setAvailabilityLoading(false);
    }
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
                scheduledFor: sessionStorage.getItem("telz:strategic-scheduled-for"),
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
    pendingOffer ? (
      <main className="flex min-h-screen items-start justify-center bg-surface-00 p-4 text-cream sm:p-8">
        <section className="w-full max-w-xl space-y-5 rounded-2xl border border-surface-03 bg-surface-01 p-5">
          <button type="button" onClick={() => { setPendingOffer(null); setAvailability(null); }} className="text-sm text-stone hover:text-cream">← Voltar para ofertas</button>
          <div><p className="text-xs font-black uppercase tracking-widest text-gold">Disponibilidade</p><h1 className="text-xl font-black">Quando você quer receber?</h1><p className="mt-1 text-sm text-stone">Escolha o horário antes de montar sua pizza.</p></div>
          {availabilityLoading ? <p role="status" className="text-stone">Carregando horários...</p> : (
            <div className="space-y-3">
              {campaign.commercial_config.sales_mode !== "preorder" && <button type="button" onClick={() => openOffer(pendingOffer)} className="w-full rounded-xl border border-gold bg-gold/10 p-4 text-left"><strong>Agora</strong><span className="mt-1 block text-xs text-stone">Venda imediata, se a loja estiver aberta.</span></button>}
              {availability?.dates.flatMap((day) => day.slots).filter((slot) => slot.available).map((slot) => <button key={slot.id} type="button" onClick={() => { const value = localDateTimeValue(slot.starts_at); setSelectedScheduledFor(value); openOffer(pendingOffer, value); }} className={`w-full rounded-xl border p-4 text-left ${selectedScheduledFor === localDateTimeValue(slot.starts_at) ? "border-gold bg-gold/10" : "border-surface-03 bg-surface-02"}`}><strong>{slot.label || new Date(slot.starts_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</strong><span className="mt-1 block text-xs text-stone">{slot.remaining_capacity} vagas disponíveis</span></button>)}
              {campaign.commercial_config.sales_mode === "preorder" && !availability?.dates.some((day) => day.slots.some((slot) => slot.available)) && <p role="alert" className="rounded-xl bg-amber-500/10 p-4 text-amber-200">Nenhum horário disponível para esta oferta.</p>}
            </div>
          )}
        </section>
      </main>
    ) : (
    <main className="min-h-screen">
      <StrategicCampaignRenderer
        campaign={campaign}
        mode="public"
        onOfferSelect={selectOffer}
      />
    </main>
    )
  );
}

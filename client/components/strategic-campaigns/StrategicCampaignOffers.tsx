import { useEffect, useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { strategicCampaignsApi } from "@/lib/api";
import {
  normalizeStrategicOfferConfiguration,
  type AvailableStrategicCampaign,
  type AvailableStrategicOffer,
  type StrategicEntryChannel,
  type StrategicOfferConfiguration,
} from "@/lib/strategicOfferSelection";

type AvailableOffersApi = typeof strategicCampaignsApi & {
  listAvailableOffers: (
    campaignId: string,
    entryChannel: StrategicEntryChannel,
  ) => Promise<AvailableStrategicOffer[]>;
};

export default function StrategicCampaignOffers({
  campaign,
  entryChannel,
  query,
  onConfigure,
  onSelectKit,
}: {
  campaign: AvailableStrategicCampaign;
  entryChannel: StrategicEntryChannel;
  query: string;
  onConfigure: (configuration: StrategicOfferConfiguration) => void;
  onSelectKit?: (offer: AvailableStrategicOffer) => void;
}) {
  const [offers, setOffers] = useState<AvailableStrategicOffer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [opening, setOpening] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    (strategicCampaignsApi as AvailableOffersApi)
      .listAvailableOffers(campaign.id, entryChannel)
      .then((value) => {
        if (active) setOffers(value);
      })
      .catch(() => {
        if (active)
          setError("Não foi possível carregar as ofertas desta campanha.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [campaign.id, entryChannel]);
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const visible = offers.filter(
    (offer) =>
      !normalizedQuery ||
      `${offer.title} ${offer.description || ""}`
        .toLocaleLowerCase()
        .includes(normalizedQuery),
  );
  if (loading)
    return (
      <p
        role="status"
        className="col-span-full flex items-center justify-center gap-2 py-8 text-stone"
      >
        <Loader2 className="animate-spin" size={18} /> Carregando ofertas...
      </p>
    );
  if (error)
    return (
      <p
        role="alert"
        className="col-span-full rounded-xl bg-red-500/10 p-4 text-red-200"
      >
        {error}
      </p>
    );
  if (!visible.length)
    return (
      <p className="col-span-full py-8 text-center text-stone">
        Nenhuma oferta disponível nesta campanha.
      </p>
    );
  return (
    <>
      {visible.map((offer) => {
        const soldOut = offer.available === false;
        return (
          <button
            key={offer.id}
            type="button"
            disabled={opening === offer.id || soldOut}
            onClick={async () => {
              setOpening(offer.id);
              setError("");
              try {
                if (offer.reference_type === "kit" && onSelectKit) {
                  onSelectKit(offer);
                  return;
                }
                const raw = await strategicCampaignsApi.getOfferConfiguration(
                  offer.id,
                  campaign.published_version,
                );
                const configuration = normalizeStrategicOfferConfiguration(raw);
                onConfigure({
                  ...configuration,
                  title:
                    configuration.title === "Oferta estratégica"
                      ? offer.title
                      : configuration.title,
                });
              } catch {
                setError("Não foi possível abrir a configuração desta oferta.");
              } finally {
                setOpening(null);
              }
            }}
            className="group relative flex min-h-44 min-w-0 flex-col items-center gap-3 rounded-2xl border border-surface-03 bg-surface-02 p-4 text-center transition-all hover:-translate-y-0.5 hover:border-gold/60 disabled:opacity-60"
          >
            <span className="text-xs font-black uppercase tracking-widest text-gold">
              {offer.badge_text || "Oferta especial"}
            </span>
            <strong>{offer.title}</strong>
            {offer.description && (
              <span className="text-xs text-stone">{offer.description}</span>
            )}
            {offer.price_promotional != null && (
              <span className="font-black text-gold">
                {offer.reference_type === "subcategory" ||
                offer.reference_type === "mixed_subcategories"
                  ? "A partir de "
                  : ""}
                R$ {offer.price_promotional.toFixed(2).replace(".", ",")}
              </span>
            )}
            <span
              className={
                soldOut
                  ? "text-xs font-bold text-red-300"
                  : "text-xs font-bold text-emerald-300"
              }
            >
              {soldOut
                ? "Esgotada"
                : opening === offer.id
                  ? "Abrindo..."
                  : offer.button_text || "Configurar oferta"}
            </span>
            {!soldOut && (
              <span className="absolute bottom-3 right-3 grid h-9 w-9 place-items-center rounded-full bg-gold text-black">
                <Plus size={17} />
              </span>
            )}
          </button>
        );
      })}
    </>
  );
}

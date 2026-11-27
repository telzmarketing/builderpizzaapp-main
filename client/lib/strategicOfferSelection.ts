import type { ProductConfiguratorProps } from "@/pages/Product";
import type {
  ApiAvailableStrategicCampaign,
  ApiProduct,
  ApiStrategicOffer,
  ApiStrategicOfferConfiguration,
  ApiStrategicOfferConfigurationStep,
  StrategicEntryChannel,
  StrategicOfferSelectionIn,
} from "./api";
import {
  configuredManualLine,
  type ManualCartLine,
  type StrategicManualGroupMeta,
} from "./manualOrder";

export type AvailableStrategicCampaign = ApiAvailableStrategicCampaign;
export type AvailableStrategicOffer = ApiStrategicOffer;
export type { StrategicEntryChannel };

export interface StrategicOfferStep extends ApiStrategicOfferConfigurationStep {
  title: string;
}

export interface StrategicOfferConfiguration extends Omit<ApiStrategicOfferConfiguration, "steps"> {
  title: string;
  steps: StrategicOfferStep[];
}

export type ProductConfigurationArgs = Parameters<
  NonNullable<ProductConfiguratorProps["onAdd"]>
>;

export interface ConfiguredStrategicStep {
  step: StrategicOfferStep;
  args: ProductConfigurationArgs;
  line: ManualCartLine;
}

export type StrategicOfferSelection = StrategicOfferSelectionIn;

function numberValue(value: unknown, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function referenceType(value: unknown): StrategicOfferConfiguration["reference_type"] {
  return value === "kit" || value === "subcategory" || value === "mixed_subcategories"
    ? value
    : "product";
}

export function campaignLabel(campaign: AvailableStrategicCampaign) {
  return campaign.commercial_name?.trim() || campaign.name?.trim() || "Campanha";
}

export function strategicCampaignTab(campaignId: string) {
  return `strategic:${campaignId}`;
}

export function strategicCampaignIdFromTab(tab: string) {
  return tab.startsWith("strategic:") ? tab.slice("strategic:".length) : null;
}

export function normalizeStrategicOfferConfiguration(
  raw: unknown,
): StrategicOfferConfiguration {
  const value = (raw && typeof raw === "object" ? raw : {}) as Record<
    string,
    unknown
  >;
  const rawSteps = Array.isArray(value.steps) ? value.steps : [];
  const steps = rawSteps
    .map((candidate, index): StrategicOfferStep | null => {
      if (!candidate || typeof candidate !== "object") return null;
      const step = candidate as Record<string, unknown>;
      const products = Array.isArray(step.eligible_products)
        ? (step.eligible_products as ApiProduct[])
        : [];
      return {
        key: String(step.key || `step-${index + 1}`),
        position: numberValue(step.position, index + 1),
        subcategory_id: String(step.subcategory_id || ""),
        title: String(step.title || step.subcategory_name || `Item ${index + 1}`),
        eligible_products: products as ApiStrategicOfferConfigurationStep["eligible_products"],
        restrictions: step.restrictions && typeof step.restrictions === "object"
          ? step.restrictions as Record<string, unknown>
          : {},
      };
    })
    .filter((step): step is StrategicOfferStep => !!step)
    .sort((left, right) => left.position - right.position);
  return {
    offer_id: String(value.offer_id || ""),
    campaign_id: String(value.campaign_id || ""),
    campaign_version: numberValue(value.campaign_version, 1),
    composition_revision: numberValue(value.composition_revision, 1),
    reference_type: referenceType(value.reference_type),
    pricing_strategy: value.pricing_strategy
      ? String(value.pricing_strategy) as StrategicOfferConfiguration["pricing_strategy"]
      : "catalog",
    price_range: (value.price_range && typeof value.price_range === "object"
      ? value.price_range
      : { minimum: 0, maximum: 0, fixed_promotional: null }) as StrategicOfferConfiguration["price_range"],
    title: String(value.title || value.offer_title || "Oferta estratégica"),
    steps,
  };
}

export function buildStrategicOfferSelection(
  configuration: StrategicOfferConfiguration,
  configured: ConfiguredStrategicStep[],
  instanceId = crypto.randomUUID(),
): { selection: StrategicOfferSelection; lines: ManualCartLine[]; instanceId: string } {
  if (!configuration.steps.length || configured.length !== configuration.steps.length) {
    throw new Error("Configure todos os itens da oferta antes de continuar.");
  }
  const groupBase: StrategicManualGroupMeta = {
    instanceId,
    name: configuration.title,
    campaignVersion: configuration.campaign_version,
    compositionRevision: configuration.composition_revision,
    referenceType: configuration.reference_type,
  };
  const lines = configured.map(({ line, step }) => ({
    ...line,
    strategic: {
      campaignId: configuration.campaign_id,
      offerId: configuration.offer_id,
      group: {
        ...groupBase,
        sourceSubcategoryId: step.subcategory_id,
        stepKey: step.key,
      },
    },
  }));
  return {
    lines,
    instanceId,
    selection: {
      offer_id: configuration.offer_id,
      campaign_version: configuration.campaign_version,
      composition_revision: configuration.composition_revision,
      quantity: 1,
      selections: lines.map((line, index) => ({
        step_key: configured[index].step.key,
        item: line.item,
      })),
    },
  };
}

export function configuredStrategicStep(
  step: StrategicOfferStep,
  args: ProductConfigurationArgs,
): ConfiguredStrategicStep {
  return {
    step,
    args,
    line: configuredManualLine(args, `strategic:${step.key}:${crypto.randomUUID()}`),
  };
}


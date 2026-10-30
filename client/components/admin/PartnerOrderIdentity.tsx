import { ImageOff } from "lucide-react";
import { resolveAssetUrl, type ApiOrder } from "@/lib/api";
import { partnerLogoUrl, partnerOriginLabel } from "@/lib/partnerIdentification";

type IdentitySource = Pick<ApiOrder, "order_origin" | "partner_order_number" | "partner_logo_url" | "order_identification"> & { order_origin?: string | null };

export default function PartnerOrderIdentity({ order, compact = false, className = "" }: { order: IdentitySource; compact?: boolean; className?: string }) {
  const label = partnerOriginLabel(order.order_origin);
  const logo = order.partner_logo_url || order.order_identification?.logo_url || partnerLogoUrl(order.order_origin);
  const resolvedLabel = order.order_identification?.display_name || label;
  return (
    <div className={`flex min-w-0 items-center gap-2 ${className}`} data-testid="partner-order-identity">
      <span className={`flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-gold/30 bg-gold/10 ${compact ? "h-7 w-7" : "h-9 w-9"}`}>
        {logo ? <img src={resolveAssetUrl(logo)} alt={`Logo ${resolvedLabel}`} className="max-h-full max-w-full object-contain p-1" /> : <ImageOff size={compact ? 13 : 16} className="text-gold" aria-hidden="true" />}
      </span>
      <span className="min-w-0 truncate text-[11px] font-black uppercase tracking-wide text-gold">
        {resolvedLabel}{order.partner_order_number ? ` · ${order.partner_order_number}` : ""}
      </span>
    </div>
  );
}

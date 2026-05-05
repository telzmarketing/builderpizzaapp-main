import { useEffect, useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { CreditCard, Loader2 } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { paymentsApi } from "@/lib/api";

function isMercadoPagoCheckoutUrl(value: string): boolean {
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    return url.protocol === "https:" && (
      host === "www.mercadopago.com.br" ||
      host === "mercadopago.com.br" ||
      host.endsWith(".mercadopago.com.br") ||
      host === "www.mercadopago.com" ||
      host === "mercadopago.com" ||
      host.endsWith(".mercadopago.com")
    );
  } catch {
    return false;
  }
}

export default function PaymentCheckout() {
  const [searchParams] = useSearchParams();
  const orderId = searchParams.get("orderId") || "";
  const directUrl = searchParams.get("url") || "";
  const [checkoutUrl, setCheckoutUrl] = useState("");
  const [error, setError] = useState("");

  const trackingUrl = useMemo(
    () => orderId ? `/order-tracking?orderId=${encodeURIComponent(orderId)}` : "/checkout",
    [orderId],
  );

  useEffect(() => {
    if (directUrl && isMercadoPagoCheckoutUrl(directUrl)) {
      setCheckoutUrl(directUrl);
      return;
    }
    if (!orderId) {
      setError("Pedido nao encontrado para abrir o pagamento.");
      return;
    }
    paymentsApi.getByOrder(orderId)
      .then((payment) => {
        if (payment.payment_url && isMercadoPagoCheckoutUrl(payment.payment_url)) {
          setCheckoutUrl(payment.payment_url);
        } else {
          setError("Checkout de cartao nao encontrado para este pedido.");
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Nao foi possivel abrir o checkout de cartao.");
      });
  }, [directUrl, orderId]);

  useEffect(() => {
    if (!checkoutUrl) return;
    const id = window.setTimeout(() => {
      window.location.assign(checkoutUrl);
    }, 600);
    return () => window.clearTimeout(id);
  }, [checkoutUrl]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      <div className="bg-brand-dark px-4 py-3 flex justify-center sticky top-0 z-30">
        <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
      </div>
      <main className="px-4 py-12">
        <section className="mx-auto max-w-sm rounded-xl border border-surface-03 bg-surface-02 p-5 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-gold/15 text-gold">
            {error ? <CreditCard size={24} /> : <Loader2 size={24} className="animate-spin" />}
          </div>
          <h1 className="mb-2 text-xl font-bold text-cream">
            {error ? "Pagamento indisponivel" : "Abrindo checkout de cartao"}
          </h1>
          <p className="mb-5 text-sm leading-relaxed text-stone">
            {error || "Voce sera direcionado para preencher os dados do cartao no checkout seguro."}
          </p>
          {checkoutUrl ? (
            <a
              href={checkoutUrl}
              className="block w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white transition-colors hover:bg-blue-500"
            >
              Continuar para o checkout
            </a>
          ) : (
            <Link
              to={trackingUrl}
              className="block w-full rounded-xl bg-gold px-4 py-3 text-sm font-bold text-cream transition-colors hover:bg-gold/90"
            >
              Voltar ao pedido
            </Link>
          )}
        </section>
      </main>
    </div>
  );
}

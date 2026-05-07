import { useEffect, useRef, useState } from "react";
import { ShoppingBag, X } from "lucide-react";
import { useLocation } from "react-router-dom";
import {
  isAssetUrl,
  resolveAssetUrl,
  storeNotificationsApi,
  type ApiStoreNotificationNext,
  type ApiStoreNotificationPage,
} from "@/lib/api";

function pageFromPath(pathname: string): ApiStoreNotificationPage | null {
  if (pathname === "/") return "home";
  if (pathname === "/cardapio") return "cardapio";
  if (pathname.startsWith("/product/")) return "product";
  if (pathname === "/cart") return "cart";
  return null;
}

export default function StoreSocialProofNotification() {
  const { pathname } = useLocation();
  const page = pageFromPath(pathname);
  const [notification, setNotification] = useState<ApiStoreNotificationNext | null>(null);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dismissedRef = useRef(false);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setNotification(null);
    setVisible(false);
    dismissedRef.current = false;
    if (!page) return;

    let cancelled = false;

    const schedule = (seconds: number) => {
      if (cancelled) return;
      timerRef.current = setTimeout(fetchNext, Math.max(5, seconds) * 1000);
    };

    const fetchNext = async () => {
      if (cancelled || dismissedRef.current) return;
      try {
        const result = await storeNotificationsApi.next(page);
        if (cancelled) return;
        if (!result.notification) {
          schedule(result.next_delay_seconds);
          return;
        }
        setNotification(result.notification);
        setVisible(true);
        timerRef.current = setTimeout(() => {
          setVisible(false);
          timerRef.current = setTimeout(() => {
            setNotification(null);
            schedule(result.next_delay_seconds);
          }, 350);
        }, Math.max(3, result.notification.display_seconds) * 1000);
      } catch {
        schedule(45);
      }
    };

    schedule(8);
    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [page]);

  if (!notification || !page) return null;

  const productImage = notification.product_image;
  const hasImage = isAssetUrl(productImage);

  return (
    <div className="pointer-events-none fixed bottom-[7.75rem] left-3 right-auto z-40 sm:left-5 sm:bottom-6">
      <div
        className={`pointer-events-auto w-[min(21rem,calc(100vw-6rem))] transform rounded-2xl border border-gold/25 bg-surface-02/95 p-3 text-cream shadow-2xl backdrop-blur transition-all duration-300 sm:max-w-sm ${
          visible ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"
        }`}
      >
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-surface-03 bg-surface-03">
            {hasImage ? (
              <img src={resolveAssetUrl(productImage)} alt="" className="h-full w-full object-cover" />
            ) : (
              <ShoppingBag size={18} className="text-gold" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium leading-snug">{notification.message}</p>
            <p className="mt-1 text-xs text-stone">
              Pedido confirmado na loja
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              dismissedRef.current = true;
              setVisible(false);
              if (timerRef.current) clearTimeout(timerRef.current);
              timerRef.current = setTimeout(() => setNotification(null), 250);
            }}
            className="rounded-lg p-1 text-stone transition-colors hover:bg-surface-03 hover:text-cream"
            aria-label="Fechar notificacao"
          >
            <X size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

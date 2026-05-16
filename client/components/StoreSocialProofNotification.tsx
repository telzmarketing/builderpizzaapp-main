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

const SEEN_KEY = "sn_seen";
const ANON_KEY = "sn_anon_session";
const SEEN_MAX = 60;
const SEEN_EXPIRY_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

type SeenEntry = { id: string; ts: number };

function loadSeenIds(): string[] {
  try {
    const raw = localStorage.getItem(SEEN_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SeenEntry[];
    const cutoff = Date.now() - SEEN_EXPIRY_MS;
    return parsed.filter((e) => e.ts > cutoff).map((e) => e.id);
  } catch {
    return [];
  }
}

function addSeenId(id: string): void {
  try {
    const raw = localStorage.getItem(SEEN_KEY);
    const parsed: SeenEntry[] = raw ? JSON.parse(raw) : [];
    const cutoff = Date.now() - SEEN_EXPIRY_MS;
    const filtered = parsed.filter((e) => e.ts > cutoff && e.id !== id);
    filtered.push({ id, ts: Date.now() });
    localStorage.setItem(SEEN_KEY, JSON.stringify(filtered.slice(-SEEN_MAX)));
  } catch {}
}

function getStoredCustomerId(): string | undefined {
  try {
    const raw = localStorage.getItem("customer");
    if (!raw) return undefined;
    const c = JSON.parse(raw) as { id?: string };
    return c.id || undefined;
  } catch {
    return undefined;
  }
}

function getAnonymousSessionId(): string {
  try {
    const existing = localStorage.getItem(ANON_KEY);
    if (existing) return existing;
    const generated = `snanon-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(ANON_KEY, generated);
    return generated;
  } catch {
    return `snanon-${Date.now().toString(36)}`;
  }
}

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
  const isFirstRef = useRef(true);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setNotification(null);
    setVisible(false);
    dismissedRef.current = false;
    isFirstRef.current = true;
    if (!page) return;

    let cancelled = false;

    const schedule = (seconds: number) => {
      if (cancelled) return;
      timerRef.current = setTimeout(fetchNext, Math.max(1, seconds) * 1000);
    };

    const fetchNext = async () => {
      if (cancelled || dismissedRef.current) return;
      try {
        const seenIds = loadSeenIds();
        const customerId = getStoredCustomerId();
        const anonymousSessionId = getAnonymousSessionId();
        const result = await storeNotificationsApi.next(page, {
          seen_ids: seenIds.length ? seenIds.join(",") : undefined,
          customer_id: customerId,
          anonymous_session_id: anonymousSessionId,
        });
        if (cancelled) return;

        if (!result.notification) {
          schedule(result.next_delay_seconds);
          return;
        }

        const notifId = result.notification.notification_id;
        if (notifId && seenIds.includes(notifId)) {
          schedule(result.next_delay_seconds);
          return;
        }

        const showAfter = isFirstRef.current
          ? Math.max(1, result.initial_delay_seconds ?? 5)
          : 0;
        isFirstRef.current = false;

        timerRef.current = setTimeout(() => {
          if (cancelled || dismissedRef.current) return;
          setNotification(result.notification);
          setVisible(true);
          if (notifId) {
            addSeenId(notifId);
            storeNotificationsApi.recordImpression(notifId, {
              page,
              customer_id: customerId,
              anonymous_session_id: anonymousSessionId,
            }).catch(() => {});
          }

          timerRef.current = setTimeout(() => {
            setVisible(false);
            timerRef.current = setTimeout(() => {
              setNotification(null);
              schedule(result.next_delay_seconds);
            }, 350);
          }, Math.max(3, result.notification!.display_seconds) * 1000);
        }, showAfter * 1000);
      } catch {
        schedule(45);
      }
    };

    schedule(0);
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

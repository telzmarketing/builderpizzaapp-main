import { useEffect, useState } from "react";
import { Clock, Store } from "lucide-react";
import { storeOperationApi, type StoreOperationStatus } from "@/lib/api";

export default function StoreStatusBanner({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<StoreOperationStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => storeOperationApi.status().then((data) => {
      if (!cancelled) setStatus(data);
    }).catch(() => {});
    load();
    const id = window.setInterval(load, 60000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (!status) return null;

  return (
    <div className={`rounded-xl border px-4 py-3 ${status.is_open ? "bg-emerald-500/10 border-emerald-500/30" : "bg-red-500/10 border-red-500/30"}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 h-8 w-8 rounded-lg flex items-center justify-center ${status.is_open ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"}`}>
          <Store size={16} />
        </div>
        <div className="min-w-0">
          <p className={`text-sm font-bold ${status.is_open ? "text-emerald-300" : "text-red-300"}`}>
            {status.status_label}
          </p>
          {!compact && (
            <p className="text-stone text-xs mt-0.5">
              Hoje: {status.today_hours}
              {!status.is_open && status.next_opening_label ? ` · Volta ${status.next_opening_label}` : ""}
            </p>
          )}
          {!status.is_open && (
            <p className="text-parchment text-xs mt-1 flex items-center gap-1">
              <Clock size={12} /> {status.message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

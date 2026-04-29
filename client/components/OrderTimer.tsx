import { useEffect, useState } from "react";
import { Clock3, AlertTriangle, CheckCircle2 } from "lucide-react";

interface OrderTimerProps {
  paidAt: string | null;
  deliveredAt?: string | null;
  targetMinutes?: number;
  status?: string;
}

export default function OrderTimer({
  paidAt,
  deliveredAt,
  targetMinutes = 45,
  status: _status,
}: OrderTimerProps) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (deliveredAt || !paidAt) return;
    const id = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(id);
  }, [paidAt, deliveredAt]);

  if (!paidAt) return null;

  const paidMs = new Date(paidAt).getTime();
  const endMs = deliveredAt ? new Date(deliveredAt).getTime() : now;
  const elapsedMin = Math.floor((endMs - paidMs) / 60000);
  const isDelivered = !!deliveredAt;
  const isLate = elapsedMin >= targetMinutes;
  const isWarning = !isLate && elapsedMin >= Math.floor(targetMinutes * 0.78);

  if (isDelivered) {
    const onTime = elapsedMin <= targetMinutes;
    return (
      <div className="mt-2 rounded-lg bg-surface-02/70 px-3 py-2 space-y-0.5">
        <div className={`flex items-center gap-1.5 text-xs font-bold ${onTime ? "text-green-400" : "text-red-400"}`}>
          <CheckCircle2 size={12} />
          <span>Entregue em {elapsedMin} min</span>
        </div>
        <p className="text-stone text-[10px]">Meta: {targetMinutes} min</p>
      </div>
    );
  }

  const iconColor = isLate
    ? "text-red-400"
    : isWarning
    ? "text-amber-400"
    : "text-green-400";

  const textColor = isLate
    ? "text-red-400"
    : isWarning
    ? "text-amber-400"
    : "text-green-400";

  const Icon = isLate || isWarning ? AlertTriangle : Clock3;

  return (
    <div className="mt-2 rounded-lg bg-surface-02/70 px-3 py-2 space-y-0.5">
      <div className="flex items-center justify-between gap-2">
        <div className={`flex items-center gap-1.5 text-xs font-bold ${textColor}`}>
          <Icon size={12} className={iconColor} />
          <span>{elapsedMin} min</span>
        </div>
        {isLate && (
          <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-[9px] font-black text-red-400 uppercase tracking-wide">
            Atrasado
          </span>
        )}
      </div>
      <p className="text-stone text-[10px]">Meta: {targetMinutes} min</p>
    </div>
  );
}

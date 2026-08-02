import { useEffect, useState } from "react";
import { Clock3, Headphones, Loader2, X } from "lucide-react";
import { platformSupportApi } from "@/lib/api";
import {
  isPlatformSupportSessionActive,
  readPlatformSupportSession,
  restorePlatformMasterSession,
  type PlatformSupportSessionState,
} from "@/lib/platformSupportSession";

export default function PlatformSupportBanner() {
  const [session, setSession] = useState<PlatformSupportSessionState | null>(() => readPlatformSupportSession());
  const [now, setNow] = useState(Date.now());
  const [ending, setEnding] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!session) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [session]);

  const remainingSeconds = session
    ? Math.max(0, Math.floor((Date.parse(session.expires_at) - now) / 1000))
    : 0;
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = String(remainingSeconds % 60).padStart(2, "0");
  const active = isPlatformSupportSessionActive(session, now);

  async function end() {
    if (!session || ending) return;
    setEnding(true);
    setError("");
    try {
      await platformSupportApi.end(session.session_id, session.master_token);
      restorePlatformMasterSession();
      setSession(null);
      window.location.replace("/painel/plataforma");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel encerrar a sessao.");
      setEnding(false);
    }
  }

  useEffect(() => {
    if (session && !active && !ending) void end();
  }, [active, ending, session]);

  if (!session) return null;

  return (
    <div className="border-b border-yellow-400/40 bg-yellow-400/15 px-4 py-2 text-yellow-50">
      <div className="mx-auto flex max-w-[100rem] flex-col gap-2 text-xs sm:flex-row sm:items-center">
        <span className="flex items-center gap-2 font-black"><Headphones size={15} /> Modo suporte: {session.tenant_name}</span>
        <span className="flex items-center gap-1 text-yellow-100/80"><Clock3 size={13} /> {active ? `${minutes}:${seconds} restantes` : "sessao expirada"}</span>
        {error && <span className="text-red-200">{error}</span>}
        <button type="button" disabled={ending} onClick={() => void end()} className="ml-auto inline-flex items-center gap-2 rounded-lg border border-yellow-200/40 px-3 py-1.5 font-black hover:bg-yellow-200/10 disabled:opacity-50">
          {ending ? <Loader2 size={13} className="animate-spin" /> : <X size={13} />}
          Encerrar e voltar ao Master
        </button>
      </div>
    </div>
  );
}

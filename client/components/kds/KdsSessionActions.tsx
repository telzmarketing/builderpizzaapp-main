import { LogOut } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { clearAdminSession } from "@/lib/adminSession";
import { rememberPwaContext } from "@/lib/motoboyPwa";

export default function KdsSessionActions() {
  const navigate = useNavigate();
  const { pathname, search, hash } = useLocation();

  const leaveStation = () => {
    rememberPwaContext(pathname, search, hash);
    clearAdminSession();
    navigate("/painel/login", { replace: true });
  };

  return (
    <button
      type="button"
      onClick={leaveStation}
      className="flex min-h-12 items-center justify-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-4 font-bold text-parchment transition-transform active:scale-95"
      aria-label="Sair e bloquear estacao"
    >
      <LogOut size={20} />
      <span className="hidden sm:inline">Sair</span>
    </button>
  );
}

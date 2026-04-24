import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Lock, Mail, Loader2,
  ShoppingBag, Package, BarChart3, Users, Trophy, MessageCircle,
} from "lucide-react";
import { adminAuthApi } from "@/lib/api";
import MoschettieriLogo from "@/components/MoschettieriLogo";

const SIDEBAR_NAV = [
  { icon: ShoppingBag, label: "Pedidos",   active: false },
  { icon: Package,     label: "Produtos",  active: false },
  { icon: BarChart3,   label: "Dashboard", active: true  },
  { icon: Users,       label: "Clientes",  active: false },
  { icon: Trophy,      label: "Fidelidade",active: false },
  { icon: MessageCircle,label:"Chatbot",   active: false },
];

const OVERVIEW_CARDS = [
  { label: "Pedidos hoje", value: "—",   tone: "bg-gold/15 text-gold" },
  { label: "Receita",      value: "R$—",  tone: "bg-green-500/15 text-green-400" },
  { label: "Pendentes",    value: "—",   tone: "bg-red-500/15 text-red-400" },
  { label: "Clientes",     value: "—",   tone: "bg-blue-500/15 text-blue-400" },
];

export default function AdminLogin() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) return;
    setLoading(true);
    setError("");
    try {
      const { access_token, admin } = await adminAuthApi.login(email.trim(), password);
      localStorage.setItem("admin_token", access_token);
      localStorage.setItem("admin_user", JSON.stringify(admin));
      navigate("/painel");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "E-mail ou senha incorretos.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-00 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-5xl rounded-2xl border border-surface-03 overflow-hidden shadow-2xl shadow-black/40 flex" style={{ minHeight: 640 }}>

        {/* ── Left panel — Dashboard preview ─────────────────────────── */}
        <aside className="hidden lg:flex flex-col w-72 bg-surface-02 border-r border-surface-03 flex-shrink-0">

          {/* Brand */}
          <div className="px-5 pt-6 pb-5 border-b border-surface-03">
            <MoschettieriLogo className="text-gold text-base" />
            <p className="text-stone text-[11px] mt-0.5">Painel administrativo</p>
          </div>

          {/* Mock admin profile */}
          <div className="px-4 py-4 border-b border-surface-03">
            <div className="flex items-center gap-3 bg-surface-03/50 rounded-xl px-3 py-3">
              <div className="w-8 h-8 rounded-full bg-gold/20 border border-gold/30 flex items-center justify-center flex-shrink-0">
                <span className="text-gold text-xs font-bold">AD</span>
              </div>
              <div className="min-w-0">
                <p className="text-cream text-xs font-semibold">Administrador</p>
                <p className="text-stone text-[10px]">admin@loja.com</p>
              </div>
            </div>
          </div>

          {/* Mock nav */}
          <nav className="flex-1 px-3 py-3 space-y-0.5">
            {SIDEBAR_NAV.map(({ icon: Icon, label, active }) => (
              <div
                key={label}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium ${
                  active ? "bg-gold text-cream" : "text-stone"
                }`}
              >
                <Icon size={16} className="flex-shrink-0" />
                <span>{label}</span>
              </div>
            ))}
          </nav>
        </aside>

        {/* ── Center panel — Dashboard preview ─────────────────────────── */}
        <div className="hidden lg:flex flex-col flex-1 bg-surface-01 overflow-hidden">
          {/* Mock topbar */}
          <div className="bg-surface-02 border-b border-surface-03 px-6 py-3.5 flex items-center justify-between flex-shrink-0">
            <div>
              <p className="text-stone text-[10px]">Bem-vindo de volta,</p>
              <p className="text-cream text-sm font-bold">Administrador!</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-7 w-36 bg-surface-03/70 rounded-lg flex items-center px-3 gap-2">
                <div className="w-3 h-3 rounded-full bg-surface-03/80" />
                <div className="h-1.5 flex-1 bg-surface-03 rounded-full" />
              </div>
              <div className="h-7 w-7 rounded-lg bg-gold/10 border border-gold/20" />
            </div>
          </div>

          <div className="flex-1 overflow-hidden p-5 space-y-4">
            {/* Overview cards */}
            <div>
              <p className="text-stone text-[10px] uppercase tracking-widest font-semibold mb-2.5">Visão Geral</p>
              <div className="grid grid-cols-2 gap-3">
                {OVERVIEW_CARDS.map(({ label, value, tone }) => (
                  <div key={label} className="bg-surface-02 rounded-xl border border-surface-03 px-4 py-3">
                    <p className="text-stone text-[10px]">{label}</p>
                    <p className={`text-lg font-black mt-1 ${tone}`}>{value}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Mock chart */}
            <div className="bg-surface-02 rounded-xl border border-surface-03 p-4">
              <p className="text-parchment text-xs font-semibold mb-3">Receita — Últimos 7 dias</p>
              <div className="flex items-end gap-1.5 h-20">
                {[30, 52, 41, 68, 55, 80, 74].map((h, i) => (
                  <div key={i} className="flex-1 rounded-t-sm" style={{ height: `${h}%`, background: i === 5 ? "#f97316" : "#2d3d56" }} />
                ))}
              </div>
              <div className="flex justify-between mt-2">
                {["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"].map((d) => (
                  <span key={d} className="text-stone text-[9px]">{d}</span>
                ))}
              </div>
            </div>

            {/* Mock recent orders */}
            <div className="bg-surface-02 rounded-xl border border-surface-03 p-4">
              <p className="text-parchment text-xs font-semibold mb-3">Pedidos Recentes</p>
              {[1,2,3].map((i) => (
                <div key={i} className="flex items-center gap-3 py-1.5 border-b border-surface-03 last:border-0">
                  <div className="w-5 h-5 rounded-full bg-surface-03 flex-shrink-0" />
                  <div className="flex-1 space-y-1">
                    <div className="h-1.5 w-24 bg-surface-03 rounded-full" />
                    <div className="h-1 w-14 bg-surface-03/60 rounded-full" />
                  </div>
                  <div className="h-1.5 w-10 bg-gold/30 rounded-full" />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Right panel — Login form ──────────────────────────────────── */}
        <section className="flex-1 lg:max-w-xs xl:max-w-sm bg-surface-02 flex items-center justify-center p-8 lg:p-10">
          <div className="w-full max-w-sm">

            {/* Mobile logo */}
            <div className="lg:hidden mb-8 text-center">
              <MoschettieriLogo className="text-gold text-xl inline-block" />
              <p className="text-stone text-xs mt-1">Painel administrativo</p>
            </div>

            <div className="mb-7">
              <p className="text-gold text-[10px] font-bold uppercase tracking-[0.22em]">Acesso seguro</p>
              <h2 className="text-cream font-black text-2xl mt-2">Entrar no painel</h2>
              <p className="text-stone text-sm mt-1.5">Use suas credenciais de administrador.</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="text-parchment text-xs mb-1.5 block font-semibold">E-mail</label>
                <div className="flex items-center gap-3 bg-surface-03/60 border border-surface-03 rounded-xl px-4 py-3 focus-within:border-gold/60 transition-colors">
                  <Mail size={16} className="text-stone flex-shrink-0" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="admin@exemplo.com"
                    required
                    className="flex-1 bg-transparent text-cream placeholder-stone/50 outline-none text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="text-parchment text-xs mb-1.5 block font-semibold">Senha</label>
                <div className="flex items-center gap-3 bg-surface-03/60 border border-surface-03 rounded-xl px-4 py-3 focus-within:border-gold/60 transition-colors">
                  <Lock size={16} className="text-stone flex-shrink-0" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Digite sua senha"
                    required
                    className="flex-1 bg-transparent text-cream placeholder-stone/50 outline-none text-sm"
                  />
                </div>
              </div>

              {error && (
                <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2.5 text-red-400 text-sm text-center">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-xl bg-gold hover:bg-gold/90 disabled:opacity-60 text-cream font-bold flex items-center justify-center gap-2 transition-colors mt-2 shadow-lg shadow-gold/15"
              >
                {loading && <Loader2 size={17} className="animate-spin" />}
                {loading ? "Entrando..." : "Entrar"}
              </button>
            </form>

            <p className="text-stone/50 text-[10px] text-center mt-8">
              Moschettieri © 2026 · Painel administrativo
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

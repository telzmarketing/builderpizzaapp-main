import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Lock, Mail, Loader2,
  ShoppingBag, BarChart3, Zap, Shield,
} from "lucide-react";
import { adminAuthApi } from "@/lib/api";
import MoschettieriLogo from "@/components/MoschettieriLogo";

const FEATURES = [
  { icon: ShoppingBag, label: "Pedidos em tempo real",    desc: "Acompanhe e atualize o status de cada pedido ao vivo" },
  { icon: BarChart3,   label: "Relatórios e receita",     desc: "Visão completa do faturamento e desempenho da loja"  },
  { icon: Zap,         label: "Promoções e campanhas",    desc: "Crie cupons, campanhas e programa de fidelidade"      },
  { icon: Shield,      label: "Acesso seguro com JWT",    desc: "Autenticação criptografada para proteger sua loja"    },
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
      <div
        className="w-full max-w-4xl rounded-2xl border border-surface-03 overflow-hidden shadow-2xl shadow-black/40 flex"
        style={{ minHeight: 600 }}
      >
        {/* ── Left — brand panel ───────────────────────────────────────── */}
        <aside className="hidden lg:flex flex-col flex-1 bg-surface-02 border-r border-surface-03 p-10 justify-between">
          {/* Logo */}
          <div>
            <div className="inline-flex items-center gap-2 bg-surface-03/60 rounded-xl px-4 py-3 border border-surface-03">
              <MoschettieriLogo className="text-gold text-base" />
            </div>
            <p className="text-stone text-xs mt-2 ml-1">Painel administrativo</p>
          </div>

          {/* Headline */}
          <div className="my-8">
            <p className="text-gold text-xs font-bold uppercase tracking-[0.2em] mb-3">Gestão completa</p>
            <h1 className="text-cream text-3xl font-black leading-snug max-w-xs">
              Tudo que sua loja precisa em um só lugar.
            </h1>
            <p className="text-stone text-sm mt-3 max-w-xs leading-relaxed">
              Controle pedidos, cardápio, frete, pagamentos e a experiência do cliente com a identidade Moschettieri.
            </p>
          </div>

          {/* Feature list */}
          <div className="space-y-4">
            {FEATURES.map(({ icon: Icon, label, desc }) => (
              <div key={label} className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-gold/15 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Icon size={15} className="text-gold" />
                </div>
                <div>
                  <p className="text-parchment text-sm font-semibold">{label}</p>
                  <p className="text-stone text-xs leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Footer tag */}
          <p className="text-stone/40 text-xs mt-8">Moschettieri © 2026</p>
        </aside>

        {/* ── Right — login form ───────────────────────────────────────── */}
        <section className="flex-1 lg:max-w-sm bg-surface-01 flex items-center justify-center p-8 lg:p-12">
          <div className="w-full max-w-sm">

            {/* Mobile logo */}
            <div className="lg:hidden mb-8 text-center">
              <MoschettieriLogo className="text-gold text-xl inline-block" />
              <p className="text-stone text-xs mt-1">Painel administrativo</p>
            </div>

            <div className="mb-8">
              <p className="text-gold text-[10px] font-bold uppercase tracking-[0.22em]">Acesso seguro</p>
              <h2 className="text-cream font-black text-2xl mt-2">Entrar no painel</h2>
              <p className="text-stone text-sm mt-1.5">Use suas credenciais de administrador.</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="text-parchment text-xs mb-1.5 block font-semibold">E-mail</label>
                <div className="flex items-center gap-3 bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 focus-within:border-gold/60 transition-colors">
                  <Mail size={16} className="text-stone flex-shrink-0" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="seu@email.com"
                    required
                    className="flex-1 bg-transparent text-cream placeholder-stone/50 outline-none text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="text-parchment text-xs mb-1.5 block font-semibold">Senha</label>
                <div className="flex items-center gap-3 bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 focus-within:border-gold/60 transition-colors">
                  <Lock size={16} className="text-stone flex-shrink-0" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
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

            <p className="text-stone/40 text-[10px] text-center mt-8">
              Moschettieri © 2026 · Painel administrativo
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

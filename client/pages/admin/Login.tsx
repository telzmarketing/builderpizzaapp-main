import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3, Lock, Mail, Package, ShoppingBag, Loader2 } from "lucide-react";
import { adminAuthApi } from "@/lib/api";
import MoschettieriLogo from "@/components/MoschettieriLogo";

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
    <div className="min-h-screen bg-surface-00 px-4 py-6 flex items-center justify-center">
      <div className="w-full max-w-6xl overflow-hidden rounded-[22px] border border-surface-03 bg-surface-02 shadow-2xl shadow-black/35">
        <div className="grid min-h-[680px] lg:grid-cols-[1.08fr_0.92fr]">
          <section className="hidden lg:flex flex-col justify-between bg-brand-dark border-r border-surface-03 p-8">
            <div className="flex items-center justify-between">
              <div className="rounded-lg border border-cream/10 bg-cream/5 px-5 py-4">
                <MoschettieriLogo className="text-[24px] scale-[1.08] origin-center whitespace-nowrap" />
              </div>
              <span className="text-stone text-sm font-semibold">2026</span>
            </div>

            <div>
              <p className="text-gold text-xs font-bold uppercase tracking-[0.2em]">Painel administrativo</p>
              <h1 className="text-cream text-4xl font-black mt-4 max-w-md">Gestao da loja em uma unica tela.</h1>
              <p className="text-stone text-sm mt-4 max-w-md">Acompanhe pedidos, produtos, pagamentos e experiencia da loja com a identidade Moschettieri.</p>
            </div>

            <div className="rounded-lg border border-surface-03 bg-surface-00/45 p-5">
              <div className="grid grid-cols-3 gap-3">
                <PreviewCard icon={ShoppingBag} label="Pedidos" value="Hoje" />
                <PreviewCard icon={Package} label="Cardapio" value="Ativo" />
                <PreviewCard icon={BarChart3} label="Receita" value="Online" />
              </div>
              <div className="mt-5 rounded-lg bg-surface-02/80 border border-surface-03 p-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-parchment font-semibold">Operacao</span>
                  <span className="text-gold font-bold">Painel seguro</span>
                </div>
                <div className="mt-4 space-y-2">
                  <div className="h-2 rounded-full bg-surface-03 overflow-hidden">
                    <div className="h-full w-[72%] bg-gold" />
                  </div>
                  <div className="h-2 rounded-full bg-surface-03 overflow-hidden">
                    <div className="h-full w-[48%] bg-cream/70" />
                  </div>
                  <div className="h-2 rounded-full bg-surface-03 overflow-hidden">
                    <div className="h-full w-[60%] bg-green-400/80" />
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="flex items-center justify-center p-6 sm:p-10 bg-surface-01">
            <div className="w-full max-w-[410px]">
              <div className="lg:hidden mx-auto mb-6 flex w-48 items-center justify-center rounded-lg border border-surface-03 bg-surface-02 px-6 py-4">
                <MoschettieriLogo className="text-[24px] scale-[1.08] origin-center whitespace-nowrap" />
              </div>

              <div className="mb-7">
                <p className="text-gold text-xs font-bold uppercase tracking-[0.22em]">Acesso seguro</p>
                <h2 className="text-cream font-black text-3xl mt-2">Entrar no painel</h2>
                <p className="text-stone text-sm mt-2">Use suas credenciais administrativas para gerenciar a loja.</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-parchment text-xs mb-1.5 block font-semibold">E-mail</label>
                  <div className="flex items-center gap-3 bg-surface-02 rounded-lg px-4 py-3 border border-surface-03 focus-within:border-gold/70 transition-colors">
                    <Mail size={18} className="text-stone flex-shrink-0" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="admin@exemplo.com"
                      required
                      className="flex-1 bg-transparent text-cream placeholder-stone/60 outline-none text-sm"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-parchment text-xs mb-1.5 block font-semibold">Senha</label>
                  <div className="flex items-center gap-3 bg-surface-02 rounded-lg px-4 py-3 border border-surface-03 focus-within:border-gold/70 transition-colors">
                    <Lock size={18} className="text-stone flex-shrink-0" />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Digite sua senha"
                      required
                      className="flex-1 bg-transparent text-cream placeholder-stone/60 outline-none text-sm"
                    />
                  </div>
                </div>

                {error && (
                  <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-red-400 text-sm text-center">{error}</p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-lg bg-gold hover:bg-gold/90 disabled:opacity-60 text-cream font-bold flex items-center justify-center gap-2 transition-colors shadow-lg shadow-gold/10"
                >
                  {loading && <Loader2 size={18} className="animate-spin" />}
                  {loading ? "Entrando..." : "Entrar"}
                </button>
              </form>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function PreviewCard({ icon: Icon, label, value }: { icon: typeof ShoppingBag; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-surface-03 bg-surface-02/70 p-3">
      <Icon size={18} className="text-gold" />
      <p className="text-cream text-sm font-bold mt-3">{value}</p>
      <p className="text-stone text-xs mt-1">{label}</p>
    </div>
  );
}

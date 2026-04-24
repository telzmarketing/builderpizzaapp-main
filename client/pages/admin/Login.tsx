import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, Mail, Loader2 } from "lucide-react";
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
    <div className="min-h-screen bg-gradient-to-br from-surface-00 via-brand-dark to-surface-00 flex items-center justify-center px-4">
      <div className="w-full max-w-[380px]">
        <div className="text-center mb-7">
          <div className="mx-auto mb-5 flex w-48 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02 px-6 py-4 shadow-2xl shadow-black/30">
            <MoschettieriLogo className="text-[24px] scale-[1.08] origin-center whitespace-nowrap" />
          </div>
          <p className="text-gold text-xs font-bold uppercase tracking-[0.24em]">Painel Administrativo</p>
          <h1 className="text-cream font-bold text-2xl mt-2">Bem-vindo de volta</h1>
          <p className="text-stone text-sm mt-1">Entre para gerenciar a loja.</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-surface-02 rounded-2xl p-6 border border-surface-03 space-y-4 shadow-2xl shadow-black/30">
          <div>
            <label className="text-stone text-xs mb-1.5 block ml-1 font-medium">E-mail</label>
            <div className="flex items-center gap-3 bg-surface-03/70 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold/70 transition-colors">
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
            <label className="text-stone text-xs mb-1.5 block ml-1 font-medium">Senha</label>
            <div className="flex items-center gap-3 bg-surface-03/70 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold/70 transition-colors">
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
            <p className="text-red-400 text-sm text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl bg-gold hover:bg-gold/90 disabled:opacity-60 text-cream font-bold flex items-center justify-center gap-2 transition-colors shadow-lg shadow-gold/10"
          >
            {loading && <Loader2 size={18} className="animate-spin" />}
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}

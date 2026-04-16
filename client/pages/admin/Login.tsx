import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, Mail, Loader2 } from "lucide-react";
import { adminAuthApi } from "@/lib/api";

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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-5xl mb-4">🍕</div>
          <h1 className="text-white font-bold text-2xl">Painel Admin</h1>
          <p className="text-slate-400 text-sm mt-1">Entre com suas credenciais</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-slate-800 rounded-2xl p-6 border border-slate-700 space-y-4">
          <div>
            <label className="text-slate-400 text-xs mb-1 block ml-1">E-mail</label>
            <div className="flex items-center gap-3 bg-slate-700 rounded-xl px-4 py-3 border border-slate-600 focus-within:border-orange-500 transition-colors">
              <Mail size={18} className="text-slate-400 flex-shrink-0" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@exemplo.com"
                required
                className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none text-sm"
              />
            </div>
          </div>

          <div>
            <label className="text-slate-400 text-xs mb-1 block ml-1">Senha</label>
            <div className="flex items-center gap-3 bg-slate-700 rounded-xl px-4 py-3 border border-slate-600 focus-within:border-orange-500 transition-colors">
              <Lock size={18} className="text-slate-400 flex-shrink-0" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none text-sm"
              />
            </div>
          </div>

          {error && (
            <p className="text-red-400 text-sm text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-full bg-orange-500 hover:bg-orange-600 disabled:opacity-60 text-white font-bold flex items-center justify-center gap-2 transition-colors"
          >
            {loading && <Loader2 size={18} className="animate-spin" />}
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}

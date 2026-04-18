import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, Edit2, Check, Home, ShoppingCart, ShoppingBag, User, LogIn } from "lucide-react";
import { useApp } from "@/context/AppContext";

export default function Conta() {
  const navigate = useNavigate();
  const { orders, siteContent, customer, customerLogin, customerLogout } = useApp();
  const { pages, nav } = siteContent;
  const c = pages.conta;

  // Login form state
  const [loginPhone, setLoginPhone] = useState("");
  const [loginName, setLoginName] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // Profile edit state
  const [editMode, setEditMode] = useState(false);
  const [draft, setDraft] = useState({
    name: customer?.name ?? "",
    phone: customer?.phone ?? "",
    email: customer?.email ?? "",
  });

  const handleLogin = async () => {
    if (!loginPhone.trim()) return;
    setLoginLoading(true);
    setLoginError("");
    try {
      await customerLogin(loginPhone.trim(), loginName.trim() || undefined);
    } catch (err: unknown) {
      setLoginError(err instanceof Error ? err.message : "Erro ao fazer login.");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleSave = () => setEditMode(false);
  const handleCancel = () => {
    setDraft({ name: customer?.name ?? "", phone: customer?.phone ?? "", email: customer?.email ?? "" });
    setEditMode(false);
  };

  const totalSpent = orders.reduce((sum, o) => sum + o.total, 0);

  const menuLinks = [
    { icon: "🏆", label: "Programa de Fidelidade", path: "/fidelidade" },
    { icon: "🎟️", label: "Meus Cupons", path: "/cupons" },
    { icon: "📦", label: "Meus Pedidos", path: "/pedidos" },
    { icon: "📍", label: "Localização", path: "/localizacao" },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950">

      {/* Header */}
      <div className="bg-slate-900 px-4 py-4 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-slate-300 hover:text-white transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="text-white font-bold flex-1 text-center">{c.title}</h1>
        {customer && (
          <button
            onClick={() => (editMode ? handleSave() : setEditMode(true))}
            className="text-orange-400 hover:text-orange-300 transition-colors"
          >
            {editMode ? <Check size={22} /> : <Edit2 size={20} />}
          </button>
        )}
        {!customer && <div className="w-6" />}
      </div>

      <div className="px-4 pt-6 pb-32 space-y-6">
        {/* ── Not logged in ── */}
        {!customer && (
          <div className="bg-slate-800 rounded-2xl p-6 border border-slate-700 space-y-4">
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-slate-700 flex items-center justify-center mx-auto mb-3">
                <User size={32} className="text-slate-400" />
              </div>
              <p className="text-white font-bold text-lg">Entrar na conta</p>
              <p className="text-slate-400 text-sm mt-1">Use seu número de telefone para entrar ou criar uma conta.</p>
            </div>

            <div className="space-y-3">
              <div>
                <p className="text-slate-400 text-xs mb-1 ml-1">Telefone / WhatsApp</p>
                <input
                  type="tel"
                  value={loginPhone}
                  onChange={(e) => setLoginPhone(e.target.value)}
                  placeholder="(00) 00000-0000"
                  className="w-full bg-slate-700 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-500 outline-none focus:border-orange-500 text-sm"
                />
              </div>
              <div>
                <p className="text-slate-400 text-xs mb-1 ml-1">Nome (para nova conta)</p>
                <input
                  type="text"
                  value={loginName}
                  onChange={(e) => setLoginName(e.target.value)}
                  placeholder="Seu nome completo"
                  className="w-full bg-slate-700 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-500 outline-none focus:border-orange-500 text-sm"
                />
              </div>
              {loginError && <p className="text-red-400 text-sm text-center">{loginError}</p>}
              <button
                onClick={handleLogin}
                disabled={loginLoading || !loginPhone.trim()}
                className="w-full py-3 rounded-full bg-orange-500 text-white font-bold flex items-center justify-center gap-2 disabled:opacity-60 hover:bg-orange-600 transition-colors"
              >
                <LogIn size={18} />
                {loginLoading ? "Entrando..." : "Entrar"}
              </button>
            </div>
          </div>
        )}

        {/* ── Logged in ── */}
        {customer && (
          <>
            {/* Avatar + Name */}
            <div className="flex flex-col items-center gap-3">
              <div className="w-24 h-24 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center text-5xl shadow-lg">
                👤
              </div>
              <div className="text-center">
                <p className="text-white font-bold text-xl">{customer.name}</p>
                {customer.phone && <p className="text-slate-400 text-sm">{customer.phone}</p>}
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-800 rounded-xl p-4 border border-slate-700 text-center">
                <p className="text-orange-500 font-bold text-2xl">{orders.length}</p>
                <p className="text-slate-400 text-xs mt-1">{c.statsOrders}</p>
              </div>
              <div className="bg-slate-800 rounded-xl p-4 border border-slate-700 text-center">
                <p className="text-orange-500 font-bold text-2xl">R${totalSpent.toFixed(0)}</p>
                <p className="text-slate-400 text-xs mt-1">{c.statsSpent}</p>
              </div>
            </div>

            {/* Profile Fields */}
            <div>
              <h2 className="text-white font-bold text-lg mb-4">{c.personalDataTitle}</h2>
              <div className="space-y-3">
                {[
                  { label: "Nome", field: "name" as const, placeholder: "Seu nome completo" },
                  { label: "Telefone", field: "phone" as const, placeholder: "(00) 00000-0000" },
                  { label: "E-mail", field: "email" as const, placeholder: "seu@email.com" },
                ].map(({ label, field, placeholder }) => (
                  <div key={field}>
                    <p className="text-slate-400 text-xs mb-1 ml-1">{label}</p>
                    <div className={`flex items-center gap-3 bg-slate-800 rounded-xl px-4 py-3 border transition-colors ${editMode ? "border-orange-500" : "border-slate-700"}`}>
                      <input
                        type="text"
                        value={editMode ? draft[field] : (customer as Record<string, string>)[field] ?? ""}
                        onChange={(e) => setDraft((prev) => ({ ...prev, [field]: e.target.value }))}
                        disabled={!editMode}
                        placeholder={placeholder}
                        className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none text-sm disabled:text-slate-300"
                      />
                      {editMode && <Edit2 size={14} className="text-orange-400 flex-shrink-0" />}
                    </div>
                  </div>
                ))}
                {editMode && (
                  <button onClick={handleCancel} className="w-full py-2 rounded-full border border-slate-600 text-slate-400 text-sm hover:border-slate-500 transition-colors">
                    Cancelar
                  </button>
                )}
              </div>
            </div>

            {/* Quick Links */}
            <div>
              <h2 className="text-white font-bold text-lg mb-4">{c.shortcutsTitle}</h2>
              <div className="space-y-2">
                {menuLinks.map((item) => (
                  <button
                    key={item.path}
                    onClick={() => navigate(item.path)}
                    className="w-full flex items-center gap-4 bg-slate-800 hover:bg-slate-700 rounded-xl px-4 py-4 border border-slate-700 transition-colors"
                  >
                    <span className="text-2xl">{item.icon}</span>
                    <span className="text-white text-sm font-medium flex-1 text-left">{item.label}</span>
                    <ChevronRight size={18} className="text-slate-400" />
                  </button>
                ))}
              </div>
            </div>

            {/* Logout */}
            <button
              onClick={customerLogout}
              className="w-full py-4 rounded-full border-2 border-red-500/40 text-red-400 font-bold hover:bg-red-500/10 transition-colors"
            >
              {c.logoutButton}
            </button>
          </>
        )}
      </div>

      {/* Bottom Navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-slate-950 to-transparent pt-4">
        <div className="mx-4 mb-4 bg-orange-500 rounded-full py-3 px-6 flex justify-around items-center shadow-lg">
          <button onClick={() => navigate("/")} className="text-white/60 hover:text-white flex flex-col items-center gap-1 transition-colors">
            <Home size={20} />
            <span className="text-xs font-medium">{nav.home}</span>
          </button>
          <button onClick={() => navigate("/cart")} className="text-white/60 hover:text-white flex flex-col items-center gap-1 transition-colors">
            <ShoppingCart size={20} />
            <span className="text-xs font-medium">{nav.cart}</span>
          </button>
          <button onClick={() => navigate("/pedidos")} className="text-white/60 hover:text-white flex flex-col items-center gap-1 transition-colors">
            <ShoppingBag size={20} />
            <span className="text-xs font-medium">{nav.orders}</span>
          </button>
          <button className="text-white flex flex-col items-center gap-1">
            <User size={20} />
            <span className="text-xs font-medium">{nav.account}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

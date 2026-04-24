import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, Edit2, Check, LogIn, User } from "lucide-react";
import { useApp } from "@/context/AppContext";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";

export default function Conta() {
  const navigate = useNavigate();
  const { orders, siteContent, customer, customerLogin, customerLogout, updateCustomer } = useApp();
  const { pages, nav } = siteContent;
  const c = pages.conta;

  // Login form state
  const [loginPhone, setLoginPhone] = useState("");
  const [loginName, setLoginName] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // Profile edit state
  const [editMode, setEditMode] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
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

  const handleSave = async () => {
    setSavingProfile(true);
    try {
      await updateCustomer({ name: draft.name, phone: draft.phone });
      setEditMode(false);
    } catch {
      // keep editing mode open on error
    } finally {
      setSavingProfile(false);
    }
  };
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
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">

      {/* Header */}
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
        {customer && (
          <button
            onClick={() => (editMode ? handleSave() : setEditMode(true))}
            disabled={savingProfile}
            className="text-gold-light hover:text-orange-300 transition-colors disabled:opacity-50"
          >
            {savingProfile ? <span className="text-xs text-gold">...</span> : editMode ? <Check size={22} /> : <Edit2 size={20} />}
          </button>
        )}
        {!customer && <div className="w-6" />}
      </div>

      <div className="px-4 pt-6 pb-32 space-y-6">
        {/* ── Not logged in ── */}
        {!customer && (
          <div className="bg-surface-02 rounded-2xl p-6 border border-surface-03 space-y-4">
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-surface-03 flex items-center justify-center mx-auto mb-3">
                <User size={32} className="text-stone" />
              </div>
              <p className="text-cream font-bold text-lg">Entrar na conta</p>
              <p className="text-stone text-sm mt-1">Use seu número de telefone para entrar ou criar uma conta.</p>
            </div>

            <div className="space-y-3">
              <div>
                <p className="text-stone text-xs mb-1 ml-1">Telefone / WhatsApp</p>
                <input
                  type="tel"
                  value={loginPhone}
                  onChange={(e) => setLoginPhone(e.target.value)}
                  placeholder="(00) 00000-0000"
                  className="w-full bg-surface-03 border border-brand-mid rounded-xl px-4 py-3 text-cream placeholder-stone/70 outline-none focus:border-gold text-sm"
                />
              </div>
              <div>
                <p className="text-stone text-xs mb-1 ml-1">Nome (para nova conta)</p>
                <input
                  type="text"
                  value={loginName}
                  onChange={(e) => setLoginName(e.target.value)}
                  placeholder="Seu nome completo"
                  className="w-full bg-surface-03 border border-brand-mid rounded-xl px-4 py-3 text-cream placeholder-stone/70 outline-none focus:border-gold text-sm"
                />
              </div>
              {loginError && <p className="text-red-400 text-sm text-center">{loginError}</p>}
              <button
                onClick={handleLogin}
                disabled={loginLoading || !loginPhone.trim()}
                className="w-full py-3 rounded-full bg-gold text-cream font-bold flex items-center justify-center gap-2 disabled:opacity-60 hover:bg-gold/90 transition-colors"
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
                <p className="text-cream font-bold text-xl">{customer.name}</p>
                {customer.phone && <p className="text-stone text-sm">{customer.phone}</p>}
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-surface-02 rounded-xl p-4 border border-surface-03 text-center">
                <p className="text-gold font-bold text-2xl">{orders.length}</p>
                <p className="text-stone text-xs mt-1">{c.statsOrders}</p>
              </div>
              <div className="bg-surface-02 rounded-xl p-4 border border-surface-03 text-center">
                <p className="text-gold font-bold text-2xl">R${totalSpent.toFixed(0)}</p>
                <p className="text-stone text-xs mt-1">{c.statsSpent}</p>
              </div>
            </div>

            {/* Profile Fields */}
            <div>
              <h2 className="text-cream font-bold text-lg mb-4">{c.personalDataTitle}</h2>
              <div className="space-y-3">
                {[
                  { label: "Nome", field: "name" as const, placeholder: "Seu nome completo" },
                  { label: "Telefone", field: "phone" as const, placeholder: "(00) 00000-0000" },
                  { label: "E-mail", field: "email" as const, placeholder: "seu@email.com" },
                ].map(({ label, field, placeholder }) => (
                  <div key={field}>
                    <p className="text-stone text-xs mb-1 ml-1">{label}</p>
                    <div className={`flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border transition-colors ${editMode ? "border-gold" : "border-surface-03"}`}>
                      <input
                        type="text"
                        value={editMode ? draft[field] : (customer as unknown as Record<string, string>)[field] ?? ""}
                        onChange={(e) => setDraft((prev) => ({ ...prev, [field]: e.target.value }))}
                        disabled={!editMode}
                        placeholder={placeholder}
                        className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm disabled:text-parchment"
                      />
                      {editMode && <Edit2 size={14} className="text-gold-light flex-shrink-0" />}
                    </div>
                  </div>
                ))}
                {editMode && (
                  <button onClick={handleCancel} className="w-full py-2 rounded-full border border-brand-mid text-stone text-sm hover:border-slate-500 transition-colors">
                    Cancelar
                  </button>
                )}
              </div>
            </div>

            {/* Quick Links */}
            <div>
              <h2 className="text-cream font-bold text-lg mb-4">{c.shortcutsTitle}</h2>
              <div className="space-y-2">
                {menuLinks.map((item) => (
                  <button
                    key={item.path}
                    onClick={() => navigate(item.path)}
                    className="w-full flex items-center gap-4 bg-surface-02 hover:bg-surface-03 rounded-xl px-4 py-4 border border-surface-03 transition-colors"
                  >
                    <span className="text-2xl">{item.icon}</span>
                    <span className="text-cream text-sm font-medium flex-1 text-left">{item.label}</span>
                    <ChevronRight size={18} className="text-stone" />
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

      <BottomNav />
    </div>
  );
}

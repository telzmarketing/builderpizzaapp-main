import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronLeft, ChevronRight, Edit2, Check, User, Mail, Phone,
  MapPin, Home, Hash, Eye, EyeOff, LogOut, Plus, Trash2, Shield,
} from "lucide-react";
import { useApp } from "@/context/AppContext";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { lgpdApi, customersApi, type ApiLgpdPolicy, type ApiAddress } from "@/lib/api";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: object) => void;
          renderButton: (element: HTMLElement | null, config: object) => void;
        };
      };
    };
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

type AuthTab = "login" | "register";
type RegStep = "form" | "lgpd";

function Field({
  icon: Icon, label, placeholder, value, onChange, type = "text", error, required,
}: {
  icon: React.ElementType; label: string; placeholder: string;
  value: string; onChange: (v: string) => void;
  type?: string; error?: string; required?: boolean;
}) {
  const [show, setShow] = useState(false);
  const isPassword = type === "password";
  return (
    <div>
      <p className="text-stone text-xs mb-1 ml-0.5 font-medium">
        {label}
        {required && <span className="text-red-400 ml-0.5">*</span>}
      </p>
      <div className={`flex items-center gap-3 bg-surface-01 border rounded-xl px-4 py-3 focus-within:border-gold/60 transition-colors ${error ? "border-red-500/50" : "border-surface-03"}`}>
        <Icon size={15} className="text-stone/60 flex-shrink-0" />
        <input
          type={isPassword && show ? "text" : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="flex-1 bg-transparent text-cream placeholder-stone/40 outline-none text-sm"
        />
        {isPassword && (
          <button type="button" onClick={() => setShow((s) => !s)} className="text-stone/50 hover:text-stone">
            {show ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        )}
      </div>
      {error && <p className="text-red-400 text-xs mt-1 ml-0.5">{error}</p>}
    </div>
  );
}

function LgpdModal({
  policy, onAccept, onBack, loading,
}: {
  policy: ApiLgpdPolicy | null;
  onAccept: (marketingEmail: boolean, marketingWhatsapp: boolean) => void;
  onBack: () => void;
  loading: boolean;
}) {
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [marketingEmail, setMarketingEmail] = useState(false);
  const [marketingWhatsapp, setMarketingWhatsapp] = useState(false);

  const sections = policy ? [
    { label: "Sobre esta Política", text: policy.intro_text },
    { label: "Controlador dos Dados", text: policy.data_controller_text },
    { label: "Dados Coletados", text: policy.data_collected_text },
    { label: "Finalidade do Uso", text: policy.data_usage_text },
    { label: "Retenção e Exclusão", text: policy.data_retention_text },
    { label: "Seus Direitos (LGPD)", text: policy.rights_text },
    { label: "Contato", text: policy.contact_text },
  ].filter((s) => s.text) : [];

  return (
    <div className="bg-surface-02 rounded-2xl border border-surface-03 overflow-hidden">
      {/* Header */}
      <div className="bg-surface-03/60 px-5 py-4 border-b border-surface-03 flex items-center gap-3">
        <Shield size={20} className="text-gold flex-shrink-0" />
        <div>
          <p className="text-cream font-bold text-sm">
            {policy?.title ?? "Política de Privacidade"}
          </p>
          {policy?.version && (
            <p className="text-stone text-xs mt-0.5">Versão {policy.version}</p>
          )}
        </div>
      </div>

      {/* Scrollable policy content */}
      <div className="max-h-64 overflow-y-auto px-5 py-4 space-y-4 scrollbar-thin">
        {sections.length > 0 ? sections.map((s) => (
          <div key={s.label}>
            <p className="text-gold text-xs font-bold uppercase tracking-wide mb-1">{s.label}</p>
            <p className="text-stone text-xs leading-relaxed">{s.text}</p>
          </div>
        )) : (
          <p className="text-stone text-xs leading-relaxed">
            Ao criar sua conta, você concorda com o tratamento dos seus dados pessoais para fins de
            processamento de pedidos, conforme a Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018).
          </p>
        )}
      </div>

      {/* Checkboxes */}
      <div className="px-5 py-4 border-t border-surface-03 space-y-3">
        {/* Required: accept terms */}
        <label className="flex items-start gap-3 cursor-pointer group">
          <div
            onClick={() => setTermsAccepted((v) => !v)}
            className={`mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
              termsAccepted ? "bg-gold border-gold" : "border-surface-03 group-hover:border-gold/50"
            }`}
          >
            {termsAccepted && <Check size={12} className="text-cream" />}
          </div>
          <p className="text-cream text-xs leading-relaxed">
            <span className="font-semibold">Li e aceito</span> a Política de Privacidade e Proteção de Dados,
            concordando com o tratamento das minhas informações para os fins descritos.{" "}
            <span className="text-red-400">*</span>
          </p>
        </label>

        {/* Optional: email marketing */}
        <label className="flex items-start gap-3 cursor-pointer group">
          <div
            onClick={() => setMarketingEmail((v) => !v)}
            className={`mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
              marketingEmail ? "bg-gold border-gold" : "border-surface-03 group-hover:border-gold/50"
            }`}
          >
            {marketingEmail && <Check size={12} className="text-cream" />}
          </div>
          <p className="text-stone text-xs leading-relaxed">
            {policy?.marketing_email_label ?? "Desejo receber promoções e novidades por e-mail"}{" "}
            <span className="text-stone/50">(opcional)</span>
          </p>
        </label>

        {/* Optional: WhatsApp marketing */}
        <label className="flex items-start gap-3 cursor-pointer group">
          <div
            onClick={() => setMarketingWhatsapp((v) => !v)}
            className={`mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
              marketingWhatsapp ? "bg-gold border-gold" : "border-surface-03 group-hover:border-gold/50"
            }`}
          >
            {marketingWhatsapp && <Check size={12} className="text-cream" />}
          </div>
          <p className="text-stone text-xs leading-relaxed">
            {policy?.marketing_whatsapp_label ?? "Desejo receber promoções e novidades pelo WhatsApp"}{" "}
            <span className="text-stone/50">(opcional)</span>
          </p>
        </label>

        <p className="text-stone/50 text-[10px]">
          Você pode revogar estes consentimentos a qualquer momento nas configurações da sua conta.
        </p>
      </div>

      {/* Actions */}
      <div className="px-5 pb-5 flex flex-col gap-2">
        <button
          onClick={() => termsAccepted && onAccept(marketingEmail, marketingWhatsapp)}
          disabled={!termsAccepted || loading}
          className="w-full py-3 rounded-full bg-gold text-cream font-bold disabled:opacity-50 hover:bg-gold/90 transition-colors"
        >
          {loading ? "Criando conta..." : "Concordar e Criar Conta"}
        </button>
        <button
          onClick={onBack}
          disabled={loading}
          className="w-full py-2.5 rounded-full border border-surface-03 text-stone text-sm hover:border-stone/50 transition-colors"
        >
          Voltar ao formulário
        </button>
      </div>
    </div>
  );
}

export default function Conta() {
  const navigate = useNavigate();
  const {
    orders, siteContent, customer,
    emailLogin, registerCustomer, googleLogin,
    customerLogout, updateCustomer, loyaltySettings,
  } = useApp();
  const { pages } = siteContent;
  const c = pages.conta;

  // ── Auth state ───────────────────────────────────────────────────────────────
  const [tab, setTab] = useState<AuthTab>("login");
  const [regStep, setRegStep] = useState<RegStep>("form");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lgpdPolicy, setLgpdPolicy] = useState<ApiLgpdPolicy | null>(null);

  // Login tab
  const [loginIdentifier, setLoginIdentifier] = useState("");

  // Register tab
  const [reg, setReg] = useState({
    name: "", email: "", phone: "",
    street: "", number: "", complement: "",
    neighborhood: "", city: "", zip_code: "",
    label: "",
  });
  const [regErrors, setRegErrors] = useState<Partial<Record<keyof typeof reg, string>>>({});

  const googleBtnRef = useRef<HTMLDivElement>(null);

  // ── Profile edit ─────────────────────────────────────────────────────────────
  const [editMode, setEditMode] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [draft, setDraft] = useState({ name: "", phone: "", email: "" });

  // ── Add address form ─────────────────────────────────────────────────────────
  const [showAddAddr, setShowAddAddr] = useState(false);
  const [addrForm, setAddrForm] = useState({ label: "", street: "", number: "", complement: "", neighborhood: "", city: "", zip_code: "" });
  const [savingAddr, setSavingAddr] = useState(false);

  useEffect(() => {
    if (customer) setDraft({ name: customer.name, phone: customer.phone ?? "", email: customer.email ?? "" });
  }, [customer?.id]);

  useEffect(() => {
    lgpdApi.current().then(setLgpdPolicy).catch(() => setLgpdPolicy(null));
  }, []);

  // ── Google Sign-In ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (customer || !GOOGLE_CLIENT_ID) return;
    const render = () => {
      if (!window.google?.accounts?.id || !googleBtnRef.current) return;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (res: { credential: string }) => {
          setError("");
          setLoading(true);
          try { await googleLogin(res.credential); }
          catch (e) { setError(e instanceof Error ? e.message : "Erro no login com Google."); }
          finally { setLoading(false); }
        },
      });
      window.google.accounts.id.renderButton(googleBtnRef.current, {
        theme: "outline", size: "large", shape: "pill",
        width: googleBtnRef.current?.offsetWidth || 300,
        text: "continue_with", locale: "pt-BR",
      });
    };
    if (window.google) { render(); }
    else {
      const id = setInterval(() => { if (window.google) { render(); clearInterval(id); } }, 200);
      return () => clearInterval(id);
    }
  }, [customer, tab]);

  // ── Handlers ─────────────────────────────────────────────────────────────────
  const handleLogin = async () => {
    if (!loginIdentifier.trim()) return;
    setLoading(true); setError("");
    try { await emailLogin(loginIdentifier.trim()); }
    catch (e) { setError(e instanceof Error ? e.message : "Erro ao entrar."); }
    finally { setLoading(false); }
  };

  const validateReg = () => {
    const errs: Partial<Record<keyof typeof reg, string>> = {};
    if (!reg.name.trim()) errs.name = "Nome completo obrigatório";
    if (!reg.email.trim() || !reg.email.includes("@")) errs.email = "E-mail inválido";
    if (!reg.phone.trim() || reg.phone.replace(/\D/g, "").length < 10) errs.phone = "Telefone obrigatório (mínimo 10 dígitos)";
    if (!reg.street.trim()) errs.street = "Rua obrigatória";
    if (!reg.number.trim()) errs.number = "Número obrigatório";
    if (!reg.neighborhood.trim()) errs.neighborhood = "Bairro obrigatório";
    if (!reg.city.trim()) errs.city = "Cidade obrigatória";
    if (!reg.zip_code.trim() || reg.zip_code.replace(/\D/g, "").length < 8) errs.zip_code = "CEP obrigatório (8 dígitos)";
    setRegErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleRegisterStep1 = () => {
    if (!validateReg()) return;
    setRegStep("lgpd");
  };

  const handleRegisterConfirm = async (marketingEmail: boolean, marketingWhatsapp: boolean) => {
    setLoading(true); setError("");
    try {
      await registerCustomer({
        ...reg,
        lgpd_consent: true,
        lgpd_policy_version: lgpdPolicy?.version,
        marketing_email_consent: marketingEmail,
        marketing_whatsapp_consent: marketingWhatsapp,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao criar conta.");
      setRegStep("form");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSavingProfile(true);
    try { await updateCustomer({ name: draft.name, phone: draft.phone }); setEditMode(false); }
    catch { /* stay in edit */ }
    finally { setSavingProfile(false); }
  };

  const handleAddAddress = async () => {
    if (!addrForm.street.trim() || !addrForm.city.trim()) return;
    if (!customer) return;
    setSavingAddr(true);
    try {
      await customersApi.addAddress(customer.id, {
        ...addrForm,
        is_default: (customer.addresses?.length ?? 0) === 0,
      });
      setAddrForm({ label: "", street: "", number: "", complement: "", neighborhood: "", city: "", zip_code: "" });
      setShowAddAddr(false);
      window.location.reload();
    } catch {
      /* keep form open */
    } finally {
      setSavingAddr(false);
    }
  };

  const handleDeleteAddress = async (addr: ApiAddress) => {
    if (!customer) return;
    if (!confirm(`Excluir o endereço "${addr.street}"?`)) return;
    try {
      await customersApi.deleteAddress(customer.id, addr.id);
      window.location.reload();
    } catch { /* ignore */ }
  };

  const totalSpent = orders.reduce((s, o) => s + o.total, 0);

  const menuLinks = [
    ...(loyaltySettings.enabled ? [{ icon: "🏆", label: "Programa de Fidelidade", path: "/fidelidade" }] : []),
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
        {customer ? (
          <button
            onClick={() => (editMode ? handleSave() : setEditMode(true))}
            disabled={savingProfile}
            className="text-gold-light hover:text-orange-300 transition-colors disabled:opacity-50"
          >
            {savingProfile ? <span className="text-xs text-gold">...</span> : editMode ? <Check size={22} /> : <Edit2 size={20} />}
          </button>
        ) : <div className="w-6" />}
      </div>

      <div className="px-4 pt-6 pb-32 space-y-5 max-w-md mx-auto">

        {/* ── NOT LOGGED IN ─────────────────────────────────────────────────── */}
        {!customer && (
          <div className="space-y-5">

            {/* Card header */}
            <div className="text-center pt-2">
              <div className="w-14 h-14 rounded-full bg-gold/15 border border-gold/30 flex items-center justify-center mx-auto mb-3">
                <User size={26} className="text-gold" />
              </div>
              <p className="text-cream font-bold text-xl">Sua conta</p>
              <p className="text-stone text-sm mt-1">Entre ou crie sua conta para pedidos mais rápidos.</p>
            </div>

            {/* Google Sign-In */}
            {GOOGLE_CLIENT_ID && tab !== "register" && (
              <div className="flex justify-center">
                <div ref={googleBtnRef} className="w-full" style={{ minHeight: 44 }} />
              </div>
            )}

            {/* Divider */}
            {GOOGLE_CLIENT_ID && tab !== "register" && (
              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-surface-03" />
                <span className="text-stone/50 text-xs tracking-wide">ou</span>
                <div className="flex-1 h-px bg-surface-03" />
              </div>
            )}

            {/* Tabs */}
            <div className="flex rounded-xl bg-surface-02 border border-surface-03 p-1 gap-1">
              {(["login", "register"] as AuthTab[]).map((t) => (
                <button
                  key={t}
                  onClick={() => { setTab(t); setError(""); setRegStep("form"); }}
                  className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${tab === t ? "bg-gold text-cream shadow-sm" : "text-stone hover:text-parchment"}`}
                >
                  {t === "login" ? "Entrar" : "Criar conta"}
                </button>
              ))}
            </div>

            {/* ── Login tab ── */}
            {tab === "login" && (
              <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5 space-y-4">
                <div>
                  <p className="text-cream font-semibold mb-1">Bem-vindo de volta</p>
                  <p className="text-stone text-xs">Digite seu e-mail ou telefone para entrar.</p>
                </div>
                <Field
                  icon={Mail} label="E-mail ou Telefone" placeholder="seu@email.com ou (00) 00000-0000"
                  value={loginIdentifier} onChange={setLoginIdentifier}
                />
                {error && <p className="text-red-400 text-sm text-center">{error}</p>}
                <button
                  onClick={handleLogin}
                  disabled={loading || !loginIdentifier.trim()}
                  className="w-full py-3 rounded-full bg-gold text-cream font-bold disabled:opacity-60 hover:bg-gold/90 transition-colors"
                >
                  {loading ? "Entrando..." : "Entrar"}
                </button>
                <p className="text-center text-xs text-stone">
                  Ainda não tem conta?{" "}
                  <button onClick={() => setTab("register")} className="text-gold font-semibold hover:underline">
                    Criar conta
                  </button>
                </p>
              </div>
            )}

            {/* ── Register tab ── */}
            {tab === "register" && regStep === "form" && (
              <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5 space-y-4">
                <div>
                  <p className="text-cream font-semibold mb-1">Criar conta</p>
                  <p className="text-stone text-xs">Preencha todos os campos para criar sua conta.</p>
                </div>

                {/* Personal data */}
                <div className="space-y-3">
                  <p className="text-gold text-[10px] font-bold uppercase tracking-widest">Dados pessoais</p>
                  <Field icon={User} label="Nome completo" placeholder="João da Silva" required
                    value={reg.name} onChange={(v) => setReg((p) => ({ ...p, name: v }))} error={regErrors.name} />
                  <Field icon={Mail} label="E-mail" placeholder="seu@email.com" type="email" required
                    value={reg.email} onChange={(v) => setReg((p) => ({ ...p, email: v }))} error={regErrors.email} />
                  <Field icon={Phone} label="Telefone / WhatsApp" placeholder="(00) 00000-0000" type="tel" required
                    value={reg.phone} onChange={(v) => setReg((p) => ({ ...p, phone: v }))} error={regErrors.phone} />
                </div>

                {/* Address */}
                <div className="space-y-3 pt-1">
                  <p className="text-gold text-[10px] font-bold uppercase tracking-widest">Endereço de entrega</p>
                  <Field icon={MapPin} label="CEP" placeholder="00000-000" required
                    value={reg.zip_code} onChange={(v) => setReg((p) => ({ ...p, zip_code: v }))} error={regErrors.zip_code} />
                  <Field icon={Home} label="Rua / Logradouro" placeholder="Rua das Flores" required
                    value={reg.street} onChange={(v) => setReg((p) => ({ ...p, street: v }))} error={regErrors.street} />
                  <div className="grid grid-cols-2 gap-3">
                    <Field icon={Hash} label="Número" placeholder="123" required
                      value={reg.number} onChange={(v) => setReg((p) => ({ ...p, number: v }))} error={regErrors.number} />
                    <Field icon={Home} label="Complemento" placeholder="Apto 4"
                      value={reg.complement} onChange={(v) => setReg((p) => ({ ...p, complement: v }))} />
                  </div>
                  <Field icon={MapPin} label="Bairro" placeholder="Centro" required
                    value={reg.neighborhood} onChange={(v) => setReg((p) => ({ ...p, neighborhood: v }))} error={regErrors.neighborhood} />
                  <Field icon={MapPin} label="Cidade" placeholder="São Paulo" required
                    value={reg.city} onChange={(v) => setReg((p) => ({ ...p, city: v }))} error={regErrors.city} />
                </div>

                {error && <p className="text-red-400 text-sm text-center">{error}</p>}

                <button
                  onClick={handleRegisterStep1}
                  disabled={loading}
                  className="w-full py-3 rounded-full bg-gold text-cream font-bold disabled:opacity-60 hover:bg-gold/90 transition-colors"
                >
                  Continuar →
                </button>
                <p className="text-center text-xs text-stone">
                  Já tem conta?{" "}
                  <button onClick={() => setTab("login")} className="text-gold font-semibold hover:underline">
                    Entrar
                  </button>
                </p>
              </div>
            )}

            {/* ── LGPD step ── */}
            {tab === "register" && regStep === "lgpd" && (
              <LgpdModal
                policy={lgpdPolicy}
                onAccept={handleRegisterConfirm}
                onBack={() => { setRegStep("form"); setError(""); }}
                loading={loading}
              />
            )}
          </div>
        )}

        {/* ── LOGGED IN ─────────────────────────────────────────────────────── */}
        {customer && (
          <>
            {/* Avatar */}
            <div className="flex flex-col items-center gap-3 pt-2">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-gold/30 to-gold/10 border-2 border-gold/40 flex items-center justify-center shadow-lg">
                <User size={36} className="text-gold" />
              </div>
              <div className="text-center">
                <p className="text-cream font-bold text-xl">{customer.name}</p>
                <p className="text-stone text-sm">{customer.email}</p>
                {customer.phone && <p className="text-stone/70 text-xs mt-0.5">{customer.phone}</p>}
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

            {/* Profile fields */}
            <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5 space-y-3">
              <p className="text-cream font-semibold">{c.personalDataTitle}</p>
              {[
                { label: "Nome", field: "name" as const, placeholder: "Seu nome" },
                { label: "Telefone", field: "phone" as const, placeholder: "(00) 00000-0000" },
                { label: "E-mail", field: "email" as const, placeholder: "seu@email.com" },
              ].map(({ label, field, placeholder }) => (
                <div key={field}>
                  <p className="text-stone text-xs mb-1 ml-0.5">{label}</p>
                  <div className={`flex items-center gap-3 bg-surface-01 rounded-xl px-4 py-3 border transition-colors ${editMode ? "border-gold/50" : "border-surface-03"}`}>
                    <input
                      type="text"
                      value={editMode ? draft[field] : (customer as unknown as Record<string, string>)[field] ?? ""}
                      onChange={(e) => setDraft((p) => ({ ...p, [field]: e.target.value }))}
                      disabled={!editMode}
                      placeholder={placeholder}
                      className="flex-1 bg-transparent text-cream placeholder-stone/50 outline-none text-sm disabled:text-parchment"
                    />
                    {editMode && <Edit2 size={13} className="text-gold/60 flex-shrink-0" />}
                  </div>
                </div>
              ))}
              {editMode && (
                <button onClick={() => { setDraft({ name: customer.name, phone: customer.phone ?? "", email: customer.email ?? "" }); setEditMode(false); }}
                  className="w-full py-2 rounded-full border border-surface-03 text-stone text-sm hover:border-stone/50 transition-colors">
                  Cancelar
                </button>
              )}
            </div>

            {/* Saved addresses */}
            <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-cream font-semibold">Endereços salvos</p>
                <button
                  onClick={() => setShowAddAddr((v) => !v)}
                  className="flex items-center gap-1 text-xs text-gold hover:text-gold-light transition-colors"
                >
                  <Plus size={14} />
                  Novo
                </button>
              </div>

              {(customer.addresses ?? []).length === 0 && !showAddAddr && (
                <p className="text-stone text-xs">Nenhum endereço cadastrado.</p>
              )}

              {customer.addresses.map((addr) => (
                <div key={addr.id} className="flex items-start gap-3 bg-surface-01 rounded-xl px-4 py-3 border border-surface-03">
                  <MapPin size={15} className="text-gold mt-0.5 flex-shrink-0" />
                  <div className="text-sm min-w-0 flex-1">
                    {addr.label && <p className="text-gold text-xs font-semibold mb-0.5">{addr.label}</p>}
                    <p className="text-cream">{addr.street}{addr.number ? `, ${addr.number}` : ""}</p>
                    <p className="text-stone text-xs mt-0.5 truncate">
                      {[addr.neighborhood, addr.city, addr.zip_code].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    {addr.is_default && (
                      <span className="text-[10px] text-gold bg-gold/10 border border-gold/20 rounded px-1.5 py-0.5">Principal</span>
                    )}
                    <button
                      onClick={() => handleDeleteAddress(addr)}
                      className="text-red-400/60 hover:text-red-400 transition-colors mt-0.5"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}

              {/* Add address form */}
              {showAddAddr && (
                <div className="space-y-3 pt-2 border-t border-surface-03">
                  <p className="text-gold text-xs font-bold uppercase tracking-wide">Novo endereço</p>
                  <Field icon={Home} label="Identificação" placeholder="Casa, Trabalho..." value={addrForm.label} onChange={(v) => setAddrForm((p) => ({ ...p, label: v }))} />
                  <Field icon={MapPin} label="CEP" placeholder="00000-000" value={addrForm.zip_code} onChange={(v) => setAddrForm((p) => ({ ...p, zip_code: v }))} />
                  <Field icon={Home} label="Rua" placeholder="Rua das Flores" value={addrForm.street} onChange={(v) => setAddrForm((p) => ({ ...p, street: v }))} />
                  <div className="grid grid-cols-2 gap-2">
                    <Field icon={Hash} label="Número" placeholder="123" value={addrForm.number} onChange={(v) => setAddrForm((p) => ({ ...p, number: v }))} />
                    <Field icon={Home} label="Complemento" placeholder="Apto 4" value={addrForm.complement} onChange={(v) => setAddrForm((p) => ({ ...p, complement: v }))} />
                  </div>
                  <Field icon={MapPin} label="Bairro" placeholder="Centro" value={addrForm.neighborhood} onChange={(v) => setAddrForm((p) => ({ ...p, neighborhood: v }))} />
                  <Field icon={MapPin} label="Cidade" placeholder="São Paulo" value={addrForm.city} onChange={(v) => setAddrForm((p) => ({ ...p, city: v }))} />
                  <div className="flex gap-2">
                    <button
                      onClick={() => setShowAddAddr(false)}
                      className="flex-1 py-2.5 rounded-full border border-surface-03 text-stone text-sm"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={handleAddAddress}
                      disabled={savingAddr || !addrForm.street.trim() || !addrForm.city.trim()}
                      className="flex-1 py-2.5 rounded-full bg-gold text-cream text-sm font-bold disabled:opacity-60"
                    >
                      {savingAddr ? "Salvando..." : "Salvar"}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Quick links */}
            <div className="space-y-2">
              {menuLinks.map((item) => (
                <button key={item.path} onClick={() => navigate(item.path)}
                  className="w-full flex items-center gap-4 bg-surface-02 hover:bg-surface-03 rounded-xl px-4 py-4 border border-surface-03 transition-colors">
                  <span className="text-2xl">{item.icon}</span>
                  <span className="text-cream text-sm font-medium flex-1 text-left">{item.label}</span>
                  <ChevronRight size={18} className="text-stone" />
                </button>
              ))}
            </div>

            {/* Logout */}
            <button onClick={customerLogout}
              className="w-full py-4 rounded-full border-2 border-red-500/30 text-red-400/80 font-semibold hover:bg-red-500/10 hover:border-red-500/50 hover:text-red-400 transition-colors flex items-center justify-center gap-2">
              <LogOut size={17} />
              {c.logoutButton}
            </button>
          </>
        )}
      </div>

      <BottomNav />
    </div>
  );
}

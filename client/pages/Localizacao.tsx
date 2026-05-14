import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, MapPin, Plus, Trash2, Loader2 } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import BottomNav from "@/components/BottomNav";
import { useApp } from "@/context/AppContext";
import { customersApi, type ApiAddress } from "@/lib/api";

export default function Localizacao() {
  const navigate = useNavigate();
  const { customer, addCustomerAddress } = useApp();

  const [addresses, setAddresses] = useState<ApiAddress[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [apiError, setApiError] = useState("");
  const [form, setForm] = useState({
    label: "",
    street: "",
    number: "",
    neighborhood: "",
    city: "",
    complement: "",
  });
  const [errors, setErrors] = useState<Partial<typeof form>>({});

  useEffect(() => {
    if (!customer) {
      navigate("/conta?redirect=/localizacao", { replace: true });
      return;
    }
    setLoading(true);
    customersApi
      .listAddresses(customer.id)
      .then((list) => setAddresses(list))
      .catch(() => setAddresses(customer.addresses ?? []))
      .finally(() => setLoading(false));
  }, [customer?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!customer) return null;

  const validate = () => {
    const e: Partial<typeof form> = {};
    if (!form.street.trim()) e.street = "Rua obrigatória";
    if (!form.city.trim()) e.city = "Cidade obrigatória";
    return e;
  };

  const handleAdd = async () => {
    const e = validate();
    if (Object.keys(e).length) { setErrors(e); return; }
    setSaving(true);
    setApiError("");
    try {
      await addCustomerAddress({
        label: form.label.trim() || undefined,
        street: form.street.trim(),
        number: form.number.trim() || undefined,
        neighborhood: form.neighborhood.trim() || undefined,
        city: form.city.trim(),
        complement: form.complement.trim() || undefined,
      });
      const fresh = await customersApi.listAddresses(customer.id);
      setAddresses(fresh);
      setForm({ label: "", street: "", number: "", neighborhood: "", city: "", complement: "" });
      setErrors({});
      setShowForm(false);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Erro ao salvar endereço.");
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (addressId: string) => {
    setRemoving(addressId);
    try {
      await customersApi.deleteAddress(customer.id, addressId);
      setAddresses((prev) => prev.filter((a) => a.id !== addressId));
    } catch {
      setApiError("Erro ao remover endereço.");
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <button onClick={() => navigate("/")} aria-label="Ir para a home da loja">
          <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
        </button>
        <div className="w-6" />
      </div>

      <div className="px-4 pt-6 pb-32 space-y-6">
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-cream font-bold text-lg">Endereços salvos</h2>
            <button
              onClick={() => { setShowForm((v) => !v); setApiError(""); setErrors({}); }}
              className="flex items-center gap-1 text-gold-light text-sm font-medium hover:text-orange-300 transition-colors"
            >
              <Plus size={18} />
              Adicionar
            </button>
          </div>

          {showForm && (
            <div className="bg-surface-02 rounded-2xl p-4 border border-gold/40 mb-4 space-y-3">
              <p className="text-cream font-bold text-sm">Novo endereço</p>
              {[
                { key: "label" as const, placeholder: "Nome (ex: Casa, Trabalho) — opcional" },
                { key: "street" as const, placeholder: "Rua *" },
                { key: "number" as const, placeholder: "Número" },
                { key: "neighborhood" as const, placeholder: "Bairro" },
                { key: "city" as const, placeholder: "Cidade *" },
                { key: "complement" as const, placeholder: "Complemento (apto, bloco...)" },
              ].map(({ key, placeholder }) => (
                <div key={key}>
                  <input
                    type="text"
                    placeholder={placeholder}
                    value={form[key]}
                    onChange={(e) => {
                      setForm((p) => ({ ...p, [key]: e.target.value }));
                      if (errors[key]) setErrors((p) => ({ ...p, [key]: undefined }));
                    }}
                    className={`w-full bg-surface-03 text-cream placeholder-stone/70 rounded-xl px-4 py-3 text-sm outline-none border transition-colors ${errors[key] ? "border-red-500" : "border-brand-mid focus:border-gold"}`}
                  />
                  {errors[key] && <p className="text-red-400 text-xs mt-1 ml-1">{errors[key]}</p>}
                </div>
              ))}
              {apiError && <p className="text-red-400 text-xs">{apiError}</p>}
              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => { setShowForm(false); setErrors({}); setApiError(""); }}
                  className="flex-1 py-2.5 rounded-full border border-brand-mid text-stone text-sm hover:border-slate-500 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleAdd}
                  disabled={saving}
                  className="flex-1 py-2.5 rounded-full bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold text-sm transition-colors flex items-center justify-center gap-2"
                >
                  {saving ? <Loader2 size={16} className="animate-spin" /> : null}
                  {saving ? "Salvando..." : "Salvar"}
                </button>
              </div>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12 gap-2 text-stone">
              <Loader2 size={20} className="animate-spin" />
              <span className="text-sm">Carregando endereços...</span>
            </div>
          ) : addresses.length === 0 && !showForm ? (
            <div className="text-center py-12">
              <MapPin size={48} className="text-slate-600 mx-auto mb-3" />
              <p className="text-cream font-bold">Nenhum endereço salvo</p>
              <p className="text-stone text-sm mt-1">Adicione um endereço para agilizar seus pedidos.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {addresses.map((addr) => (
                <div
                  key={addr.id}
                  className={`bg-surface-02 rounded-2xl p-4 border transition-colors ${addr.is_default ? "border-gold" : "border-surface-03"}`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${addr.is_default ? "bg-gold" : "bg-surface-03"}`}>
                      <MapPin size={18} className="text-cream" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        {addr.label && <p className="text-cream font-bold text-sm">{addr.label}</p>}
                        {addr.is_default && (
                          <span className="text-xs bg-gold/20 text-gold-light px-2 py-0.5 rounded-full">Padrão</span>
                        )}
                      </div>
                      <p className="text-parchment text-sm">
                        {addr.street}{addr.number ? `, ${addr.number}` : ""}
                      </p>
                      {addr.neighborhood && <p className="text-stone text-xs">{addr.neighborhood}</p>}
                      {addr.complement && <p className="text-stone text-xs">{addr.complement}</p>}
                      <p className="text-stone text-xs">{addr.city}{addr.state ? ` - ${addr.state}` : ""}</p>
                    </div>
                  </div>
                  <div className="flex justify-end mt-3 pt-3 border-t border-surface-03">
                    <button
                      onClick={() => handleRemove(addr.id)}
                      disabled={removing === addr.id}
                      className="flex items-center justify-center gap-1 py-2 px-4 rounded-full border border-red-500/30 text-red-400 text-xs hover:bg-red-500/10 disabled:opacity-50 transition-colors"
                    >
                      {removing === addr.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      Remover
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      <BottomNav />
    </div>
  );
}

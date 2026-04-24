import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, MapPin, Plus, Trash2, Check, Home as HomeIcon, Building2, Briefcase } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";

interface Address {
  id: string;
  label: string;
  street: string;
  city: string;
  complement: string;
  isDefault: boolean;
  icon: "home" | "building" | "work";
}

const iconMap = {
  home: HomeIcon,
  building: Building2,
  work: Briefcase,
};

const initialAddresses: Address[] = [
  {
    id: "1",
    label: "Casa",
    street: "Rua das Flores, 123",
    city: "São Paulo - SP",
    complement: "Apto 42",
    isDefault: true,
    icon: "home",
  },
  {
    id: "2",
    label: "Trabalho",
    street: "Av. Paulista, 1000",
    city: "São Paulo - SP",
    complement: "Andar 5, sala 501",
    isDefault: false,
    icon: "work",
  },
];

export default function Localizacao() {
  const navigate = useNavigate();
  const [addresses, setAddresses] = useState<Address[]>(initialAddresses);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ label: "", street: "", city: "", complement: "", icon: "home" as Address["icon"] });
  const [errors, setErrors] = useState<Partial<typeof form>>({});

  const setDefault = (id: string) => {
    setAddresses((prev) => prev.map((a) => ({ ...a, isDefault: a.id === id })));
  };

  const remove = (id: string) => {
    setAddresses((prev) => prev.filter((a) => a.id !== id));
  };

  const validate = () => {
    const e: Partial<typeof form> = {};
    if (!form.label.trim()) e.label = "Nome obrigatório";
    if (!form.street.trim()) e.street = "Rua obrigatória";
    if (!form.city.trim()) e.city = "Cidade obrigatória";
    return e;
  };

  const handleAdd = () => {
    const e = validate();
    if (Object.keys(e).length) { setErrors(e); return; }
    const newAddr: Address = {
      id: Date.now().toString(),
      label: form.label,
      street: form.street,
      city: form.city,
      complement: form.complement,
      isDefault: addresses.length === 0,
      icon: form.icon,
    };
    setAddresses((prev) => [...prev, newAddr]);
    setForm({ label: "", street: "", city: "", complement: "", icon: "home" });
    setErrors({});
    setShowForm(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">

      {/* Header */}
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base" />
        <div className="w-6"></div>
      </div>

      <div className="px-4 pt-6 pb-32 space-y-6">
        {/* Map Placeholder */}
        <div className="relative w-full h-48 rounded-2xl overflow-hidden bg-surface-02 border border-surface-03 flex items-center justify-center">
          <div className="absolute inset-0 opacity-20"
            style={{
              backgroundImage: `repeating-linear-gradient(0deg, transparent, transparent 30px, rgba(100,116,139,0.3) 30px, rgba(100,116,139,0.3) 31px),
                repeating-linear-gradient(90deg, transparent, transparent 30px, rgba(100,116,139,0.3) 30px, rgba(100,116,139,0.3) 31px)`
            }}
          />
          <div className="flex flex-col items-center gap-3 z-10">
            <div className="w-12 h-12 rounded-full bg-gold flex items-center justify-center shadow-lg shadow-orange-500/40 animate-pulse">
              <MapPin size={24} className="text-cream" />
            </div>
            <p className="text-parchment text-sm font-medium">São Paulo, SP</p>
            <p className="text-stone/70 text-xs">Integração com mapa disponível em breve</p>
          </div>
        </div>

        {/* Saved Addresses */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-cream font-bold text-lg">Endereços salvos</h2>
            <button
              onClick={() => setShowForm((v) => !v)}
              className="flex items-center gap-1 text-gold-light text-sm font-medium hover:text-orange-300 transition-colors"
            >
              <Plus size={18} />
              Adicionar
            </button>
          </div>

          {/* Add Form */}
          {showForm && (
            <div className="bg-surface-02 rounded-2xl p-4 border border-gold/40 mb-4 space-y-3">
              <p className="text-cream font-bold text-sm mb-2">Novo endereço</p>

              {/* Icon selector */}
              <div className="flex gap-2">
                {(["home", "building", "work"] as const).map((ic) => {
                  const Icon = iconMap[ic];
                  return (
                    <button
                      key={ic}
                      onClick={() => setForm((p) => ({ ...p, icon: ic }))}
                      className={`flex-1 flex flex-col items-center gap-1 py-2 rounded-xl border text-xs transition-colors ${
                        form.icon === ic ? "bg-gold/20 border-gold text-gold-light" : "bg-surface-03 border-brand-mid text-stone"
                      }`}
                    >
                      <Icon size={18} />
                      {ic === "home" ? "Casa" : ic === "building" ? "Apto" : "Trabalho"}
                    </button>
                  );
                })}
              </div>

              {[
                { key: "label" as const, placeholder: "Nome (ex: Casa, Trabalho)" },
                { key: "street" as const, placeholder: "Rua e número" },
                { key: "city" as const, placeholder: "Cidade - UF" },
                { key: "complement" as const, placeholder: "Complemento (opcional)" },
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

              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => { setShowForm(false); setErrors({}); }}
                  className="flex-1 py-2.5 rounded-full border border-brand-mid text-stone text-sm hover:border-slate-500 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleAdd}
                  className="flex-1 py-2.5 rounded-full bg-gold hover:bg-gold/90 text-cream font-bold text-sm transition-colors"
                >
                  Salvar
                </button>
              </div>
            </div>
          )}

          {/* Address list */}
          <div className="space-y-3">
            {addresses.map((addr) => {
              const Icon = iconMap[addr.icon];
              return (
                <div
                  key={addr.id}
                  className={`bg-surface-02 rounded-2xl p-4 border transition-colors ${addr.isDefault ? "border-gold" : "border-surface-03"}`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${addr.isDefault ? "bg-gold" : "bg-surface-03"}`}>
                      <Icon size={18} className="text-cream" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <p className="text-cream font-bold text-sm">{addr.label}</p>
                        {addr.isDefault && (
                          <span className="text-xs bg-gold/20 text-gold-light px-2 py-0.5 rounded-full">Padrão</span>
                        )}
                      </div>
                      <p className="text-parchment text-sm">{addr.street}</p>
                      {addr.complement && <p className="text-stone text-xs">{addr.complement}</p>}
                      <p className="text-stone text-xs">{addr.city}</p>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-3 pt-3 border-t border-surface-03">
                    {!addr.isDefault && (
                      <button
                        onClick={() => setDefault(addr.id)}
                        className="flex-1 flex items-center justify-center gap-1 py-2 rounded-full border border-gold/40 text-gold-light text-xs font-medium hover:bg-gold/10 transition-colors"
                      >
                        <Check size={14} />
                        Definir padrão
                      </button>
                    )}
                    <button
                      onClick={() => remove(addr.id)}
                      className="flex items-center justify-center gap-1 py-2 px-4 rounded-full border border-red-500/30 text-red-400 text-xs hover:bg-red-500/10 transition-colors"
                    >
                      <Trash2 size={14} />
                      Remover
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {addresses.length === 0 && !showForm && (
            <div className="text-center py-12">
              <MapPin size={48} className="text-slate-600 mx-auto mb-3" />
              <p className="text-cream font-bold">Nenhum endereço salvo</p>
              <p className="text-stone text-sm mt-1">Adicione um endereço para agilizar seus pedidos.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

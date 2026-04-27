import { useEffect, useMemo, useState } from "react";
import { Search, Users, MapPin, Phone, Mail, Calendar, ShieldCheck, ShieldOff, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import { customersApi, type ApiCustomer } from "@/lib/api";

function formatDate(s: string) {
  return new Date(s).toLocaleDateString("pt-BR");
}

function ConsentBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded ${ok ? "bg-emerald-500/15 text-emerald-400" : "bg-stone/20 text-stone"}`}>
      {ok ? <ShieldCheck size={10} /> : <ShieldOff size={10} />} {label}
    </span>
  );
}

function CustomerRow({ customer }: { customer: ApiCustomer }) {
  const [open, setOpen] = useState(false);
  const defaultAddr = customer.addresses.find((a) => a.is_default) ?? customer.addresses[0];

  return (
    <div className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-surface-03/30 transition-colors"
      >
        {/* Avatar */}
        <div className="w-10 h-10 rounded-full bg-gold/20 border border-gold/30 flex items-center justify-center flex-shrink-0">
          <span className="text-gold font-bold text-sm">
            {customer.name.split(" ").slice(0, 2).map((n) => n[0]?.toUpperCase()).join("")}
          </span>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <p className="text-cream font-semibold text-sm truncate">{customer.name}</p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-0.5 mt-0.5">
            <span className="text-stone text-xs flex items-center gap-1 truncate">
              <Mail size={10} /> {customer.email}
            </span>
            {customer.phone && (
              <span className="text-stone text-xs flex items-center gap-1">
                <Phone size={10} /> {customer.phone}
              </span>
            )}
          </div>
        </div>

        {/* Meta */}
        <div className="hidden md:flex flex-col items-end gap-1 flex-shrink-0">
          <span className="text-stone text-xs flex items-center gap-1">
            <Calendar size={10} /> {formatDate(customer.created_at)}
          </span>
          {defaultAddr && (
            <span className="text-stone text-xs flex items-center gap-1 truncate max-w-[200px]">
              <MapPin size={10} /> {defaultAddr.city}
            </span>
          )}
        </div>

        <div className="flex-shrink-0 text-stone">
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {open && (
        <div className="border-t border-surface-03 px-5 py-4 grid grid-cols-1 md:grid-cols-2 gap-5 bg-surface-01/40">
          {/* Consentimentos */}
          <div>
            <p className="text-stone text-xs font-semibold uppercase tracking-wider mb-2">Privacidade & Consentimento</p>
            <div className="flex flex-wrap gap-2">
              <ConsentBadge ok={customer.lgpd_consent} label="LGPD" />
              <ConsentBadge ok={customer.marketing_email_consent} label="E-mail mkt" />
              <ConsentBadge ok={customer.marketing_whatsapp_consent} label="WhatsApp mkt" />
            </div>
            {customer.lgpd_policy_version && (
              <p className="text-stone text-xs mt-2">Versão política: {customer.lgpd_policy_version}</p>
            )}
          </div>

          {/* Endereços */}
          <div>
            <p className="text-stone text-xs font-semibold uppercase tracking-wider mb-2">
              Endereços ({customer.addresses.length})
            </p>
            {customer.addresses.length === 0 ? (
              <p className="text-stone text-xs">Nenhum endereço cadastrado.</p>
            ) : (
              <div className="space-y-1.5">
                {customer.addresses.map((addr) => (
                  <div key={addr.id} className="text-xs text-parchment bg-surface-03/50 rounded-lg px-3 py-2">
                    {addr.label && <span className="font-semibold mr-1">{addr.label}:</span>}
                    {addr.street}{addr.number ? `, ${addr.number}` : ""}
                    {addr.complement ? ` — ${addr.complement}` : ""}, {addr.city}
                    {addr.is_default && <span className="ml-2 text-gold text-[10px] font-bold">(principal)</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminClientes() {
  const [customers, setCustomers] = useState<ApiCustomer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    customersApi.list()
      .then(setCustomers)
      .catch(() => setError("Não foi possível carregar os clientes."))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return customers;
    return customers.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q) ||
        (c.phone ?? "").includes(q)
    );
  }, [customers, search]);

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />

      <main className="flex-1 overflow-y-auto">
        <header className="bg-surface-02 border-b border-surface-03 px-6 py-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <p className="text-gold text-xs font-bold uppercase tracking-[0.2em]">CRM</p>
            <h1 className="text-cream text-2xl font-bold">Clientes</h1>
            <p className="text-stone text-sm mt-1">
              {loading ? "Carregando..." : `${customers.length} cliente${customers.length !== 1 ? "s" : ""} cadastrado${customers.length !== 1 ? "s" : ""}`}
            </p>
          </div>

          {/* Search */}
          <div className="flex items-center gap-2 bg-surface-03/60 border border-surface-03 rounded-xl px-4 py-2.5 w-full md:w-72">
            <Search size={15} className="text-stone flex-shrink-0" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar por nome, e-mail ou telefone..."
              className="bg-transparent text-cream placeholder-stone/60 text-sm outline-none flex-1 min-w-0"
            />
          </div>
        </header>

        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-24 gap-2 text-stone">
              <Loader2 size={22} className="animate-spin" /> Carregando clientes...
            </div>
          ) : error ? (
            <div className="text-red-400 text-sm text-center py-12">{error}</div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 gap-3 text-stone">
              <Users size={40} className="opacity-30" />
              <p>{search ? "Nenhum cliente encontrado para essa busca." : "Nenhum cliente cadastrado ainda."}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.map((c) => (
                <CustomerRow key={c.id} customer={c} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

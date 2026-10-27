import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Users, MapPin, Phone, Mail, Calendar, ShieldCheck, ShieldOff, Loader2, ChevronDown, ChevronUp, ExternalLink, Plus, X, AlertCircle, Upload, Download } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import { ApiRequestError, customersApi, type ApiCustomer } from "@/lib/api";

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

function CustomerRow({ customer, onEdit }: { customer: ApiCustomer; onEdit: (customer: ApiCustomer) => void }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
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

        <button
          onClick={(e) => { e.stopPropagation(); navigate(`/painel/clientes/${customer.id}`); }}
          className="flex-shrink-0 flex items-center gap-1 text-xs text-gold hover:text-gold/80 font-medium px-2 py-1 rounded-lg hover:bg-gold/10 transition-colors"
          title="Ver perfil completo"
        >
          <ExternalLink size={12} /> Ver Perfil
        </button>
        <button type="button" onClick={(e) => { e.stopPropagation(); onEdit(customer); }} className="flex-shrink-0 rounded-lg border border-gold/40 px-2 py-1 text-xs font-bold text-gold hover:bg-gold/10">Editar</button>
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
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", email: "", street: "", number: "", complement: "", neighborhood: "", city: "", state: "", zip_code: "" });
  const [editingCustomer, setEditingCustomer] = useState<ApiCustomer | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [phoneConflict, setPhoneConflict] = useState<ApiCustomer | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<Awaited<ReturnType<typeof customersApi.importFile>> | null>(null);

  useEffect(() => {
    customersApi.list()
      .then(setCustomers)
      .catch(() => setError("Não foi possível carregar os clientes."))
      .finally(() => setLoading(false));
  }, []);

  async function createCustomer(event: FormEvent) {
    event.preventDefault();
    setFormError("");
    setPhoneConflict(null);
    if (!form.name.trim() || !form.phone.trim()) {
      setFormError("Nome e telefone são obrigatórios.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        phone: form.phone.trim(),
        email: form.email.trim() || undefined,
        ...(form.street.trim() && form.city.trim() ? { address: { street: form.street.trim(), number: form.number.trim() || undefined, complement: form.complement.trim() || undefined, neighborhood: form.neighborhood.trim() || undefined, city: form.city.trim(), state: form.state.trim() || undefined, zip_code: form.zip_code.trim() || undefined, is_default: true } } : {}),
      };
      const created = editingCustomer
        ? await customersApi.updateAdmin(editingCustomer.id, payload)
        : await customersApi.createAdmin(payload);
      setCustomers((current) => editingCustomer ? current.map((item) => item.id === created.id ? created : item) : [created, ...current]);
      setForm({ name: "", phone: "", email: "", street: "", number: "", complement: "", neighborhood: "", city: "", state: "", zip_code: "" });
      setEditingCustomer(null);
      setShowCreate(false);
    } catch (err) {
      if (err instanceof ApiRequestError && err.code === "CustomerPhoneConflict") {
        const payload = err.payload as { detail?: { customer?: ApiCustomer } } | undefined;
        setPhoneConflict(payload?.detail?.customer ?? null);
      } else {
        setFormError(err instanceof Error ? err.message : "Não foi possível cadastrar o cliente.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function previewImport() {
    if (!importFile) return;
    setImporting(true);
    try {
      setImportResult(await customersApi.importFile(importFile, false));
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Não foi possível ler o arquivo.");
    } finally {
      setImporting(false);
    }
  }

  async function commitImport() {
    if (!importFile) return;
    setImporting(true);
    try {
      const result = await customersApi.importFile(importFile, true);
      setImportResult(result);
      const refreshed = await customersApi.list();
      setCustomers(refreshed);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Não foi possível importar os clientes.");
    } finally {
      setImporting(false);
    }
  }

  async function downloadImportTemplate() {
    const template = await customersApi.importTemplate();
    const blob = new Blob([template.content], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = template.filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

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
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
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

          {/* Search + actions */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2 bg-surface-03/60 border border-surface-03 rounded-xl px-4 py-2.5 w-full md:w-72">
              <Search size={15} className="text-stone flex-shrink-0" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar por nome, e-mail ou telefone..."
                className="bg-transparent text-cream placeholder-stone/60 text-sm outline-none flex-1 min-w-0"
              />
            </div>
            <button
              type="button"
              onClick={() => { setEditingCustomer(null); setForm({ name: "", phone: "", email: "", street: "", number: "", complement: "", neighborhood: "", city: "", state: "", zip_code: "" }); setShowCreate(true); setFormError(""); setPhoneConflict(null); }}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-gold px-4 py-2.5 text-sm font-black text-surface-00 hover:bg-gold/90"
            >
              <Plus size={16} /> Cadastrar cliente
            </button>
            <button type="button" onClick={() => { setShowImport(true); setImportResult(null); setFormError(""); }} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-gold/50 px-4 py-2.5 text-sm font-black text-gold hover:bg-gold/10">
              <Upload size={16} /> Importar clientes
            </button>
            <button type="button" onClick={() => void downloadImportTemplate()} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-surface-03 px-4 py-2.5 text-sm font-bold text-stone hover:text-cream">
              <Download size={16} /> Modelo
            </button>
            <AdminTopActions />
          </div>
        </header>

        {showCreate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/70 p-4" role="dialog" aria-modal="true" aria-labelledby="create-customer-title">
            <form onSubmit={createCustomer} className="my-auto max-h-[calc(100vh-2rem)] w-full max-w-lg overflow-y-auto rounded-2xl border border-surface-03 bg-surface-01 p-6 shadow-2xl">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-gold text-xs font-bold uppercase tracking-[0.2em]">CRM</p>
                  <h2 id="create-customer-title" className="text-xl font-black text-cream">{editingCustomer ? "Editar cliente" : "Cadastrar cliente"}</h2>
                </div>
                <button type="button" onClick={() => setShowCreate(false)} className="rounded-lg p-2 text-stone hover:bg-surface-03 hover:text-cream" aria-label="Fechar"><X size={18} /></button>
              </div>
              <div className="grid gap-4">
                <label className="grid gap-1 text-sm text-stone">Nome completo<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-xl border border-surface-03 bg-surface-02 px-3 py-3 text-cream outline-none focus:border-gold" /></label>
                <label className="grid gap-1 text-sm text-stone">Telefone / WhatsApp<input required inputMode="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="rounded-xl border border-surface-03 bg-surface-02 px-3 py-3 text-cream outline-none focus:border-gold" /></label>
                <label className="grid gap-1 text-sm text-stone">E-mail (opcional)<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="rounded-xl border border-surface-03 bg-surface-02 px-3 py-3 text-cream outline-none focus:border-gold" /></label>
                <p className="pt-2 text-xs font-bold uppercase tracking-wider text-gold">Endereço (opcional)</p>
                {([['street','Rua / Avenida'],['number','Número'],['complement','Complemento'],['neighborhood','Bairro'],['city','Cidade'],['state','Estado'],['zip_code','CEP']] as const).map(([field,label]) => <label key={field} className="grid gap-1 text-sm text-stone">{label}<input value={form[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })} className="rounded-xl border border-surface-03 bg-surface-02 px-3 py-3 text-cream outline-none focus:border-gold" /></label>)}
              </div>
              {phoneConflict && (
                <div className="mt-4 rounded-xl border border-amber-400/40 bg-amber-400/10 p-4 text-sm text-amber-100">
                  <p className="flex items-center gap-2 font-black"><AlertCircle size={16} /> Esse número já está cadastrado.</p>
                  <p className="mt-1">{phoneConflict.name}{phoneConflict.phone ? ` · ${phoneConflict.phone}` : ""}</p>
                  <button type="button" onClick={() => { setShowCreate(false); window.location.assign(`/painel/clientes/${phoneConflict.id}`); }} className="mt-3 rounded-lg border border-amber-300/50 px-3 py-2 font-bold hover:bg-amber-300/10">Abrir cadastro existente</button>
                </div>
              )}
              {formError && <p className="mt-4 text-sm text-red-300">{formError}</p>}
              <div className="mt-6 flex justify-end gap-3">
                <button type="button" onClick={() => { setShowCreate(false); setEditingCustomer(null); }} className="rounded-xl border border-surface-03 px-4 py-3 text-sm font-bold text-stone hover:text-cream">Cancelar</button>
                <button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-xl bg-gold px-4 py-3 text-sm font-black text-surface-00 disabled:opacity-50">{saving && <Loader2 size={16} className="animate-spin" />} Salvar cliente</button>
              </div>
            </form>
          </div>
        )}

        {showImport && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-labelledby="import-customers-title">
            <div className="w-full max-w-2xl rounded-2xl border border-surface-03 bg-surface-01 p-6 shadow-2xl">
              <div className="mb-5 flex items-center justify-between">
                <div><p className="text-gold text-xs font-bold uppercase tracking-[0.2em]">CRM</p><h2 id="import-customers-title" className="text-xl font-black text-cream">Importar clientes</h2></div>
                <button type="button" onClick={() => setShowImport(false)} className="rounded-lg p-2 text-stone hover:bg-surface-03 hover:text-cream" aria-label="Fechar"><X size={18} /></button>
              </div>
              <input type="file" accept=".csv,.xlsx" onChange={(event) => { setImportFile(event.target.files?.[0] ?? null); setImportResult(null); setFormError(""); }} className="block w-full rounded-xl border border-surface-03 bg-surface-02 p-3 text-sm text-stone" />
              <p className="mt-2 text-xs text-stone">O telefone é a chave de duplicidade. Registros existentes não são sobrescritos e consentimentos promocionais permanecem desativados.</p>
              {formError && <p className="mt-3 text-sm text-red-300">{formError}</p>}
              {importResult && <div className="mt-4 rounded-xl border border-surface-03 bg-surface-02 p-4 text-sm text-cream"><p><strong>{importResult.valid_count}</strong> válidos · <strong>{importResult.rejected_count}</strong> rejeitados · <strong>{importResult.created_count}</strong> criados</p>{importResult.errors.length > 0 && <div className="mt-2 max-h-32 overflow-auto text-xs text-amber-200">{importResult.errors.map((item, index) => <p key={`${item.row}-${index}`}>Linha {item.row ?? "?"}: {item.reason}</p>)}</div>}</div>}
              <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={() => setShowImport(false)} className="rounded-xl border border-surface-03 px-4 py-3 text-sm font-bold text-stone hover:text-cream">Fechar</button><button type="button" disabled={!importFile || importing} onClick={() => void previewImport()} className="rounded-xl border border-gold/50 px-4 py-3 text-sm font-bold text-gold disabled:opacity-50">{importing ? "Analisando..." : "Analisar arquivo"}</button>{importResult && importResult.valid_count > 0 && importResult.created_count === 0 && <button type="button" disabled={importing} onClick={() => void commitImport()} className="rounded-xl bg-gold px-4 py-3 text-sm font-black text-surface-00 disabled:opacity-50">Confirmar importação</button>}</div>
            </div>
          </div>
        )}

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
                <CustomerRow key={c.id} customer={c} onEdit={(item) => { const address = item.addresses?.find((value) => value.is_default) ?? item.addresses?.[0]; setEditingCustomer(item); setForm({ name: item.name || "", phone: item.phone || "", email: item.email || "", street: address?.street || "", number: address?.number || "", complement: address?.complement || "", neighborhood: address?.neighborhood || "", city: address?.city || "", state: address?.state || "", zip_code: address?.zip_code || "" }); setShowCreate(true); setFormError(""); }} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import {
  Bike,
  Car,
  CheckCircle,
  Clock,
  Footprints,
  Loader2,
  Pencil,
  Plus,
  Power,
  RefreshCw,
  Star,
  User,
  XCircle,
} from "lucide-react";
import { deliveryApi, type DeliveryPerson } from "@/lib/api";

type FormData = {
  name: string;
  phone: string;
  vehicle_type: string;
  email: string;
  cpf: string;
  cnh: string;
  pix_key: string;
  password: string;
};

const BLANK: FormData = {
  name: "",
  phone: "",
  vehicle_type: "motorcycle",
  email: "",
  cpf: "",
  cnh: "",
  pix_key: "",
  password: "",
};

const VEHICLE_ICONS: Record<string, React.ReactNode> = {
  motorcycle: <Bike size={14} />,
  bicycle: <Bike size={14} />,
  car: <Car size={14} />,
  walking: <Footprints size={14} />,
};

const VEHICLE_LABELS: Record<string, string> = {
  motorcycle: "Moto",
  bicycle: "Bicicleta",
  car: "Carro",
  walking: "A pe",
};

const STATUS_CONFIG: Record<string, { label: string; cls: string; icon: React.ReactNode }> = {
  available: { label: "Disponivel", cls: "bg-green-500/15 text-green-300", icon: <CheckCircle size={12} /> },
  busy: { label: "Em rota", cls: "bg-gold/15 text-gold", icon: <Clock size={12} /> },
  offline: { label: "Offline", cls: "bg-stone/20 text-stone", icon: <XCircle size={12} /> },
};

const ACCESS_CONFIG = {
  active: { label: "Acesso ativo", cls: "bg-green-500/15 text-green-300", icon: <CheckCircle size={12} /> },
  inactive: { label: "Acesso inativo", cls: "bg-red-500/10 text-red-300", icon: <XCircle size={12} /> },
};

function Inp({
  label,
  name,
  value,
  onChange,
  type = "text",
  placeholder = "",
}: {
  label: string;
  name: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-stone text-xs font-medium">{label}</span>
      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="rounded-lg bg-surface-03 border border-surface-03 text-cream px-3 py-2 text-sm focus:outline-none focus:border-gold/50 placeholder:text-stone/50"
      />
    </label>
  );
}

export default function LogisticaMotoboys() {
  const [persons, setPersons] = useState<DeliveryPerson[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [editing, setEditing] = useState<DeliveryPerson | null>(null);
  const [form, setForm] = useState<FormData>(BLANK);
  const [formError, setFormError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await deliveryApi.listPersons({ includeInactive: true });
      setPersons(data ?? []);
    } catch {
      setError("Nao foi possivel carregar os motoboys.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setForm(BLANK);
    setFormError("");
    setEditing(null);
    setModal("create");
  }

  function openEdit(p: DeliveryPerson) {
    setForm({
      name: p.name,
      phone: p.phone,
      vehicle_type: p.vehicle_type,
      email: p.email ?? "",
      cpf: p.cpf ?? "",
      cnh: p.cnh ?? "",
      pix_key: p.pix_key ?? "",
      password: "",
    });
    setFormError("");
    setEditing(p);
    setModal("edit");
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  async function handleSubmit() {
    if (!form.name.trim() || !form.phone.trim()) {
      setFormError("Nome e telefone sao obrigatorios.");
      return;
    }
    setSaving(true);
    setFormError("");
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        phone: form.phone,
        vehicle_type: form.vehicle_type,
        email: form.email || undefined,
        cpf: form.cpf || undefined,
        cnh: form.cnh || undefined,
        pix_key: form.pix_key || undefined,
      };
      if (form.password) payload.password = form.password;

      if (modal === "create") {
        await deliveryApi.createPerson(payload);
      } else if (editing) {
        await deliveryApi.updatePerson(editing.id, payload);
      }
      setModal(null);
      await load();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus(p: DeliveryPerson) {
    const next = p.status === "available" ? "offline" : "available";
    try {
      await deliveryApi.setPersonStatus(p.id, next);
      await load();
    } catch {
      alert("Erro ao alterar status.");
    }
  }

  async function toggleAccess(p: DeliveryPerson) {
    const nextActive = !p.active;
    const action = nextActive ? "ativar" : "desativar";
    const message = nextActive
      ? `Ativar acesso de ${p.name} ao app do motoboy?`
      : `Desativar acesso de ${p.name}? Ele nao conseguira entrar no app nem receber novas entregas.`;
    if (!confirm(message)) return;
    try {
      await deliveryApi.setPersonAccess(p.id, nextActive);
      await load();
    } catch {
      alert(`Erro ao ${action} acesso.`);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-cream font-bold text-lg">Motoboys</h3>
          <p className="text-stone text-sm mt-0.5">
            Cadastro, acesso ao app do motoboy e disponibilidade para entregas.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={load}
            className="flex items-center gap-1.5 rounded-xl border border-surface-03 px-3 py-2 text-stone text-sm hover:text-cream transition-colors"
            title="Atualizar lista"
          >
            <RefreshCw size={14} />
          </button>
          <button
            type="button"
            onClick={openCreate}
            className="flex items-center gap-2 rounded-xl bg-gold px-4 py-2 text-sm font-bold text-cream hover:bg-gold/90 transition-colors"
          >
            <Plus size={16} /> Novo Motoboy
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={36} className="animate-spin text-gold" />
        </div>
      ) : persons.length === 0 ? (
        <div className="flex flex-col items-center py-16 text-center">
          <User size={48} className="text-stone mb-4" />
          <p className="text-cream font-bold">Nenhum motoboy cadastrado</p>
          <p className="text-stone text-sm mt-1">Clique em "Novo Motoboy" para adicionar.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {persons.map((p) => {
            const st = STATUS_CONFIG[p.status] ?? STATUS_CONFIG.offline;
            const access = p.active ? ACCESS_CONFIG.active : ACCESS_CONFIG.inactive;
            return (
              <div
                key={p.id}
                className={`rounded-2xl border border-surface-03 bg-surface-02 p-5 ${p.active ? "" : "opacity-75"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h4 className="text-cream font-bold text-sm truncate">{p.name}</h4>
                    <p className="text-stone text-xs mt-0.5">{p.phone}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-bold ${access.cls}`}>
                      {access.icon}
                      {access.label}
                    </span>
                    <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-bold ${st.cls}`}>
                      {st.icon}
                      {st.label}
                    </span>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-stone">
                  <span className="flex items-center gap-1">
                    {VEHICLE_ICONS[p.vehicle_type]}
                    {VEHICLE_LABELS[p.vehicle_type] ?? p.vehicle_type}
                  </span>
                  <span className="flex items-center gap-1">
                    <Star size={11} className="text-gold" />
                    {p.average_rating.toFixed(1)}
                  </span>
                  <span>{p.total_deliveries} entregas</span>
                </div>

                {p.email && <p className="mt-2 text-stone/70 text-xs truncate">{p.email}</p>}

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => openEdit(p)}
                    className="flex-1 flex items-center justify-center gap-1 rounded-lg bg-surface-03/60 hover:bg-surface-03 text-parchment text-xs py-2 transition-colors"
                  >
                    <Pencil size={12} /> Editar
                  </button>
                  {p.active && p.status !== "busy" && (
                    <button
                      type="button"
                      onClick={() => toggleStatus(p)}
                      className={`flex-1 rounded-lg text-xs py-2 font-medium transition-colors ${
                        p.status === "available"
                          ? "bg-stone/20 hover:bg-stone/30 text-stone"
                          : "bg-green-500/15 hover:bg-green-500/25 text-green-300"
                      }`}
                    >
                      {p.status === "available" ? "Colocar offline" : "Disponibilizar"}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => toggleAccess(p)}
                    className={`flex items-center justify-center gap-1 rounded-lg text-xs px-3 py-2 font-medium transition-colors ${
                      p.active
                        ? "bg-red-500/10 hover:bg-red-500/20 text-red-300"
                        : "bg-green-500/15 hover:bg-green-500/25 text-green-300"
                    }`}
                  >
                    <Power size={13} />
                    {p.active ? "Bloquear acesso" : "Liberar acesso"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 rounded-2xl border border-surface-03 p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h3 className="text-cream font-bold text-lg mb-2">
              {modal === "create" ? "Novo Motoboy" : "Editar Motoboy"}
            </h3>
            <p className="mb-5 text-xs text-stone">
              Email e senha liberam o acesso ao modulo /motoboy. O acesso pode ser bloqueado depois sem remover o cadastro.
            </p>

            <div className="grid gap-4 sm:grid-cols-2">
              <Inp label="Nome *" name="name" value={form.name} onChange={handleChange} placeholder="Nome completo" />
              <Inp label="Telefone *" name="phone" value={form.phone} onChange={handleChange} placeholder="(00) 00000-0000" />
              <Inp label="Email" name="email" value={form.email} onChange={handleChange} type="email" placeholder="para acesso ao app" />
              <Inp
                label="Senha"
                name="password"
                value={form.password}
                onChange={handleChange}
                type="password"
                placeholder={modal === "edit" ? "deixe em branco para manter" : ""}
              />
              <Inp label="CPF" name="cpf" value={form.cpf} onChange={handleChange} placeholder="000.000.000-00" />
              <Inp label="CNH" name="cnh" value={form.cnh} onChange={handleChange} placeholder="numero da CNH" />
              <Inp label="Chave PIX" name="pix_key" value={form.pix_key} onChange={handleChange} placeholder="para repasse de valores" />

              <label className="flex flex-col gap-1">
                <span className="text-stone text-xs font-medium">Veiculo</span>
                <select
                  name="vehicle_type"
                  value={form.vehicle_type}
                  onChange={handleChange}
                  className="rounded-lg bg-surface-03 border border-surface-03 text-cream px-3 py-2 text-sm"
                >
                  <option value="motorcycle">Moto</option>
                  <option value="bicycle">Bicicleta</option>
                  <option value="car">Carro</option>
                  <option value="walking">A pe</option>
                </select>
              </label>
            </div>

            {formError && <p className="mt-3 text-sm text-red-300">{formError}</p>}

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={() => setModal(null)}
                className="flex-1 rounded-xl border border-surface-03 py-2.5 text-stone text-sm hover:text-cream transition-colors"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={saving}
                className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-gold py-2.5 text-cream text-sm font-bold hover:bg-gold/90 disabled:opacity-50 transition-colors"
              >
                {saving && <Loader2 size={14} className="animate-spin" />}
                {modal === "create" ? "Cadastrar" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

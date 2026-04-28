import { useEffect, useState } from "react";
import {
  Users, Plus, Pencil, Trash2, Loader2, AlertCircle, Check, X, Eye, EyeOff, ShieldCheck, ShieldOff,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import { adminUsersApi, type ApiAdminUser } from "@/lib/api";

const cls = "w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone/60 outline-none focus:border-gold";

type FormState = { name: string; email: string; password: string; active: boolean };
const emptyForm = (): FormState => ({ name: "", email: "", password: "", active: true });

function formatDate(s: string) {
  return new Date(s).toLocaleDateString("pt-BR");
}

function UserModal({
  editing,
  onClose,
  onSave,
}: {
  editing: ApiAdminUser | null;
  onClose: () => void;
  onSave: (form: FormState) => Promise<void>;
}) {
  const [form, setForm] = useState<FormState>(
    editing
      ? { name: editing.name, email: editing.email, password: "", active: editing.active }
      : emptyForm()
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showPw, setShowPw] = useState(false);

  const set = (k: keyof FormState, v: string | boolean) => setForm((p) => ({ ...p, [k]: v }));

  const handleSubmit = async () => {
    if (!form.name.trim() || !form.email.trim()) {
      setError("Nome e e-mail são obrigatórios.");
      return;
    }
    if (!editing && form.password.length < 8) {
      setError("Senha mínima de 8 caracteres.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onSave(form);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="bg-surface-02 border border-surface-03 rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-cream font-bold text-lg">{editing ? "Editar usuário" : "Novo usuário"}</h2>
          <button onClick={onClose} className="text-stone hover:text-cream"><X size={18} /></button>
        </div>

        {error && (
          <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-red-400 text-sm">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        <div>
          <label className="text-parchment text-xs mb-1 block">Nome</label>
          <input value={form.name} onChange={(e) => set("name", e.target.value)} className={cls} placeholder="Nome completo" />
        </div>

        <div>
          <label className="text-parchment text-xs mb-1 block">E-mail</label>
          <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} className={cls} placeholder="email@exemplo.com" />
        </div>

        <div>
          <label className="text-parchment text-xs mb-1 block">
            {editing ? "Nova senha (deixe em branco para manter)" : "Senha"}
          </label>
          <div className="relative">
            <input
              type={showPw ? "text" : "password"}
              value={form.password}
              onChange={(e) => set("password", e.target.value)}
              className={cls + " pr-10"}
              placeholder={editing ? "••••••••" : "Mínimo 8 caracteres"}
              autoComplete="new-password"
            />
            <button type="button" onClick={() => setShowPw((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-stone hover:text-cream">
              {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </div>

        <label className="flex items-center gap-2 text-parchment text-sm">
          <input type="checkbox" checked={form.active} onChange={(e) => set("active", e.target.checked)} className="accent-gold" />
          Usuário ativo
        </label>

        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 border border-surface-03 text-stone hover:text-cream rounded-xl py-2.5 text-sm transition-colors">
            Cancelar
          </button>
          <button onClick={handleSubmit} disabled={saving} className="flex-1 bg-gold hover:bg-gold/90 disabled:opacity-60 text-cream font-bold rounded-xl py-2.5 text-sm transition-colors flex items-center justify-center gap-2">
            {saving ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
            {editing ? "Salvar" : "Criar"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AdminUsuarios() {
  const [users, setUsers] = useState<ApiAdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modal, setModal] = useState<"new" | ApiAdminUser | null>(null);
  const [message, setMessage] = useState("");

  const currentAdminId = (() => {
    try { return JSON.parse(localStorage.getItem("admin_user") ?? "{}").id ?? ""; } catch { return ""; }
  })();

  const load = () => {
    setLoading(true);
    adminUsersApi.list()
      .then(setUsers)
      .catch(() => setError("Não foi possível carregar os usuários."))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSave = async (form: FormState) => {
    const editing = modal !== "new" ? modal as ApiAdminUser : null;
    if (editing) {
      const payload: Parameters<typeof adminUsersApi.update>[1] = {
        name: form.name, email: form.email, active: form.active,
      };
      if (form.password) payload.password = form.password;
      const updated = await adminUsersApi.update(editing.id, payload);
      setUsers((prev) => prev.map((u) => (u.id === editing.id ? updated : u)));
      setMessage("Usuário atualizado.");
    } else {
      const created = await adminUsersApi.create({ name: form.name, email: form.email, password: form.password, active: form.active });
      setUsers((prev) => [...prev, created]);
      setMessage("Usuário criado com sucesso.");
    }
    setModal(null);
    setTimeout(() => setMessage(""), 3000);
  };

  const handleRemove = async (user: ApiAdminUser) => {
    if (!confirm(`Desativar o usuário "${user.name}"?`)) return;
    await adminUsersApi.remove(user.id);
    setUsers((prev) => prev.map((u) => (u.id === user.id ? { ...u, active: false } : u)));
    setMessage("Usuário desativado.");
    setTimeout(() => setMessage(""), 3000);
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />

      <main className="flex-1 overflow-y-auto">
        <header className="bg-surface-02 border-b border-surface-03 px-6 py-5 flex items-center justify-between gap-4">
          <div>
            <p className="text-gold text-xs font-bold uppercase tracking-[0.2em]">Acesso</p>
            <h1 className="text-cream text-2xl font-bold">Usuários do Sistema</h1>
            <p className="text-stone text-sm mt-1">Administradores com acesso ao painel.</p>
          </div>
          <button
            onClick={() => setModal("new")}
            className="inline-flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold px-5 py-3 rounded-xl transition-colors"
          >
            <Plus size={17} /> Novo usuário
          </button>
        </header>

        <div className="p-6">
          {message && (
            <div className="mb-4 flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-4 py-3 text-emerald-400 text-sm">
              <Check size={14} /> {message}
            </div>
          )}

          {loading ? (
            <div className="flex items-center gap-2 text-stone py-24 justify-center">
              <Loader2 size={22} className="animate-spin" /> Carregando...
            </div>
          ) : error ? (
            <div className="text-red-400 text-sm text-center py-12">{error}</div>
          ) : (
            <div className="space-y-3">
              {users.map((user) => (
                <div key={user.id} className="bg-surface-02 border border-surface-03 rounded-xl px-5 py-4 flex items-center gap-4">
                  {/* Avatar */}
                  <div className="w-10 h-10 rounded-full bg-gold/20 border border-gold/30 flex items-center justify-center flex-shrink-0">
                    <span className="text-gold font-bold text-sm">
                      {user.name.split(" ").slice(0, 2).map((n) => n[0]?.toUpperCase()).join("")}
                    </span>
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-cream font-semibold truncate">{user.name}</p>
                      {user.id === currentAdminId && (
                        <span className="text-[10px] font-bold text-gold bg-gold/15 border border-gold/25 rounded px-1.5 py-0.5">Você</span>
                      )}
                    </div>
                    <p className="text-stone text-sm truncate">{user.email}</p>
                    <p className="text-stone text-xs mt-0.5">Criado em {formatDate(user.created_at)}</p>
                  </div>

                  {/* Status */}
                  <div className="flex-shrink-0">
                    {user.active
                      ? <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full bg-emerald-500/15 text-emerald-400"><ShieldCheck size={12} /> Ativo</span>
                      : <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full bg-red-500/15 text-red-400"><ShieldOff size={12} /> Inativo</span>
                    }
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => setModal(user)}
                      className="text-stone hover:text-cream bg-surface-03/60 hover:bg-surface-03 rounded-lg p-2 transition-colors"
                    >
                      <Pencil size={15} />
                    </button>
                    {user.id !== currentAdminId && (
                      <button
                        onClick={() => handleRemove(user)}
                        className="text-stone hover:text-red-400 bg-surface-03/60 hover:bg-red-500/10 rounded-lg p-2 transition-colors"
                      >
                        <Trash2 size={15} />
                      </button>
                    )}
                  </div>
                </div>
              ))}

              {users.length === 0 && (
                <div className="flex flex-col items-center justify-center py-24 gap-3 text-stone">
                  <Users size={40} className="opacity-30" />
                  <p>Nenhum usuário encontrado.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {modal !== null && (
        <UserModal
          editing={modal === "new" ? null : modal}
          onClose={() => setModal(null)}
          onSave={handleSave}
        />
      )}
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import {
  Users, Shield, History, Plus, Search, Edit2, Trash2,
  CheckCircle2, XCircle, Copy, Save, ChevronDown, AlertTriangle,
  Loader2, Key, ToggleLeft, ToggleRight, User, Clock,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import {
  adminUsersApi, rbacApi,
  type ApiAdminUser, type ApiRole, type ApiModule,
  type ApiPermission, type ApiRolePermission, type ApiAuditLog,
} from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

type Tab = "usuarios" | "perfis" | "permissoes" | "auditoria";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(dateStr?: string | null) {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function roleBadge(roleName?: string | null) {
  const name = (roleName ?? "master").toLowerCase();
  const map: Record<string, string> = {
    master:        "bg-red-500/20 text-red-300 border-red-500/30",
    administrador: "bg-orange-500/20 text-orange-300 border-orange-500/30",
    gerente:       "bg-blue-500/20 text-blue-300 border-blue-500/30",
    atendente:     "bg-green-500/20 text-green-300 border-green-500/30",
    cozinha:       "bg-amber-500/20 text-amber-300 border-amber-500/30",
    entregador:    "bg-purple-500/20 text-purple-300 border-purple-500/30",
    financeiro:    "bg-teal-500/20 text-teal-300 border-teal-500/30",
    marketing:     "bg-pink-500/20 text-pink-300 border-pink-500/30",
  };
  return map[name] ?? "bg-surface-03 text-stone border-surface-03";
}

const ACTION_LABELS: Record<string, string> = {
  create:             "Criou",
  update:             "Atualizou",
  delete:             "Excluiu",
  deactivate:         "Desativou",
  toggle_status:      "Alterou status",
  reset_password:     "Redefiniu senha",
  update_permissions: "Atualizou permissões",
};

// ── User modal ────────────────────────────────────────────────────────────────

interface UserModalProps {
  user?: ApiAdminUser | null;
  roles: ApiRole[];
  onClose: () => void;
  onSave: () => void;
}

function UserModal({ user, roles, onClose, onSave }: UserModalProps) {
  const isEdit = !!user;
  const [name, setName]         = useState(user?.name ?? "");
  const [email, setEmail]       = useState(user?.email ?? "");
  const [phone, setPhone]       = useState(user?.phone ?? "");
  const [roleId, setRoleId]     = useState(user?.role_id ?? "");
  const [storeId, setStoreId]   = useState(user?.store_id ?? "");
  const [active, setActive]     = useState(user?.active ?? true);
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [saving, setSaving]     = useState(false);

  const handleSave = async () => {
    if (!name.trim() || !email.trim()) { setError("Nome e e-mail são obrigatórios."); return; }
    if (!isEdit && password.length < 8) { setError("Senha deve ter no mínimo 8 caracteres."); return; }
    setSaving(true); setError("");
    try {
      const body: Record<string, unknown> = {
        name: name.trim(), email: email.trim(),
        phone: phone.trim() || null,
        role_id: roleId || null,
        store_id: storeId.trim() || null,
        active,
      };
      if (password) body.password = password;
      if (isEdit) {
        await adminUsersApi.update(user!.id, body as Parameters<typeof adminUsersApi.update>[1]);
      } else {
        await adminUsersApi.create(body as Parameters<typeof adminUsersApi.create>[0]);
      }
      onSave();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg shadow-2xl">
        <div className="px-6 py-4 border-b border-surface-03 flex items-center justify-between">
          <h3 className="text-cream font-bold text-base">{isEdit ? "Editar Usuário" : "Novo Usuário"}</h3>
          <button onClick={onClose} className="text-stone hover:text-cream"><XCircle size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm flex items-center gap-2">
              <AlertTriangle size={14} /> {error}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="text-stone text-xs mb-1 block">Nome *</label>
              <input value={name} onChange={e => setName(e.target.value)}
                className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold/50"
                placeholder="Nome completo" />
            </div>
            <div>
              <label className="text-stone text-xs mb-1 block">E-mail *</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold/50"
                placeholder="email@exemplo.com" />
            </div>
            <div>
              <label className="text-stone text-xs mb-1 block">Telefone</label>
              <input value={phone} onChange={e => setPhone(e.target.value)}
                className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold/50"
                placeholder="(11) 99999-9999" />
            </div>
            <div>
              <label className="text-stone text-xs mb-1 block">Perfil / Cargo</label>
              <div className="relative">
                <select value={roleId} onChange={e => setRoleId(e.target.value)}
                  className="w-full appearance-none bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold/50">
                  <option value="">Master (acesso total)</option>
                  {roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
                <ChevronDown size={14} className="absolute right-3 top-3 text-stone pointer-events-none" />
              </div>
            </div>
            <div>
              <label className="text-stone text-xs mb-1 block">Loja / Unidade</label>
              <input value={storeId} onChange={e => setStoreId(e.target.value)}
                className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold/50"
                placeholder="ID ou nome da loja" />
            </div>
            <div className="col-span-2">
              <label className="text-stone text-xs mb-1 block">
                {isEdit ? "Nova Senha (deixe em branco para manter)" : "Senha *"}
              </label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold/50"
                placeholder="Mínimo 8 caracteres" />
            </div>
            <div className="col-span-2 flex items-center justify-between p-3 bg-surface-03/40 rounded-lg">
              <span className="text-stone text-sm">Status da conta</span>
              <button onClick={() => setActive(a => !a)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors ${
                  active ? "border-green-500/40 bg-green-500/10 text-green-400" : "border-surface-03 text-stone"
                }`}>
                {active ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                {active ? "Ativo" : "Inativo"}
              </button>
            </div>
          </div>
        </div>
        <div className="px-6 py-4 border-t border-surface-03 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 rounded-lg border border-surface-03 text-stone hover:text-cream text-sm">
            Cancelar
          </button>
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-gold text-cream font-semibold text-sm disabled:opacity-50">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {isEdit ? "Salvar alterações" : "Criar usuário"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Reset password modal ──────────────────────────────────────────────────────

function ResetPasswordModal({ userId, onClose }: { userId: string; onClose: () => void }) {
  const [pw, setPw]         = useState("");
  const [done, setDone]     = useState(false);
  const [err, setErr]       = useState("");
  const [saving, setSaving] = useState(false);

  const handle = async () => {
    if (pw.length < 8) { setErr("Mínimo 8 caracteres."); return; }
    setSaving(true); setErr("");
    try { await adminUsersApi.resetPassword(userId, pw); setDone(true); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : "Erro."); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-sm shadow-2xl p-6 space-y-4">
        <h3 className="text-cream font-bold flex items-center gap-2"><Key size={16} className="text-gold" /> Redefinir Senha</h3>
        {done
          ? <div className="text-green-400 text-sm flex items-center gap-2"><CheckCircle2 size={14} /> Senha redefinida com sucesso.</div>
          : <>
              {err && <p className="text-red-400 text-sm">{err}</p>}
              <input type="password" value={pw} onChange={e => setPw(e.target.value)}
                className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold/50"
                placeholder="Nova senha (mín. 8 caracteres)" />
            </>
        }
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onClose} className="px-4 py-2 rounded-lg border border-surface-03 text-stone hover:text-cream text-sm">
            {done ? "Fechar" : "Cancelar"}
          </button>
          {!done && (
            <button onClick={handle} disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gold text-cream font-semibold text-sm disabled:opacity-50">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Key size={14} />}
              Redefinir
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Role modal ────────────────────────────────────────────────────────────────

function RoleModal({ role, onClose, onSave }: { role?: ApiRole | null; onClose: () => void; onSave: () => void }) {
  const [name, setName]     = useState(role?.name ?? "");
  const [desc, setDesc]     = useState(role?.description ?? "");
  const [error, setError]   = useState("");
  const [saving, setSaving] = useState(false);

  const handle = async () => {
    if (!name.trim()) { setError("Nome é obrigatório."); return; }
    setSaving(true); setError("");
    try {
      if (role) await rbacApi.updateRole(role.id, { name: name.trim(), description: desc.trim() || undefined });
      else      await rbacApi.createRole({ name: name.trim(), description: desc.trim() || undefined });
      onSave();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erro ao salvar."); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-md shadow-2xl">
        <div className="px-6 py-4 border-b border-surface-03 flex items-center justify-between">
          <h3 className="text-cream font-bold text-base">{role ? "Editar Perfil" : "Novo Perfil"}</h3>
          <button onClick={onClose} className="text-stone hover:text-cream"><XCircle size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <div>
            <label className="text-stone text-xs mb-1 block">Nome do perfil *</label>
            <input value={name} onChange={e => setName(e.target.value)} disabled={role?.is_system}
              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold/50 disabled:opacity-50"
              placeholder="Ex: Supervisor" />
            {role?.is_system && <p className="text-stone text-xs mt-1">Perfis do sistema não podem ser renomeados.</p>}
          </div>
          <div>
            <label className="text-stone text-xs mb-1 block">Descrição</label>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={3}
              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold/50 resize-none"
              placeholder="Descreva as responsabilidades deste perfil" />
          </div>
        </div>
        <div className="px-6 py-4 border-t border-surface-03 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 rounded-lg border border-surface-03 text-stone hover:text-cream text-sm">Cancelar</button>
          <button onClick={handle} disabled={saving}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-gold text-cream font-semibold text-sm disabled:opacity-50">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Salvar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Permission matrix ─────────────────────────────────────────────────────────

const PERM_KEYS = ["view", "create", "edit", "delete", "approve", "export", "manage"];
const PERM_LABELS: Record<string, string> = {
  view: "Ver", create: "Criar", edit: "Editar", delete: "Excluir",
  approve: "Aprovar", export: "Exportar", manage: "Gerenciar",
};

function PermissionMatrix({ roleId, modules, permissions }: {
  roleId: string;
  modules: ApiModule[];
  permissions: ApiPermission[];
}) {
  const [matrix, setMatrix] = useState<Record<string, Record<string, boolean>>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [saved, setSaved]     = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await rbacApi.getRolePermissions(roleId);
      const m: Record<string, Record<string, boolean>> = {};
      const permById = Object.fromEntries(permissions.map(p => [p.id, p.key]));
      const modById  = Object.fromEntries(modules.map(mod => [mod.id, mod.key]));
      for (const row of rows) {
        const mk = modById[row.module_id];
        const pk = permById[row.permission_id];
        if (mk && pk) { m[mk] ??= {}; m[mk][pk] = row.allowed; }
      }
      setMatrix(m);
    } finally { setLoading(false); }
  }, [roleId, modules, permissions]);

  useEffect(() => { load(); }, [load]);

  const toggle = (mk: string, pk: string) =>
    setMatrix(prev => ({ ...prev, [mk]: { ...(prev[mk] ?? {}), [pk]: !(prev[mk]?.[pk]) } }));

  const setAllModule = (mk: string, val: boolean) =>
    setMatrix(prev => ({ ...prev, [mk]: Object.fromEntries(PERM_KEYS.map(k => [k, val])) }));

  const setAllColumn = (pk: string, val: boolean) =>
    setMatrix(prev => {
      const next = { ...prev };
      for (const mod of modules) { next[mod.key] = { ...(next[mod.key] ?? {}), [pk]: val }; }
      return next;
    });

  const handleSave = async () => {
    setSaving(true);
    try {
      const permByKey = Object.fromEntries(permissions.map(p => [p.key, p.id]));
      const modByKey  = Object.fromEntries(modules.map(m => [m.key, m.id]));
      const entries: ApiRolePermission[] = [];
      for (const [mk, perms] of Object.entries(matrix)) {
        for (const [pk, allowed] of Object.entries(perms)) {
          if (allowed && modByKey[mk] && permByKey[pk])
            entries.push({ module_id: modByKey[mk], permission_id: permByKey[pk], allowed: true });
        }
      }
      await rbacApi.updateRolePermissions(roleId, entries);
      setSaved(true); setTimeout(() => setSaved(false), 2500);
    } catch { /* noop */ }
    finally { setSaving(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-40 text-stone gap-2">
      <Loader2 size={18} className="animate-spin" /> Carregando permissões...
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-stone text-sm">Marque as permissões que este perfil deve ter em cada módulo.</p>
        <button onClick={handleSave} disabled={saving}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gold text-cream font-semibold text-sm disabled:opacity-50">
          {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <CheckCircle2 size={14} /> : <Save size={14} />}
          {saving ? "Salvando..." : saved ? "Salvo!" : "Salvar Permissões"}
        </button>
      </div>
      <div className="overflow-x-auto rounded-xl border border-surface-03">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-03/60">
              <th className="text-left px-4 py-3 text-stone font-medium w-52">Módulo</th>
              {PERM_KEYS.map(pk => (
                <th key={pk} className="text-center px-2 py-3 text-stone font-medium min-w-[68px]">
                  <div className="text-xs">{PERM_LABELS[pk]}</div>
                  <div className="flex gap-1 justify-center mt-1.5">
                    <button onClick={() => setAllColumn(pk, true)} title="Marcar coluna"
                      className="text-green-500/60 hover:text-green-400 text-[10px] px-1">✓</button>
                    <button onClick={() => setAllColumn(pk, false)} title="Desmarcar coluna"
                      className="text-red-500/60 hover:text-red-400 text-[10px] px-1">✗</button>
                  </div>
                </th>
              ))}
              <th className="text-center px-2 py-3 text-stone font-medium w-20 text-xs">Linha</th>
            </tr>
          </thead>
          <tbody>
            {modules.map((mod, i) => {
              const allOn = PERM_KEYS.every(pk => matrix[mod.key]?.[pk]);
              return (
                <tr key={mod.id} className={`border-t border-surface-03 ${i % 2 === 0 ? "" : "bg-surface-03/20"}`}>
                  <td className="px-4 py-2.5 text-cream text-sm font-medium">{mod.name}</td>
                  {PERM_KEYS.map(pk => {
                    const checked = !!(matrix[mod.key]?.[pk]);
                    return (
                      <td key={pk} className="text-center px-2 py-2.5">
                        <button onClick={() => toggle(mod.key, pk)}
                          className={`w-5 h-5 rounded border-2 transition-all flex items-center justify-center mx-auto ${
                            checked
                              ? "bg-gold border-gold text-cream"
                              : "border-surface-03 bg-surface-03/50 hover:border-gold/40"
                          }`}>
                          {checked && <CheckCircle2 size={10} />}
                        </button>
                      </td>
                    );
                  })}
                  <td className="text-center px-2 py-2.5">
                    <button onClick={() => setAllModule(mod.key, !allOn)}
                      className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                        allOn ? "bg-green-500/20 text-green-400" : "bg-surface-03 text-stone hover:text-cream"
                      }`}>
                      {allOn ? "Todos" : "—"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminUsuarios() {
  const [tab, setTab]                 = useState<Tab>("usuarios");
  const [users, setUsers]             = useState<ApiAdminUser[]>([]);
  const [roles, setRoles]             = useState<ApiRole[]>([]);
  const [modules, setModules]         = useState<ApiModule[]>([]);
  const [permissions, setPermissions] = useState<ApiPermission[]>([]);
  const [auditLogs, setAuditLogs]     = useState<ApiAuditLog[]>([]);
  const [auditTotal, setAuditTotal]   = useState(0);
  const [loading, setLoading]         = useState(true);

  const [userModal, setUserModal]         = useState<"new" | ApiAdminUser | null>(null);
  const [roleModal, setRoleModal]         = useState<"new" | ApiRole | null>(null);
  const [resetUser, setResetUser]         = useState<string | null>(null);
  const [selectedRole, setSelectedRole]   = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{ type: "user" | "role"; id: string; name: string } | null>(null);

  const [search, setSearch]             = useState("");
  const [filterRole, setFilterRole]     = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [auditOffset, setAuditOffset]   = useState(0);

  const currentAdmin = (() => {
    try { return JSON.parse(localStorage.getItem("admin_user") ?? "{}"); } catch { return {}; }
  })();

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [u, r, m, p] = await Promise.all([
        adminUsersApi.list(),
        rbacApi.listRoles(),
        rbacApi.listModules(),
        rbacApi.listPermissions(),
      ]);
      setUsers(u); setRoles(r); setModules(m); setPermissions(p);
      if (!selectedRole && r.length > 0) setSelectedRole(r[0].id);
    } finally { setLoading(false); }
  }, [selectedRole]);

  const loadAudit = useCallback(async (offset = 0) => {
    try {
      const res = await rbacApi.getAuditLogs({ limit: 50, offset });
      setAuditLogs(res.items); setAuditTotal(res.total); setAuditOffset(offset);
    } catch { /* noop */ }
  }, []);

  useEffect(() => { loadAll(); }, []);
  useEffect(() => { if (tab === "auditoria") loadAudit(0); }, [tab]);

  const filteredUsers = users.filter(u => {
    const q = search.toLowerCase();
    const matchSearch = !q ||
      u.name.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      (u.phone ?? "").includes(q);
    const matchRole = !filterRole ||
      u.role_id === filterRole ||
      (!u.role_id && filterRole === "__master__");
    const matchStatus = !filterStatus ||
      (filterStatus === "active" && u.active) ||
      (filterStatus === "inactive" && !u.active);
    return matchSearch && matchRole && matchStatus;
  });

  const handleDeleteConfirm = async () => {
    if (!confirmDelete) return;
    try {
      if (confirmDelete.type === "user") await adminUsersApi.remove(confirmDelete.id);
      else await rbacApi.deleteRole(confirmDelete.id);
      await loadAll();
    } catch { /* noop */ }
    setConfirmDelete(null);
  };

  const TABS: { id: Tab; icon: typeof Users; label: string }[] = [
    { id: "usuarios",   icon: Users,   label: "Usuários" },
    { id: "perfis",     icon: Shield,  label: "Perfis & Cargos" },
    { id: "permissoes", icon: Key,     label: "Matriz de Permissões" },
    { id: "auditoria",  icon: History, label: "Auditoria" },
  ];

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-surface-02 border-b border-surface-03 px-6 py-4 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <Shield size={22} className="text-gold" />
            <div>
              <h2 className="text-xl font-bold text-cream">Usuários e Permissões</h2>
              <p className="text-stone text-xs">Controle de acesso baseado em perfis (RBAC)</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {tab === "usuarios" && (
              <button onClick={() => setUserModal("new")}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gold text-cream font-semibold text-sm hover:bg-gold/90 transition-colors">
                <Plus size={15} /> Novo Usuário
              </button>
            )}
            {tab === "perfis" && (
              <button onClick={() => setRoleModal("new")}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gold text-cream font-semibold text-sm hover:bg-gold/90 transition-colors">
                <Plus size={15} /> Novo Perfil
              </button>
            )}
            <AdminTopActions />
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-surface-02/50 border-b border-surface-03 px-6 flex-shrink-0">
          <div className="flex gap-1">
            {TABS.map(t => {
              const Icon = t.icon;
              return (
                <button key={t.id} onClick={() => setTab(t.id)}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                    tab === t.id ? "border-gold text-gold" : "border-transparent text-stone hover:text-cream"
                  }`}>
                  <Icon size={14} /> {t.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center h-40 text-stone gap-2">
              <Loader2 size={20} className="animate-spin" /> Carregando...
            </div>
          ) : (
            <>
              {/* ── USUÁRIOS ── */}
              {tab === "usuarios" && (
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-3">
                    <div className="relative flex-1 min-w-[200px]">
                      <Search size={14} className="absolute left-3 top-2.5 text-stone" />
                      <input value={search} onChange={e => setSearch(e.target.value)}
                        className="w-full bg-surface-02 border border-surface-03 rounded-lg pl-9 pr-3 py-2 text-cream text-sm focus:outline-none focus:border-gold/50"
                        placeholder="Buscar por nome, e-mail ou telefone..." />
                    </div>
                    <div className="relative">
                      <select value={filterRole} onChange={e => setFilterRole(e.target.value)}
                        className="appearance-none bg-surface-02 border border-surface-03 rounded-lg px-3 py-2 text-stone text-sm focus:outline-none pr-8">
                        <option value="">Todos os perfis</option>
                        <option value="__master__">Master</option>
                        {roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                      </select>
                      <ChevronDown size={12} className="absolute right-2.5 top-3 text-stone pointer-events-none" />
                    </div>
                    <div className="relative">
                      <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
                        className="appearance-none bg-surface-02 border border-surface-03 rounded-lg px-3 py-2 text-stone text-sm focus:outline-none pr-8">
                        <option value="">Todos os status</option>
                        <option value="active">Ativos</option>
                        <option value="inactive">Inativos</option>
                      </select>
                      <ChevronDown size={12} className="absolute right-2.5 top-3 text-stone pointer-events-none" />
                    </div>
                  </div>

                  <div className="bg-surface-02 rounded-2xl border border-surface-03 overflow-hidden">
                    <div className="px-4 py-3 border-b border-surface-03 text-stone text-xs">
                      {filteredUsers.length} usuário(s) encontrado(s)
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-surface-03 bg-surface-03/40">
                          <th className="text-left px-4 py-3 text-stone font-medium">Usuário</th>
                          <th className="text-left px-4 py-3 text-stone font-medium">Perfil</th>
                          <th className="text-left px-4 py-3 text-stone font-medium hidden lg:table-cell">Último acesso</th>
                          <th className="text-center px-4 py-3 text-stone font-medium">Status</th>
                          <th className="text-right px-4 py-3 text-stone font-medium">Ações</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredUsers.length === 0 && (
                          <tr><td colSpan={5} className="text-center text-stone py-12 text-sm">Nenhum usuário encontrado.</td></tr>
                        )}
                        {filteredUsers.map(u => (
                          <tr key={u.id} className="border-t border-surface-03 hover:bg-surface-03/20 transition-colors">
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-gold/20 flex items-center justify-center flex-shrink-0">
                                  <User size={14} className="text-gold" />
                                </div>
                                <div>
                                  <div className="flex items-center gap-2">
                                    <p className="text-cream font-medium text-sm">{u.name}</p>
                                    {u.id === currentAdmin?.id && (
                                      <span className="text-[10px] bg-gold/20 text-gold px-1.5 py-0.5 rounded-full">Você</span>
                                    )}
                                  </div>
                                  <p className="text-stone text-xs">{u.email}</p>
                                  {u.phone && <p className="text-stone text-xs">{u.phone}</p>}
                                </div>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${roleBadge(u.role_name)}`}>
                                {u.role_name ?? "Master"}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-stone text-xs hidden lg:table-cell">
                              <div className="flex items-center gap-1"><Clock size={11} /> {fmt(u.last_login_at)}</div>
                            </td>
                            <td className="px-4 py-3 text-center">
                              {u.active
                                ? <span className="text-xs bg-green-500/20 text-green-400 border border-green-500/30 px-2 py-0.5 rounded-full">Ativo</span>
                                : <span className="text-xs bg-red-500/20 text-red-400 border border-red-500/30 px-2 py-0.5 rounded-full">Inativo</span>
                              }
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center justify-end gap-1">
                                <button onClick={() => setUserModal(u)} title="Editar"
                                  className="p-1.5 rounded-lg text-stone hover:text-gold hover:bg-gold/10 transition-colors">
                                  <Edit2 size={14} />
                                </button>
                                <button onClick={() => setResetUser(u.id)} title="Redefinir senha"
                                  className="p-1.5 rounded-lg text-stone hover:text-amber-400 hover:bg-amber-500/10 transition-colors">
                                  <Key size={14} />
                                </button>
                                {u.id !== currentAdmin?.id && (
                                  <>
                                    <button
                                      onClick={async () => { await adminUsersApi.toggleStatus(u.id); loadAll(); }}
                                      title={u.active ? "Desativar" : "Ativar"}
                                      className={`p-1.5 rounded-lg transition-colors ${
                                        u.active
                                          ? "text-stone hover:text-red-400 hover:bg-red-500/10"
                                          : "text-stone hover:text-green-400 hover:bg-green-500/10"
                                      }`}>
                                      {u.active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                                    </button>
                                    <button
                                      onClick={() => setConfirmDelete({ type: "user", id: u.id, name: u.name })}
                                      title="Desativar conta"
                                      className="p-1.5 rounded-lg text-stone hover:text-red-400 hover:bg-red-500/10 transition-colors">
                                      <Trash2 size={14} />
                                    </button>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* ── PERFIS ── */}
              {tab === "perfis" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {roles.map(r => (
                    <div key={r.id} className="bg-surface-02 rounded-2xl border border-surface-03 p-5 space-y-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <Shield size={14} className="text-gold" />
                          <h3 className="text-cream font-bold text-sm">{r.name}</h3>
                          {r.is_system && (
                            <span className="text-[10px] bg-surface-03 text-stone px-1.5 py-0.5 rounded">Sistema</span>
                          )}
                        </div>
                        {r.description && <p className="text-stone text-xs leading-relaxed">{r.description}</p>}
                      </div>
                      <div className="text-stone text-xs flex items-center gap-1 py-2 border-t border-surface-03">
                        <Users size={11} />
                        {(r.user_count ?? 0)} usuário(s) vinculado(s)
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button onClick={() => setRoleModal(r)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-surface-03 text-stone hover:text-cream text-xs transition-colors">
                          <Edit2 size={11} /> Editar
                        </button>
                        <button onClick={async () => { await rbacApi.duplicateRole(r.id); loadAll(); }}
                          title="Duplicar" className="p-1.5 rounded-lg border border-surface-03 text-stone hover:text-cream transition-colors">
                          <Copy size={12} />
                        </button>
                        <button onClick={() => { setSelectedRole(r.id); setTab("permissoes"); }}
                          title="Editar permissões"
                          className="p-1.5 rounded-lg border border-gold/30 text-gold/70 hover:text-gold hover:bg-gold/10 transition-colors">
                          <Key size={12} />
                        </button>
                        {!r.is_system && (
                          <button onClick={() => setConfirmDelete({ type: "role", id: r.id, name: r.name })}
                            className="p-1.5 rounded-lg border border-surface-03 text-stone hover:text-red-400 hover:bg-red-500/10 transition-colors">
                            <Trash2 size={12} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* ── PERMISSÕES ── */}
              {tab === "permissoes" && (
                <div className="space-y-4">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-stone text-sm">Editando perfil:</span>
                    <div className="relative">
                      <select value={selectedRole ?? ""} onChange={e => setSelectedRole(e.target.value)}
                        className="appearance-none bg-surface-02 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none pr-8 font-medium">
                        {roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                      </select>
                      <ChevronDown size={12} className="absolute right-2.5 top-3 text-stone pointer-events-none" />
                    </div>
                    <p className="text-stone text-xs">Perfil "Master" tem acesso total independente das configurações abaixo.</p>
                  </div>
                  {selectedRole && modules.length > 0 && permissions.length > 0 && (
                    <PermissionMatrix key={selectedRole} roleId={selectedRole} modules={modules} permissions={permissions} />
                  )}
                </div>
              )}

              {/* ── AUDITORIA ── */}
              {tab === "auditoria" && (
                <div className="space-y-4">
                  <div className="bg-surface-02 rounded-2xl border border-surface-03 overflow-hidden">
                    <div className="px-4 py-3 border-b border-surface-03 text-stone text-xs">
                      {auditTotal} registro(s) no total
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-surface-03 bg-surface-03/40">
                          <th className="text-left px-4 py-3 text-stone font-medium">Data/Hora</th>
                          <th className="text-left px-4 py-3 text-stone font-medium">Usuário</th>
                          <th className="text-left px-4 py-3 text-stone font-medium">Ação</th>
                          <th className="text-left px-4 py-3 text-stone font-medium hidden md:table-cell">Entidade</th>
                          <th className="text-left px-4 py-3 text-stone font-medium hidden lg:table-cell">IP</th>
                        </tr>
                      </thead>
                      <tbody>
                        {auditLogs.length === 0 && (
                          <tr><td colSpan={5} className="text-center text-stone py-12 text-sm">Nenhum registro encontrado.</td></tr>
                        )}
                        {auditLogs.map(log => (
                          <tr key={log.id} className="border-t border-surface-03 hover:bg-surface-03/20">
                            <td className="px-4 py-2.5 text-stone text-xs whitespace-nowrap">{fmt(log.created_at)}</td>
                            <td className="px-4 py-2.5 text-cream text-xs">{log.user_name ?? "—"}</td>
                            <td className="px-4 py-2.5">
                              <span className="text-xs bg-surface-03 text-parchment px-2 py-0.5 rounded">
                                {ACTION_LABELS[log.action] ?? log.action}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-stone text-xs hidden md:table-cell">
                              {log.entity_type}{log.entity_id ? ` · ${log.entity_id.slice(0, 8)}` : ""}
                            </td>
                            <td className="px-4 py-2.5 text-stone text-xs hidden lg:table-cell">
                              {log.ip_address ?? "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {auditTotal > 50 && (
                    <div className="flex items-center justify-between text-sm text-stone">
                      <span>{auditOffset + 1}–{Math.min(auditOffset + 50, auditTotal)} de {auditTotal}</span>
                      <div className="flex gap-2">
                        <button disabled={auditOffset === 0} onClick={() => loadAudit(auditOffset - 50)}
                          className="px-3 py-1.5 rounded-lg border border-surface-03 disabled:opacity-40 hover:text-cream text-xs">
                          Anterior
                        </button>
                        <button disabled={auditOffset + 50 >= auditTotal} onClick={() => loadAudit(auditOffset + 50)}
                          className="px-3 py-1.5 rounded-lg border border-surface-03 disabled:opacity-40 hover:text-cream text-xs">
                          Próxima
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Modals ── */}
      {userModal && (
        <UserModal
          user={userModal === "new" ? null : userModal}
          roles={roles}
          onClose={() => setUserModal(null)}
          onSave={() => { setUserModal(null); loadAll(); }}
        />
      )}
      {roleModal && (
        <RoleModal
          role={roleModal === "new" ? null : roleModal}
          onClose={() => setRoleModal(null)}
          onSave={() => { setRoleModal(null); loadAll(); }}
        />
      )}
      {resetUser && <ResetPasswordModal userId={resetUser} onClose={() => setResetUser(null)} />}

      {confirmDelete && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-sm shadow-2xl p-6 space-y-4">
            <div className="flex items-center gap-3">
              <AlertTriangle size={20} className="text-red-400" />
              <h3 className="text-cream font-bold">Confirmar exclusão</h3>
            </div>
            <p className="text-stone text-sm">
              {confirmDelete.type === "user"
                ? `O usuário "${confirmDelete.name}" será desativado.`
                : `O perfil "${confirmDelete.name}" será excluído permanentemente.`}
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setConfirmDelete(null)}
                className="px-4 py-2 rounded-lg border border-surface-03 text-stone hover:text-cream text-sm">
                Cancelar
              </button>
              <button onClick={handleDeleteConfirm}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white font-semibold text-sm">
                <Trash2 size={14} /> Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

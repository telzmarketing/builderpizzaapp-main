import { useEffect, useState } from "react";
import { KeyRound, Loader2, Lock } from "lucide-react";
import { useNavigate } from "react-router-dom";
import TelzLogo from "@/components/TelzLogo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminAuthApi, type ApiAdmin } from "@/lib/api";
import {
  clearAdminSession,
  markAdminPasswordChanged,
  mustChangeAdminPassword,
  readStoredAdminSession,
} from "@/lib/adminSession";

export default function AdminChangePassword() {
  const navigate = useNavigate();
  const [admin, setAdmin] = useState<ApiAdmin | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [checking, setChecking] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) {
      navigate("/painel/login", { replace: true });
      return;
    }
    let cancelled = false;
    adminAuthApi.me()
      .then((profile) => {
        if (cancelled) return;
        setAdmin(profile);
        localStorage.setItem("admin_user", JSON.stringify(profile));
      })
      .catch(() => {
        if (cancelled) return;
        if (!localStorage.getItem("admin_token")) navigate("/painel/login", { replace: true });
        else setError("Nao foi possivel validar a sessao. Tente novamente.");
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => { cancelled = true; };
  }, [navigate]);

  const required = mustChangeAdminPassword(admin ?? readStoredAdminSession());
  const valid = currentPassword.length > 0
    && newPassword.length >= 8
    && newPassword.length <= 72
    && newPassword === confirmation
    && newPassword !== currentPassword;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!valid) return;
    setSaving(true);
    setError("");
    try {
      await adminAuthApi.changePassword(currentPassword, newPassword);
      clearAdminSession();
      markAdminPasswordChanged();
      navigate("/painel/login", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel alterar a senha.");
    } finally {
      setSaving(false);
    }
  }

  function logout() {
    clearAdminSession();
    navigate("/painel/login", { replace: true });
  }

  if (checking) {
    return <div className="flex min-h-screen items-center justify-center bg-surface-00"><Loader2 className="animate-spin text-gold" /></div>;
  }

  return (
    <div className="admin-shell flex min-h-screen items-center justify-center bg-surface-00 px-4 py-8 text-cream">
      <section className="w-full max-w-md rounded-2xl border border-surface-03 bg-surface-02 p-6 shadow-2xl shadow-black/40 md:p-8">
        <TelzLogo className="text-2xl text-gold" />
        <div className="mt-7 flex h-12 w-12 items-center justify-center rounded-xl bg-gold/10 text-gold"><KeyRound size={22} /></div>
        <h1 className="mt-4 text-2xl font-black">{required ? "Troca de senha obrigatoria" : "Alterar senha"}</h1>
        <p className="mt-2 text-sm leading-relaxed text-stone">
          {required
            ? "Antes de acessar o painel, defina uma senha pessoal diferente da senha temporaria."
            : "Confirme sua senha atual e escolha uma nova senha segura."}
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <PasswordField label="Senha atual" value={currentPassword} onChange={setCurrentPassword} autoComplete="current-password" />
          <PasswordField label="Nova senha" value={newPassword} onChange={setNewPassword} autoComplete="new-password" />
          <PasswordField label="Confirmar nova senha" value={confirmation} onChange={setConfirmation} autoComplete="new-password" />

          {newPassword && newPassword.length < 8 && <p className="text-xs text-yellow-200">A nova senha precisa ter pelo menos 8 caracteres.</p>}
          {confirmation && confirmation !== newPassword && <p className="text-xs text-yellow-200">A confirmacao nao corresponde a nova senha.</p>}
          {newPassword && newPassword === currentPassword && <p className="text-xs text-yellow-200">A nova senha precisa ser diferente da atual.</p>}
          {error && <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}

          <Button type="submit" disabled={saving || !valid} className="w-full gap-2 bg-gold text-surface-00 hover:bg-gold/90">
            {saving && <Loader2 size={16} className="animate-spin" />}
            Salvar nova senha
          </Button>
          <Button type="button" variant="ghost" onClick={logout} className="w-full text-stone">Sair desta sessao</Button>
        </form>
      </section>
    </div>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-bold text-stone">{label}</span>
      <div className="flex items-center gap-3 rounded-xl border border-surface-03 bg-surface-01 px-3 focus-within:border-gold">
        <Lock size={15} className="text-stone" />
        <Input
          type="password"
          value={value}
          minLength={label === "Senha atual" ? 1 : 8}
          maxLength={72}
          autoComplete={autoComplete}
          onChange={(event) => onChange(event.target.value)}
          className="border-0 bg-transparent px-0 text-cream focus-visible:ring-0"
        />
      </div>
    </label>
  );
}

import { useMemo, useState } from "react";
import { CheckCircle2, KeyRound, Loader2 } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import TelzLogo from "@/components/TelzLogo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { platformInvitationApi, type ApiPlatformAdminPublic } from "@/lib/api";
import {
  platformInvitationPasswordError,
  resolvePlatformInvitationToken,
} from "@/lib/platformInvitation";

export default function AcceptPlatformInvitation() {
  const { token: pathToken } = useParams();
  const [searchParams] = useSearchParams();
  const token = useMemo(
    () => resolvePlatformInvitationToken(pathToken, searchParams.get("token")),
    [pathToken, searchParams],
  );
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [saving, setSaving] = useState(false);
  const [accepted, setAccepted] = useState<{ tenant_id: string; user: ApiPlatformAdminPublic } | null>(null);
  const [error, setError] = useState("");
  const passwordError = useMemo(
    () => platformInvitationPasswordError(password, confirmation),
    [confirmation, password],
  );

  async function accept(event: React.FormEvent) {
    event.preventDefault();
    if (!token || passwordError) return;
    setSaving(true);
    setError("");
    try {
      const result = await platformInvitationApi.accept(token, password || undefined);
      setAccepted({ tenant_id: result.tenant_id, user: result.user });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel aceitar o convite.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="admin-shell flex min-h-screen items-center justify-center bg-surface-00 px-4 py-8 text-cream">
      <section className="w-full max-w-md rounded-2xl border border-surface-03 bg-surface-02 p-6 shadow-2xl shadow-black/40 md:p-8">
        <TelzLogo className="text-2xl text-gold" />
        {accepted ? (
          <div className="mt-8 text-center">
            <CheckCircle2 size={44} className="mx-auto text-green-300" />
            <h1 className="mt-4 text-2xl font-black">Convite aceito</h1>
            <p className="mt-2 text-sm text-stone">
              {accepted.user.name}, seu acesso empresarial foi ativado para o e-mail {accepted.user.email}.
            </p>
            <Button asChild className="mt-6 w-full bg-gold text-surface-00 hover:bg-gold/90"><Link to="/painel/login">Ir para o login</Link></Button>
          </div>
        ) : (
          <>
            <div className="mt-7 flex h-12 w-12 items-center justify-center rounded-xl bg-gold/10 text-gold"><KeyRound size={22} /></div>
            <h1 className="mt-4 text-2xl font-black">Aceitar convite</h1>
            <p className="mt-2 text-sm leading-relaxed text-stone">
              Se este for seu primeiro acesso, crie uma senha. Quem ja possui conta pode deixar os campos de senha vazios.
            </p>
            <form onSubmit={accept} className="mt-6 space-y-4">
              {!token && <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">O link nao contem um token de convite.</p>}
              <label className="block">
                <span className="mb-2 block text-xs font-bold text-stone">Nova senha (primeiro acesso)</span>
                <Input type="password" minLength={8} maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" className="border-surface-03 bg-surface-01 text-cream" />
              </label>
              <label className="block">
                <span className="mb-2 block text-xs font-bold text-stone">Confirmar nova senha</span>
                <Input type="password" minLength={8} maxLength={72} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" className="border-surface-03 bg-surface-01 text-cream" />
              </label>
              {passwordError && <p className="text-xs text-yellow-200">{passwordError}</p>}
              {error && <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
              <Button type="submit" disabled={saving || !token || !!passwordError} className="w-full gap-2 bg-gold text-surface-00 hover:bg-gold/90">
                {saving && <Loader2 size={15} className="animate-spin" />} Aceitar convite
              </Button>
            </form>
          </>
        )}
      </section>
    </div>
  );
}

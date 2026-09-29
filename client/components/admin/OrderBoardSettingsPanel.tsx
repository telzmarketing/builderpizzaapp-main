import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Copy, Loader2, Monitor, Pencil, Power, RefreshCw, ShieldCheck, Trash2, X } from "lucide-react";
import { adminOrderBoardApi, type OrderBoardDevice, type OrderBoardSettings } from "@/lib/api";

const inputClass = "w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2.5 text-sm text-cream outline-none focus:border-gold";

function lastSeenLabel(value?: string | null) {
  if (!value) return "Nunca conectado";
  const elapsed = Math.max(0, Date.now() - Date.parse(value));
  if (elapsed < 60_000) return "Agora";
  if (elapsed < 3_600_000) return `Há ${Math.floor(elapsed / 60_000)} min`;
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

export default function OrderBoardSettingsPanel() {
  const [settings, setSettings] = useState<OrderBoardSettings | null>(null);
  const [devices, setDevices] = useState<OrderBoardDevice[]>([]);
  const [code, setCode] = useState("");
  const [deviceName, setDeviceName] = useState("TV da operação");
  const [editing, setEditing] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextSettings, nextDevices] = await Promise.all([
        adminOrderBoardApi.getSettings(), adminOrderBoardApi.listDevices(),
      ]);
      setSettings(nextSettings);
      setDevices(nextDevices);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível carregar os painéis.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onlineIds = useMemo(() => new Set(devices.filter((device) => (
    device.status === "active" && !!device.last_seen_at && Date.now() - Date.parse(device.last_seen_at) < 45_000
  )).map((device) => device.id)), [devices]);

  const saveSettings = async () => {
    if (!settings) return;
    setSaving(true); setError(null); setMessage(null);
    try {
      setSettings(await adminOrderBoardApi.updateSettings(settings));
      setMessage("Configurações do painel salvas.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível salvar."); }
    finally { setSaving(false); }
  };

  const approve = async () => {
    if (!code.trim() || !deviceName.trim()) return;
    setSaving(true); setError(null); setMessage(null);
    try {
      const device = await adminOrderBoardApi.approveActivation(code.trim().toUpperCase(), deviceName.trim());
      setDevices((current) => [device, ...current.filter((item) => item.id !== device.id)]);
      setCode("");
      setMessage("TV vinculada com sucesso.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Código inválido ou expirado."); }
    finally { setSaving(false); }
  };

  const rename = async (device: OrderBoardDevice) => {
    if (!editingName.trim()) return;
    try {
      const updated = await adminOrderBoardApi.renameDevice(device.id, editingName.trim());
      setDevices((current) => current.map((item) => item.id === updated.id ? updated : item));
      setEditing(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível renomear."); }
  };

  const revoke = async (device: OrderBoardDevice) => {
    if (!window.confirm(`Revogar o acesso de “${device.name}”?`)) return;
    try {
      const updated = await adminOrderBoardApi.revokeDevice(device.id);
      setDevices((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível revogar."); }
  };

  const remove = async (device: OrderBoardDevice) => {
    if (!window.confirm(`Excluir o painel “${device.name}”?`)) return;
    try {
      await adminOrderBoardApi.deleteDevice(device.id);
      setDevices((current) => current.filter((item) => item.id !== device.id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível excluir."); }
  };

  if (loading) return <div className="flex min-h-64 items-center justify-center gap-3 text-stone"><Loader2 className="animate-spin" /> Carregando painéis…</div>;

  return (
    <div className="space-y-6">
      {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-bold text-red-200">{error}</div>}
      {message && <div role="status" className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-bold text-emerald-200">{message}</div>}

      <section className="rounded-2xl border border-surface-03 bg-surface-02 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><h3 className="text-lg font-bold text-cream">Painel TV de motoboys</h3><p className="mt-1 text-sm text-stone">Exibe somente entregas atribuídas, sem dados pessoais do cliente.</p></div>
          {settings && <button type="button" onClick={() => setSettings({ ...settings, enabled: !settings.enabled })} className={`flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-black ${settings.enabled ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-200" : "border-surface-03 text-stone"}`}><Power size={16} />{settings.enabled ? "Habilitado" : "Desabilitado"}</button>}
        </div>

        {settings && <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="block text-sm text-parchment"><span className="mb-1.5 block font-medium">Nome da empresa no painel</span><input value={settings.company_name} maxLength={200} onChange={(event) => setSettings({ ...settings, company_name: event.target.value })} className={inputClass} /></label>
          <label className="block text-sm text-parchment"><span className="mb-1.5 block font-medium">Logo da empresa</span><input value={settings.logo_url ?? ""} maxLength={500} onChange={(event) => setSettings({ ...settings, logo_url: event.target.value || null })} placeholder="/uploads/logo.png ou https://..." className={inputClass} /></label>
          <NumberField label="Atualização" suffix="seg" min={3} max={60} value={settings.polling_interval_seconds} onChange={(value) => setSettings({ ...settings, polling_interval_seconds: value })} />
          <NumberField label="Máximo de pedidos" suffix="" min={10} max={200} value={settings.max_orders} onChange={(value) => setSettings({ ...settings, max_orders: value })} />
        </div>}
        <button type="button" disabled={saving || !settings} onClick={saveSettings} className="mt-5 flex items-center gap-2 rounded-xl bg-gold px-5 py-2.5 text-sm font-black text-cream disabled:opacity-50">{saving ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />} Salvar configurações</button>
      </section>

      <section className="rounded-2xl border border-surface-03 bg-surface-02 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><ShieldCheck className="text-gold" /><div><h3 className="font-bold text-cream">Vincular uma TV</h3><p className="text-sm text-stone">Abra <strong className="text-parchment">/tv/motoboys</strong> na televisão e informe o código temporário.</p></div></div><a href="/tv/motoboys" target="_blank" rel="noreferrer" className="rounded-xl border border-gold/40 px-4 py-2 text-sm font-black text-gold-light hover:bg-gold/10">Abrir painel</a></div>
        <div className="mt-5 grid gap-3 md:grid-cols-[1fr_1.5fr_auto]">
          <input aria-label="Código da TV" value={code} maxLength={12} onChange={(event) => setCode(event.target.value.replace(/\s/g, "").toUpperCase())} placeholder="CÓDIGO" className={`${inputClass} font-mono uppercase tracking-[0.2em]`} />
          <input aria-label="Nome do painel" value={deviceName} maxLength={120} onChange={(event) => setDeviceName(event.target.value)} placeholder="Ex.: TV da cozinha" className={inputClass} />
          <button type="button" disabled={saving || !code.trim() || !deviceName.trim()} onClick={approve} className="rounded-xl bg-gold px-5 py-2.5 text-sm font-black text-cream disabled:opacity-50">Autorizar TV</button>
        </div>
      </section>

      <section className="rounded-2xl border border-surface-03 bg-surface-02 p-6">
        <div className="mb-4 flex items-center justify-between"><div><h3 className="font-bold text-cream">Dispositivos vinculados</h3><p className="text-sm text-stone">Revogar bloqueia a próxima atualização da TV.</p></div><button type="button" onClick={load} className="rounded-lg border border-surface-03 p-2 text-stone hover:text-cream" title="Atualizar"><RefreshCw size={17} /></button></div>
        <div className="space-y-3">
          {devices.length === 0 && <div className="rounded-xl border border-dashed border-surface-03 py-10 text-center text-sm text-stone"><Monitor className="mx-auto mb-2" />Nenhuma TV vinculada.</div>}
          {devices.map((device) => <article key={device.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-surface-03 bg-surface-01 p-4">
            <div className="min-w-0 flex-1">
              {editing === device.id ? <div className="flex max-w-md gap-2"><input autoFocus value={editingName} maxLength={120} onChange={(event) => setEditingName(event.target.value)} className={inputClass} /><button onClick={() => rename(device)} className="text-emerald-300"><Check /></button><button onClick={() => setEditing(null)} className="text-stone"><X /></button></div> : <div className="flex items-center gap-2"><Monitor size={18} className="text-gold" /><strong className="truncate text-cream">{device.name}</strong><button onClick={() => { setEditing(device.id); setEditingName(device.name); }} title="Renomear" className="text-stone hover:text-cream"><Pencil size={14} /></button></div>}
              <p className="mt-1 text-xs text-stone"><span className={`mr-2 inline-block h-2 w-2 rounded-full ${onlineIds.has(device.id) ? "bg-emerald-400" : "bg-stone/50"}`} />{device.status === "revoked" ? "Revogado" : onlineIds.has(device.id) ? "Online" : "Offline"} · {lastSeenLabel(device.last_seen_at)}</p>
            </div>
            <div className="flex gap-2">{device.status !== "revoked" && <button type="button" onClick={() => revoke(device)} className="rounded-lg border border-amber-500/30 px-3 py-2 text-xs font-bold text-amber-200">Revogar</button>}<button type="button" onClick={() => remove(device)} title="Excluir" className="rounded-lg border border-red-500/25 p-2 text-red-300"><Trash2 size={16} /></button></div>
          </article>)}
        </div>
        <p className="mt-4 flex items-center gap-2 text-xs text-stone/70"><Copy size={13} /> O token da TV nunca é exibido nem armazenado no navegador pelo painel administrativo.</p>
      </section>
    </div>
  );
}

function NumberField({ label, suffix, value, min, max, onChange }: { label: string; suffix: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return <label className="block text-sm text-parchment"><span className="mb-1.5 block font-medium">{label}</span><div className="relative"><input type="number" min={min} max={max} value={value} onChange={(event) => onChange(Math.max(min, Math.min(max, Number(event.target.value) || min)))} className={inputClass} />{suffix && <span className="pointer-events-none absolute right-3 top-2.5 text-xs text-stone">{suffix}</span>}</div></label>;
}

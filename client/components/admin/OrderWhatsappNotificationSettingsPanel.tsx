import { useCallback, useEffect, useMemo, useState } from "react";
import { Bell, CheckCircle2, Loader2, MessageCircle, RefreshCw, Save, Users } from "lucide-react";
import {
  ordersApi,
  type ApiOrderWhatsappNotificationConfig,
  type ApiOrderWhatsappNotificationSettings,
} from "@/lib/api";

export default function OrderWhatsappNotificationSettingsPanel() {
  const [config, setConfig] = useState<ApiOrderWhatsappNotificationConfig | null>(null);
  const [draft, setDraft] = useState<ApiOrderWhatsappNotificationSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const recipientsWithPhone = useMemo(
    () => config?.available_recipients.filter((recipient) => recipient.has_phone) ?? [],
    [config],
  );

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setError("");
    setSaved(false);
    try {
      const data = await ordersApi.getWhatsappNotifications();
      setConfig(data);
      setDraft({ ...data.settings, recipient_admin_ids: [...data.settings.recipient_admin_ids] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar a configuracao.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const toggleRecipient = useCallback((recipientId: string) => {
    setDraft((current) => {
      if (!current) return current;
      const selected = new Set(current.recipient_admin_ids);
      if (selected.has(recipientId)) selected.delete(recipientId);
      else selected.add(recipientId);
      return { ...current, recipient_admin_ids: Array.from(selected) };
    });
  }, []);

  const saveConfig = useCallback(async () => {
    if (!draft) return;
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const data = await ordersApi.updateWhatsappNotifications(draft);
      setConfig(data);
      setDraft({ ...data.settings, recipient_admin_ids: [...data.settings.recipient_admin_ids] });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel salvar a configuracao.");
    } finally {
      setSaving(false);
    }
  }, [draft]);

  return (
    <section className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
      <div className="border-b border-surface-03 p-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-gold/30 bg-gold/10 text-gold">
            <MessageCircle size={18} />
          </div>
          <div className="min-w-0">
            <h2 className="text-base font-bold text-cream">Aviso WhatsApp de novo pedido</h2>
            <p className="mt-1 text-xs text-stone">
              Envia um aviso interno para administradores e gestores selecionados.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {saved && (
            <span className="inline-flex h-9 items-center gap-2 rounded-xl border border-green-500/30 bg-green-500/10 px-3 text-xs font-semibold text-green-200">
              <CheckCircle2 size={14} />
              Salvo
            </span>
          )}
          <button
            type="button"
            onClick={loadConfig}
            disabled={loading || saving}
            className="flex h-9 items-center gap-2 rounded-xl border border-surface-03 px-3 text-xs font-semibold text-stone transition-colors hover:text-cream disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Atualizar
          </button>
          <button
            type="button"
            onClick={saveConfig}
            disabled={saving || loading || !draft || (draft.enabled && draft.recipient_admin_ids.length === 0)}
            className="flex h-9 items-center gap-2 rounded-xl bg-gold px-3 text-xs font-bold text-black transition-colors hover:bg-gold/90 disabled:opacity-50"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Salvar
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading || !draft ? (
        <div className="m-4 flex min-h-48 items-center justify-center rounded-xl border border-surface-03 bg-surface-03/40">
          <Loader2 size={28} className="animate-spin text-gold" />
        </div>
      ) : (
        <div className="p-4 space-y-5">
          <label className="flex items-center justify-between gap-4 rounded-xl border border-surface-03 bg-surface-03/40 px-4 py-3">
            <span className="flex items-start gap-3">
              <Bell size={17} className="mt-0.5 shrink-0 text-gold" />
              <span>
                <span className="block text-sm font-bold text-cream">Ativar aviso interno</span>
                <span className="mt-0.5 block text-xs text-stone">
                  O envio usa o WhatsApp Gateway conectado e nao entra no historico de conversas.
                </span>
              </span>
            </span>
            <input
              type="checkbox"
              checked={draft.enabled}
              onChange={(event) => setDraft((current) => current ? { ...current, enabled: event.target.checked } : current)}
              className="h-5 w-5 shrink-0 accent-gold"
            />
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-xs font-bold uppercase tracking-widest text-stone">
              Modelo da mensagem
            </span>
            <textarea
              value={draft.message_template}
              onChange={(event) => setDraft((current) => current ? { ...current, message_template: event.target.value } : current)}
              rows={4}
              maxLength={500}
              className="resize-none rounded-xl border border-surface-03 bg-surface-03 px-3 py-2 text-sm font-semibold text-cream outline-none transition-colors placeholder:text-stone focus:border-gold/60"
            />
            <span className="text-xs text-stone">
              Variaveis disponiveis: {"{order_number}"} e {"{customer_name}"}.
            </span>
          </label>

          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-xs font-bold uppercase tracking-widest text-stone">
                Pessoas que receberao
              </span>
              <span className="text-xs font-semibold text-gold">
                {draft.recipient_admin_ids.length} selecionado(s)
              </span>
            </div>

            {config?.available_recipients.length === 0 ? (
              <div className="rounded-xl border border-dashed border-surface-03 p-6 text-center">
                <Users size={30} className="mx-auto mb-2 text-stone" />
                <p className="text-sm text-stone">Nenhum usuario interno encontrado.</p>
              </div>
            ) : recipientsWithPhone.length === 0 ? (
              <div className="rounded-xl border border-dashed border-surface-03 p-6 text-center">
                <Users size={30} className="mx-auto mb-2 text-stone" />
                <p className="text-sm text-stone">Cadastre telefone nos usuarios internos antes de ativar o aviso.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                {config?.available_recipients.map((recipient) => {
                  const disabled = !recipient.has_phone;
                  const selected = draft.recipient_admin_ids.includes(recipient.id);
                  return (
                    <button
                      key={recipient.id}
                      type="button"
                      onClick={() => !disabled && toggleRecipient(recipient.id)}
                      disabled={disabled}
                      className={`flex min-h-16 w-full items-center justify-between gap-4 rounded-xl border px-4 py-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${
                        selected
                          ? "border-gold bg-gold/10"
                          : "border-surface-03 bg-surface-03/40 hover:border-gold/40"
                      }`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-bold text-cream">{recipient.name}</span>
                        <span className="mt-0.5 block truncate text-xs text-stone">
                          {recipient.role_name || "Sem perfil"} - {recipient.phone || "Sem telefone"}
                        </span>
                      </span>
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={disabled}
                        onChange={() => null}
                        className="h-5 w-5 shrink-0 accent-gold"
                      />
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 px-4 py-3">
            <p className="text-xs font-semibold text-blue-100">
              Avisos internos sao enviados diretamente pelo Gateway e ficam separados do atendimento do Agente WhatsApp.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

import { useEffect, useState } from "react";
import { Save, Loader2, ExternalLink, AlertCircle, Check } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import { exitPopupApi } from "@/lib/api";

type PopupForm = {
  enabled: boolean;
  title: string;
  subtitle: string;
  coupon_code: string;
  button_text: string;
  image_url: string;
  show_once_per_session: boolean;
  trigger_delay_seconds: number;
};

const cls = "w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone/60 outline-none focus:border-gold";

export default function AdminExitPopup() {
  const [form, setForm] = useState<PopupForm>({
    enabled: false,
    title: "Espera! Temos uma oferta para voce",
    subtitle: "Use o cupom abaixo e ganhe desconto no seu pedido!",
    coupon_code: "",
    button_text: "Usar cupom agora",
    image_url: "",
    show_once_per_session: true,
    trigger_delay_seconds: 10,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    exitPopupApi.get()
      .then((data) =>
        setForm({
          enabled: data.enabled ?? false,
          title: data.title ?? "",
          subtitle: data.subtitle ?? "",
          coupon_code: data.coupon_code ?? "",
          button_text: data.button_text ?? "",
          image_url: data.image_url ?? "",
          show_once_per_session: data.show_once_per_session ?? true,
          trigger_delay_seconds: data.trigger_delay_seconds ?? 10,
        })
      )
      .catch(() => setMessage({ type: "err", text: "Nao foi possivel carregar a configuracao." }))
      .finally(() => setLoading(false));
  }, []);

  const set = (key: keyof PopupForm, value: string | boolean | number) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await exitPopupApi.update(form);
      setMessage({ type: "ok", text: "Configuracao salva com sucesso!" });
    } catch (e) {
      setMessage({ type: "err", text: e instanceof Error ? e.message : "Erro ao salvar." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />

      <main className="flex-1 overflow-y-auto">
        <header className="bg-surface-02 border-b border-surface-03 px-6 py-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <p className="text-gold text-xs font-bold uppercase tracking-[0.2em]">Marketing</p>
            <h1 className="text-cream text-2xl font-bold">Popup por Tempo</h1>
            <p className="text-stone text-sm mt-1">Exibe uma oferta depois de alguns segundos na loja.</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving || loading}
              className="inline-flex items-center justify-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-60 text-cream font-bold px-5 py-3 rounded-xl transition-colors"
            >
              {saving ? <Loader2 size={17} className="animate-spin" /> : <Save size={17} />}
              Salvar
            </button>
            <AdminTopActions />
          </div>
        </header>

        <div className="p-6 max-w-2xl space-y-5">
          {message && (
            <div className={`flex items-center gap-2 rounded-xl px-4 py-3 text-sm ${message.type === "ok" ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-400" : "bg-red-500/10 border border-red-500/30 text-red-400"}`}>
              {message.type === "ok" ? <Check size={16} /> : <AlertCircle size={16} />}
              {message.text}
            </div>
          )}

          {loading ? (
            <div className="flex items-center gap-2 text-stone py-12">
              <Loader2 size={20} className="animate-spin" /> Carregando...
            </div>
          ) : (
            <>
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-cream font-semibold">Ativar popup por tempo</p>
                    <p className="text-stone text-sm">Quando ativo, exibe automaticamente no tempo configurado.</p>
                  </div>
                  <button
                    onClick={() => set("enabled", !form.enabled)}
                    className={`w-12 h-6 rounded-full transition-colors relative ${form.enabled ? "bg-gold" : "bg-surface-03"}`}
                  >
                    <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-cream transition-all ${form.enabled ? "left-6" : "left-0.5"}`} />
                  </button>
                </div>
              </div>

              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5 space-y-4">
                <p className="text-cream font-semibold border-b border-surface-03 pb-3">Conteudo do Popup</p>

                <div>
                  <label className="text-parchment text-xs mb-1 block">Titulo</label>
                  <input value={form.title} onChange={(e) => set("title", e.target.value)} className={cls} placeholder="Espera! Temos uma oferta para voce" />
                </div>

                <div>
                  <label className="text-parchment text-xs mb-1 block">Subtitulo / Descricao</label>
                  <textarea value={form.subtitle} onChange={(e) => set("subtitle", e.target.value)} className={`${cls} min-h-20 resize-none`} placeholder="Use o cupom abaixo e ganhe desconto..." />
                </div>

                <div>
                  <label className="text-parchment text-xs mb-1 block">Codigo do Cupom (opcional)</label>
                  <input value={form.coupon_code} onChange={(e) => set("coupon_code", e.target.value.toUpperCase())} className={cls} placeholder="BEMVINDO10" />
                  <p className="text-stone text-xs mt-1">Deixe em branco para nao exibir cupom.</p>
                </div>

                <div>
                  <label className="text-parchment text-xs mb-1 block">Texto do botao</label>
                  <input value={form.button_text} onChange={(e) => set("button_text", e.target.value)} className={cls} placeholder="Usar cupom agora" />
                </div>

                <div>
                  <label className="text-parchment text-xs mb-1 block">Imagem (URL opcional)</label>
                  <input value={form.image_url} onChange={(e) => set("image_url", e.target.value)} className={cls} placeholder="https://..." />
                  {form.image_url && (
                    <a href={form.image_url} target="_blank" rel="noopener noreferrer" className="text-gold text-xs flex items-center gap-1 mt-1 hover:underline">
                      <ExternalLink size={11} /> Visualizar imagem
                    </a>
                  )}
                </div>
              </div>

              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5 space-y-3">
                <p className="text-cream font-semibold border-b border-surface-03 pb-3">Comportamento</p>
                <div>
                  <label className="text-parchment text-xs mb-1 block">Aparecer apos quantos segundos</label>
                  <input
                    type="number"
                    min={1}
                    max={3600}
                    value={form.trigger_delay_seconds}
                    onChange={(e) => set("trigger_delay_seconds", Number(e.target.value))}
                    className={cls}
                  />
                  <p className="text-stone text-xs mt-1">No mobile, essa regra substitui a antiga deteccao de saida do mouse.</p>
                </div>
                <label className="flex items-center gap-3 text-parchment text-sm">
                  <input
                    type="checkbox"
                    checked={form.show_once_per_session}
                    onChange={(e) => set("show_once_per_session", e.target.checked)}
                    className="accent-gold"
                  />
                  Mostrar apenas uma vez por sessao do navegador
                </label>
                <p className="text-stone text-xs">O popup e disparado por tempo, ideal para clientes que saem do navegador para abrir apps de delivery.</p>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

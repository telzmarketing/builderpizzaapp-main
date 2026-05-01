import { useEffect, useState } from "react";
import { Save, Eye } from "lucide-react";
import { chatbotAdminApi, type ChatbotSettings } from "@/lib/chatbotApi";

const Inp = ({ label, ...p }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) => (
  <div>
    <label className="block text-parchment text-xs font-medium mb-1">{label}</label>
    <input {...p} className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone text-sm focus:outline-none focus:border-gold" />
  </div>
);

const Sel = ({ label, children, ...p }: { label: string; children: React.ReactNode } & React.SelectHTMLAttributes<HTMLSelectElement>) => (
  <div>
    <label className="block text-parchment text-xs font-medium mb-1">{label}</label>
    <select {...p} className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold">
      {children}
    </select>
  </div>
);

function WidgetPreview({ s }: { s: ChatbotSettings }) {
  const isRight = s.posicao_widget === "bottom-right";
  return (
    <div className="relative bg-surface-03 rounded-xl h-64 border border-surface-03 overflow-hidden">
      <p className="absolute top-3 left-3 text-stone text-xs">Preview do widget</p>
      {/* Janela do chat */}
      <div className={`absolute bottom-16 ${isRight ? "right-3" : "left-3"} w-52 bg-surface-02 rounded-xl border border-surface-03 shadow-xl`}>
        <div className="px-3 py-2 rounded-t-xl text-cream text-xs font-bold" style={{ background: s.cor_primaria }}>
          {s.nome_bot}
        </div>
        <div className="p-3">
          <div className="bg-surface-03 rounded-lg px-3 py-2 text-stone text-xs">{s.mensagem_inicial}</div>
        </div>
      </div>
      {/* Botão flutuante */}
      <div
        className={`absolute bottom-3 ${isRight ? "right-3" : "left-3"} w-10 h-10 rounded-full flex items-center justify-center text-white shadow-lg text-lg`}
        style={{ background: s.cor_primaria }}
      >
        💬
      </div>
    </div>
  );
}

export default function ChatbotConfig() {
  const [settings, setSettings] = useState<ChatbotSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => { chatbotAdminApi.getSettings().then(setSettings); }, []);

  if (!settings) return <div className="text-stone text-center py-16">Carregando...</div>;

  const upd = (k: keyof ChatbotSettings, v: unknown) =>
    setSettings((prev) => prev ? { ...prev, [k]: v } : prev);

  const save = async () => {
    setSaving(true); setMsg("");
    try {
      const s = await chatbotAdminApi.updateSettings({
        ativo: settings.ativo,
        ia_ativo: settings.ia_ativo,
        nome_bot: settings.nome_bot,
        mensagem_inicial: settings.mensagem_inicial,
        cor_primaria: settings.cor_primaria,
        posicao_widget: settings.posicao_widget,
        mensagem_fora_horario: settings.mensagem_fora_horario,
        tempo_disparo_auto: settings.tempo_disparo_auto,
        fallback_humano_ativo: settings.fallback_humano_ativo,
        horario_funcionamento: settings.horario_funcionamento,
      });
      setSettings(s); setMsg("Salvo com sucesso!");
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally { setSaving(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 max-w-5xl">
      {/* Form */}
      <div className="space-y-4">
        <h3 className="text-cream font-bold text-base">Configurações gerais</h3>

        <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03">
          <span className="text-parchment text-sm flex-1">Chatbot ativo</span>
          <button
            onClick={() => upd("ativo", !settings.ativo)}
            className={`relative w-11 h-6 rounded-full transition-colors ${settings.ativo ? "bg-gold" : "bg-surface-03"}`}
          >
            <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${settings.ativo ? "translate-x-6" : "translate-x-1"}`} />
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03">
            <span className="text-parchment text-sm flex-1">Atendimento IA</span>
            <button
              onClick={() => upd("ia_ativo", !settings.ia_ativo)}
              className={`relative w-11 h-6 rounded-full transition-colors ${settings.ia_ativo ? "bg-gold" : "bg-surface-03"}`}
              aria-label="Alternar atendimento por IA"
            >
              <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${settings.ia_ativo ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>
        </div>

        <Inp label="Nome do bot" value={settings.nome_bot} onChange={(e) => upd("nome_bot", e.target.value)} />
        <Inp label="Mensagem inicial" value={settings.mensagem_inicial} onChange={(e) => upd("mensagem_inicial", e.target.value)} />

        <div>
          <label className="block text-parchment text-xs font-medium mb-1">Cor primária</label>
          <div className="flex gap-3 items-center">
            <input type="color" value={settings.cor_primaria} onChange={(e) => upd("cor_primaria", e.target.value)}
              className="w-10 h-10 rounded-lg border border-surface-03 bg-surface-03 cursor-pointer" />
            <Inp label="" value={settings.cor_primaria} onChange={(e) => upd("cor_primaria", e.target.value)} />
          </div>
        </div>

        <Sel label="Posição do widget" value={settings.posicao_widget} onChange={(e) => upd("posicao_widget", e.target.value)}>
          <option value="bottom-right">Canto inferior direito</option>
          <option value="bottom-left">Canto inferior esquerdo</option>
        </Sel>

        <Inp
          label="Tempo para exibir automaticamente (segundos, 0 = desativado)"
          type="number" min={0} value={settings.tempo_disparo_auto}
          onChange={(e) => upd("tempo_disparo_auto", Number(e.target.value))}
        />

        <div>
          <label className="block text-parchment text-xs font-medium mb-1">Mensagem fora do horário</label>
          <textarea
            value={settings.mensagem_fora_horario}
            onChange={(e) => upd("mensagem_fora_horario", e.target.value)}
            rows={2}
            className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold resize-none"
          />
        </div>

        <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03">
          <span className="text-parchment text-sm flex-1">Atendimento humano</span>
          <button
            onClick={() => upd("fallback_humano_ativo", !settings.fallback_humano_ativo)}
            className={`relative w-11 h-6 rounded-full transition-colors ${settings.fallback_humano_ativo ? "bg-gold" : "bg-surface-03"}`}
          >
            <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${settings.fallback_humano_ativo ? "translate-x-6" : "translate-x-1"}`} />
          </button>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button onClick={save} disabled={saving}
            className="flex items-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold py-2 px-5 rounded-lg text-sm transition-colors">
            <Save size={15} /> {saving ? "Salvando..." : "Salvar configurações"}
          </button>
          {msg && <span className={msg.includes("Erro") ? "text-red-400 text-xs" : "text-green-400 text-xs"}>{msg}</span>}
        </div>
      </div>

      {/* Preview */}
      <div className="space-y-4">
        <h3 className="text-cream font-bold text-base flex items-center gap-2"><Eye size={16} /> Preview ao vivo</h3>
        <WidgetPreview s={settings} />
        <p className="text-stone text-xs">O preview reflete as alterações em tempo real antes de salvar.</p>
      </div>
    </div>
  );
}

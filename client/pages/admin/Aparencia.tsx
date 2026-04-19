import { useEffect, useRef, useState } from "react";
import { Palette, Save, RotateCcw, Check } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import { themeApi, applyTheme, DEFAULT_THEME, type ThemeSettings } from "@/lib/themeApi";

type Field = keyof Omit<ThemeSettings, "id" | "updated_at">;

interface ColorGroup {
  label: string;
  fields: { key: Field; label: string }[];
}

const GROUPS: ColorGroup[] = [
  {
    label: "Identidade Visual",
    fields: [
      { key: "primary",   label: "Cor Principal" },
      { key: "secondary", label: "Cor Secundária" },
      { key: "badge",     label: "Badge" },
      { key: "tag",       label: "Tag" },
    ],
  },
  {
    label: "Fundos",
    fields: [
      { key: "background_main", label: "Fundo Principal" },
      { key: "background_alt",  label: "Fundo Alternativo" },
      { key: "background_card", label: "Cards / Painéis" },
      { key: "overlay",         label: "Overlay / Sombra" },
    ],
  },
  {
    label: "Textos",
    fields: [
      { key: "text_primary",   label: "Texto Principal" },
      { key: "text_secondary", label: "Texto Secundário" },
      { key: "text_muted",     label: "Texto Suave" },
    ],
  },
  {
    label: "Status",
    fields: [
      { key: "status_success", label: "Sucesso" },
      { key: "status_error",   label: "Erro" },
      { key: "status_warning", label: "Aviso" },
      { key: "status_info",    label: "Informação" },
    ],
  },
  {
    label: "Interação",
    fields: [
      { key: "border",             label: "Borda" },
      { key: "interaction_hover",  label: "Hover" },
      { key: "interaction_active", label: "Ativo / Clicado" },
      { key: "interaction_focus",  label: "Foco" },
    ],
  },
  {
    label: "Estrutura",
    fields: [
      { key: "navbar",  label: "Navbar" },
      { key: "footer",  label: "Footer" },
      { key: "sidebar", label: "Sidebar" },
      { key: "modal",   label: "Modal" },
    ],
  },
];

export default function AdminAparencia() {
  const [theme, setTheme]       = useState<ThemeSettings>(DEFAULT_THEME);
  const [saved, setSaved]       = useState<ThemeSettings>(DEFAULT_THEME);
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);
  const [saveOk, setSaveOk]     = useState(false);
  const [error, setError]       = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    themeApi.get()
      .then((t) => { setTheme(t); setSaved(t); })
      .catch(() => setError("Erro ao carregar tema."))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (key: Field, value: string) => {
    const next = { ...theme, [key]: value };
    setTheme(next);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => applyTheme(next), 80);
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const token = localStorage.getItem("admin_token") ?? "";
      const updated = await themeApi.update(token, theme);
      setSaved(updated);
      setTheme(updated);
      applyTheme(updated);
      window.dispatchEvent(new Event("theme-updated"));
      setSaveOk(true);
      setTimeout(() => setSaveOk(false), 2500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setTheme(saved);
    applyTheme(saved);
  };

  const isDirty = JSON.stringify(theme) !== JSON.stringify(saved);

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      <div className="flex h-screen">
        <AdminSidebar />
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* Top bar */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3">
              <Palette size={22} className="text-gold" />
              <div>
                <h2 className="text-xl font-bold text-cream">Aparência</h2>
                <p className="text-stone text-xs">Personalize as cores do sistema</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {isDirty && (
                <button
                  onClick={handleReset}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-surface-03 text-stone hover:text-parchment text-sm transition-colors"
                >
                  <RotateCcw size={14} /> Descartar
                </button>
              )}
              <button
                onClick={handleSave}
                disabled={saving || !isDirty}
                className="flex items-center gap-2 px-5 py-2 rounded-lg bg-gold text-cream font-semibold text-sm disabled:opacity-40 hover:bg-gold/90 transition-colors"
              >
                {saveOk ? <Check size={15} /> : <Save size={15} />}
                {saving ? "Salvando..." : saveOk ? "Salvo!" : "Salvar"}
              </button>
            </div>
          </div>

          {error && (
            <div className="mx-8 mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-8">
            {loading ? (
              <div className="flex items-center justify-center h-40 text-stone text-sm">
                Carregando tema...
              </div>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 max-w-6xl">

                {/* Color editor */}
                <div className="xl:col-span-2 space-y-6">
                  {GROUPS.map((group) => (
                    <div key={group.label} className="bg-surface-02 rounded-2xl border border-surface-03 p-6">
                      <h3 className="text-cream font-semibold text-sm mb-4">{group.label}</h3>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {group.fields.map(({ key, label }) => (
                          <ColorRow
                            key={key}
                            label={label}
                            value={theme[key as keyof ThemeSettings] as string}
                            onChange={(v) => handleChange(key, v)}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Live preview */}
                <div className="space-y-4">
                  <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5 sticky top-0">
                    <h3 className="text-cream font-semibold text-sm mb-4">Preview ao vivo</h3>
                    <LivePreview theme={theme} />
                  </div>
                </div>

              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ColorRow({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const isValid = /^#[0-9A-Fa-f]{6}$/.test(value);

  return (
    <div className="flex items-center gap-3">
      <label
        className="w-8 h-8 rounded-lg border-2 border-white/10 cursor-pointer flex-shrink-0 overflow-hidden"
        style={{ background: isValid ? value : "#555" }}
        title={label}
      >
        <input
          type="color"
          value={isValid ? value : "#000000"}
          onChange={(e) => onChange(e.target.value)}
          className="opacity-0 w-full h-full cursor-pointer"
        />
      </label>
      <div className="flex-1 min-w-0">
        <p className="text-parchment text-xs mb-1 truncate">{label}</p>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          maxLength={7}
          className={`w-full bg-surface-03 border rounded-lg px-2 py-1 text-xs font-mono text-cream outline-none focus:border-gold transition-colors ${
            isValid ? "border-surface-03" : "border-red-500/50"
          }`}
        />
      </div>
    </div>
  );
}

function LivePreview({ theme }: { theme: ThemeSettings }) {
  return (
    <div className="space-y-3 text-xs">
      {/* Navbar */}
      <div className="rounded-lg px-3 py-2 flex items-center gap-2" style={{ background: theme.navbar }}>
        <span style={{ color: theme.text_primary }} className="font-bold">🍕 Moschettieri</span>
        <span style={{ color: theme.text_muted }} className="ml-auto">Menu</span>
      </div>

      {/* Card */}
      <div className="rounded-xl p-3 border" style={{ background: theme.background_card, borderColor: theme.border }}>
        <div className="flex items-center justify-between mb-2">
          <span style={{ color: theme.text_primary }} className="font-semibold">Pizza Margherita</span>
          <span className="px-1.5 py-0.5 rounded-full text-white text-[10px]" style={{ background: theme.badge }}>Novo</span>
        </div>
        <p style={{ color: theme.text_muted }}>Molho, mussarela, manjericão</p>
        <div className="flex items-center justify-between mt-2">
          <span style={{ color: theme.primary }} className="font-bold">R$ 49,90</span>
          <button
            className="px-3 py-1 rounded-lg text-white text-[10px] font-medium"
            style={{ background: theme.primary }}
          >
            Adicionar
          </button>
        </div>
      </div>

      {/* Status badges */}
      <div className="flex flex-wrap gap-1.5">
        {[
          { label: "Sucesso", color: theme.status_success },
          { label: "Erro",    color: theme.status_error },
          { label: "Aviso",   color: theme.status_warning },
          { label: "Info",    color: theme.status_info },
        ].map(({ label, color }) => (
          <span key={label} className="px-2 py-0.5 rounded-full text-white text-[10px]" style={{ background: color }}>
            {label}
          </span>
        ))}
      </div>

      {/* Input */}
      <input
        readOnly
        value="Digite algo..."
        className="w-full rounded-lg px-3 py-1.5 text-[11px] outline-none"
        style={{
          background: theme.background_alt,
          border: `1px solid ${theme.border}`,
          color: theme.text_muted,
        }}
      />

      {/* Background stripe */}
      <div className="rounded-lg h-8 flex items-center px-3 gap-2" style={{ background: theme.background_main }}>
        <span style={{ color: theme.text_secondary }} className="text-[10px]">Fundo principal</span>
        <span className="ml-auto px-1.5 py-0.5 rounded text-white text-[10px]" style={{ background: theme.tag }}>tag</span>
      </div>
    </div>
  );
}

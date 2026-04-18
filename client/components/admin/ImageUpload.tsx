import { Upload, X } from "lucide-react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  label: string;
  hint?: string;
  sizeGuide?: string;
  maxKB?: number;
  previewRounded?: boolean;
}

export default function ImageUpload({ value, onChange, label, hint, sizeGuide, maxKB = 500, previewRounded = false }: Props) {
  const id = `upload-${label.replace(/\W/g, "-").toLowerCase()}-${Math.random().toString(36).slice(2, 6)}`;

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > maxKB * 1024) {
      alert(`Arquivo muito grande. Máximo permitido: ${maxKB}KB`);
      e.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => onChange(reader.result as string);
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const isImage = value?.startsWith("data:") || value?.startsWith("http");

  return (
    <div>
      <label className="block text-parchment text-sm font-medium mb-2">{label}</label>
      <div className="flex items-center gap-4">
        <div className={`w-16 h-16 bg-surface-03 border border-surface-03 flex items-center justify-center flex-shrink-0 overflow-hidden ${previewRounded ? "rounded-full" : "rounded-xl"}`}>
          {isImage ? (
            <img src={value} alt="preview" className="w-full h-full object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          ) : (
            <span className="text-3xl">{value || "?"}</span>
          )}
        </div>
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <label htmlFor={id} className="cursor-pointer flex items-center gap-2 px-4 py-2 bg-surface-03 hover:bg-brand-mid text-parchment rounded-lg text-sm font-medium transition-colors border border-surface-03">
              <Upload size={14} />
              Fazer upload
            </label>
            {value && (
              <button type="button" onClick={() => onChange("")} className="p-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors" title="Remover imagem">
                <X size={14} />
              </button>
            )}
          </div>
          <input id={id} type="file" accept="image/*" onChange={handleFile} className="hidden" />
          {sizeGuide && <p className="text-gold/80 text-xs font-medium">📐 {sizeGuide}</p>}
          {hint && <p className="text-stone/70 text-xs">{hint}</p>}
        </div>
      </div>
    </div>
  );
}

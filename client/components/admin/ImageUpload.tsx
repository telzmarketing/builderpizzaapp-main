import { useId, useState } from "react";
import { Upload, X } from "lucide-react";
import { uploadApi, isAssetUrl, resolveAssetUrl } from "@/lib/api";

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
  const reactId = useId();
  const id = `img-upload-${reactId}`;
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);

    if (file.size > maxKB * 1024) {
      setError(`Arquivo muito grande. Máximo permitido: ${maxKB}KB`);
      e.target.value = "";
      return;
    }

    setUploading(true);
    try {
      const url = await uploadApi.upload(file);
      onChange(url);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("413")) {
        setError("Arquivo muito grande para o servidor. Use uma imagem menor (recomendado: abaixo de 1MB).");
      } else if (msg.includes("401") || msg.includes("403")) {
        setError("Sessão expirada. Recarregue a página e faça login novamente.");
      } else if (msg.includes("400")) {
        setError("Formato não suportado. Use JPEG, PNG ou WebP.");
      } else {
        setError(`Erro ao enviar: ${msg}`);
      }
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const isImage = isAssetUrl(value);

  return (
    <div>
      <label className="block text-parchment text-sm font-medium mb-2">{label}</label>
      <div className="flex items-center gap-4">
        <div className={`w-16 h-16 bg-surface-03 border border-surface-03 flex items-center justify-center flex-shrink-0 overflow-hidden ${previewRounded ? "rounded-full" : "rounded-xl"}`}>
          {isImage ? (
            <img src={resolveAssetUrl(value)} alt="preview" className="w-full h-full object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          ) : (
            <span className="text-3xl">{value || "?"}</span>
          )}
        </div>
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <label
              htmlFor={uploading ? undefined : id}
              className={`cursor-pointer flex items-center gap-2 px-4 py-2 bg-surface-03 hover:bg-brand-mid text-parchment rounded-lg text-sm font-medium transition-colors border border-surface-03 ${uploading ? "opacity-60 cursor-not-allowed" : ""}`}
            >
              <Upload size={14} />
              {uploading ? "Enviando..." : "Fazer upload"}
            </label>
            {value && !uploading && (
              <button
                type="button"
                onClick={() => { onChange(""); setError(null); }}
                className="p-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors"
                title="Remover imagem"
              >
                <X size={14} />
              </button>
            )}
          </div>
          <input
            id={id}
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            onChange={handleFile}
            className="hidden"
            disabled={uploading}
          />
          {sizeGuide && <p className="text-gold/80 text-xs font-medium">📐 {sizeGuide}</p>}
          {hint && <p className="text-stone/70 text-xs">{hint}</p>}
          {error && <p className="text-red-400 text-xs mt-1">{error}</p>}
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
import { Upload, X, Play, Video } from "lucide-react";
import { uploadApi, isAssetUrl, resolveAssetUrl } from "@/lib/api";

type MediaType = "image" | "video";

interface Props {
  value: string;
  onChange: (v: string) => void;
  mediaType: MediaType;
  label: string;
  hint?: string;
  sizeGuide?: string;
  maxKBImage?: number;
  maxKBVideo?: number;
}

const VIDEO_EXTS = [".mp4", ".webm", ".mov"];

function isVideoUrl(url: string): boolean {
  if (!url) return false;
  return VIDEO_EXTS.some((ext) => url.toLowerCase().endsWith(ext));
}

export default function MediaUpload({
  value,
  onChange,
  mediaType,
  label,
  hint,
  sizeGuide,
  maxKBImage = 5000,
  maxKBVideo = 50000,
}: Props) {
  const uid = `upload-${label.replace(/\W/g, "-").toLowerCase()}-${Math.random().toString(36).slice(2, 6)}`;
  const [uploading, setUploading] = useState(false);

  const accept = mediaType === "video" ? "video/mp4,video/webm,video/quicktime" : "image/*";
  const maxKB = mediaType === "video" ? maxKBVideo : maxKBImage;

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > maxKB * 1024) {
      alert(
        mediaType === "video"
          ? "Arquivo muito grande. Máximo permitido: 50MB para vídeos."
          : `Arquivo muito grande. Máximo permitido: ${maxKBImage / 1000}MB para imagens.`,
      );
      e.target.value = "";
      return;
    }

    setUploading(true);
    try {
      const url = await uploadApi.upload(file);
      onChange(url);
    } catch (err) {
      alert(
        `Erro ao enviar ${mediaType === "video" ? "vídeo" : "imagem"}: ${
          err instanceof Error ? err.message : "Tente novamente."
        }`,
      );
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const hasMedia = Boolean(value);
  const showAsVideo = isVideoUrl(value);

  return (
    <div>
      <label className="block text-parchment text-sm font-medium mb-2">{label}</label>
      <div className="flex items-start gap-4">
        {/* Preview */}
        <div className="w-24 h-16 bg-surface-03 border border-surface-03 rounded-xl flex items-center justify-center flex-shrink-0 overflow-hidden">
          {hasMedia ? (
            showAsVideo ? (
              <div className="relative w-full h-full">
                <video
                  src={resolveAssetUrl(value)}
                  className="w-full h-full object-cover"
                  muted
                  playsInline
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                  <Play size={18} className="text-white" />
                </div>
              </div>
            ) : isAssetUrl(value) ? (
              <img
                src={resolveAssetUrl(value)}
                alt="preview"
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
            ) : (
              <span className="text-3xl">{value}</span>
            )
          ) : (
            <div className="text-stone/40 flex flex-col items-center gap-1">
              {mediaType === "video" ? <Video size={20} /> : <Upload size={20} />}
              <span className="text-[10px]">Sem mídia</span>
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <label
              htmlFor={uploading ? undefined : uid}
              className={`cursor-pointer flex items-center gap-2 px-4 py-2 bg-surface-03 hover:bg-brand-mid text-parchment rounded-lg text-sm font-medium transition-colors border border-surface-03 ${
                uploading ? "opacity-60 cursor-not-allowed" : ""
              }`}
            >
              {mediaType === "video" ? <Video size={14} /> : <Upload size={14} />}
              {uploading ? "Enviando..." : mediaType === "video" ? "Upload de vídeo" : "Fazer upload"}
            </label>
            {hasMedia && !uploading && (
              <button
                type="button"
                onClick={() => onChange("")}
                className="p-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors"
                title="Remover"
              >
                <X size={14} />
              </button>
            )}
          </div>
          <input
            id={uid}
            type="file"
            accept={accept}
            onChange={handleFile}
            className="hidden"
            disabled={uploading}
          />
          {sizeGuide && <p className="text-gold/80 text-xs font-medium">📐 {sizeGuide}</p>}
          {mediaType === "video" && (
            <p className="text-stone/70 text-xs">Formatos: MP4, WebM, MOV — Máx. 50MB</p>
          )}
          {hint && <p className="text-stone/70 text-xs">{hint}</p>}
        </div>
      </div>
    </div>
  );
}

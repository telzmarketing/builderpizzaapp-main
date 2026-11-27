import { useState } from "react";
import { Upload, X, Play, Video } from "lucide-react";
import { uploadApi, isAssetUrl, resolveAssetUrl } from "@/lib/api";
import { prepareMediaFileForUpload } from "@/lib/mediaCompression";

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

const formatLimit = (maxKB: number) => {
  if (maxKB >= 1000) return `${maxKB / 1000}MB`;
  return `${maxKB}KB`;
};

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
  const performanceGuide = sizeGuide || (
    mediaType === "video"
      ? `Recomendado para rapidez: MP4/WebM em 720p ou menor, 5 a 12 segundos, arquivo ideal ate 2MB e max. ${formatLimit(maxKBVideo)}.`
      : `Recomendado para rapidez: WebP/JPG, miniaturas 300x300px, cards 800x800px ou banners ate 1280px, arquivo ate ${formatLimit(maxKBImage)}.`
  );

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const prepared = await prepareMediaFileForUpload(file, {
        maxImageBytes: mediaType === "image" ? maxKB * 1024 : undefined,
      });
      if (prepared.file.size > maxKB * 1024) {
        alert(
          mediaType === "video"
            ? `Arquivo muito grande. Maximo permitido: ${formatLimit(maxKBVideo)} para videos.`
            : `Arquivo muito grande. Maximo permitido: ${formatLimit(maxKBImage)} para imagens.`,
        );
        return;
      }

      const url = await uploadApi.upload(prepared.file);
      onChange(url);
    } catch (err) {
      alert(
        `Erro ao enviar ${mediaType === "video" ? "video" : "imagem"}: ${
          err instanceof Error ? err.message : "Tente novamente."
        }`,
      );
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const hasMedia = Boolean(value);
  // A legacy video URL may not expose a recognizable file extension. When the
  // field is explicitly configured as video, keep that URL previewable too.
  const showAsVideo = hasMedia && (mediaType === "video" || isVideoUrl(value));

  return (
    <div className="min-w-0">
      <label className="block text-parchment text-sm font-medium mb-2">{label}</label>
      <div className="flex min-w-0 flex-col items-stretch gap-3 sm:flex-row sm:items-start sm:gap-4">
        <div className="h-20 w-full bg-surface-03 border border-surface-03 rounded-xl flex items-center justify-center flex-shrink-0 overflow-hidden sm:h-16 sm:w-24">
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
                className="w-full h-full object-contain"
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
              <span className="text-[10px]">Sem midia</span>
            </div>
          )}
        </div>

        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <label
              htmlFor={uploading ? undefined : uid}
              className={`cursor-pointer inline-flex max-w-full items-center gap-2 whitespace-nowrap px-4 py-2 bg-surface-03 hover:bg-brand-mid text-parchment rounded-lg text-sm font-medium transition-colors border border-surface-03 ${
                uploading ? "opacity-60 cursor-not-allowed" : ""
              }`}
            >
              {mediaType === "video" ? <Video size={14} /> : <Upload size={14} />}
              {uploading ? "Enviando..." : mediaType === "video" ? "Upload de video" : "Fazer upload"}
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
          <p className="break-words whitespace-normal text-gold/80 text-xs font-medium">{performanceGuide}</p>
          {mediaType === "video" && (
            <p className="break-words whitespace-normal text-stone/70 text-xs">Formatos: MP4, WebM, MOV. Use videos curtos e comprimidos; evite arquivos acima de 2MB quando for banner ou landing.</p>
          )}
          {hint && <p className="break-words whitespace-normal text-stone/70 text-xs">{hint}</p>}
        </div>
      </div>
    </div>
  );
}

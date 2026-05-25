type MediaCompressionOptions = {
  maxImageBytes?: number;
};

export type MediaCompressionResult = {
  file: File;
  compressed: boolean;
  originalSize: number;
};

const COMPRESSIBLE_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const IMAGE_OUTPUT_TYPE = "image/webp";
const QUALITY_STEPS = [0.86, 0.78, 0.7, 0.62, 0.54, 0.46];
const MAX_CANVAS_PIXELS = 40_000_000;

function replaceExtension(fileName: string, extension: string): string {
  const cleanExtension = extension.startsWith(".") ? extension : `.${extension}`;
  return /\.[^./\\]+$/.test(fileName) ? fileName.replace(/\.[^./\\]+$/, cleanExtension) : `${fileName}${cleanExtension}`;
}

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Nao foi possivel ler a imagem selecionada."));
    };
    image.src = url;
  });
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("Nao foi possivel comprimir a imagem."));
    }, type, quality);
  });
}

async function compressImagePreservingDimensions(file: File, options: MediaCompressionOptions): Promise<MediaCompressionResult> {
  if (!COMPRESSIBLE_IMAGE_TYPES.has(file.type)) {
    return { file, compressed: false, originalSize: file.size };
  }

  const image = await loadImage(file);
  const width = image.naturalWidth || image.width;
  const height = image.naturalHeight || image.height;
  if (!width || !height) throw new Error("Imagem invalida.");
  if (width * height > MAX_CANVAS_PIXELS) {
    return { file, compressed: false, originalSize: file.size };
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext("2d");
  if (!context) throw new Error("Nao foi possivel preparar a imagem.");
  context.drawImage(image, 0, 0, width, height);

  let bestBlob: Blob | null = null;
  const targetBytes = options.maxImageBytes;
  for (const quality of QUALITY_STEPS) {
    const blob = await canvasToBlob(canvas, IMAGE_OUTPUT_TYPE, quality);
    if (!bestBlob || blob.size < bestBlob.size) bestBlob = blob;
    if (targetBytes && blob.size <= targetBytes) break;
  }

  if (!bestBlob || bestBlob.size >= file.size) {
    return { file, compressed: false, originalSize: file.size };
  }

  return {
    file: new File([bestBlob], replaceExtension(file.name, ".webp"), {
      type: IMAGE_OUTPUT_TYPE,
      lastModified: Date.now(),
    }),
    compressed: true,
    originalSize: file.size,
  };
}

export async function prepareMediaFileForUpload(
  file: File,
  options: MediaCompressionOptions = {},
): Promise<MediaCompressionResult> {
  if (file.type.startsWith("image/")) return compressImagePreservingDimensions(file, options);
  return { file, compressed: false, originalSize: file.size };
}

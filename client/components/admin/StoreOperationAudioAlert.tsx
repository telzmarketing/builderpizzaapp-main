import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { Volume2, X } from "lucide-react";
import { storeOperationApi, type StoreOperationStatus } from "@/lib/api";

const POLL_INTERVAL_MS = 30000;
const OPEN_MESSAGE = "Delivery Moschettieri Online";
const CLOSED_MESSAGE = "Finalizando operação Delivery Moschettieri";

type AlertState = {
  message: string;
  tone: "open" | "closed" | "blocked";
};

function toText(value: unknown, fallback = ""): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const text = value.map((item) => toText(item)).filter(Boolean).join(", ");
    return text || fallback;
  }
  if (typeof value === "object") {
    const objectValue = value as Record<string, unknown>;
    const candidate = objectValue.message ?? objectValue.title ?? objectValue.detail ?? objectValue.error ?? objectValue.name;
    if (candidate !== undefined && candidate !== value) return toText(candidate, fallback);
    try {
      return JSON.stringify(value);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

export default function StoreOperationAudioAlert() {
  const previousOpenRef = useRef<boolean | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const [alert, setAlert] = useState<AlertState | null>(null);
  const [audioReady, setAudioReady] = useState(false);

  useEffect(() => {
    const unlockAudio = () => {
      getAudioContext(audioContextRef)
        ?.resume()
        .then(() => setAudioReady(true))
        .catch(() => {});
    };

    window.addEventListener("pointerdown", unlockAudio, { once: true });
    window.addEventListener("keydown", unlockAudio, { once: true });

    return () => {
      window.removeEventListener("pointerdown", unlockAudio);
      window.removeEventListener("keydown", unlockAudio);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const checkStatus = async () => {
      try {
        const status = await storeOperationApi.status();
        if (cancelled) return;
        handleStatus(status);
      } catch {
        // O alerta operacional nao deve interferir no uso do painel.
      }
    };

    const handleStatus = (status: StoreOperationStatus) => {
      const previous = previousOpenRef.current;
      previousOpenRef.current = status.is_open;

      if (previous === null || previous === status.is_open) return;

      const message = status.is_open ? OPEN_MESSAGE : CLOSED_MESSAGE;
      const tone = status.is_open ? "open" : "closed";
      setAlert({ message, tone });
      triggerAudio(message, tone, audioContextRef, setAudioReady, setAlert);
    };

    checkStatus();
    const intervalId = window.setInterval(checkStatus, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, []);

  if (!alert) return null;

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-[80] max-w-sm">
      <div className={`pointer-events-auto rounded-xl border p-4 shadow-2xl backdrop-blur ${
        alert.tone === "open"
          ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-100"
          : alert.tone === "closed"
            ? "border-amber-500/40 bg-amber-500/15 text-amber-100"
            : "border-gold/40 bg-surface-02 text-cream"
      }`}>
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-black/25">
            <Volume2 size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-black uppercase tracking-[0.12em]">Alerta operacional</p>
            <p className="mt-1 text-sm font-semibold">{toText(alert.message)}</p>
            {alert.tone === "blocked" && !audioReady && (
              <button
                type="button"
                onClick={() => triggerAudio(toText(alert.message), "closed", audioContextRef, setAudioReady, setAlert)}
                className="mt-3 rounded-lg bg-gold px-3 py-2 text-xs font-black text-black"
              >
                Ativar audio do painel
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => setAlert(null)}
            className="rounded-lg p-1 text-current/70 transition hover:bg-white/10 hover:text-current"
            aria-label="Fechar alerta"
          >
            <X size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

function getAudioContext(ref: MutableRefObject<AudioContext | null>) {
  if (typeof window === "undefined") return null;
  if (!ref.current) {
    const Ctx = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return null;
    ref.current = new Ctx();
  }
  return ref.current;
}

function triggerAudio(
  message: string,
  tone: "open" | "closed",
  audioContextRef: MutableRefObject<AudioContext | null>,
  setAudioReady: (value: boolean) => void,
  setAlert: (value: AlertState | null) => void,
) {
  const context = getAudioContext(audioContextRef);
  if (!context) {
    speak(message);
    return;
  }

  context.resume()
    .then(() => {
      setAudioReady(true);
      playAlertTone(context, tone);
      window.setTimeout(() => speak(message), 650);
    })
    .catch(() => {
      setAlert({
        message: "O navegador bloqueou o áudio automático. Clique para ativar os alertas do painel.",
        tone: "blocked",
      });
    });
}

function playAlertTone(context: AudioContext, tone: "open" | "closed") {
  const now = context.currentTime;
  const frequencies = tone === "open" ? [880, 1175, 1568] : [784, 659, 523];

  frequencies.forEach((frequency, index) => {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "square";
    oscillator.frequency.setValueAtTime(frequency, now + index * 0.18);
    gain.gain.setValueAtTime(0.0001, now + index * 0.18);
    gain.gain.exponentialRampToValueAtTime(0.55, now + index * 0.18 + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + index * 0.18 + 0.15);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(now + index * 0.18);
    oscillator.stop(now + index * 0.18 + 0.16);
  });
}

function speak(message: string) {
  if (!("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(message);
  utterance.lang = "pt-BR";
  utterance.volume = 1;
  utterance.rate = 0.92;
  utterance.pitch = 1;
  const voices = window.speechSynthesis.getVoices();
  const ptVoice = voices.find((voice) => voice.lang.toLowerCase().startsWith("pt"));
  if (ptVoice) utterance.voice = ptVoice;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

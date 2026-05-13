export type OrderSoundType = "classic" | "bell" | "silent";

export interface SoundOption {
  id: OrderSoundType;
  label: string;
  description: string;
}

export const SOUND_OPTIONS: SoundOption[] = [
  {
    id: "classic",
    label: "Alarme de Pedido",
    description: "Alarme alto repetido com voz forte dizendo PEDIDO — ideal para cozinhas barulhentas.",
  },
  {
    id: "bell",
    label: "Campainha Suave",
    description: "Melodia ascendente de campainha — discreta para ambientes de atendimento.",
  },
  {
    id: "silent",
    label: "Silêncio",
    description: "Sem som. Apenas alerta visual no card de pedido.",
  },
];

const LS_KEY = "order_sound_type";

export function loadSoundType(): OrderSoundType {
  const v = localStorage.getItem(LS_KEY);
  if (v === "classic" || v === "bell" || v === "silent") return v;
  return "classic";
}

export function saveSoundType(type: OrderSoundType): void {
  localStorage.setItem(LS_KEY, type);
}

function speakPedidoAfter(delayMs: number): void {
  if (!("speechSynthesis" in window)) return;
  window.setTimeout(() => {
    try {
      window.speechSynthesis.cancel();
      const voices = window.speechSynthesis.getVoices();
      const ptVoice = voices.find((voice) => voice.lang.toLowerCase().startsWith("pt"));
      const speak = (delay: number) => {
        window.setTimeout(() => {
          const utterance = new SpeechSynthesisUtterance("PEDIDO");
          utterance.lang = "pt-BR";
          utterance.rate = 0.7;
          utterance.pitch = 0.75;
          utterance.volume = 1;
          if (ptVoice) utterance.voice = ptVoice;
          window.speechSynthesis.speak(utterance);
        }, delay);
      };
      speak(0);
      speak(850);
      speak(1700);
    } catch {
      /* speechSynthesis can be blocked by browser audio policies */
    }
  }, delayMs);
}

export function playOrderAlert(type: OrderSoundType = "classic"): void {
  if (type === "silent") return;
  try {
    const ctx = new AudioContext();

    if (type === "classic") {
      // High-volume alarm pattern: 5 loud bursts at 880→1320 Hz
      const alarm = (freq: number, start: number, dur: number) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = freq;
        osc.type = "square";
        gain.gain.setValueAtTime(0.9, ctx.currentTime + start);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
        osc.start(ctx.currentTime + start);
        osc.stop(ctx.currentTime + start + dur + 0.02);
      };
      // Burst 1
      alarm(880,  0.00, 0.12);
      alarm(1320, 0.14, 0.12);
      // Burst 2
      alarm(880,  0.32, 0.12);
      alarm(1320, 0.46, 0.12);
      // Burst 3
      alarm(880,  0.64, 0.12);
      alarm(1320, 0.78, 0.18);

      speakPedidoAfter(1100);
    }

    if (type === "bell") {
      const note = (freq: number, start: number, dur: number) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = freq;
        osc.type = "triangle";
        gain.gain.setValueAtTime(0.38, ctx.currentTime + start);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
        osc.start(ctx.currentTime + start);
        osc.stop(ctx.currentTime + start + dur + 0.05);
      };
      note(523, 0,    0.45);
      note(659, 0.18, 0.45);
      note(784, 0.36, 0.55);
      note(1047, 0.54, 0.7);
      speakPedidoAfter(1350);
    }
  } catch {
    // AudioContext pode falhar sem interação prévia do usuário
  }
}

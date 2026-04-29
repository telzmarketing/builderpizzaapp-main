export type OrderSoundType = "classic" | "bell" | "silent";

export interface SoundOption {
  id: OrderSoundType;
  label: string;
  description: string;
}

export const SOUND_OPTIONS: SoundOption[] = [
  {
    id: "classic",
    label: "Alerta Operacional",
    description: "Três bipes agudos seguidos de voz \"Novo pedido!\" — padrão para cozinhas barulhentas.",
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

export function playOrderAlert(type: OrderSoundType = "classic"): void {
  if (type === "silent") return;
  try {
    const ctx = new AudioContext();

    if (type === "classic") {
      const beep = (freq: number, start: number, dur: number) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = freq;
        osc.type = "sine";
        gain.gain.setValueAtTime(0.35, ctx.currentTime + start);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
        osc.start(ctx.currentTime + start);
        osc.stop(ctx.currentTime + start + dur + 0.05);
      };
      beep(880, 0, 0.15);
      beep(1100, 0.2, 0.15);
      beep(880, 0.4, 0.25);
      setTimeout(() => {
        if ("speechSynthesis" in window) {
          const u = new SpeechSynthesisUtterance("Novo pedido!");
          u.lang = "pt-BR";
          u.rate = 0.95;
          u.pitch = 1.1;
          window.speechSynthesis.speak(u);
        }
      }, 700);
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
    }
  } catch {
    // AudioContext pode falhar sem interação prévia do usuário
  }
}

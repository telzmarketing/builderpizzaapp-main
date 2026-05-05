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

      // Voice: "PEDIDO" spoken loudly, twice
      setTimeout(() => {
        if ("speechSynthesis" in window) {
          window.speechSynthesis.cancel();
          const speak = (text: string, delay: number) => {
            setTimeout(() => {
              const u = new SpeechSynthesisUtterance(text);
              u.lang = "pt-BR";
              u.rate = 0.8;
              u.pitch = 0.85;
              u.volume = 1;
              window.speechSynthesis.speak(u);
            }, delay);
          };
          speak("PEDIDO!", 0);
          speak("PEDIDO!", 900);
        }
      }, 1050);
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

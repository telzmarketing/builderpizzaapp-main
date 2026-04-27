import { useEffect, useRef, useState } from "react";
import { X, Tag, Copy, Check } from "lucide-react";
import { exitPopupApi, type ApiExitPopupConfig as ExitPopupConfig } from "@/lib/api";

const SESSION_KEY = "exit_popup_shown";

export default function ExitPopup() {
  const [config, setConfig] = useState<ExitPopupConfig | null>(null);
  const [visible, setVisible] = useState(false);
  const [copied, setCopied] = useState(false);
  const triggered = useRef(false);

  useEffect(() => {
    exitPopupApi.get().then(setConfig).catch(() => {});
  }, []);

  useEffect(() => {
    if (!config?.enabled) return;
    if (config.show_once_per_session && sessionStorage.getItem(SESSION_KEY)) return;

    const handleMouseLeave = (e: MouseEvent) => {
      if (triggered.current) return;
      // Trigger only when mouse moves towards the top of the viewport (leaving to browser chrome)
      if (e.clientY <= 5) {
        triggered.current = true;
        if (config.show_once_per_session) sessionStorage.setItem(SESSION_KEY, "1");
        setVisible(true);
      }
    };

    document.addEventListener("mouseleave", handleMouseLeave);
    return () => document.removeEventListener("mouseleave", handleMouseLeave);
  }, [config]);

  const handleCopy = () => {
    if (!config?.coupon_code) return;
    navigator.clipboard.writeText(config.coupon_code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (!visible || !config) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={() => setVisible(false)}
    >
      <div
        className="relative bg-surface-02 border border-surface-03 rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close */}
        <button
          onClick={() => setVisible(false)}
          className="absolute top-3 right-3 z-10 text-stone hover:text-cream transition-colors bg-surface-03/80 rounded-full p-1.5"
        >
          <X size={16} />
        </button>

        {/* Image */}
        {config.image_url && (
          <img
            src={config.image_url}
            alt="Oferta"
            className="w-full h-40 object-cover"
          />
        )}

        {/* Content */}
        <div className="p-6 text-center">
          <div className="w-12 h-12 rounded-full bg-gold/20 border border-gold/30 flex items-center justify-center mx-auto mb-4">
            <Tag size={22} className="text-gold" />
          </div>

          <h2 className="text-cream text-xl font-black leading-tight mb-2">
            {config.title}
          </h2>
          <p className="text-stone text-sm mb-5 leading-relaxed">
            {config.subtitle}
          </p>

          {config.coupon_code && (
            <div className="bg-surface-03/60 border border-gold/30 rounded-xl px-4 py-3 flex items-center justify-between gap-3 mb-5">
              <span className="text-gold font-black text-lg tracking-widest">
                {config.coupon_code}
              </span>
              <button
                onClick={handleCopy}
                className="text-stone hover:text-cream transition-colors flex-shrink-0"
                title="Copiar cupom"
              >
                {copied ? <Check size={18} className="text-emerald-400" /> : <Copy size={18} />}
              </button>
            </div>
          )}

          <button
            onClick={() => setVisible(false)}
            className="w-full bg-gold hover:bg-gold/90 text-cream font-bold py-3 rounded-xl transition-colors"
          >
            {config.button_text}
          </button>

          <button
            onClick={() => setVisible(false)}
            className="mt-3 text-stone text-sm hover:text-cream transition-colors"
          >
            Não, obrigado
          </button>
        </div>
      </div>
    </div>
  );
}

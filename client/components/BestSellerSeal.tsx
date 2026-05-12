export default function BestSellerSeal({ show }: { show?: boolean }) {
  if (!show) return null;

  return (
    <div
      className="pointer-events-none absolute bottom-0 right-0 z-20 translate-x-1/4 translate-y-1/4"
      aria-label="Mais pedida"
    >
      <div
        className="w-[46px] h-[46px] rounded-full flex flex-col items-center justify-center ring-[1.5px] ring-white/30"
        style={{
          background: "radial-gradient(circle at 35% 35%, #fde68a, #d97706 60%, #92400e)",
          boxShadow: "0 4px 12px rgba(120,53,15,0.55), 0 1px 3px rgba(0,0,0,0.3), inset 0 1px 2px rgba(255,255,255,0.25)",
        }}
      >
        <span
          className="font-black uppercase leading-none tracking-tighter text-center"
          style={{ fontSize: "7.5px", color: "#431407", lineHeight: 1.1 }}
        >
          MAIS
        </span>
        <span
          className="font-black uppercase leading-none tracking-tighter text-center"
          style={{ fontSize: "7.5px", color: "#431407", lineHeight: 1.1 }}
        >
          PEDIDA
        </span>
        <span style={{ fontSize: "9px", lineHeight: 1, marginTop: "1px" }}>🔥</span>
      </div>
    </div>
  );
}

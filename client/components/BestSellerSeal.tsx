export default function BestSellerSeal({ show, compact = false }: { show?: boolean; compact?: boolean }) {
  if (!show) return null;

  return (
    <div className="pointer-events-none absolute bottom-1 right-1 z-20" aria-label="Mais pedida">
      <div
        className={`flex items-center justify-center rounded-full border border-red-300/35 bg-red-600/80 text-center font-black uppercase leading-tight text-white shadow-sm backdrop-blur-[1px] ${
          compact ? "h-10 w-10 px-1 text-[7px] sm:h-11 sm:w-11 sm:text-[8px]" : "h-14 w-14 px-1.5 text-[9px]"
        }`}
      >
        <span>Mais pedida</span>
      </div>
    </div>
  );
}

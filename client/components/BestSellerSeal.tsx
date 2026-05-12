export default function BestSellerSeal({ show }: { show?: boolean }) {
  if (!show) return null;

  return (
    <div className="pointer-events-none absolute bottom-1 right-1 z-20" aria-label="Mais pedida">
      <div className="flex h-14 w-14 items-center justify-center rounded-full border border-red-300/35 bg-red-600/80 px-1.5 text-center text-[9px] font-black uppercase leading-tight text-white shadow-sm backdrop-blur-[1px]">
        <span>Mais pedida</span>
      </div>
    </div>
  );
}

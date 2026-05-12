export default function BestSellerSeal({ show }: { show?: boolean }) {
  if (!show) return null;

  return (
    <div className="pointer-events-none absolute bottom-1 right-1 z-20" aria-label="Mais pedida">
      <div className="flex items-center gap-1 rounded-md bg-gold/85 px-2.5 py-1 text-[10px] font-black uppercase leading-none text-cream shadow-sm">
        <span aria-hidden="true">🔥</span>
        <span>Mais pedida</span>
      </div>
    </div>
  );
}

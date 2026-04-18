export default function MoschettieriLogo({ className = "h-10" }: { className?: string }) {
  return (
    <span
      className={`font-serif tracking-[0.18em] uppercase select-none leading-none ${className}`}
      style={{ fontFamily: "'Cormorant Garamond', serif" }}
    >
      Moschettieri
    </span>
  );
}

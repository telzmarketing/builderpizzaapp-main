export default function TelzLogo({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center font-black tracking-tight ${className}`}
      aria-label="Telz"
    >
      Telz
    </span>
  );
}

import { cn } from "@/lib/utils";

export default function MoschettieriLogo({ className = "h-10" }: { className?: string }) {
  return (
    <img
      src="/assets/logo-moschettieri-branco.png"
      alt="Moschettieri"
      className={cn("block h-7 w-auto object-contain select-none", className)}
      draggable={false}
    />
  );
}

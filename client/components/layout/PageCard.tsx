import type { ReactNode } from "react";

export default function PageCard({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`page-card rounded-xl border border-surface-03 bg-surface-02 p-4 md:p-5 ${className}`}>
      {children}
    </div>
  );
}

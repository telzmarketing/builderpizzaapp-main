import type { ReactNode } from "react";

export default function PageContainer({ children }: { children: ReactNode }) {
  return (
    <div className="app-page-container flex-1 overflow-y-auto bg-surface-01">
      <div className="admin-layout-content min-h-full">
        {children}
      </div>
    </div>
  );
}

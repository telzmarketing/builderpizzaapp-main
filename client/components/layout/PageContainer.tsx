import type { ReactNode } from "react";

export default function PageContainer({ children }: { children: ReactNode }) {
  return (
    <div className="app-page-container flex-1 overflow-y-auto bg-surface-01">
      <div className="admin-layout-content min-h-full p-4 md:p-6 space-y-6">
        {children}
      </div>
    </div>
  );
}

import type { ReactNode } from "react";

export default function PageContainer({ children }: { children: ReactNode }) {
  return (
    <div className="app-page-container min-w-0 max-w-full flex-1 overflow-x-clip overflow-y-auto bg-surface-01">
      <div className="admin-layout-content min-h-full min-w-0 max-w-full space-y-6 p-4 md:p-6">
        {children}
      </div>
    </div>
  );
}

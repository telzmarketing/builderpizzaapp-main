import type { ElementType, ReactNode } from "react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import { useAdminLayout } from "@/components/layout/AdminLayoutContext";

export type AdminPageTab<T extends string> = {
  id: T;
  label: string;
  icon?: ReactNode | ElementType;
};

export function AdminPageShell({ children }: { children: ReactNode }) {
  const insideGlobalLayout = useAdminLayout();
  if (insideGlobalLayout) return <>{children}</>;

  return (
    <div className="min-h-screen bg-surface-00 flex flex-col md:flex-row md:h-screen overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        {children}
      </main>
    </div>
  );
}

export function AdminPageHeader({
  eyebrow,
  title,
  description,
  icon,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  icon?: ReactNode;
  actions?: ReactNode;
}) {
  const insideGlobalLayout = useAdminLayout();
  if (insideGlobalLayout) {
    return actions ? (
      <div className="admin-legacy-toolbar flex flex-wrap items-center justify-end gap-3">
        {actions}
      </div>
    ) : null;
  }

  return (
    <header className="bg-surface-02 border-b border-surface-03 px-4 md:px-8 py-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between flex-shrink-0">
      <div className="flex min-w-0 items-center gap-3">
        {icon && (
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border border-gold/25 bg-gold/10 text-gold">
            {icon}
          </div>
        )}
        <div className="min-w-0">
          {eyebrow && (
            <p className="text-gold text-[11px] font-bold uppercase tracking-[0.22em] mb-1">
              {eyebrow}
            </p>
          )}
          <h1 className="text-cream text-xl md:text-2xl font-black leading-tight truncate">
            {title}
          </h1>
          {description && (
            <p className="text-stone text-xs md:text-sm mt-1 leading-snug">
              {description}
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 lg:justify-end">
        {actions}
        <AdminTopActions />
      </div>
    </header>
  );
}

export function AdminPageTabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: AdminPageTab<T>[];
  active: T;
  onChange: (tab: T) => void;
}) {
  return (
    <div className="admin-local-tabs bg-surface-02 border-b border-surface-03 px-4 md:px-8 flex-shrink-0">
      <div className="flex gap-1 overflow-x-auto pt-3">
        {tabs.map((tab) => {
          const selected = active === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onChange(tab.id)}
              className={`flex items-center gap-2 whitespace-nowrap rounded-t-xl border px-4 py-2.5 text-xs md:text-sm font-semibold transition-colors ${
                selected
                  ? "border-surface-03 border-b-surface-01 bg-surface-01 text-gold"
                  : "border-transparent text-stone hover:bg-surface-03/60 hover:text-cream"
              }`}
            >
              {typeof Icon === "function" ? <Icon size={15} /> : Icon}
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function AdminPageContent({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  const insideGlobalLayout = useAdminLayout();
  if (insideGlobalLayout) {
    return <div className={`space-y-6 ${className}`}>{children}</div>;
  }

  return (
    <div className={`flex-1 overflow-y-auto bg-surface-01 p-4 md:p-6 ${className}`}>
      {children}
    </div>
  );
}

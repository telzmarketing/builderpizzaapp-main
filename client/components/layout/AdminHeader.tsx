import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import AdminTopActions from "@/components/admin/AdminTopActions";
import { getAdminPageMeta } from "@/config/adminPageMeta";

export default function AdminHeader({ actions }: { actions?: ReactNode }) {
  const { pathname } = useLocation();
  const meta = getAdminPageMeta(pathname);

  return (
    <header className="app-header sticky top-0 z-30 bg-surface-02 border-b border-surface-03 px-4 md:px-8 py-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between flex-shrink-0">
      <div className="min-w-0">
        {meta.eyebrow && (
          <p className="text-gold text-[11px] font-bold uppercase tracking-[0.22em] mb-1">
            {meta.eyebrow}
          </p>
        )}
        <h1 className="text-cream text-xl md:text-2xl font-black leading-tight truncate">
          {meta.title}
        </h1>
        {meta.subtitle && (
          <p className="text-stone text-xs md:text-sm mt-1 leading-snug">
            {meta.subtitle}
          </p>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3 lg:justify-end">
        {actions}
        <AdminTopActions force />
      </div>
    </header>
  );
}


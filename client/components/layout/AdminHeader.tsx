import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { getAdminPageMeta } from "@/config/adminPageMeta";
import { findAdminNavigationGroup } from "@/lib/adminAccess";

export default function AdminHeader({ actions }: { actions?: ReactNode }) {
  const { pathname } = useLocation();
  const meta = getAdminPageMeta(pathname);
  const group = findAdminNavigationGroup(pathname);

  return (
    <header className="app-header flex flex-shrink-0 flex-col gap-3 border-b border-surface-03 bg-surface-02/85 px-4 py-3 backdrop-blur-lg md:px-6 lg:flex-row lg:items-center lg:justify-between">
      <div className="min-w-0">
        <div className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-stone">
          <span>{group?.label ?? "Painel"}</span>
          <span className="text-gold/70">/</span>
          <span className="truncate text-gold">{meta.title}</span>
        </div>
        <div className="flex min-w-0 items-baseline gap-3">
          <h1 className="truncate text-lg font-black leading-tight text-cream md:text-xl">
            {meta.title}
          </h1>
          {meta.subtitle && (
            <p className="hidden truncate text-xs leading-snug text-stone xl:block">
              {meta.subtitle}
            </p>
          )}
        </div>
        {meta.subtitle && (
          <p className="mt-1 text-xs leading-snug text-stone xl:hidden">
            {meta.subtitle}
          </p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3 lg:justify-end">{actions}</div>}
    </header>
  );
}

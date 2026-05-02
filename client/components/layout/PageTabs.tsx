import { Link, useLocation } from "react-router-dom";
import { getAdminPageMeta } from "@/config/adminPageMeta";

function isActive(pathname: string, path: string, exact?: boolean) {
  return exact ? pathname === path : pathname === path || pathname.startsWith(`${path}/`);
}

export default function PageTabs() {
  const { pathname } = useLocation();
  const meta = getAdminPageMeta(pathname);

  if (!meta.tabs?.length) return null;

  return (
    <div className="app-page-tabs bg-surface-02 border-b border-surface-03 px-4 md:px-8 flex-shrink-0">
      <div className="flex gap-1 overflow-x-auto pt-3">
        {meta.tabs.map((tab) => {
          const active = isActive(pathname, tab.path, tab.exact);
          return (
            <Link
              key={tab.path}
              to={tab.path}
              className={`flex items-center whitespace-nowrap rounded-t-xl border px-4 py-2.5 text-xs md:text-sm font-semibold transition-colors ${
                active
                  ? "border-surface-03 border-b-surface-01 bg-surface-01 text-gold"
                  : "border-transparent text-stone hover:bg-surface-03/60 hover:text-cream"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}


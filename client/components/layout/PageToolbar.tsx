import { Link, useLocation } from "react-router-dom";
import { getAdminPageMeta } from "@/config/adminPageMeta";

export default function PageToolbar() {
  const { pathname } = useLocation();
  const meta = getAdminPageMeta(pathname);

  if (!meta.toolbar?.length) return null;

  return (
    <div className="app-page-toolbar bg-surface-01 border-b border-surface-03 px-4 md:px-8 py-3 flex flex-wrap items-center gap-2 flex-shrink-0">
      {meta.toolbar.map((item) =>
        item.path ? (
          <Link
            key={`${item.label}-${item.path}`}
            to={item.path}
            className="inline-flex items-center rounded-lg border border-surface-03 bg-surface-02 px-3 py-2 text-sm font-semibold text-stone transition-colors hover:text-cream"
          >
            {item.label}
          </Link>
        ) : (
          <span
            key={item.label}
            className="inline-flex items-center rounded-lg border border-surface-03 bg-surface-02 px-3 py-2 text-sm font-semibold text-stone"
          >
            {item.label}
          </span>
        ),
      )}
    </div>
  );
}


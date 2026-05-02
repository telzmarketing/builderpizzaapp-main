import AppSidebar from "@/components/layout/AppSidebar";
import { useAdminLayout } from "@/components/layout/AdminLayoutContext";

export default function AdminSidebar() {
  const insideGlobalLayout = useAdminLayout();
  if (insideGlobalLayout) {
    return <span data-admin-sidebar-placeholder className="hidden" />;
  }
  return <AppSidebar />;
}

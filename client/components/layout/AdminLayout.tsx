import { Outlet } from "react-router-dom";
import { AdminLayoutContext } from "@/components/layout/AdminLayoutContext";
import AdminHeader from "@/components/layout/AdminHeader";
import AppSidebar from "@/components/layout/AppSidebar";
import PageContainer from "@/components/layout/PageContainer";

export default function AdminLayout() {
  return (
    <AdminLayoutContext.Provider value>
      <div className="admin-shell">
        <div className="app-layout min-h-screen bg-surface-00 flex flex-col md:flex-row md:h-screen overflow-hidden">
          <AppSidebar />
          <main className="flex-1 flex flex-col overflow-hidden min-w-0">
            <AdminHeader />
            <PageContainer>
              <Outlet />
            </PageContainer>
          </main>
        </div>
      </div>
    </AdminLayoutContext.Provider>
  );
}

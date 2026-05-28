import "@/admin.css";
import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { AdminLayoutContext } from "@/components/layout/AdminLayoutContext";
import AdminHeader from "@/components/layout/AdminHeader";
import AppSidebar from "@/components/layout/AppSidebar";
import PageContainer from "@/components/layout/PageContainer";
import StoreOperationAudioAlert from "@/components/admin/StoreOperationAudioAlert";

function AdminRouteFallback() {
  return (
    <div className="flex min-h-[18rem] items-center justify-center rounded-lg border border-surface-03 bg-surface-02 text-stone shadow-soft">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Loader2 className="h-4 w-4 animate-spin text-gold" aria-hidden="true" />
        <span>Carregando modulo...</span>
      </div>
    </div>
  );
}

export default function AdminLayout() {
  return (
    <AdminLayoutContext.Provider value>
      <div className="admin-shell">
        <StoreOperationAudioAlert />
        <div className="app-layout min-h-screen bg-surface-00 flex flex-col md:flex-row md:h-screen overflow-hidden">
          <AppSidebar />
          <main className="flex-1 flex flex-col overflow-hidden min-w-0">
            <AdminHeader />
            <PageContainer>
              <Suspense fallback={<AdminRouteFallback />}>
                <Outlet />
              </Suspense>
            </PageContainer>
          </main>
        </div>
      </div>
    </AdminLayoutContext.Provider>
  );
}

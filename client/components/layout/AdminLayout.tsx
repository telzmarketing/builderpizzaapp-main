import "@/admin.css";
import { Suspense, useState } from "react";
import { Outlet } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { AdminLayoutContext } from "@/components/layout/AdminLayoutContext";
import AdminHeader from "@/components/layout/AdminHeader";
import ContextSidebar from "@/components/layout/ContextSidebar";
import PageContainer from "@/components/layout/PageContainer";
import TopNavigation from "@/components/layout/TopNavigation";
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <AdminLayoutContext.Provider value>
      <div className="admin-shell">
        <StoreOperationAudioAlert />
        <div className="app-layout flex h-screen min-h-screen flex-col overflow-hidden bg-surface-00">
          <TopNavigation mobileMenuOpen={mobileMenuOpen} onMobileMenuChange={setMobileMenuOpen} />
          <div className="flex min-h-0 flex-1 overflow-hidden">
            <ContextSidebar />
            <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
              <AdminHeader />
              <PageContainer>
                <Suspense fallback={<AdminRouteFallback />}>
                  <Outlet />
                </Suspense>
              </PageContainer>
            </main>
          </div>
        </div>
      </div>
    </AdminLayoutContext.Provider>
  );
}

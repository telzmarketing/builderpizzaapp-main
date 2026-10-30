import "@/admin.css";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { Outlet } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { AdminHeaderActionsContext, AdminLayoutContext, AdminNavigationFocusContext, AdminThemeContext } from "@/components/layout/AdminLayoutContext";
import { persistAdminTheme, readAdminTheme, type AdminTheme } from "@/lib/adminTheme";
import AdminHeader from "@/components/layout/AdminHeader";
import ContextSidebar from "@/components/layout/ContextSidebar";
import PageContainer from "@/components/layout/PageContainer";
import TopNavigation from "@/components/layout/TopNavigation";
import StoreOperationAudioAlert from "@/components/admin/StoreOperationAudioAlert";
import PlatformSupportBanner from "@/components/platform/PlatformSupportBanner";

function AdminRouteFallback() {
  return (
    <div className="flex min-h-[18rem] items-center justify-center rounded-lg border border-surface-03 bg-surface-02 text-stone shadow-soft">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Loader2 className="h-4 w-4 animate-spin text-gold" aria-hidden="true" />
        <span>Carregando módulo...</span>
      </div>
    </div>
  );
}

export default function AdminLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [headerActions, setHeaderActions] = useState<ReactNode>(null);
  const [focusedGroupLabel, setFocusedGroupLabel] = useState<string | null>(null);
  const [adminTheme, setAdminTheme] = useState<AdminTheme>(readAdminTheme);

  useEffect(() => {
    persistAdminTheme(adminTheme);
  }, [adminTheme]);

  return (
    <AdminLayoutContext.Provider value>
      <AdminThemeContext.Provider value={{ theme: adminTheme, setTheme: setAdminTheme }}>
      <AdminNavigationFocusContext.Provider value={{ focusedGroupLabel, focusGroup: setFocusedGroupLabel, clearFocus: () => setFocusedGroupLabel(null) }}>
        <AdminHeaderActionsContext.Provider value={setHeaderActions}>
        <div className={`admin-shell admin-theme-${adminTheme}`}>
          <StoreOperationAudioAlert />
          <div className="app-layout flex h-screen min-h-screen flex-col overflow-hidden bg-surface-00">
            <PlatformSupportBanner />
            <TopNavigation mobileMenuOpen={mobileMenuOpen} onMobileMenuChange={setMobileMenuOpen} />
            <div className="flex min-h-0 flex-1 overflow-hidden">
              <ContextSidebar />
              <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
                <AdminHeader actions={headerActions} />
                <PageContainer>
                  <Suspense fallback={<AdminRouteFallback />}>
                    <Outlet />
                  </Suspense>
                </PageContainer>
              </main>
            </div>
          </div>
        </div>
        </AdminHeaderActionsContext.Provider>
      </AdminNavigationFocusContext.Provider>
      </AdminThemeContext.Provider>
    </AdminLayoutContext.Provider>
  );
}

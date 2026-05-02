import type { ReactNode } from "react";
import AdminHeader from "@/components/layout/AdminHeader";

export default function AppHeader({ actions }: { actions?: ReactNode }) {
  return <AdminHeader actions={actions} />;
}

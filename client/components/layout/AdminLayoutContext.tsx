import { createContext, useContext } from "react";

export const AdminLayoutContext = createContext(false);

export function useAdminLayout() {
  return useContext(AdminLayoutContext);
}

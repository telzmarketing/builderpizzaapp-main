import { createContext, useContext, type Dispatch, type ReactNode, type SetStateAction } from "react";

export const AdminLayoutContext = createContext(false);

export function useAdminLayout() {
  return useContext(AdminLayoutContext);
}

export const AdminHeaderActionsContext = createContext<Dispatch<SetStateAction<ReactNode>> | null>(null);

export function useAdminHeaderActions() {
  return useContext(AdminHeaderActionsContext);
}

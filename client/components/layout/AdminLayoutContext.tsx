import { createContext, useContext, type Dispatch, type ReactNode, type SetStateAction } from "react";
import type { AdminTheme } from "@/lib/adminTheme";

export const AdminLayoutContext = createContext(false);

export const AdminThemeContext = createContext<{
  theme: AdminTheme;
  setTheme: (theme: AdminTheme) => void;
}>({
  theme: "dark",
  setTheme: () => undefined,
});

type AdminNavigationFocus = {
  focusedGroupLabel: string | null;
  focusGroup: (label: string) => void;
  clearFocus: () => void;
};

export const AdminNavigationFocusContext = createContext<AdminNavigationFocus>({
  focusedGroupLabel: null,
  focusGroup: () => undefined,
  clearFocus: () => undefined,
});

export function useAdminLayout() {
  return useContext(AdminLayoutContext);
}

export function useAdminTheme() {
  return useContext(AdminThemeContext);
}

export function useAdminNavigationFocus() {
  return useContext(AdminNavigationFocusContext);
}

export const AdminHeaderActionsContext = createContext<Dispatch<SetStateAction<ReactNode>> | null>(null);

export function useAdminHeaderActions() {
  return useContext(AdminHeaderActionsContext);
}

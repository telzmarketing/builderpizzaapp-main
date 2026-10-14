import { createContext, useContext } from "react";

const PlatformSurfaceContext = createContext(false);

export const PlatformSurfaceProvider = PlatformSurfaceContext.Provider;

/** True only after the backend has resolved this request host as platform. */
export function usePlatformSurface(): boolean {
  return useContext(PlatformSurfaceContext);
}

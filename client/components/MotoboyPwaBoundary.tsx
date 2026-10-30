import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { configurePwaWorker, syncMotoboyPwaHead } from "@/lib/motoboyPwa";

export default function MotoboyPwaBoundary() {
  const { pathname } = useLocation();
  useEffect(() => {
    syncMotoboyPwaHead(pathname);
    if ("serviceWorker" in navigator) {
      void configurePwaWorker(pathname, navigator.serviceWorker, window.location.origin).catch((error) => {
        console.warn("Nao foi possivel registrar o aplicativo PWA do modulo.", error);
      });
    }
    return () => syncMotoboyPwaHead("");
  }, [pathname]);
  return null;
}

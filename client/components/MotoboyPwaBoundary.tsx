import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { configurePwaWorker, rememberPwaContext, syncMotoboyPwaHead } from "@/lib/motoboyPwa";

export default function MotoboyPwaBoundary() {
  const { pathname, search, hash } = useLocation();
  useEffect(() => {
    rememberPwaContext(pathname, search, hash);
    syncMotoboyPwaHead(pathname);
    if ("serviceWorker" in navigator) {
      void configurePwaWorker(pathname, navigator.serviceWorker, window.location.origin).catch((error) => {
        console.warn("Nao foi possivel registrar o aplicativo PWA do modulo.", error);
      });
    }
    return () => syncMotoboyPwaHead("");
  }, [hash, pathname, search]);
  return null;
}

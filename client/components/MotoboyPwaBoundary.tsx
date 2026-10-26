import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { configureMotoboyWorker, syncMotoboyPwaHead } from "@/lib/motoboyPwa";

export default function MotoboyPwaBoundary() {
  const { pathname } = useLocation();
  useEffect(() => {
    syncMotoboyPwaHead(pathname);
    if ("serviceWorker" in navigator) {
      void configureMotoboyWorker(pathname, navigator.serviceWorker, window.location.origin).catch((error) => {
        console.warn("Nao foi possivel atualizar o aplicativo Motoboy.", error);
      });
    }
    return () => syncMotoboyPwaHead("");
  }, [pathname]);
  return null;
}

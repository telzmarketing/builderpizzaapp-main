import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { configureBiMobileWorker, configureMotoboyWorker, syncMotoboyPwaHead } from "@/lib/motoboyPwa";

export default function MotoboyPwaBoundary() {
  const { pathname } = useLocation();
  useEffect(() => {
    syncMotoboyPwaHead(pathname);
    if ("serviceWorker" in navigator) {
      void Promise.all([
        configureMotoboyWorker(pathname, navigator.serviceWorker, window.location.origin),
        configureBiMobileWorker(pathname, navigator.serviceWorker),
      ]).catch((error) => {
        console.warn("Nao foi possivel atualizar o aplicativo Motoboy.", error);
      });
    }
    return () => syncMotoboyPwaHead("");
  }, [pathname]);
  return null;
}

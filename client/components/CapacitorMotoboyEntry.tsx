import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Capacitor } from "@capacitor/core";

export default function CapacitorMotoboyEntry() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    if (location.pathname.startsWith("/motoboy")) return;

    navigate("/motoboy", { replace: true });
  }, [location.pathname, navigate]);

  return null;
}

import { Outlet } from "react-router-dom";
import {
  isStoreScreenshotProtectionEnabled,
  useStoreScreenshotProtection,
} from "@/hooks/useStoreScreenshotProtection";
import { isSalaoExperience } from "@/lib/experience";

export default function StoreScreenshotProtection() {
  useStoreScreenshotProtection({
    enabled: isStoreScreenshotProtectionEnabled() && !isSalaoExperience(),
  });

  return <Outlet />;
}

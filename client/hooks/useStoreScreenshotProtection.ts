import { useEffect } from "react";

type StoreScreenshotProtectionOptions = {
  enabled?: boolean;
  printScreenBlurMs?: number;
};

const PRIVACY_OVERLAY_ID = "store-privacy-overlay";
const EDITABLE_SELECTOR = [
  "input",
  "textarea",
  "select",
  "option",
  "[contenteditable='true']",
  "[role='textbox']",
].join(",");

export function isStoreScreenshotProtectionEnabled() {
  return String(import.meta.env.VITE_STORE_SCREENSHOT_PROTECTION ?? "").toLowerCase() === "true";
}

function getTargetElement(target: EventTarget | null) {
  return target instanceof Element ? target : null;
}

function isEditableTarget(target: EventTarget | null) {
  return Boolean(getTargetElement(target)?.closest(EDITABLE_SELECTOR));
}

function isImageDragTarget(target: EventTarget | null) {
  return Boolean(getTargetElement(target)?.closest("img"));
}

function ensurePrivacyOverlay() {
  const existing = document.getElementById(PRIVACY_OVERLAY_ID);
  if (existing) return { overlay: existing, created: false };

  const overlay = document.createElement("div");
  overlay.id = PRIVACY_OVERLAY_ID;
  overlay.setAttribute("aria-hidden", "true");
  document.body.appendChild(overlay);

  return { overlay, created: true };
}

export function useStoreScreenshotProtection({
  enabled = isStoreScreenshotProtectionEnabled(),
  printScreenBlurMs = 1200,
}: StoreScreenshotProtectionOptions = {}) {
  useEffect(() => {
    if (!enabled) return;

    const { overlay, created } = ensurePrivacyOverlay();
    let temporaryBlurTimer: number | undefined;

    const showPrivacyOverlay = (durationMs?: number) => {
      window.clearTimeout(temporaryBlurTimer);
      document.body.classList.add("store-privacy-visible");

      if (durationMs) {
        temporaryBlurTimer = window.setTimeout(() => {
          document.body.classList.remove("store-privacy-visible");
        }, durationMs);
      }
    };

    const hidePrivacyOverlay = () => {
      window.clearTimeout(temporaryBlurTimer);
      document.body.classList.remove("store-privacy-visible");
    };

    const onContextMenu = (event: MouseEvent) => {
      if (isEditableTarget(event.target)) return;
      event.preventDefault();
    };

    const onDragStart = (event: DragEvent) => {
      if (!isImageDragTarget(event.target)) return;
      event.preventDefault();
    };

    const onKeyUp = (event: KeyboardEvent) => {
      if (event.key !== "PrintScreen" && event.code !== "PrintScreen") return;
      showPrivacyOverlay(printScreenBlurMs);
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        showPrivacyOverlay();
        return;
      }
      hidePrivacyOverlay();
    };

    const onWindowBlur = () => showPrivacyOverlay();

    document.body.classList.add("store-protection-active");
    document.addEventListener("contextmenu", onContextMenu);
    document.addEventListener("dragstart", onDragStart, true);
    document.addEventListener("keyup", onKeyUp);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("blur", onWindowBlur);
    window.addEventListener("focus", hidePrivacyOverlay);

    return () => {
      window.clearTimeout(temporaryBlurTimer);
      document.body.classList.remove("store-protection-active", "store-privacy-visible");
      document.removeEventListener("contextmenu", onContextMenu);
      document.removeEventListener("dragstart", onDragStart, true);
      document.removeEventListener("keyup", onKeyUp);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("blur", onWindowBlur);
      window.removeEventListener("focus", hidePrivacyOverlay);
      if (created) overlay.remove();
    };
  }, [enabled, printScreenBlurMs]);
}
